# models/

This directory stores trained model artifacts for the Deepfake Agentic AI system.

## Contents

| File | Description | Produced by |
|------|-------------|------------|
| `fusion_classifier.pkl` | Scikit-learn pipeline (scaler + best classifier) for the pass/borderline/fail fusion decision | `scripts/train_fusion_classifier.py` |

## Loading the model

```python
import joblib

model = joblib.load("models/fusion_classifier.pkl")

# Feature order must match FEATURE_COLS in train_fusion_classifier.py:
# [deepfake_score, blink_rate_bpm, av_sync_ms,
#  cosine_similarity_score, registry_velocity_6hr]

X = [[0.12, 14.5, -8.3, 0.91, 1]]   # one sample
pred = model.predict(X)              # e.g. [0] = pass
prob = model.predict_proba(X)        # class probabilities
```

## Label mapping

| Integer | Decision |
|---------|----------|
| 0       | pass |
| 1       | borderline |
| 2       | fail |

## Re-training

```bash
# From synthetic batch (day 1, no real data):
python scripts/generate_synthetic_batch.py
python scripts/train_fusion_classifier.py --batch data/onboarding_batch.json

# From FF++ feature CSV (once dataset access arrives):
python scripts/extract_deepfake_scores.py --frames-dir data/raw/ff_plus_frames/
python scripts/train_fusion_classifier.py --features data/raw/ff_plus_features.csv
```
