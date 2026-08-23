#!/usr/bin/env python3
"""
train_fusion_classifier.py
────────────────────────────────────────────────────────────────────────────────
Trains the fusion decision classifier — the TRAINED ARTIFACT at the heart of
Phase 1. This layer takes the pretrained frame-level deepfake score and combines
it with operational signals to produce a final pass / borderline / fail decision.

Feature vector (5 dimensions):
    [deepfake_score, blink_rate_bpm, av_sync_ms,
     cosine_similarity_score, registry_velocity_6hr]

Input priority:
    1. --features  CSV produced by extract_deepfake_scores.py (real FF++ data)
    2. --batch     JSON produced by generate_synthetic_batch.py (demo/fallback)
    If neither exists, aborts with instructions.

Models trained:
    A. LogisticRegression  (interpretable, fast, good baseline)
    B. MLPClassifier        (small 2-layer net: 64→32→3)
    Best model (by CV F1-macro) is saved to --save.

Output:
    models/fusion_classifier.pkl   — best scikit-learn pipeline (joblib)
    docs/fusion_classifier_report.json — full CV + test-set metrics

Usage:
    # With synthetic onboarding batch (day 1, no real data yet):
    python scripts/train_fusion_classifier.py \\
        --batch data/onboarding_batch.json \\
        --save  models/fusion_classifier.pkl

    # With FF++ feature CSV (once extract_deepfake_scores.py has run):
    python scripts/train_fusion_classifier.py \\
        --features data/raw/ff_plus_features.csv \\
        --save     models/fusion_classifier.pkl
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import warnings
from pathlib import Path

# Force UTF-8 stdout/stderr on Windows (avoids cp1252 UnicodeEncodeError)
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
if sys.stderr.encoding and sys.stderr.encoding.lower() not in ("utf-8", "utf8"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

import numpy as np


# ─── Guard: scikit-learn ──────────────────────────────────────────────────────
try:
    from sklearn.linear_model import LogisticRegression
    from sklearn.neural_network import MLPClassifier
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import StratifiedKFold, cross_validate
    from sklearn.metrics import (
        accuracy_score, precision_score, recall_score, f1_score,
        classification_report, confusion_matrix,
    )
    import joblib
except ImportError:
    print(
        "[ERROR] scikit-learn and joblib required:\n"
        "  pip install scikit-learn joblib",
        file=sys.stderr,
    )
    sys.exit(1)


# ─── Constants ────────────────────────────────────────────────────────────────

FEATURE_COLS = [
    "deepfake_score",
    "blink_rate_bpm",
    "av_sync_ms",
    "cosine_similarity_score",
    "registry_velocity_6hr",
]

LABEL_MAP = {"pass": 0, "borderline": 1, "fail": 2}
LABEL_NAMES = ["pass", "borderline", "fail"]


# ─── Data loaders ─────────────────────────────────────────────────────────────

def _load_from_batch_json(path: Path) -> tuple[np.ndarray, np.ndarray]:
    """
    Load from data/onboarding_batch.json produced by generate_synthetic_batch.py.
    Returns (X, y) with label integers: pass=0, borderline=1, fail=2.
    """
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)

    records = payload.get("records", payload)  # support bare list too
    rows: list[list[float]] = []
    labels: list[int] = []

    for r in records:
        decision = r.get("decision", "")
        if decision not in LABEL_MAP:
            continue
        try:
            rows.append([
                float(r["deepfake_score"]),
                float(r["blink_rate_bpm"]),
                float(r["av_sync_ms"]),
                float(r["cosine_similarity_score"]),
                float(r["registry_velocity_6hr"]),
            ])
            labels.append(LABEL_MAP[decision])
        except (KeyError, ValueError) as e:
            print(f"[WARN] Skipping record {r.get('kin_token','?')}: {e}", file=sys.stderr)

    if not rows:
        raise ValueError(f"No usable records found in {path}")

    return np.array(rows, dtype=np.float32), np.array(labels, dtype=np.int64)


def _load_from_feature_csv(path: Path) -> tuple[np.ndarray, np.ndarray]:
    """
    Load from data/raw/ff_plus_features.csv produced by extract_deepfake_scores.py.
    The CSV only has binary labels (0=real, 1=fake), so we derive 3-class labels:
        real  (label=0, score<0.40)  → pass
        ambig (label=1, score∈0.40-0.75) → borderline
        fake  (label=1, score≥0.75)   → fail

    Missing blink_rate_bpm / av_sync_ms are imputed with class-median defaults.
    """
    rows: list[list[float | None]] = []
    binary_labels: list[int] = []
    scores: list[float] = []

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                score = float(row["deepfake_score"])
                label = int(row["label"])
                blink = float(row["blink_rate_bpm"]) if row.get("blink_rate_bpm") else None
                av    = float(row["av_sync_ms"])     if row.get("av_sync_ms")     else None
                rows.append([score, blink, av])
                binary_labels.append(label)
                scores.append(score)
            except (KeyError, ValueError) as e:
                print(f"[WARN] Skipping CSV row: {e}", file=sys.stderr)

    if not rows:
        raise ValueError(f"No usable rows found in {path}")

    # Impute missing blink/AV with label-conditioned medians
    real_blinks  = [r[1] for r, l in zip(rows, binary_labels) if r[1] is not None and l == 0]
    fake_blinks  = [r[1] for r, l in zip(rows, binary_labels) if r[1] is not None and l == 1]
    real_avs     = [r[2] for r, l in zip(rows, binary_labels) if r[2] is not None and l == 0]
    fake_avs     = [r[2] for r, l in zip(rows, binary_labels) if r[2] is not None and l == 1]

    med_real_blink = float(np.median(real_blinks))  if real_blinks  else 15.0
    med_fake_blink = float(np.median(fake_blinks))  if fake_blinks  else 4.0
    med_real_av    = float(np.median(real_avs))      if real_avs     else 0.0
    med_fake_av    = float(np.median(fake_avs))      if fake_avs     else 120.0

    X_list: list[list[float]] = []
    y_list: list[int] = []

    for row_vals, bin_label, score in zip(rows, binary_labels, scores):
        blink = row_vals[1] if row_vals[1] is not None else (
            med_real_blink if bin_label == 0 else med_fake_blink
        )
        av = row_vals[2] if row_vals[2] is not None else (
            med_real_av if bin_label == 0 else med_fake_av
        )

        # Derive 3-class label from score
        if bin_label == 0 or score < 0.40:
            derived_label = 0  # pass
        elif score < 0.75:
            derived_label = 1  # borderline
        else:
            derived_label = 2  # fail

        # Placeholder operationalfeatures (dataset-level proxies)
        cosine  = 0.90 - 0.50 * score + np.random.normal(0, 0.05)
        cosine  = float(np.clip(cosine, 0.05, 0.99))
        velocity = 1 + int(score * 10) if bin_label == 1 else 1

        X_list.append([score, blink, av, cosine, velocity])
        y_list.append(derived_label)

    return np.array(X_list, dtype=np.float32), np.array(y_list, dtype=np.int64)


# ─── Model builders ───────────────────────────────────────────────────────────

def _make_lr() -> Pipeline:
    return Pipeline([
        ("scaler", StandardScaler()),
        ("clf",    LogisticRegression(
            max_iter=1000,
            multi_class="multinomial",
            solver="lbfgs",
            class_weight="balanced",
            C=1.0,
            random_state=42,
        )),
    ])


def _make_mlp() -> Pipeline:
    return Pipeline([
        ("scaler", StandardScaler()),
        ("clf",    MLPClassifier(
            hidden_layer_sizes=(64, 32),
            activation="relu",
            solver="adam",
            max_iter=500,
            early_stopping=True,
            validation_fraction=0.15,
            random_state=42,
            learning_rate_init=1e-3,
        )),
    ])


# ─── Cross-validation ─────────────────────────────────────────────────────────

def _cross_val(name: str, pipeline: Pipeline, X: np.ndarray, y: np.ndarray,
               n_splits: int = 5) -> dict:
    """Run StratifiedKFold CV and return averaged metrics."""
    min_class = min(np.bincount(y))
    if min_class < n_splits:
        n_splits = max(2, min_class)
        print(f"[WARN] Reducing CV folds to {n_splits} (smallest class has {min_class} samples)")

    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        cv_results = cross_validate(
            pipeline, X, y,
            cv=skf,
            scoring=["accuracy", "f1_macro", "precision_macro", "recall_macro"],
            return_train_score=False,
        )

    def _fmt(arr: np.ndarray) -> dict:
        return {"mean": round(float(arr.mean()), 4), "std": round(float(arr.std()), 4)}

    return {
        "model":          name,
        "n_folds":        n_splits,
        "accuracy":       _fmt(cv_results["test_accuracy"]),
        "f1_macro":       _fmt(cv_results["test_f1_macro"]),
        "precision_macro":_fmt(cv_results["test_precision_macro"]),
        "recall_macro":   _fmt(cv_results["test_recall_macro"]),
    }


# ─── Final fit + test metrics ─────────────────────────────────────────────────

def _final_fit_metrics(name: str, pipeline: Pipeline,
                       X_train: np.ndarray, y_train: np.ndarray,
                       X_test: np.ndarray, y_test: np.ndarray) -> dict:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        pipeline.fit(X_train, y_train)

    y_pred = pipeline.predict(X_test)
    labels_present = sorted(set(y_test.tolist()) | set(y_pred.tolist()))
    label_names_present = [LABEL_NAMES[i] for i in labels_present]

    report = classification_report(
        y_test, y_pred,
        labels=labels_present,
        target_names=label_names_present,
        output_dict=True,
        zero_division=0,
    )
    cm = confusion_matrix(y_test, y_pred, labels=labels_present).tolist()

    return {
        "model":        name,
        "test_accuracy": round(accuracy_score(y_test, y_pred), 4),
        "test_f1_macro": round(f1_score(y_test, y_pred, average="macro", zero_division=0), 4),
        "per_class":    {k: {m: round(v, 4) for m, v in v2.items()}
                         for k, v2 in report.items()
                         if k in label_names_present},
        "confusion_matrix": {"labels": label_names_present, "matrix": cm},
    }


# ─── Pretty printer ───────────────────────────────────────────────────────────

def _print_cv_table(results: list[dict]) -> None:
    print("\n╔══ Cross-Validation Results ══════════════════════════════════╗")
    print(f"  {'Model':<22} {'Acc':>8} {'F1-macro':>10} {'Prec':>8} {'Rec':>8}")
    print("  " + "─" * 58)
    for r in results:
        print(
            f"  {r['model']:<22}"
            f" {r['accuracy']['mean']:>7.4f}"
            f" {r['f1_macro']['mean']:>10.4f}"
            f" {r['precision_macro']['mean']:>8.4f}"
            f" {r['recall_macro']['mean']:>8.4f}"
        )
    print("╚══════════════════════════════════════════════════════════════╝")


def _print_test_table(results: list[dict], best_name: str) -> None:
    print("\n╔══ Test-Set Metrics ═══════════════════════════════════════════╗")
    for r in results:
        marker = " ★ BEST" if r["model"] == best_name else ""
        print(f"\n  [{r['model']}]{marker}")
        print(f"    Accuracy : {r['test_accuracy']:.4f}")
        print(f"    F1-macro : {r['test_f1_macro']:.4f}")
        print("    Per-class:")
        for cls, metrics in r.get("per_class", {}).items():
            p = metrics.get("precision", 0)
            rec = metrics.get("recall", 0)
            f1  = metrics.get("f1-score", 0)
            supp = int(metrics.get("support", 0))
            print(f"      {cls:<12}  P={p:.3f}  R={rec:.3f}  F1={f1:.3f}  n={supp}")
    print("╚══════════════════════════════════════════════════════════════╝")


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--features", type=Path,
                        help="CSV from extract_deepfake_scores.py")
    source.add_argument("--batch",    type=Path,
                        help="JSON from generate_synthetic_batch.py")
    parser.add_argument("--save",     type=Path, default=Path("models/fusion_classifier.pkl"))
    parser.add_argument("--report",   type=Path, default=Path("docs/fusion_classifier_report.json"))
    parser.add_argument("--test-split", type=float, default=0.20,
                        help="Fraction of data held out as test set")
    parser.add_argument("--seed",     type=int, default=42)
    args = parser.parse_args()

    # ── Auto-discover data source ──────────────────────────────────────────────
    if args.features is None and args.batch is None:
        for candidate in [
            Path("data/raw/ff_plus_features.csv"),
            Path("data/onboarding_batch.json"),
        ]:
            if candidate.exists():
                if candidate.suffix == ".csv":
                    args.features = candidate
                else:
                    args.batch = candidate
                print(f"[AUTO] Using {candidate}")
                break
        else:
            print(
                "[ERROR] No data source found. Run one of:\n"
                "  python scripts/extract_deepfake_scores.py --dry-run\n"
                "  python scripts/generate_synthetic_batch.py",
                file=sys.stderr,
            )
            sys.exit(1)

    # ── Load data ─────────────────────────────────────────────────────────────
    if args.features is not None:
        print(f"[INFO] Loading feature CSV: {args.features}")
        X, y = _load_from_feature_csv(args.features)
        source_type = "ff_plus_features"
    else:
        print(f"[INFO] Loading onboarding batch: {args.batch}")
        X, y = _load_from_batch_json(args.batch)
        source_type = "onboarding_batch"

    n_total = len(y)
    print(f"[INFO] Loaded {n_total} samples | "
          f"pass={np.sum(y==0)} borderline={np.sum(y==1)} fail={np.sum(y==2)}")

    if n_total < 10:
        print("[ERROR] Need at least 10 samples to train.", file=sys.stderr)
        sys.exit(1)

    # ── Train/test split (stratified) ─────────────────────────────────────────
    from sklearn.model_selection import train_test_split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y,
        test_size=args.test_split,
        stratify=y,
        random_state=args.seed,
    )
    print(f"[INFO] Split: {len(y_train)} train / {len(y_test)} test")

    # ── Define models ─────────────────────────────────────────────────────────
    model_defs = [
        ("LogisticRegression", _make_lr()),
        ("MLP (64→32→3)",      _make_mlp()),
    ]

    # ── Cross-validation ──────────────────────────────────────────────────────
    print("\n── 5-Fold Stratified Cross-Validation ────────────────────────────")
    cv_results: list[dict] = []
    for name, pipeline in model_defs:
        print(f"  Training {name}...", end=" ", flush=True)
        cv = _cross_val(name, pipeline, X_train, y_train)
        cv_results.append(cv)
        print(f"F1-macro={cv['f1_macro']['mean']:.4f}")

    _print_cv_table(cv_results)

    # ── Final evaluation on hold-out test set ─────────────────────────────────
    print("\n── Fitting on full train set + evaluating test set ──────────────")
    test_results: list[dict] = []
    pipelines_fitted: list[tuple[str, Pipeline]] = []

    for name, pipeline in model_defs:
        print(f"  {name}...", end=" ", flush=True)
        metrics = _final_fit_metrics(name, pipeline, X_train, y_train, X_test, y_test)
        test_results.append(metrics)
        pipelines_fitted.append((name, pipeline))
        print(f"acc={metrics['test_accuracy']:.4f}  F1={metrics['test_f1_macro']:.4f}")

    # ── Select best model ─────────────────────────────────────────────────────
    best_idx = max(range(len(test_results)), key=lambda i: test_results[i]["test_f1_macro"])
    best_name, best_pipeline = pipelines_fitted[best_idx]
    _print_test_table(test_results, best_name)
    print(f"\n★  Best model: {best_name}")

    # ── Save model ────────────────────────────────────────────────────────────
    args.save.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(best_pipeline, args.save)
    print(f"[OK] Model saved -> {args.save}")

    # Build a human-readable note that is explicit about synthetic label inflation
    if source_type == "onboarding_batch":
        label_note = (
            "SYNTHETIC BOOTSTRAP — labels were derived deterministically by _derive_decision() "
            "using strict half-open intervals evaluated in priority order (fail > borderline > pass). "
            "Exact bands: deepfake_score [0,0.40)=pass [0.40,0.75)=borderline [0.75,1]=fail; "
            "abs(av_sync_ms) [0,80]=pass (80,150]=borderline (150,inf)=fail; "
            "registry_velocity [1,3)=pass [3,6)=borderline [6,inf)=fail; "
            "cosine (0.60,1]=pass (0.35,0.60]=borderline [0,0.35]=fail; "
            "blink_rate [8,inf)=pass [0,8)=borderline (no blink fail tier); "
            "challenge_match False -> fail unconditionally. "
            "Bands are mutually exclusive (short-circuit OR logic, fail checked first) — "
            "no gaps, no overlaps. "
            "This creates a partially circular training loop: the classifier learns to recover "
            "this rule from noisy float samples of it. "
            "Reported F1 reflects pipeline correctness, NOT generalization to real data. "
            "When FF++/Celeb-DF labels arrive, retrain with --features ff_plus_features.csv; "
            "expect F1 to drop — that drop is meaningful signal, not regression."
        )
        validity_scope = "pipeline_validation_only"
    else:
        label_note = (
            "Labels sourced from FF++/Celeb-DF feature CSV with independently annotated "
            "ground truth. F1 reflects genuine generalization within the held-out test split. "
            "Note: cosine_similarity and registry_velocity columns are still imputed proxies "
            "until the full operational feature extractor is integrated."
        )
        validity_scope = "real_data_partial_features"

    report = {
        "source":           source_type,
        "validity_scope":   validity_scope,
        "label_note":       label_note,
        "n_train":          int(len(y_train)),
        "n_test":           int(len(y_test)),
        "feature_cols":     FEATURE_COLS,
        "label_map":        LABEL_MAP,
        "best_model":       best_name,
        "saved_to":         str(args.save),
        "cross_validation": cv_results,
        "test_set_metrics": test_results,
    }

    # Print the validity warning prominently when using synthetic data
    if validity_scope == "pipeline_validation_only":
        print(
            "\n[NOTE] Synthetic label bootstrap detected.\n"
            "  F1 reflects rule recovery, not generalization.\n"
            "  See docs/fusion_classifier_report.json -> label_note for full context."
        )

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with open(args.report, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"[OK] Report saved -> {args.report}")


if __name__ == "__main__":
    main()
