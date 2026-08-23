# Phase 1 — Datasets

> **Read this before touching any data.** You are NOT training a deepfake detector from scratch.

---

## What trains vs. what's pretrained

| Component | Status | Your work |
|-----------|--------|-----------|
| Frame-level deepfake scorer | **Pretrained** (Xception, DeepfakeBench) | Pull checkpoint, run inference |
| Fusion decision classifier | **Trained by you** (LR / MLP, scikit-learn) | This is your novel artifact |

The frame-level model produces `deepfake_score ∈ [0,1]`. Your fusion layer combines it with operational signals (`blink_rate_bpm`, `av_sync_ms`, `cosine_similarity_score`, `registry_velocity_6hr`) to emit `pass / borderline / fail`.

---

## Dataset access

### FaceForensics++ (FF++) — *Primary*

- **Access**: Request at https://docs.google.com/forms/d/e/1FAIpQLSdRRR3L5zAv6tQ_CKxmK4W96tAab_pfBu2EqKA7GJEMLfk9gQ/viewform
- **What to pull**: c23 quality (H.264 compressed), `original_sequences/` + at least 2 manipulation types (`Deepfakes/`, `Face2Face/`)
- **Size needed**: A few hundred clips (~10–20 GB at c23 quality)
- **Timeline**: Access typically granted in 1–3 business days

### Celeb-DF v2 — *Alternative / Supplementary*

- **Access**: https://github.com/yuezunli/celeb-deepfakeforensics — email request
- **Why**: Higher quality fakes, good for testing generalization beyond FF++
- **Size**: ~590 videos (real + fake)

### DFDC (Kaggle) — *Optional, largest*

- **Access**: https://www.kaggle.com/competitions/deepfake-detection-challenge/data
- **Why**: Use only if FF++/Celeb-DF access is slow; largest dataset
- **Tradeoff**: Noisier labels, very large (470 GB full / ~10 GB sample on Kaggle)

---

## Pretrained checkpoint — DeepfakeBench (Xception)

**Repository**: https://github.com/SCLBD/DeepfakeBench

**Model choice rationale** (via Awesome-Deepfakes-Detection):

| Model | AUC on FF++ | Inference speed | Size |
|-------|------------|----------------|------|
| Xception | ~0.99 | ~15ms/frame @ GPU | 88 MB |
| EfficientNet-B4 | ~0.99 | ~12ms/frame | 75 MB |
| ViT-B | ~0.99 | ~40ms/frame | 340 MB |

**Xception chosen** because:
- Best speed/accuracy tradeoff at ≤15ms/frame (within latency budget)
- Pretrained weights available via `timm`
- Native to DeepfakeBench codebase

**Download** (auto via `extract_deepfake_scores.py`):
```bash
pip install timm
python scripts/extract_deepfake_scores.py --dry-run   # test without checkpoint
python scripts/extract_deepfake_scores.py \
    --frames-dir data/raw/ff_plus_frames/ \
    --device cuda \
    --output data/raw/ff_plus_features.csv
```

---

## Fusion classifier training pipeline

```
FF++ frames
    └──► extract_deepfake_scores.py ──► ff_plus_features.csv
                                              │
synthetic batch (fallback)                    ▼
    └──► generate_synthetic_batch.py   train_fusion_classifier.py
              onboarding_batch.json ──►      │
                                             ├──► models/fusion_classifier.pkl
                                             └──► docs/fusion_classifier_report.json
```

**Feature vector** (5 dimensions):
```
deepfake_score          float  [0, 1]   — from pretrained Xception
blink_rate_bpm          float  [0, 30]  — from MediaPipe face mesh
av_sync_ms              float  [−300, 300] — audio-video alignment offset
cosine_similarity_score float  [0, 1]   — face embedding vs. claimed identity
registry_velocity_6hr   int    [1, 20]  — new-account attempts in 6hr window
```

**Decision thresholds** (same in both data generation and inference):
```
FAIL       if deepfake_score ≥ 0.75 OR velocity ≥ 6 OR cosine < 0.35 OR challenge_fail
BORDERLINE if deepfake_score ∈ [0.40, 0.75) OR velocity ∈ [3, 6) OR cosine ∈ [0.35, 0.60) OR |av_sync| > 80ms
PASS       otherwise
```

---

## Day-1 pipeline (no data access required)

```bash
# 1. Generate synthetic onboarding batch (60 records)
python scripts/generate_synthetic_batch.py --n 60 --output data/onboarding_batch.json

# 2. Generate synthetic FF++ feature CSV (dry-run, no GPU/checkpoint)
python scripts/extract_deepfake_scores.py --dry-run --n-real 120 --n-fake 120

# 3. Train fusion classifier
python scripts/train_fusion_classifier.py
# → auto-discovers data/raw/ff_plus_features.csv
# → saves models/fusion_classifier.pkl
# → saves docs/fusion_classifier_report.json
```

---

## References

- [Awesome-Deepfakes-Detection](https://github.com/Daisy-Zhang/Awesome-Deepfakes-Detection) — model comparison
- [DeepfakeBench](https://github.com/SCLBD/DeepfakeBench) — benchmark codebase & checkpoints
- [FaceForensics++](https://github.com/ondyari/FaceForensics) — dataset
- [Celeb-DF](https://github.com/yuezunli/celeb-deepfakeforensics) — dataset
