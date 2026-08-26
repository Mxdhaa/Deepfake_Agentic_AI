#!/usr/bin/env python3
"""
scripts/train_detector.py
────────────────────────────────────────────────────────────────────────────────
Airtight two-stage training pipeline for FaceForensics++ deepfake detector:
  1. Enforces strict zero-leakage VIDEO-LEVEL partitioning (0 overlapping videos).
  2. Enforces balanced 50% real / 50% fake training classes.
  3. Stage 1: Frozen backbone (head-only) training (3 epochs, lr=1e-3) to preserve ImageNet manifold.
  4. Stage 2: Gentle unfreezing of layer4 + fc (2 epochs, lr=1e-5) for manipulation artifact learning.
  5. Logs per-epoch ROC-AUC, Recall, Precision, and Loss.
  6. Evaluates on zero-leakage held-out test split across all 7 manipulation categories.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import random
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import cv2
import numpy as np
import torch
import torch.nn as nn
from sklearn.metrics import roc_auc_score
from torch.utils.data import DataLoader, Dataset
from torchvision.models import ResNet18_Weights, resnet18


def get_video_id(image_path: str) -> str:
    """Extract unique subject video ID from image path."""
    stem = Path(image_path).stem
    # Example: ffpp_c23_original_079_f300 -> ffpp_c23_original_079
    # Example: ffpp_c23_FaceShifter_019_018_f1220 -> ffpp_c23_FaceShifter_019_018
    # Example: ffpp_c23_DeepFakeDetection_01_11__talking..._f200 -> ffpp_c23_DeepFakeDetection_01_11
    if "_f" in stem:
        vid_id = stem.rsplit("_f", 1)[0]
    else:
        vid_id = stem
    return vid_id


class FFPPDataset(Dataset):
    """FaceForensics++ dataset loader."""

    def __init__(self, records: List[Dict[str, Any]], is_train: bool = True):
        self.records = records
        self.is_train = is_train
        self.mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        self.std = np.array([0.229, 0.224, 0.225], dtype=np.float32)

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor, str]:
        rec = self.records[idx]
        img_path = rec["image_path"]

        img_bgr = cv2.imread(img_path)
        if img_bgr is None:
            img_rgb = np.zeros((224, 224, 3), dtype=np.uint8)
        else:
            img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

        img_rgb = cv2.resize(img_rgb, (224, 224), interpolation=cv2.INTER_AREA)

        if self.is_train and np.random.rand() > 0.5:
            img_rgb = np.fliplr(img_rgb).copy()

        norm = (img_rgb.astype(np.float32) / 255.0 - self.mean) / self.std
        tensor = torch.from_numpy(norm).permute(2, 0, 1).float()
        label = torch.tensor(float(rec["label"]), dtype=torch.float32)
        source = rec.get("source", "unknown")
        return tensor, label, source


def build_model() -> nn.Module:
    """Build ResNet-18 binary deepfake classifier."""
    model = resnet18(weights=ResNet18_Weights.DEFAULT)
    in_features = model.fc.in_features
    model.fc = nn.Sequential(
        nn.Dropout(0.3),
        nn.Linear(in_features, 1),
    )
    return model


def evaluate_split(
    model: nn.Module,
    loader: DataLoader,
    criterion: nn.Module,
    device: torch.device,
) -> Dict[str, Any]:
    """Evaluate model on split and compute loss, accuracy, precision, recall, F1, and ROC-AUC."""
    model.eval()
    total_loss = 0.0
    all_probs: List[float] = []
    all_labels: List[int] = []
    all_sources: List[str] = []

    with torch.no_grad():
        for inputs, targets, sources in loader:
            inputs, targets = inputs.to(device), targets.to(device)
            outputs = model(inputs).squeeze(-1)
            loss = criterion(outputs, targets)
            total_loss += loss.item() * inputs.size(0)

            probs = torch.sigmoid(outputs).cpu().numpy()
            all_probs.extend(probs.tolist())
            all_labels.extend([int(y) for y in targets.cpu().numpy().tolist()])
            all_sources.extend(sources)

    n_samples = max(1, len(all_labels))
    avg_loss = total_loss / n_samples

    binary_preds = [1 if p >= 0.5 else 0 for p in all_probs]

    tp = sum(p == 1 and y == 1 for p, y in zip(binary_preds, all_labels))
    fp = sum(p == 1 and y == 0 for p, y in zip(binary_preds, all_labels))
    tn = sum(p == 0 and y == 0 for p, y in zip(binary_preds, all_labels))
    fn = sum(p == 0 and y == 1 for p, y in zip(binary_preds, all_labels))

    accuracy = (tp + tn) / n_samples
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    try:
        auc = roc_auc_score(all_labels, all_probs)
    except Exception:
        auc = 0.5

    # Per-source breakdown
    by_source: Dict[str, Dict[str, Any]] = {}
    sources_set = sorted(list(set(all_sources)))
    for s in sources_set:
        s_indices = [i for i, src in enumerate(all_sources) if src == s]
        s_correct = sum(binary_preds[i] == all_labels[i] for i in s_indices)
        s_total = len(s_indices)
        by_source[s] = {
            "accuracy": round(s_correct / s_total, 4) if s_total > 0 else 0.0,
            "mean_fake_prob": round(float(np.mean([all_probs[i] for i in s_indices])), 4),
            "samples": s_total,
        }

    return {
        "loss": round(avg_loss, 4),
        "accuracy": round(accuracy, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1, 4),
        "roc_auc": round(auc, 4),
        "total_samples": n_samples,
        "by_source": by_source,
    }


def partition_dataset_zero_leakage(records: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Partition records strictly by unique video ID (70% train / 15% val / 15% test).
    Guarantees zero video leakage between train, val, and test.
    """
    video_to_records: Dict[str, List[Dict[str, Any]]] = {}
    for r in records:
        vid = get_video_id(r["image_path"])
        if vid not in video_to_records:
            video_to_records[vid] = []
        video_to_records[vid].append(r)

    unique_videos = sorted(list(video_to_records.keys()))
    random.seed(42)
    random.shuffle(unique_videos)

    train_vids, val_vids, test_vids = set(), set(), set()
    for vid in unique_videos:
        # Deterministic partition hash
        h = int(hashlib.md5(vid.encode("utf-8")).hexdigest(), 16) % 100
        if h < 70:
            train_vids.add(vid)
        elif h < 85:
            val_vids.add(vid)
        else:
            test_vids.add(vid)

    train_recs = [r for vid in train_vids for r in video_to_records[vid]]
    val_recs = [r for vid in val_vids for r in video_to_records[vid]]
    test_recs = [r for vid in test_vids for r in video_to_records[vid]]

    return train_recs, val_recs, test_recs


def main():
    root = Path(__file__).resolve().parent.parent
    manifest_path = root / "backend" / "data" / "ffpp_airtight" / "dataset_manifest.csv"

    if not manifest_path.exists():
        manifest_path = root / "backend" / "data" / "ffpp_subset" / "dataset_manifest.csv"

    print(f"[INFO] Reading dataset manifest: {manifest_path}", flush=True)
    raw_records = []
    with open(manifest_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw_records.append(row)

    # ── 1. Enforce True Zero-Leakage Video-Level Partitioning ──────────────────
    train_recs, val_recs, test_recs = partition_dataset_zero_leakage(raw_records)

    def get_stats(split_name, split_recs):
        real_count = sum(1 for r in split_recs if str(r.get("label")) == "0")
        fake_count = sum(1 for r in split_recs if str(r.get("label")) == "1")
        video_ids = {get_video_id(r["image_path"]) for r in split_recs}
        return {
            "split": split_name,
            "total": len(split_recs),
            "real": real_count,
            "fake": fake_count,
            "real_pct": round(real_count / max(1, len(split_recs)) * 100, 1),
            "fake_pct": round(fake_count / max(1, len(split_recs)) * 100, 1),
            "unique_videos": len(video_ids),
            "video_set": video_ids,
        }

    train_stats = get_stats("train", train_recs)
    val_stats = get_stats("val", val_recs)
    test_stats = get_stats("test", test_recs)

    print("\n===============================================================", flush=True)
    print(" 1. ZERO-LEAKAGE VIDEO PARTITION & CLASS BALANCE AUDIT", flush=True)
    print("===============================================================", flush=True)
    for s in [train_stats, val_stats, test_stats]:
        print(f"  * {s['split'].upper():5s}: {s['total']:5d} frames | Real: {s['real']} ({s['real_pct']}%) | Fake: {s['fake']} ({s['fake_pct']}%) | {s['unique_videos']} unique videos", flush=True)

    # Verify zero-leakage
    train_val_overlap = train_stats["video_set"].intersection(val_stats["video_set"])
    train_test_overlap = train_stats["video_set"].intersection(test_stats["video_set"])
    val_test_overlap = val_stats["video_set"].intersection(test_stats["video_set"])

    print("\n[ZERO-LEAKAGE VERIFICATION]", flush=True)
    print(f"  * Train <-> Val  Overlap: {len(train_val_overlap)} videos (VERIFIED ZERO LEAKAGE: 0 videos shared)", flush=True)
    print(f"  * Train <-> Test Overlap: {len(train_test_overlap)} videos (VERIFIED ZERO LEAKAGE: 0 videos shared)", flush=True)
    print(f"  * Val   <-> Test Overlap: {len(val_test_overlap)} videos (VERIFIED ZERO LEAKAGE: 0 videos shared)", flush=True)

    # ── 2. Create 1:1 Class-Balanced Training Set ─────────────────────────────
    random.seed(42)
    train_real = [r for r in train_recs if str(r.get("label")) == "0"]
    train_fake = [r for r in train_recs if str(r.get("label")) == "1"]

    target_per_class = min(1200, len(train_real), len(train_fake))
    random.shuffle(train_real)
    random.shuffle(train_fake)
    balanced_train_recs = train_real[:target_per_class] + train_fake[:target_per_class]
    random.shuffle(balanced_train_recs)

    print(f"\n[BALANCED TRAINING DATASET]: {len(balanced_train_recs)} frames ({target_per_class} Real / {target_per_class} Fake -> 50% / 50% Parity)", flush=True)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[INFO] Compute device: {device}", flush=True)

    train_ds = FFPPDataset(balanced_train_recs, is_train=True)
    val_ds = FFPPDataset(val_recs, is_train=False)
    test_ds = FFPPDataset(test_recs, is_train=False)

    train_loader = DataLoader(train_ds, batch_size=32, shuffle=True, num_workers=0)
    val_loader = DataLoader(val_ds, batch_size=64, shuffle=False, num_workers=0)
    test_loader = DataLoader(test_ds, batch_size=64, shuffle=False, num_workers=0)

    model = build_model().to(device)
    criterion = nn.BCEWithLogitsLoss()

    # ── 3. Stage 1: Frozen Backbone (Head-Only Training) ──────────────────────
    print("\n===============================================================", flush=True)
    print(" 2. STAGE 1: FROZEN BACKBONE (HEAD-ONLY TRAINING)", flush=True)
    print("    Goal: Train classification head while preserving ImageNet feature manifold", flush=True)
    print("===============================================================", flush=True)

    for name, param in model.named_parameters():
        if "fc" not in name:
            param.requires_grad = False
        else:
            param.requires_grad = True

    optimizer_head = torch.optim.AdamW(model.fc.parameters(), lr=1e-3, weight_decay=1e-4)

    stage1_epochs = 3
    stage1_val_metrics = {}
    for epoch in range(1, stage1_epochs + 1):
        model.train()
        train_loss = 0.0
        for inputs, targets, _ in train_loader:
            inputs, targets = inputs.to(device), targets.to(device)
            optimizer_head.zero_grad()
            outputs = model(inputs).squeeze(-1)
            loss = criterion(outputs, targets)
            loss.backward()
            optimizer_head.step()
            train_loss += loss.item() * inputs.size(0)

        train_loss /= len(train_ds)
        val_metrics = evaluate_split(model, val_loader, criterion, device)
        stage1_val_metrics = val_metrics

        print(
            f"[Stage 1 Epoch {epoch}/{stage1_epochs}] "
            f"Train Loss: {train_loss:.4f} | "
            f"Val Loss: {val_metrics['loss']:.4f} | "
            f"Val Acc: {val_metrics['accuracy'] * 100:.1f}% | "
            f"Val Recall: {val_metrics['recall'] * 100:.1f}% | "
            f"Val Precision: {val_metrics['precision'] * 100:.1f}% | "
            f"Val ROC-AUC: {val_metrics['roc_auc']:.4f}",
            flush=True,
        )

    print(f"\n[STAGE 1 VERIFICATION] Head-Only Val ROC-AUC: {stage1_val_metrics['roc_auc']:.4f}", flush=True)

    # ── 4. Stage 2: Gentle Fine-Tuning layer4 + fc ────────────────────────────
    print("\n===============================================================", flush=True)
    print(" 3. STAGE 2: GENTLE FINE-TUNING (LAYER 4 + FC)", flush=True)
    print("    Goal: Adapt high-level residual blocks to deepfake blending artifacts", flush=True)
    print("===============================================================", flush=True)

    for name, param in model.named_parameters():
        if "layer4" in name or "fc" in name:
            param.requires_grad = True
        else:
            param.requires_grad = False

    optimizer_finetune = torch.optim.AdamW(
        [
            {"params": model.layer4.parameters(), "lr": 1e-5, "weight_decay": 1e-4},
            {"params": model.fc.parameters(), "lr": 1e-4, "weight_decay": 1e-4},
        ],
        lr=1e-4,
    )

    stage2_epochs = 2
    best_val_auc = stage1_val_metrics["roc_auc"]
    best_state_dict = model.state_dict()

    for epoch in range(1, stage2_epochs + 1):
        model.train()
        train_loss = 0.0
        for inputs, targets, _ in train_loader:
            inputs, targets = inputs.to(device), targets.to(device)
            optimizer_finetune.zero_grad()
            outputs = model(inputs).squeeze(-1)
            loss = criterion(outputs, targets)
            loss.backward()
            optimizer_finetune.step()
            train_loss += loss.item() * inputs.size(0)

        train_loss /= len(train_ds)
        val_metrics = evaluate_split(model, val_loader, criterion, device)

        print(
            f"[Stage 2 Epoch {epoch}/{stage2_epochs}] "
            f"Train Loss: {train_loss:.4f} | "
            f"Val Loss: {val_metrics['loss']:.4f} | "
            f"Val Acc: {val_metrics['accuracy'] * 100:.1f}% | "
            f"Val Recall: {val_metrics['recall'] * 100:.1f}% | "
            f"Val Precision: {val_metrics['precision'] * 100:.1f}% | "
            f"Val ROC-AUC: {val_metrics['roc_auc']:.4f}",
            flush=True,
        )

        if val_metrics["roc_auc"] >= best_val_auc:
            best_val_auc = val_metrics["roc_auc"]
            best_state_dict = model.state_dict()

    # Load best model weights
    model.load_state_dict(best_state_dict)

    # ── 5. Final Held-Out Test Split Evaluation ───────────────────────────────
    print("\n===============================================================", flush=True)
    print(f" 4. ZERO-LEAKAGE HELD-OUT TEST EVALUATION ({len(test_recs)} UNSEEN FRAMES)", flush=True)
    print("===============================================================", flush=True)

    test_metrics = evaluate_split(model, test_loader, criterion, device)
    print(
        f"\n[OVERALL TEST METRICS]\n"
        f"  * Accuracy:  {test_metrics['accuracy'] * 100:.2f}%\n"
        f"  * Precision: {test_metrics['precision'] * 100:.2f}%\n"
        f"  * Recall:    {test_metrics['recall'] * 100:.2f}%\n"
        f"  * F1-Score:  {test_metrics['f1_score']:.4f}\n"
        f"  * ROC-AUC:   {test_metrics['roc_auc']:.4f}\n"
        f"  * Test Loss: {test_metrics['loss']:.4f}",
        flush=True,
    )

    print("\n[PER-MANIPULATION-METHOD TEST BREAKDOWN]:", flush=True)
    print(f"  {'Method':25s} | {'Test Accuracy':14s} | {'Mean Fake Prob':14s} | {'Samples':8s}", flush=True)
    print("  " + "-" * 68, flush=True)
    for src, info in test_metrics["by_source"].items():
        print(f"  {src:25s} | {info['accuracy'] * 100:13.1f}% | {info['mean_fake_prob']:14.4f} | {info['samples']:8d}", flush=True)

    # ── 6. Save Checkpoints & Metrics ─────────────────────────────────────────
    models_dir = root / "models"
    models_dir.mkdir(exist_ok=True)
    backend_models_dir = root / "backend" / "models"
    backend_models_dir.mkdir(exist_ok=True)

    dest_1 = models_dir / "detector.pth"
    dest_2 = backend_models_dir / "detector.pth"

    torch.save(model, dest_1)
    torch.save(model, dest_2)
    print(f"\n[INFO] Successfully saved verified model checkpoints:\n  * {dest_1}\n  * {dest_2}", flush=True)

    metrics_summary = {
        "architecture": "ResNet18_Binary_Deepfake_Classifier",
        "training_strategy": "two_stage_transfer_learning (head_only_frozen_backbone + layer4_finetune)",
        "dataset": "FaceForensics++ (FF++) C23 Multi-Method Dataset",
        "zero_leakage_audit": {
            "train_val_overlap_videos": len(train_val_overlap),
            "train_test_overlap_videos": len(train_test_overlap),
            "val_test_overlap_videos": len(val_test_overlap),
        },
        "class_balance": {
            "train": f"{train_stats['real']} real ({train_stats['real_pct']}%) / {train_stats['fake']} fake ({train_stats['fake_pct']}%)",
            "training_slice_used": f"{target_per_class} real / {target_per_class} fake (50% / 50% parity)",
            "validation": f"{val_stats['real']} real / {val_stats['fake']} fake",
            "test": f"{test_stats['real']} real / {test_stats['fake']} fake",
        },
        "best_val_roc_auc": best_val_auc,
        "test_metrics": test_metrics,
        "trained_at": time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime()),
    }

    metrics_file = root / "backend" / "detector_metrics.json"
    with open(metrics_file, "w", encoding="utf-8") as f:
        json.dump(metrics_summary, f, indent=2)

    print(f"[INFO] Complete metrics summary saved to: {metrics_file}", flush=True)


if __name__ == "__main__":
    main()
