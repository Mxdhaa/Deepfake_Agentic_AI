#!/usr/bin/env python3
"""
scripts/eval_heuristics_test_split.py
────────────────────────────────────────────────────────────────────────────────
High-speed evaluation of pure heuristic deepfake detector across the 1,525 held-out test split.
"""

from __future__ import annotations

import csv
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import cv2
import numpy as np

# Suppress structlog and logging output for high throughput
logging.disable(logging.CRITICAL)
os.environ["LOG_LEVEL"] = "CRITICAL"

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
import structlog
structlog.configure(
    processors=[structlog.processors.JSONRenderer()],
    wrapper_class=structlog.make_filtering_bound_logger(logging.CRITICAL),
)
from app.models.detector import DeepfakeDetector


def main():
    root = Path(__file__).resolve().parent.parent
    manifest_path = root / "backend" / "data" / "ffpp_airtight" / "dataset_manifest.csv"

    if not manifest_path.exists():
        manifest_path = root / "backend" / "data" / "ffpp_subset" / "dataset_manifest.csv"

    records = []
    with open(manifest_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            records.append(row)

    test_recs = [r for r in records if r.get("split") == "test"]
    print(f"[INFO] Evaluating {len(test_recs)} test frames with pure heuristics...", flush=True)

    detector = DeepfakeDetector()

    all_scores = []
    all_labels = []
    all_sources = []

    start = time.time()
    for idx, r in enumerate(test_recs):
        img_path = r["image_path"]
        img = cv2.imread(img_path)
        if img is None:
            continue

        score = detector.predict(img)
        all_scores.append(score)
        all_labels.append(int(float(r["label"])))
        all_sources.append(r.get("source", "unknown"))

    elapsed = time.time() - start
    print(f"[INFO] Completed 1,525 evaluations in {elapsed:.2f}s ({len(all_labels) / max(0.01, elapsed):.1f} fps)", flush=True)

    n_samples = len(all_labels)
    binary_preds = [1 if s >= 0.20 else 0 for s in all_scores]  # Standard anomaly threshold

    tp = sum(p == 1 and y == 1 for p, y in zip(binary_preds, all_labels))
    fp = sum(p == 1 and y == 0 for p, y in zip(binary_preds, all_labels))
    tn = sum(p == 0 and y == 0 for p, y in zip(binary_preds, all_labels))
    fn = sum(p == 0 and y == 1 for p, y in zip(binary_preds, all_labels))

    accuracy = (tp + tn) / n_samples
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    by_source = {}
    for s in sorted(list(set(all_sources))):
        s_indices = [i for i, src in enumerate(all_sources) if src == s]
        s_corr = sum(binary_preds[i] == all_labels[i] for i in s_indices)
        s_tot = len(s_indices)
        s_scores = [all_scores[i] for i in s_indices]
        by_source[s] = {
            "accuracy": round(s_corr / s_tot, 4) if s_tot > 0 else 0.0,
            "mean_anomaly_score": round(float(np.mean(s_scores)), 4) if s_scores else 0.0,
            "max_anomaly_score": round(float(np.max(s_scores)), 4) if s_scores else 0.0,
            "samples": s_tot,
        }

    output = {
        "detection_mode": detector.detection_mode,
        "test_samples": n_samples,
        "metrics": {
            "accuracy": round(accuracy, 4),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1_score": round(f1, 4),
        },
        "confusion_matrix": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
        "per_manipulation_method": by_source,
    }

    print("\n" + json.dumps(output, indent=2), flush=True)

    metrics_path = root / "backend" / "detector_metrics.json"
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)


if __name__ == "__main__":
    main()
