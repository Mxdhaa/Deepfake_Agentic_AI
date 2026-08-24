"""
eval_cross_dataset.py — Cross-Dataset Generalization Benchmark for Deepfake Detector
────────────────────────────────────────────────────────────────────────────────────
Loads a trained PyTorch model checkpoint (e.g. models/detector.pth) and evaluates
performance against an out-of-distribution / secondary dataset manifest to quantify
generalization drop and domain shift vulnerability.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path
from typing import Dict, Any, List, Tuple

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms
from PIL import Image
from sklearn.metrics import roc_curve, roc_auc_score, precision_recall_fscore_support, accuracy_score, confusion_matrix


class EvalManifestDataset(Dataset):
    def __init__(self, manifest_path: Path, transform=None) -> None:
        self.transform = transform
        self.samples: List[Tuple[str, int, str]] = []

        if not manifest_path.exists():
            raise FileNotFoundError(f"Evaluation manifest not found at {manifest_path}")

        with open(manifest_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                img_p = row["image_path"]
                lbl = int(row["label"])
                src = row.get("source", "unknown")
                self.samples.append((img_p, lbl, src))

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        img_path, label, _ = self.samples[idx]
        try:
            image = Image.open(img_path).convert("RGB")
        except Exception:
            image = Image.new("RGB", (299, 299), (128, 128, 128))

        if self.transform:
            image = self.transform(image)

        return image, torch.tensor(label, dtype=torch.float32)


def eval_cross_dataset(
    model_path: Path,
    eval_manifest_path: Path,
    output_metrics_path: Path,
    decision_threshold: float = 0.50,
    batch_size: int = 16,
    device_str: str = "auto",
) -> Dict[str, Any]:
    # Select Device
    if device_str == "auto":
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    else:
        device = torch.device(device_str)

    print(f"\n[BENCHMARK] Loading trained model from: {model_path}")
    if not model_path.exists():
        raise FileNotFoundError(f"Model checkpoint not found at {model_path}")

    # Load Model Checkpoint
    try:
        model = torch.load(str(model_path), map_location=device, weights_only=False)
        model.eval()
    except Exception as exc:
        raise RuntimeError(f"Failed to load model weights: {exc}")

    # Preprocessing Transform
    transform = transforms.Compose([
        transforms.Resize((299, 299)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])

    dataset = EvalManifestDataset(eval_manifest_path, transform=transform)
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=False)

    print(f"  * Cross-dataset samples : {len(dataset)} from {eval_manifest_path}")

    # Inference Loop
    criterion = nn.BCEWithLogitsLoss()
    total_loss = 0.0
    all_targets = []
    all_probs = []

    start_time = time.time()
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

    eval_time = round(time.time() - start_time, 2)
    mean_loss = total_loss / max(1, len(all_targets))
    y_true = np.array(all_targets)
    y_scores = np.array(all_probs)

    # ROC-AUC
    try:
        auc = float(roc_auc_score(y_true, y_scores)) if len(np.unique(y_true)) > 1 else 0.5
    except Exception:
        auc = 0.5

    # Threshold-based Performance
    y_pred = (y_scores >= decision_threshold).astype(int)
    acc = float(accuracy_score(y_true, y_pred))
    prec, rec, f1, _ = precision_recall_fscore_support(y_true, y_pred, average="binary", zero_division=0)
    cm = confusion_matrix(y_true, y_pred).tolist() if len(y_true) > 0 else [[0, 0], [0, 0]]

    # Also compute optimal threshold on this cross-dataset for domain shift comparison
    if len(np.unique(y_true)) > 1:
        fpr, tpr, thresholds = roc_curve(y_true, y_scores)
        youden_j = tpr - fpr
        best_idx = int(np.argmax(youden_j))
        domain_optimal_thresh = float(thresholds[best_idx])
    else:
        domain_optimal_thresh = decision_threshold

    results = {
        "model_path": str(model_path.resolve()),
        "eval_manifest": str(eval_manifest_path.resolve()),
        "total_samples": len(y_true),
        "real_count": int(np.sum(y_true == 0)),
        "fake_count": int(np.sum(y_true == 1)),
        "inference_time_seconds": eval_time,
        "loss": round(mean_loss, 4),
        "cross_dataset_auc": round(auc, 4),
        "fixed_threshold_used": round(decision_threshold, 4),
        "metrics_at_fixed_threshold": {
            "accuracy": round(acc, 4),
            "precision": round(float(prec), 4),
            "recall": round(float(rec), 4),
            "f1_score": round(float(f1), 4),
        },
        "domain_optimal_threshold": round(domain_optimal_thresh, 4),
        "confusion_matrix": cm,
    }

    output_metrics_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_metrics_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"\n================ CROSS-DATASET BENCHMARK METRICS ================")
    print(f"  * Cross-Dataset ROC-AUC      : {auc:.4f}")
    print(f"  * Accuracy (at th={decision_threshold:.2f}) : {acc * 100:.2f}%")
    print(f"  * Precision                  : {prec:.4f}")
    print(f"  * Recall                     : {rec:.4f}")
    print(f"  * F1-Score                   : {f1:.4f}")
    print(f"  * Domain Optimal Threshold   : {domain_optimal_thresh:.4f}")
    print(f"  * Results saved to           : {output_metrics_path}")
    print(f"=================================================================\n")

    return results


def main():
    parser = argparse.ArgumentParser(description="Evaluate deepfake model checkpoint on cross-dataset.")
    parser.add_argument("--model-path", type=str, default="models/detector.pth", help="Path to trained .pth model checkpoint")
    parser.add_argument("--eval-manifest", type=str, required=True, help="Path to cross-dataset manifest CSV")
    parser.add_argument("--output-metrics", type=str, default="cross_dataset_metrics.json", help="Path to output JSON")
    parser.add_argument("--threshold", type=float, default=0.50, help="Classification decision threshold")
    parser.add_argument("--batch-size", type=int, default=16, help="Inference batch size")
    parser.add_argument("--device", type=str, default="auto", help="Device (cuda, cpu, auto)")

    args = parser.parse_args()

    eval_cross_dataset(
        model_path=Path(args.model_path),
        eval_manifest_path=Path(args.eval_manifest),
        output_metrics_path=Path(args.output_metrics),
        decision_threshold=args.threshold,
        batch_size=args.batch_size,
        device_str=args.device,
    )


if __name__ == "__main__":
    main()
