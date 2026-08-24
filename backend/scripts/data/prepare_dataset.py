"""
prepare_dataset.py — Unified Deepfake Dataset Ingestion & Preprocessing
────────────────────────────────────────────────────────────────────────
Ingests diverse deepfake data sources and produces a standardized manifest:
  1. Image directories (e.g. Kaggle 140k real_and_fake_faces: real/ vs fake/)
  2. Video directories (e.g. FaceForensics++ / Celeb-DF) with face extraction & subsampling
  3. Synthetic dummy generator (--generate-dummy) for instant pipeline scaffolding

Output:
  Unified manifest CSV containing: [image_path, label (0=real, 1=fake), split (train/val/test), source]
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import random
import sys
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional

import cv2
import numpy as np
from PIL import Image

# Common target face crop size (Xception: 299x299, EfficientNet: 224x224 to 380x380)
DEFAULT_IMAGE_SIZE = (299, 299)


# ─── Face Extractor (OpenCV Haar Cascade with MTCNN fallback) ─────────────────

class FaceExtractor:
    def __init__(self, target_size: Tuple[int, int] = DEFAULT_IMAGE_SIZE) -> None:
        self.target_size = target_size
        self.mtcnn = None
        self._init_detector()

    def _init_detector(self) -> None:
        # Try MTCNN from facenet_pytorch
        try:
            from facenet_pytorch import MTCNN
            self.mtcnn = MTCNN(keep_all=False, select_largest=True, post_process=False, device="cpu")
            print("  [INFO] Initialized MTCNN face detector.")
        except Exception:
            # Fallback to OpenCV Haar Cascade
            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            self.cascade = cv2.CascadeClassifier(cascade_path)
            print("  [INFO] MTCNN not found, initialized OpenCV Haar face detector.")

    def extract_face(self, frame_bgr: np.ndarray) -> Optional[np.ndarray]:
        if frame_bgr is None or frame_bgr.size == 0:
            return None

        h, w = frame_bgr.shape[:2]
        if self.mtcnn is not None:
            try:
                frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(frame_rgb)
                boxes, _ = self.mtcnn.detect(pil_img)
                if boxes is not None and len(boxes) > 0:
                    box = boxes[0]
                    x1, y1, x2, y2 = [int(b) for b in box]
                    # Add 10% margin
                    margin_x = int((x2 - x1) * 0.1)
                    margin_y = int((y2 - y1) * 0.1)
                    x1 = max(0, x1 - margin_x)
                    y1 = max(0, y1 - margin_y)
                    x2 = min(w, x2 + margin_x)
                    y2 = min(h, y2 + margin_y)
                    crop = frame_rgb[y1:y2, x1:x2]
                    if crop.size > 0:
                        crop_resized = cv2.resize(crop, self.target_size, interpolation=cv2.INTER_AREA)
                        return cv2.cvtColor(crop_resized, cv2.COLOR_RGB2BGR)
            except Exception:
                pass

        # Haar Cascade fallback
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        faces = self.cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(60, 60))
        if len(faces) > 0:
            # Pick largest face
            faces = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)
            x, y, fw, fh = faces[0]
            # Add 10% margin
            mx = int(fw * 0.1)
            my = int(fh * 0.1)
            x1 = max(0, x - mx)
            y1 = max(0, y - my)
            x2 = min(w, x + fw + mx)
            y2 = min(h, y + fh + my)
            crop = frame_bgr[y1:y2, x1:x2]
            if crop.size > 0:
                return cv2.resize(crop, self.target_size, interpolation=cv2.INTER_AREA)

        # If no face detected, center crop square & resize
        min_dim = min(h, w)
        sy = (h - min_dim) // 2
        sx = (w - min_dim) // 2
        crop = frame_bgr[sy : sy + min_dim, sx : sx + min_dim]
        return cv2.resize(crop, self.target_size, interpolation=cv2.INTER_AREA)


# ─── Dataset Processors ───────────────────────────────────────────────────────

def process_image_folder(
    data_dir: Path,
    output_dir: Path,
    source_name: str = "image_folder",
) -> List[Dict[str, Any]]:
    """
    Ingests an image folder with structure:
      data_dir/
        real/ (or 0/)
        fake/ (or 1/)
    """
    records = []
    output_images_dir = output_dir / "processed_images"
    output_images_dir.mkdir(parents=True, exist_ok=True)
    extractor = FaceExtractor()

    real_dirs = [data_dir / "real", data_dir / "0", data_dir / "original"]
    fake_dirs = [data_dir / "fake", data_dir / "1", data_dir / "manipulated", data_dir / "deepfakes"]

    valid_real = [d for d in real_dirs if d.exists()]
    valid_fake = [d for d in fake_dirs if d.exists()]

    if not valid_real and not valid_fake:
        raise ValueError(f"Could not find real/ or fake/ subdirectories inside {data_dir}")

    for r_dir in valid_real:
        for p in r_dir.glob("*.*"):
            if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
                img = cv2.imread(str(p))
                if img is not None:
                    face = extractor.extract_face(img)
                    if face is not None:
                        out_name = f"{source_name}_real_{p.stem}.jpg"
                        out_path = output_images_dir / out_name
                        cv2.imwrite(str(out_path), face)
                        records.append({
                            "image_path": str(out_path.resolve()),
                            "label": 0,
                            "source": source_name,
                        })

    for f_dir in valid_fake:
        for p in f_dir.glob("*.*"):
            if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
                img = cv2.imread(str(p))
                if img is not None:
                    face = extractor.extract_face(img)
                    if face is not None:
                        out_name = f"{source_name}_fake_{p.stem}.jpg"
                        out_path = output_images_dir / out_name
                        cv2.imwrite(str(out_path), face)
                        records.append({
                            "image_path": str(out_path.resolve()),
                            "label": 1,
                            "source": source_name,
                        })

    return records


def process_video_dataset(
    video_dir: Path,
    output_dir: Path,
    sample_every_n: int = 15,
    source_name: str = "faceforensics",
) -> List[Dict[str, Any]]:
    """
    Ingests video datasets (FaceForensics++ style).
    Extracts faces every Nth frame.
    """
    records = []
    output_images_dir = output_dir / "processed_images"
    output_images_dir.mkdir(parents=True, exist_ok=True)
    extractor = FaceExtractor()

    video_exts = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
    video_files = [p for p in video_dir.rglob("*.*") if p.suffix.lower() in video_exts]

    print(f"  [INFO] Found {len(video_files)} video files in {video_dir}")

    for v_idx, v_path in enumerate(video_files):
        # Determine label by path heuristic
        path_str = str(v_path).lower()
        if "original" in path_str or "real" in path_str or "youtube" in path_str:
            label = 0
        else:
            label = 1

        cap = cv2.VideoCapture(str(v_path))
        frame_idx = 0
        saved_from_video = 0

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            if frame_idx % sample_every_n == 0:
                face = extractor.extract_face(frame)
                if face is not None:
                    out_name = f"{source_name}_v{v_idx}_{'fake' if label == 1 else 'real'}_f{frame_idx}.jpg"
                    out_path = output_images_dir / out_name
                    cv2.imwrite(str(out_path), face)
                    records.append({
                        "image_path": str(out_path.resolve()),
                        "label": label,
                        "source": source_name,
                    })
                    saved_from_video += 1
            frame_idx += 1

        cap.release()

    return records


def generate_dummy_dataset(output_dir: Path, count_per_class: int = 25) -> List[Dict[str, Any]]:
    """
    Generates synthetic 299x299 real & fake sample face images for rapid pipeline scaffolding.
    Real samples: smooth gradients + natural noise.
    Fake samples: boundary checkerboard patterns + high frequency blending artifacts.
    """
    records = []
    output_images_dir = output_dir / "processed_images"
    output_images_dir.mkdir(parents=True, exist_ok=True)

    print(f"  [INFO] Generating {count_per_class * 2} synthetic dummy face images for pipeline testing...")

    # Real Samples (label=0)
    for i in range(count_per_class):
        img = np.zeros((299, 299, 3), dtype=np.uint8)
        # Smooth skin-tone gradient
        base_color = np.array([random.randint(140, 190), random.randint(160, 210), random.randint(190, 240)], dtype=np.float32)
        for y in range(299):
            gradient = (y / 299.0) * 0.3 + 0.85
            img[y, :] = np.clip(base_color * gradient, 0, 255).astype(np.uint8)
        # Natural Gaussian blur & slight noise
        img = cv2.GaussianBlur(img, (9, 9), 2.0)
        noise = np.random.normal(0, 3, (299, 299, 3)).astype(np.uint8)
        img = cv2.add(img, noise)

        out_path = output_images_dir / f"dummy_real_{i:03d}.jpg"
        cv2.imwrite(str(out_path), img)
        records.append({
            "image_path": str(out_path.resolve()),
            "label": 0,
            "source": "dummy_synthetic",
        })

    # Fake Samples (label=1)
    for i in range(count_per_class):
        img = np.zeros((299, 299, 3), dtype=np.uint8)
        base_color = np.array([random.randint(140, 190), random.randint(160, 210), random.randint(190, 240)], dtype=np.float32)
        for y in range(299):
            gradient = (y / 299.0) * 0.3 + 0.85
            img[y, :] = np.clip(base_color * gradient, 0, 255).astype(np.uint8)

        # Add synthetic boundary blending artifact
        cv2.rectangle(img, (60, 60), (240, 240), (random.randint(100, 220), random.randint(100, 220), random.randint(100, 220)), 2)
        # High-frequency checkerboard grid
        grid = (np.indices((299, 299)).sum(axis=0) % 8 == 0).astype(np.uint8) * 15
        img = cv2.add(img, cv2.merge([grid, grid, grid]))

        out_path = output_images_dir / f"dummy_fake_{i:03d}.jpg"
        cv2.imwrite(str(out_path), img)
        records.append({
            "image_path": str(out_path.resolve()),
            "label": 1,
            "source": "dummy_synthetic",
        })

    return records


# ─── Stratified Split & Manifest Generator ───────────────────────────────────

def create_stratified_manifest(
    records: List[Dict[str, Any]],
    output_manifest_path: Path,
    train_ratio: float = 0.70,
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
    seed: int = 42,
) -> None:
    random.seed(seed)
    reals = [r for r in records if r["label"] == 0]
    fakes = [r for r in records if r["label"] == 1]

    random.shuffle(reals)
    random.shuffle(fakes)

    def split_list(items: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        n = len(items)
        n_train = int(n * train_ratio)
        n_val = int(n * val_ratio)
        train_set = items[:n_train]
        val_set = items[n_train : n_train + n_val]
        test_set = items[n_train + n_val :]
        return train_set, val_set, test_set

    r_train, r_val, r_test = split_list(reals)
    f_train, f_val, f_test = split_list(fakes)

    for r in r_train + f_train:
        r["split"] = "train"
    for r in r_val + f_val:
        r["split"] = "val"
    for r in r_test + f_test:
        r["split"] = "test"

    all_records = r_train + f_train + r_val + f_val + r_test + f_test
    random.shuffle(all_records)

    output_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_manifest_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["image_path", "label", "split", "source"])
        writer.writeheader()
        writer.writerows(all_records)

    print(f"\n[OK] Unified Manifest created at: {output_manifest_path}")
    print(f"  * Total Samples : {len(all_records)}")
    print(f"  * Train Split   : {len(r_train) + len(f_train)} (Real: {len(r_train)}, Fake: {len(f_train)})")
    print(f"  * Val Split     : {len(r_val) + len(f_val)} (Real: {len(r_val)}, Fake: {len(f_val)})")
    print(f"  * Test Split    : {len(r_test) + len(f_test)} (Real: {len(r_test)}, Fake: {len(f_test)})\n")


# ─── CLI Entrypoint ──────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Ingest images/videos into unified deepfake training manifest.")
    parser.add_argument("--image-dir", type=str, help="Path to image dataset with real/ and fake/ subfolders")
    parser.add_argument("--video-dir", type=str, help="Path to video dataset (FaceForensics++ style)")
    parser.add_argument("--generate-dummy", action="store_true", help="Generate 50 synthetic real/fake samples for testing")
    parser.add_argument("--output-dir", type=str, default="data/processed_dataset", help="Output directory for crops and manifest")
    parser.add_argument("--manifest-name", type=str, default="dataset_manifest.csv", help="Name of manifest CSV")
    parser.add_argument("--sample-rate", type=int, default=15, help="Frame sampling step for videos")
    parser.add_argument("--source-name", type=str, default="dataset_v1", help="Dataset source identifier")

    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    manifest_path = output_dir / args.manifest_name

    records = []

    if args.generate_dummy:
        records.extend(generate_dummy_dataset(output_dir, count_per_class=25))
    elif args.image_dir:
        records.extend(process_image_folder(Path(args.image_dir), output_dir, source_name=args.source_name))
    elif args.video_dir:
        records.extend(process_video_dataset(Path(args.video_dir), output_dir, sample_every_n=args.sample_rate, source_name=args.source_name))
    else:
        print("[ERROR] Please provide --image-dir, --video-dir, or --generate-dummy")
        sys.exit(1)

    if not records:
        print("[ERROR] No samples were extracted.")
        sys.exit(1)

    create_stratified_manifest(records, manifest_path)


if __name__ == "__main__":
    main()
