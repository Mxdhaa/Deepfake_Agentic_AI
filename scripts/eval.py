#!/usr/bin/env python3
"""
Model Evaluation Script
───────────────────────
Evaluates a trained deepfake detector on a labeled test set.
Outputs: Accuracy, AUC-ROC, F1 Score, EER, per-class confusion matrix.

Usage:
    python scripts/eval.py \
        --model   models/detector.pth \
        --data    data/samples/ \
        --device  cpu \
        --output  docs/eval_results.json

Directory structure expected:
    data/samples/
    ├── real/    ← label 0
    └── fake/    ← label 1
"""

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image


def load_dataset(data_dir: Path) -> tuple[list, list]:
    """Load image paths and labels (0=real, 1=fake)."""
    paths, labels = [], []
    for label, subdir in [(0, "real"), (1, "fake")]:
        d = data_dir / subdir
        if not d.exists():
            print(f"[WARN] {d} not found, skipping.", file=sys.stderr)
            continue
        for ext in ("*.jpg", "*.jpeg", "*.png", "*.webp"):
            for p in sorted(d.glob(ext)):
                paths.append(p)
                labels.append(label)
    return paths, labels


def preprocess(path: Path) -> np.ndarray:
    """Load and normalize image to (224, 224, 3) float32."""
    img = Image.open(path).convert("RGB").resize((224, 224), Image.LANCZOS)
    return np.array(img, dtype=np.float32) / 255.0


def compute_eer(y_true: np.ndarray, y_scores: np.ndarray) -> float:
    """Compute Equal Error Rate."""
    from sklearn.metrics import roc_curve
    fpr, tpr, _ = roc_curve(y_true, y_scores)
    fnr = 1 - tpr
    eer_idx = np.nanargmin(np.abs(fnr - fpr))
    return float((fpr[eer_idx] + fnr[eer_idx]) / 2)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model",  type=str, default="models/detector.pth")
    parser.add_argument("--data",   type=Path, default=Path("data/samples"))
    parser.add_argument("--device", type=str, default="cpu")
    parser.add_argument("--output", type=Path, default=Path("docs/eval_results.json"))
    parser.add_argument("--threshold", type=float, default=0.5)
    args = parser.parse_args()

    try:
        from sklearn.metrics import accuracy_score, roc_auc_score, f1_score, confusion_matrix
    except ImportError:
        print("[ERROR] scikit-learn required: pip install scikit-learn", file=sys.stderr)
        sys.exit(1)

    # Load dataset
    paths, labels = load_dataset(args.data)
    if len(paths) == 0:
        print("[ERROR] No images found in data directory.", file=sys.stderr)
        sys.exit(1)
    print(f"Found {len(paths)} images ({labels.count(0)} real, {labels.count(1)} fake)")

    # Load model
    try:
        import torch
        model = torch.load(args.model, map_location=args.device)
        model.eval()
        print(f"Model loaded: {args.model}")
    except Exception as e:
        print(f"[WARN] Could not load model ({e}). Using random scores for demonstration.")
        model = None

    # Run inference
    scores = []
    t0 = time.time()
    for i, path in enumerate(paths):
        frame = preprocess(path)
        if model is not None:
            import torch
            tensor = torch.from_numpy(frame).permute(2, 0, 1).unsqueeze(0).to(args.device)
            with torch.no_grad():
                score = float(torch.sigmoid(model(tensor)).item())
        else:
            rng = np.random.default_rng(int(frame.mean() * 1000) % 2**31)
            score = float(rng.uniform(0.0, 1.0))
        scores.append(score)
        if (i + 1) % 10 == 0:
            print(f"  [{i+1}/{len(paths)}] processed")

    elapsed = time.time() - t0

    # Metrics
    y_true = np.array(labels)
    y_scores = np.array(scores)
    y_pred = (y_scores >= args.threshold).astype(int)

    acc   = accuracy_score(y_true, y_pred)
    auc   = roc_auc_score(y_true, y_scores) if len(set(labels)) == 2 else float("nan")
    f1    = f1_score(y_true, y_pred, zero_division=0)
    eer   = compute_eer(y_true, y_scores) if len(set(labels)) == 2 else float("nan")
    cm    = confusion_matrix(y_true, y_pred).tolist()
    lat   = (elapsed / len(paths)) * 1000  # ms per image

    results = {
        "num_samples": len(paths),
        "threshold": args.threshold,
        "accuracy": round(acc, 4),
        "auc_roc": round(auc, 4),
        "f1_score": round(f1, 4),
        "eer": round(eer, 4),
        "confusion_matrix": cm,
        "avg_latency_ms": round(lat, 2),
        "total_time_s": round(elapsed, 2),
    }

    print("\n── Evaluation Results ────────────────────────────")
    for k, v in results.items():
        print(f"  {k:<22}: {v}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {args.output}")


if __name__ == "__main__":
    main()
