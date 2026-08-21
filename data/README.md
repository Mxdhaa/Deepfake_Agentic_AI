# Data Directory

This directory holds media samples for development and evaluation.

## Structure

```
data/
├── samples/
│   ├── real/     ← Real (authentic) face images/videos for testing
│   └── fake/     ← Deepfake face images/videos for testing
└── raw/          ← GITIGNORED — full downloaded datasets go here
```

## ⚠️ What is NOT committed

The `/data/raw/` directory is gitignored because full datasets are large (hundreds of GB).
Only small curated samples in `/data/samples/` are committed.

## Downloading Full Datasets

Use the provided scripts:

```bash
# Download FaceForensics++ samples
bash scripts/download_datasets.sh ff++ --subset c23 --num-videos 100

# Download DFDC preview dataset  
bash scripts/download_datasets.sh dfdc --split train

# Download Celeb-DF v2
bash scripts/download_datasets.sh celebdf
```

## Dataset Sources

| Dataset | URL | Notes |
|---|---|---|
| FaceForensics++ | https://github.com/ondyari/FaceForensics | Requires access request |
| DFDC | https://ai.meta.com/datasets/dfdc/ | Meta AI dataset |
| Celeb-DF v2 | https://github.com/yuezunli/celeb-deepfakeforensics | Public |
| UADFV | https://github.com/yuezunli/WIFS2018_In_Ictu_Oculi | Public |

## Synthetic Data

See `scripts/gen_synthetic.py` for generating synthetic training samples using
face-swap augmentation (for data augmentation, NOT replacing real datasets).
