#!/usr/bin/env python3
"""
Synthetic Deepfake Data Generator
────────────────────────────────────
Generates synthetic training samples by applying face-swap augmentations
to real face images. Used for data augmentation (NOT as a replacement
for real benchmark datasets).

Usage:
    python scripts/gen_synthetic.py \
        --input  data/samples/real/ \
        --output data/samples/synthetic/ \
        --n      500 \
        --method blend   # blend | warp | color

Methods:
    blend  — Alpha-blend two faces with random opacity
    warp   — Affine warp + paste to simulate geometric artifacts
    color  — Color histogram transfer to introduce colour mismatch
"""

import argparse
import random
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


# ─── Helpers ──────────────────────────────────────────────────────────────────

def load_images(directory: Path) -> list[np.ndarray]:
    """Load all JPG/PNG images from a directory as BGR numpy arrays."""
    images = []
    for ext in ("*.jpg", "*.jpeg", "*.png", "*.webp"):
        for p in sorted(directory.glob(ext)):
            img = cv2.imread(str(p))
            if img is not None:
                images.append(img)
    return images


def blend_faces(src: np.ndarray, dst: np.ndarray, alpha: float = 0.5) -> np.ndarray:
    """Alpha-blend src onto dst face region."""
    h, w = dst.shape[:2]
    src_resized = cv2.resize(src, (w, h))
    blended = cv2.addWeighted(src_resized, alpha, dst, 1 - alpha, 0)
    return blended


def warp_face(src: np.ndarray, dst: np.ndarray) -> np.ndarray:
    """Affine warp src and paste onto dst — simulates geometric misalignment."""
    h, w = dst.shape[:2]
    src_resized = cv2.resize(src, (w, h))

    # Random affine transform
    pts_src = np.float32([[0, 0], [w, 0], [0, h]])
    jitter = 15
    pts_dst = pts_src + np.random.uniform(-jitter, jitter, pts_src.shape).astype(np.float32)
    M = cv2.getAffineTransform(pts_src, pts_dst)
    warped = cv2.warpAffine(src_resized, M, (w, h))

    # Paste with elliptical mask
    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.ellipse(mask, (w // 2, h // 2), (w // 3, h // 2), 0, 0, 360, 255, -1)
    mask_3d = cv2.merge([mask, mask, mask])
    result = np.where(mask_3d > 0, warped, dst)
    return result


def color_transfer(src: np.ndarray, dst: np.ndarray) -> np.ndarray:
    """Transfer colour statistics from src to dst in LAB space."""
    src_lab = cv2.cvtColor(src.astype(np.float32), cv2.COLOR_BGR2LAB)
    dst_lab = cv2.cvtColor(dst.astype(np.float32), cv2.COLOR_BGR2LAB)

    for i in range(3):
        src_mean, src_std = src_lab[:, :, i].mean(), src_lab[:, :, i].std()
        dst_mean, dst_std = dst_lab[:, :, i].mean(), dst_lab[:, :, i].std()
        if dst_std > 0:
            dst_lab[:, :, i] = (dst_lab[:, :, i] - dst_mean) * (src_std / dst_std) + src_mean

    result = cv2.cvtColor(np.clip(dst_lab, 0, 255).astype(np.uint8), cv2.COLOR_LAB2BGR)
    return result


METHODS = {
    "blend": blend_faces,
    "warp": warp_face,
    "color": color_transfer,
}


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input",  type=Path, default=Path("data/samples/real"), help="Directory of real face images")
    parser.add_argument("--output", type=Path, default=Path("data/samples/synthetic"), help="Output directory")
    parser.add_argument("--n",      type=int,  default=100, help="Number of synthetic samples to generate")
    parser.add_argument("--method", choices=list(METHODS.keys()), default="blend")
    parser.add_argument("--seed",   type=int,  default=42)
    args = parser.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)

    if not args.input.exists():
        print(f"[ERROR] Input directory not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    images = load_images(args.input)
    if len(images) < 2:
        print(f"[ERROR] Need at least 2 images in {args.input}", file=sys.stderr)
        sys.exit(1)

    args.output.mkdir(parents=True, exist_ok=True)
    method_fn = METHODS[args.method]

    print(f"Generating {args.n} synthetic samples using method='{args.method}'...")
    for i in range(args.n):
        src, dst = random.sample(images, 2)
        result = method_fn(src, dst)
        out_path = args.output / f"synthetic_{i:04d}.jpg"
        cv2.imwrite(str(out_path), result)
        if (i + 1) % 50 == 0:
            print(f"  [{i+1}/{args.n}] saved to {out_path}")

    print(f"\nDone. {args.n} synthetic images saved to {args.output}/")


if __name__ == "__main__":
    main()
