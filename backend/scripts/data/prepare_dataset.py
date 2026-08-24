"""
prepare_dataset.py — Unified Deepfake Dataset Ingestion & Preprocessing
────────────────────────────────────────────────────────────────────────
Ingests diverse deepfake data sources and produces a standardized manifest:
  1. Zip Archives (e.g. archive.zip containing FaceForensics++ C23: original + 6 manipulation types)
  2. Image directories (e.g. Kaggle 140k real_and_fake_faces: real/ vs fake/)
  3. Video directories (e.g. FaceForensics++ / Celeb-DF) with face extraction & subsampling
  4. Synthetic dummy generator (--generate-dummy) for instant pipeline scaffolding

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
import tempfile
import zipfile
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional

import cv2
import numpy as np
from PIL import Image

DEFAULT_IMAGE_SIZE = (299, 299)


# ─── Face Extractor (OpenCV Haar Cascade with MTCNN fallback) ─────────────────

class FaceExtractor:
    def __init__(self, target_size: Tuple[int, int] = DEFAULT_IMAGE_SIZE) -> None:
        self.target_size = target_size
        self.mtcnn = None
        self._init_detector()

    def _init_detector(self) -> None:
        try:
            from facenet_pytorch import MTCNN
            self.mtcnn = MTCNN(keep_all=False, select_largest=True, post_process=False, device="cpu")
            print("  [INFO] Initialized MTCNN face detector.", flush=True)
        except Exception:
            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            self.cascade = cv2.CascadeClassifier(cascade_path)
            print("  [INFO] MTCNN not installed, using OpenCV Haar Cascade face detector.", flush=True)

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
            faces = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)
            x, y, fw, fh = faces[0]
            mx = int(fw * 0.1)
            my = int(fh * 0.1)
            x1 = max(0, x - mx)
            y1 = max(0, y - my)
            x2 = min(w, x + fw + mx)
            y2 = min(h, y + fh + my)
            crop = frame_bgr[y1:y2, x1:x2]
            if crop.size > 0:
                return cv2.resize(crop, self.target_size, interpolation=cv2.INTER_AREA)

        # Center crop square fallback if face not detected
        min_dim = min(h, w)
        sy = (h - min_dim) // 2
        sx = (w - min_dim) // 2
        crop = frame_bgr[sy : sy + min_dim, sx : sx + min_dim]
        return cv2.resize(crop, self.target_size, interpolation=cv2.INTER_AREA)


# ─── Zip Archive Ingestion (FaceForensics++ C23) ───────────────────────────────

def process_faceforensics_zip(
    zip_path: Path,
    output_dir: Path,
    max_videos_per_class: int = 50,
    sample_every_n: int = 15,
    methods: Optional[List[str]] = None,
    source_name: str = "ffpp_c23",
) -> List[Dict[str, Any]]:
    """
    Ingests FaceForensics++ zip archive directly without requiring full 18GB disk extraction.
    Streams MP4 files, extracts face frames, and saves standardized crops.
    """
    records = []
    output_images_dir = output_dir / "processed_images"
    output_images_dir.mkdir(parents=True, exist_ok=True)
    extractor = FaceExtractor()

    print(f"\n[INGESTION] Inspecting FaceForensics++ archive: {zip_path}", flush=True)
    with zipfile.ZipFile(str(zip_path), "r") as z:
        all_entries = z.namelist()
        mp4_entries = [e for e in all_entries if e.lower().endswith(".mp4")]

        # Group by category
        categories: Dict[str, List[str]] = {}
        for entry in mp4_entries:
            parts = entry.split("/")
            if len(parts) >= 2:
                cat = parts[1]
                categories.setdefault(cat, []).append(entry)

        print(f"  * Total MP4 videos in archive: {len(mp4_entries)}")
        for cat, entries in categories.items():
            print(f"    - {cat:20}: {len(entries)} videos")

        # Select target categories
        target_real_cats = ["original"]
        all_fake_cats = ["Deepfakes", "Face2Face", "FaceShifter", "FaceSwap", "NeuralTextures", "DeepFakeDetection"]
        if methods and "all" not in methods:
            target_fake_cats = [m for m in methods if m in all_fake_cats]
        else:
            target_fake_cats = all_fake_cats

        selected_tasks: List[Tuple[str, int, str]] = []  # (entry_path, label, category)

        # Sample real videos
        for cat in target_real_cats:
            items = categories.get(cat, [])
            selected = items[:max_videos_per_class] if max_videos_per_class > 0 else items
            for item in selected:
                selected_tasks.append((item, 0, cat))

        # Sample fake videos (split quota across selected fake methods)
        per_fake_quota = max(1, max_videos_per_class // len(target_fake_cats)) if max_videos_per_class > 0 else 0
        for cat in target_fake_cats:
            items = categories.get(cat, [])
            selected = items[:per_fake_quota] if per_fake_quota > 0 else items
            for item in selected:
                selected_tasks.append((item, 1, cat))

        print(f"\n[EXTRACTING] Processing {len(selected_tasks)} selected videos (every {sample_every_n} frames)...", flush=True)

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_video_path = Path(tmp_dir) / "temp_video.mp4"

            for idx, (zip_entry, label, cat) in enumerate(selected_tasks, start=1):
                try:
                    # Extract single video to temp file
                    with z.open(zip_entry) as vf, open(tmp_video_path, "wb") as tf:
                        tf.write(vf.read())

                    cap = cv2.VideoCapture(str(tmp_video_path))
                    frame_idx = 0
                    saved_from_video = 0
                    video_stem = Path(zip_entry).stem

                    while cap.isOpened():
                        ret, frame = cap.read()
                        if not ret:
                            break

                        if frame_idx % sample_every_n == 0:
                            face = extractor.extract_face(frame)
                            if face is not None:
                                out_name = f"{source_name}_{cat}_{video_stem}_f{frame_idx}.jpg"
                                out_path = output_images_dir / out_name
                                cv2.imwrite(str(out_path), face)
                                records.append({
                                    "image_path": str(out_path.resolve()),
                                    "label": label,
                                    "source": f"{source_name}_{cat}",
                                })
                                saved_from_video += 1

                        frame_idx += 1

                    cap.release()

                    if idx % 10 == 0 or idx == len(selected_tasks):
                        print(f"  [{idx:03d}/{len(selected_tasks):03d}] {cat:16} -> Extracted {saved_from_video} face crops (Total: {len(records)})", flush=True)

                except Exception as exc:
                    print(f"  [WARN] Failed to process {zip_entry}: {exc}", flush=True)

    return records


# ─── Image Folder & Directory Ingestion ───────────────────────────────────────

def process_image_folder(
    data_dir: Path,
    output_dir: Path,
    source_name: str = "image_folder",
) -> List[Dict[str, Any]]:
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


def generate_dummy_dataset(output_dir: Path, count_per_class: int = 25) -> List[Dict[str, Any]]:
    records = []
    output_images_dir = output_dir / "processed_images"
    output_images_dir.mkdir(parents=True, exist_ok=True)

    print(f"  [INFO] Generating {count_per_class * 2} synthetic dummy face images for pipeline testing...", flush=True)

    for i in range(count_per_class):
        img = np.zeros((299, 299, 3), dtype=np.uint8)
        base_color = np.array([random.randint(140, 190), random.randint(160, 210), random.randint(190, 240)], dtype=np.float32)
        for y in range(299):
            gradient = (y / 299.0) * 0.3 + 0.85
            img[y, :] = np.clip(base_color * gradient, 0, 255).astype(np.uint8)
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

    for i in range(count_per_class):
        img = np.zeros((299, 299, 3), dtype=np.uint8)
        base_color = np.array([random.randint(140, 190), random.randint(160, 210), random.randint(190, 240)], dtype=np.float32)
        for y in range(299):
            gradient = (y / 299.0) * 0.3 + 0.85
            img[y, :] = np.clip(base_color * gradient, 0, 255).astype(np.uint8)

        cv2.rectangle(img, (60, 60), (240, 240), (random.randint(100, 220), random.randint(100, 220), random.randint(100, 220)), 2)
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

    print(f"\n[OK] Unified Manifest created at: {output_manifest_path}", flush=True)
    print(f"  * Total Face Crops : {len(all_records)}")
    print(f"  * Train Split      : {len(r_train) + len(f_train)} (Real: {len(r_train)}, Fake: {len(f_train)})")
    print(f"  * Val Split        : {len(r_val) + len(f_val)} (Real: {len(r_val)}, Fake: {len(f_val)})")
    print(f"  * Test Split       : {len(r_test) + len(f_test)} (Real: {len(r_test)}, Fake: {len(f_test)})\n", flush=True)


# ─── CLI Entrypoint ──────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Ingest images/videos into unified deepfake training manifest.")
    parser.add_argument("--zip-file", type=str, help="Path to FaceForensics++ zip archive (e.g. archive.zip)")
    parser.add_argument("--image-dir", type=str, help="Path to image dataset with real/ and fake/ subfolders")
    parser.add_argument("--video-dir", type=str, help="Path to unzipped video dataset")
    parser.add_argument("--generate-dummy", action="store_true", help="Generate synthetic dummy dataset")
    parser.add_argument("--output-dir", type=str, default="data/processed_dataset", help="Output directory for crops and manifest")
    parser.add_argument("--manifest-name", type=str, default="dataset_manifest.csv", help="Name of manifest CSV")
    parser.add_argument("--sample-rate", type=int, default=20, help="Frame sampling step for videos")
    parser.add_argument("--max-videos", type=int, default=50, help="Max videos per category (0 for all)")
    parser.add_argument("--methods", type=str, default="all", help="Comma-separated fake methods e.g. Deepfakes,Face2Face or 'all'")
    parser.add_argument("--source-name", type=str, default="ffpp_c23", help="Dataset source identifier")

    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    manifest_path = output_dir / args.manifest_name

    records = []

    if args.zip_file:
        method_list = [m.strip() for m in args.methods.split(",")] if args.methods else None
        records.extend(process_faceforensics_zip(
            zip_path=Path(args.zip_file),
            output_dir=output_dir,
            max_videos_per_class=args.max_videos,
            sample_every_n=args.sample_rate,
            methods=method_list,
            source_name=args.source_name,
        ))
    elif args.generate_dummy:
        records.extend(generate_dummy_dataset(output_dir, count_per_class=25))
    elif args.image_dir:
        records.extend(process_image_folder(Path(args.image_dir), output_dir, source_name=args.source_name))
    else:
        print("[ERROR] Please provide --zip-file, --image-dir, or --generate-dummy")
        sys.exit(1)

    if not records:
        print("[ERROR] No samples were extracted.")
        sys.exit(1)

    create_stratified_manifest(records, manifest_path)


if __name__ == "__main__":
    main()
