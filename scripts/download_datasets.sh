#!/usr/bin/env env bash
# ─── Dataset Download Script ─────────────────────────────────────────────────
# Usage:
#   bash scripts/download_datasets.sh <dataset> [options]
#
# Datasets:
#   ff++    FaceForensics++ (requires credentials)
#   dfdc    DFDC Preview Dataset
#   celebdf Celeb-DF v2
#   uadfv   UADFV
#
# Options for ff++:
#   --subset  c23|c40|raw    (default: c23)
#   --type    Face2Face|Deepfakes|FaceSwap|NeuralTextures (default: all)
#   --n       number of videos (default: 50)
#
# Example:
#   bash scripts/download_datasets.sh ff++ --subset c23 --n 50
#   bash scripts/download_datasets.sh celebdf
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

DATASET="${1:-}"
RAW_DIR="data/raw"
mkdir -p "$RAW_DIR"

usage() {
  sed -n '2,20p' "$0" | sed 's/^# //'
  exit 1
}

check_dependency() {
  if ! command -v "$1" &>/dev/null; then
    echo "[ERROR] '$1' not found. Please install it first."
    exit 1
  fi
}

# ─── FaceForensics++ ─────────────────────────────────────────────────────────
download_ff_plus_plus() {
  check_dependency python3
  SUBSET="c23"
  N=50
  shift
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --subset) SUBSET="$2"; shift 2 ;;
      --n)      N="$2";      shift 2 ;;
      *) shift ;;
    esac
  done

  FF_DIR="$RAW_DIR/FaceForensics"
  mkdir -p "$FF_DIR"

  echo "Downloading FaceForensics++ (subset=$SUBSET, n=$N)..."
  echo "[INFO] You need the download script from:"
  echo "       https://github.com/ondyari/FaceForensics/tree/master/dataset"
  echo "       Place it at scripts/faceforensics_download_v4.py and re-run."

  if [[ -f "scripts/faceforensics_download_v4.py" ]]; then
    python3 scripts/faceforensics_download_v4.py \
      "$FF_DIR" \
      -d all \
      -c "$SUBSET" \
      -t videos \
      --num_videos "$N"
  else
    echo "[SKIP] Download script not found. See instructions above."
  fi
}

# ─── Celeb-DF v2 ─────────────────────────────────────────────────────────────
download_celebdf() {
  check_dependency git
  CELEB_DIR="$RAW_DIR/Celeb-DF-v2"
  if [[ -d "$CELEB_DIR" ]]; then
    echo "[SKIP] $CELEB_DIR already exists."
    return
  fi
  echo "Downloading Celeb-DF v2..."
  echo "[INFO] Visit https://github.com/yuezunli/celeb-deepfakeforensics"
  echo "       to request access and download the dataset."
  mkdir -p "$CELEB_DIR"
}

# ─── DFDC ────────────────────────────────────────────────────────────────────
download_dfdc() {
  DFDC_DIR="$RAW_DIR/DFDC"
  mkdir -p "$DFDC_DIR"
  echo "Downloading DFDC Preview Dataset..."
  echo "[INFO] Visit https://ai.meta.com/datasets/dfdc/ to register and download."
  echo "       Place downloaded files in $DFDC_DIR/"
}

# ─── UADFV ───────────────────────────────────────────────────────────────────
download_uadfv() {
  check_dependency wget
  UADFV_DIR="$RAW_DIR/UADFV"
  mkdir -p "$UADFV_DIR"
  echo "Downloading UADFV..."
  echo "[INFO] Visit https://github.com/yuezunli/WIFS2018_In_Ictu_Oculi for access."
}

# ─── Dispatch ─────────────────────────────────────────────────────────────────
case "$DATASET" in
  ff++)    download_ff_plus_plus "$@" ;;
  dfdc)    download_dfdc ;;
  celebdf) download_celebdf ;;
  uadfv)   download_uadfv ;;
  *)       usage ;;
esac

echo ""
echo "Done. Raw data in: $RAW_DIR/"
echo "Note: $RAW_DIR/ is gitignored — large files stay local only."
