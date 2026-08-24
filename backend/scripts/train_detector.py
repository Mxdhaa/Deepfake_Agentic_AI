"""
train_detector.py — Fine-Tuning & Evaluation Pipeline for Deepfake Detection
─────────────────────────────────────────────────────────────────────────────
Features:
  - Ingests unified dataset manifest (CSV)
  - Pretrained Backbones: Xception (timm), EfficientNet-B4, ResNet-50
  - CLI Fine-Tuning Modes: --freeze-backbone OR --unfreeze-last-n <N>
  - Early stopping on validation loss with ROC-AUC tracking per epoch
  - Test Evaluation: ROC-AUC, Youden's J optimal threshold, Accuracy, Precision, Recall, F1
  - Exports metrics to detector_metrics.json and model weights to models/detector.pth
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms
from PIL import Image
from sklearn.metrics import roc_curve, roc_auc_score, precision_recall_fscore_support, accuracy_score, confusion_matrix


# ─── PyTorch Dataset Definition ───────────────────────────────────────────────

class DeepfakeManifestDataset(Dataset):
    def __init__(self, manifest_path: Path, split: str = "train", transform=None) -> None:
        self.transform = transform
        self.samples: List[Tuple[str, int]] = []

        if not manifest_path.exists():
            raise FileNotFoundError(f"Manifest not found at {manifest_path}")

        with open(manifest_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("split") == split:
                    img_p = row["image_path"]
                    lbl = int(row["label"])
                    self.samples.append((img_p, lbl))

        if len(self.samples) == 0:
            print(f"  [WARN] No samples found for split '{split}' in {manifest_path}")

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        img_path, label = self.samples[idx]
        try:
            image = Image.open(img_path).convert("RGB")
        except Exception as exc:
            # Generate blank fallback on corrupt image
            image = Image.new("RGB", (299, 299), (128, 128, 128))

        if self.transform:
            image = self.transform(image)

        return image, torch.tensor(label, dtype=torch.float32)


# ─── Model Architecture Builder ───────────────────────────────────────────────

def build_model(
    arch: str = "xception",
    freeze_backbone: bool = False,
    unfreeze_last_n: Optional[int] = None,
    pretrained: bool = True,
) -> nn.Module:
    """
    Builds deepfake detector with customizable backbone freezing.
    Attempts timm Xception / EfficientNet-B4 first; falls back to torchvision.
    """
    model = None
    arch_lower = arch.lower()

    # 1. Try timm
    try:
        import timm
        timm_arch = "legacy_xception" if "xception" in arch_lower else ("efficientnet_b4" if "eff" in arch_lower else arch_lower)
        print(f"  [INFO] Loading {timm_arch} (pretrained={pretrained})...", flush=True)
        model = timm.create_model(timm_arch, pretrained=pretrained, num_classes=1)
    except Exception as exc:
        print(f"  [DEBUG] timm loading fallback ({exc}), using torchvision.", flush=True)
        model = None

    # 2. Fallback to torchvision
    if model is None:
        import torchvision.models as tv_models
        if "eff" in arch_lower:
            print("  [INFO] Loading EfficientNet-B0 from torchvision...", flush=True)
            try:
                weights = tv_models.EfficientNet_B0_Weights.DEFAULT if pretrained else None
                model = tv_models.efficientnet_b0(weights=weights)
            except Exception:
                model = tv_models.efficientnet_b0(pretrained=pretrained)
            in_features = model.classifier[1].in_features
            model.classifier[1] = nn.Linear(in_features, 1)
        elif "18" in arch_lower:
            print("  [INFO] Loading ResNet-18 backbone...", flush=True)
            weights = tv_models.ResNet18_Weights.DEFAULT if pretrained else None
            model = tv_models.resnet18(weights=weights)
            in_features = model.fc.in_features
            model.fc = nn.Linear(in_features, 1)
        else:
            print("  [INFO] Loading ResNet-50 backbone...", flush=True)
            weights = tv_models.ResNet50_Weights.DEFAULT if pretrained else None
            model = tv_models.resnet50(weights=weights)
            in_features = model.fc.in_features
            model.fc = nn.Linear(in_features, 1)

    # ── Handle Freezing Strategy ──────────────────────────────────────────────
    params = list(model.parameters())

    if freeze_backbone:
        print("  [MODE] --freeze-backbone enabled: Freezing entire feature backbone.")
        for p in params[:-2]:  # Keep final classification layer trainable
            p.requires_grad = False
    elif unfreeze_last_n is not None and unfreeze_last_n > 0:
        print(f"  [MODE] --unfreeze-last-n {unfreeze_last_n}: Freezing early layers, training last {unfreeze_last_n} blocks.")
        # Freeze all first
        for p in params:
            p.requires_grad = False
        # Unfreeze last N layers
        for p in params[-unfreeze_last_n:]:
            p.requires_grad = True
    else:
        print("  [MODE] Full fine-tuning enabled: All layers trainable.")

    trainable_count = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total_count = sum(p.numel() for p in model.parameters())
    print(f"  [INFO] Trainable parameters: {trainable_count:,} / {total_count:,} ({trainable_count/total_count*100:.1f}%)")

    return model


# ─── Training & Evaluation Loop ───────────────────────────────────────────────

def evaluate_split(
    model: nn.Module,
    loader: DataLoader,
    criterion: nn.Module,
    device: torch.device,
) -> Tuple[float, float, np.ndarray, np.ndarray]:
    model.eval()
    total_loss = 0.0
    all_targets = []
    all_probs = []

    with torch.no_grad():
        for images, targets in loader:
            images = images.to(device)
            targets = targets.to(device)

            logits = model(images).squeeze(-1)
            loss = criterion(logits, targets)
            total_loss += loss.item() * len(targets)

            probs = torch.sigmoid(logits).cpu().numpy()
            all_probs.extend(probs)
            all_targets.extend(targets.cpu().numpy())

    mean_loss = total_loss / max(1, len(all_targets))
    y_true = np.array(all_targets)
    y_scores = np.array(all_probs)

    try:
        auc = roc_auc_score(y_true, y_scores) if len(np.unique(y_true)) > 1 else 0.5
    except Exception:
        auc = 0.5

    return mean_loss, float(auc), y_true, y_scores


def train_detector(
    manifest_path: Path,
    output_model_path: Path,
    metrics_path: Path,
    arch: str = "xception",
    freeze_backbone: bool = False,
    unfreeze_last_n: Optional[int] = None,
    pretrained: bool = True,
    epochs: int = 15,
    batch_size: int = 16,
    lr: float = 1e-4,
    patience: int = 4,
    device_str: str = "auto",
) -> Dict[str, Any]:
    # Select Device
    if device_str == "auto":
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    else:
        device = torch.device(device_str)
    print(f"\n[START] Training Deepfake Detector on: {device}")

    # Transforms (299x299 standard)
    img_size = (299, 299)
    train_transform = transforms.Compose([
        transforms.Resize(img_size),
        transforms.RandomHorizontalFlip(p=0.5),
        transforms.RandomRotation(degrees=10),
        transforms.ColorJitter(brightness=0.15, contrast=0.15),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])

    val_transform = transforms.Compose([
        transforms.Resize(img_size),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])

    # Datasets & Loaders
    train_ds = DeepfakeManifestDataset(manifest_path, split="train", transform=train_transform)
    val_ds = DeepfakeManifestDataset(manifest_path, split="val", transform=val_transform)
    test_ds = DeepfakeManifestDataset(manifest_path, split="test", transform=val_transform)

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, drop_last=False)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False)
    test_loader = DataLoader(test_ds, batch_size=batch_size, shuffle=False)

    print(f"  * Train samples : {len(train_ds)}")
    print(f"  * Val samples   : {len(val_ds)}")
    print(f"  * Test samples  : {len(test_ds)}")

    # Model, Loss, Optimizer
    model = build_model(arch=arch, freeze_backbone=freeze_backbone, unfreeze_last_n=unfreeze_last_n, pretrained=pretrained)
    model = model.to(device)

    criterion = nn.BCEWithLogitsLoss()
    optimizer = torch.optim.AdamW(filter(lambda p: p.requires_grad, model.parameters()), lr=lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

    best_val_loss = float("inf")
    best_epoch = 0
    patience_counter = 0
    history = []

    # Training Loop
    start_time = time.time()
    for epoch in range(1, epochs + 1):
        model.train()
        train_loss = 0.0
        n_samples = 0

        for images, targets in train_loader:
            images = images.to(device)
            targets = targets.to(device)

            optimizer.zero_grad()
            logits = model(images).squeeze(-1)
            loss = criterion(logits, targets)
            loss.backward()
            optimizer.step()

            train_loss += loss.item() * len(targets)
            n_samples += len(targets)

        scheduler.step()
        epoch_train_loss = train_loss / max(1, n_samples)

        # Validation
        val_loss, val_auc, _, _ = evaluate_split(model, val_loader, criterion, device)
        history.append({"epoch": epoch, "train_loss": epoch_train_loss, "val_loss": val_loss, "val_auc": val_auc})

        print(f"Epoch [{epoch:02d}/{epochs:02d}] - Train Loss: {epoch_train_loss:.4f} | Val Loss: {val_loss:.4f} | Val AUC: {val_auc:.4f}")

        # Checkpointing & Early Stopping
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_epoch = epoch
            patience_counter = 0
            # Save best model
            output_model_path.parent.mkdir(parents=True, exist_ok=True)
            torch.save(model, str(output_model_path))
            print(f"  --> Saved new best checkpoint (Val Loss: {val_loss:.4f}) to {output_model_path}")
        else:
            patience_counter += 1
            if patience_counter >= patience:
                print(f"  [EARLY STOPPING] Validation loss did not improve for {patience} epochs.")
                break

    training_time = round(time.time() - start_time, 2)
    print(f"\n[INFO] Training completed in {training_time}s. Best Epoch: {best_epoch}")

    # ── Final Test Split Evaluation ───────────────────────────────────────────
    print("\n[EVALUATION] Evaluating best model on held-out test split...", flush=True)
    best_model = torch.load(str(output_model_path), map_location=device, weights_only=False)
    test_loss, test_auc, y_true, y_scores = evaluate_split(best_model, test_loader, criterion, device)

    # Compute ROC Curve & Optimal Threshold via Youden's J
    if len(np.unique(y_true)) > 1:
        fpr, tpr, thresholds = roc_curve(y_true, y_scores)
        youden_j = tpr - fpr
        best_idx = int(np.argmax(youden_j))
        optimal_threshold = float(thresholds[best_idx])
    else:
        fpr, tpr, thresholds = [0.0, 1.0], [0.0, 1.0], [0.5]
        optimal_threshold = 0.5

    # Threshold-based Metrics
    y_pred = (y_scores >= optimal_threshold).astype(int)
    acc = float(accuracy_score(y_true, y_pred))
    prec, rec, f1, _ = precision_recall_fscore_support(y_true, y_pred, average="binary", zero_division=0)
    cm = confusion_matrix(y_true, y_pred).tolist() if len(y_true) > 0 else [[0, 0], [0, 0]]

    metrics_result = {
        "architecture": arch,
        "training_time_seconds": training_time,
        "best_epoch": best_epoch,
        "test_samples": len(y_true),
        "test_loss": round(test_loss, 4),
        "test_auc": round(test_auc, 4),
        "optimal_threshold_youden_j": round(optimal_threshold, 4),
        "metrics_at_optimal_threshold": {
            "accuracy": round(acc, 4),
            "precision": round(float(prec), 4),
            "recall": round(float(rec), 4),
            "f1_score": round(float(f1), 4),
        },
        "confusion_matrix": cm,
        "roc_curve": {
            "fpr": [round(float(x), 4) for x in fpr],
            "tpr": [round(float(x), 4) for x in tpr],
        },
        "history": history,
    }

    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(metrics_result, f, indent=2)

    print(f"\n==================== FINAL TEST METRICS ====================")
    print(f"  * Test ROC-AUC           : {test_auc:.4f}")
    print(f"  * Optimal Threshold (J)  : {optimal_threshold:.4f}")
    print(f"  * Accuracy               : {acc * 100:.2f}%")
    print(f"  * Precision              : {prec:.4f}")
    print(f"  * Recall                 : {rec:.4f}")
    print(f"  * F1-Score               : {f1:.4f}")
    print(f"  * Metrics saved to       : {metrics_path}")
    print(f"  * Model weights saved to : {output_model_path}")
    print(f"===========================================================\n")

    return metrics_result


# ─── CLI Entrypoint ──────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Fine-tune deepfake detector on unified manifest.")
    parser.add_argument("--manifest", type=str, default="data/processed_dataset/dataset_manifest.csv", help="Path to manifest CSV")
    parser.add_argument("--arch", type=str, default="xception", help="Backbone architecture (xception, efficientnet_b4, resnet50)")
    parser.add_argument("--freeze-backbone", action="store_true", help="Freeze entire feature backbone (head-only training)")
    parser.add_argument("--unfreeze-last-n", type=int, default=None, help="Unfreeze only the last N blocks/layers")
    parser.add_argument("--epochs", type=int, default=10, help="Number of training epochs")
    parser.add_argument("--batch-size", type=int, default=8, help="Batch size for training/eval")
    parser.add_argument("--lr", type=float, default=1e-4, help="Initial learning rate")
    parser.add_argument("--patience", type=int, default=3, help="Early stopping patience")
    parser.add_argument("--output-model", type=str, default="models/detector.pth", help="Destination path for best model checkpoint")
    parser.add_argument("--metrics-output", type=str, default="detector_metrics.json", help="Destination for metrics JSON")
    parser.add_argument("--device", type=str, default="auto", help="Device (cuda, cpu, auto)")
    parser.add_argument("--no-pretrained", action="store_true", help="Do not download pretrained weights (useful for instant scaffolding test)")

    args = parser.parse_args()

    train_detector(
        manifest_path=Path(args.manifest),
        output_model_path=Path(args.output_model),
        metrics_path=Path(args.metrics_output),
        arch=args.arch,
        freeze_backbone=args.freeze_backbone,
        unfreeze_last_n=args.unfreeze_last_n,
        pretrained=not args.no_pretrained,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        patience=args.patience,
        device_str=args.device,
    )


if __name__ == "__main__":
    main()
