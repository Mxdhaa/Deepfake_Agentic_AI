"""
identity.py
───────────
Stage 2: Deterministic Identity Match Service.

Provides:
  1. Vectorized Cosine Similarity between face embeddings.
  2. Registry Velocity Lookup in 6-hour window (synthetic CKYC dataset).
  3. Hierarchical Deterministic Decision Rule (mirrors generate_synthetic_batch.py):
       - FAIL:       cosine_similarity < 0.35  OR  registry_velocity >= 6
       - BORDERLINE: cosine_similarity < 0.60  OR  registry_velocity >= 3
       - PASS:       cosine_similarity >= 0.60 AND registry_velocity < 3
  4. Millisecond-latency execution (< 2ms for deterministic evaluation).
  5. Cryptographic audit trail integration (record_type: "identity").
  6. Pretrained face feature extraction with image archival and wire hashing.
"""

from __future__ import annotations

import functools
import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, TypedDict, Union

import numpy as np
import yaml

from app.services.audit import log_identity_event
from app.services.storage import compute_sha256, get_storage
from app.utils.logging import get_logger

log = get_logger(__name__)

# Base root paths on D: drive
_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent


# ─── Config Loader ────────────────────────────────────────────────────────────

@functools.lru_cache(maxsize=1)
def get_identity_config() -> dict:
    """Load identity_config.yaml."""
    env_path = os.getenv("IDENTITY_CONFIG_PATH")
    if env_path:
        cfg_path = Path(env_path)
    else:
        cfg_path = Path(__file__).resolve().parent.parent / "core" / "identity_config.yaml"

    if not cfg_path.exists():
        log.warning("identity.config_missing", path=str(cfg_path), using="defaults")
        return _default_config()

    with open(cfg_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _default_config() -> dict:
    return {
        "config_version": "default-stage2",
        "thresholds": {
            "similarity_pass": 0.60,
            "similarity_fail": 0.35,
            "velocity_borderline": 3,
            "velocity_fail": 6,
        },
        "embedding": {"dimension": 512, "backbone": "resnet50_feature_extractor"},
        "synthetic_data_path": "data/onboarding_batch.json",
    }


# ─── Synthetic CKYC Dataset Indexer ───────────────────────────────────────────

_dataset_cache: Optional[Dict[str, Any]] = None
_dataset_mtime: float = 0.0


def _load_synthetic_dataset() -> Dict[str, Any]:
    """Load and index onboarding_batch.json by kin_token and device_id."""
    global _dataset_cache, _dataset_mtime

    cfg = get_identity_config()
    rel_path = cfg.get("synthetic_data_path", "data/onboarding_batch.json")
    dataset_path = (_BACKEND_ROOT.parent / rel_path).resolve()

    if not dataset_path.exists():
        # Check backend/data fallback
        dataset_path = (_BACKEND_ROOT / rel_path).resolve()

    if not dataset_path.exists():
        log.warning("identity.dataset_not_found", path=str(dataset_path))
        return {"by_kin": {}, "by_device": {}}

    mtime = dataset_path.stat().st_mtime
    if _dataset_cache is not None and mtime == _dataset_mtime:
        return _dataset_cache

    try:
        data = json.loads(dataset_path.read_text(encoding="utf-8"))
        records = data.get("records", [])
        by_kin = {r["kin_token"]: r for r in records if "kin_token" in r}
        by_device = {}
        for r in records:
            dev = r.get("device_id")
            if dev:
                by_device.setdefault(dev, []).append(r)

        _dataset_cache = {"by_kin": by_kin, "by_device": by_device}
        _dataset_mtime = mtime
        log.info("identity.dataset_indexed", total_records=len(records))
        return _dataset_cache
    except Exception as exc:
        log.error("identity.dataset_load_error", error=str(exc))
        return {"by_kin": {}, "by_device": {}}


def lookup_ckyc_record(kin_token: str) -> Optional[dict]:
    """Retrieve synthetic CKYC record by KIN token."""
    db = _load_synthetic_dataset()
    return db["by_kin"].get(kin_token)


def lookup_registry_velocity(
    kin_token: Optional[str] = None,
    device_id: Optional[str] = None,
) -> int:
    """
    Look up 6-hour attempt velocity for a KIN or device_id in synthetic data.
    Defaults to 1 (normal single onboarding) if not found.
    """
    db = _load_synthetic_dataset()
    if kin_token and kin_token in db["by_kin"]:
        return int(db["by_kin"][kin_token].get("registry_velocity_6hr", 1))

    if device_id and device_id in db["by_device"]:
        recs = db["by_device"][device_id]
        if recs:
            return int(recs[0].get("registry_velocity_6hr", len(recs)))

    return 1


# ─── Cosine Similarity Math ───────────────────────────────────────────────────

def compute_cosine_similarity(
    emb1: Union[np.ndarray, List[float]],
    emb2: Union[np.ndarray, List[float]],
) -> float:
    """
    Compute cosine similarity between two feature vectors:
        cos(u, v) = (u . v) / (||u|| * ||v||)
    Returns float clamped in [-1.0, 1.0].

    Note on Zero/Degenerate Vectors:
      Cosine similarity is mathematically undefined for zero-norm vectors (e.g. when
      face extraction fails or an empty vector is provided). By convention, this function
      returns 0.0 (orthogonal/no-match) to avoid NaN division errors. Upstream callers
      should verify that embeddings have non-zero norms if they need to distinguish
      extraction failures from true physiological mismatches.
    """
    u = np.asarray(emb1, dtype=np.float32).flatten()
    v = np.asarray(emb2, dtype=np.float32).flatten()

    if u.size == 0 or v.size == 0:
        return 0.0

    norm_u = float(np.linalg.norm(u))
    norm_v = float(np.linalg.norm(v))

    if norm_u < 1e-12 or norm_v < 1e-12:
        log.debug("identity.zero_norm_vector_detected", norm_u=norm_u, norm_v=norm_v)
        return 0.0

    dot = float(np.dot(u, v))
    similarity = dot / (norm_u * norm_v)
    return float(np.clip(similarity, -1.0, 1.0))


# ─── Pretrained Face Feature Extractor ─────────────────────────────────────────

class FaceFeatureExtractor:
    """
    Extracts normalized 512-d face feature embeddings using PyTorch / OpenCV.
    No model trained from scratch.
    """

    def __init__(self) -> None:
        self._model = None
        self._initialized = False

    def _init_model(self) -> None:
        if self._initialized:
            return
        try:
            import torchvision.models as models
            import torch
            import torch.nn as nn

            # Use pretrained backbone as feature extractor (evaluation mode)
            base = models.resnet18(weights=models.ResNet18_Weights.DEFAULT)
            base.fc = nn.Identity()  # 512-d feature vector
            base.eval()
            self._model = base
            log.info("identity.feature_extractor_loaded", backbone="resnet18_512d")
        except Exception as exc:
            log.warning("identity.feature_extractor_fallback", error=str(exc))
            self._model = None
        self._initialized = True

    def extract_from_bytes(self, image_bytes: bytes) -> np.ndarray:
        """Extract a unit-normalized 512-d embedding from image bytes."""
        self._init_model()
        if len(image_bytes) == 0:
            return np.zeros(512, dtype=np.float32)

        import cv2

        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            log.warning("identity.image_decode_failed")
            return np.zeros(512, dtype=np.float32)

        return self.extract_from_bgr(img)

    def extract_from_bgr(self, bgr_img: np.ndarray) -> np.ndarray:
        """Extract a unit-normalized 512-d embedding from BGR image array."""
        self._init_model()
        import cv2

        if self._model is not None:
            try:
                import torch
                rgb = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2RGB)
                resized = cv2.resize(rgb, (224, 224), interpolation=cv2.INTER_LINEAR)
                # Standard ImageNet normalization
                tensor = torch.from_numpy(resized).permute(2, 0, 1).float() / 255.0
                mean = torch.tensor([0.485, 0.456, 0.406]).view(3, 1, 1)
                std = torch.tensor([0.229, 0.224, 0.225]).view(3, 1, 1)
                tensor = (tensor - mean) / std
                tensor = tensor.unsqueeze(0)

                with torch.no_grad():
                    feat = self._model(tensor).squeeze(0).cpu().numpy()
                norm = np.linalg.norm(feat)
                return feat / (norm + 1e-12)
            except Exception as exc:
                log.error("identity.pytorch_extract_error", error=str(exc))

        # Fast deterministic fallback: histogram projection normalized to 512-d
        gray = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2GRAY)
        resized = cv2.resize(gray, (32, 16)).flatten().astype(np.float32)
        norm = np.linalg.norm(resized)
        return resized / (norm + 1e-12)


_extractor = FaceFeatureExtractor()


# ─── Decision TypedDicts ──────────────────────────────────────────────────────

class IdentityMatchResult(TypedDict):
    session_id: str
    cosine_similarity: float
    registry_velocity: int
    decision: str               # "pass" | "borderline" | "fail"
    face_match: bool
    velocity_flagged: bool
    decision_latency_ms: float  # Pure vector math + rule latency (< 2ms)
    embedding_extraction_ms: float
    total_processing_ms: float
    config_version: str
    kin_token: Optional[str]
    device_id: Optional[str]
    live_sha256: Optional[str]
    ckyc_sha256: Optional[str]


# ─── Decision Evaluators ──────────────────────────────────────────────────────

def evaluate_identity_embeddings(
    live_embedding: Union[np.ndarray, List[float]],
    ckyc_embedding: Union[np.ndarray, List[float]],
    kin_token: Optional[str] = None,
    device_id: Optional[str] = None,
    session_id: Optional[str] = None,
    ip: str = "unknown",
    live_sha256: Optional[str] = None,
    ckyc_sha256: Optional[str] = None,
    embedding_extraction_ms: float = 0.0,
) -> IdentityMatchResult:
    """
    Deterministic identity evaluation on precomputed feature embeddings.
    Runs strictly in single-digit milliseconds (< 2ms) with zero LLM invocations.
    """
    t0 = time.perf_counter()
    sid = session_id or str(uuid.uuid4())
    cfg = get_identity_config()
    T = cfg["thresholds"]

    # 1. Cosine similarity
    cos_sim = round(compute_cosine_similarity(live_embedding, ckyc_embedding), 4)

    # 2. Registry velocity
    velocity = lookup_registry_velocity(kin_token=kin_token, device_id=device_id)

    # 3. Threshold checks
    sim_pass_thresh = float(T["similarity_pass"])      # 0.60
    sim_fail_thresh = float(T["similarity_fail"])      # 0.35
    vel_border_thresh = int(T["velocity_borderline"])  # 3
    vel_fail_thresh = int(T["velocity_fail"])          # 6

    # 4. Hierarchical Decision Rule (mirrors _derive_decision)
    if cos_sim < sim_fail_thresh or velocity >= vel_fail_thresh:
        decision = "fail"
    elif cos_sim < sim_pass_thresh or velocity >= vel_border_thresh:
        decision = "borderline"
    else:
        decision = "pass"

    face_match = cos_sim >= sim_pass_thresh
    velocity_flagged = velocity >= vel_border_thresh

    decision_latency_ms = round((time.perf_counter() - t0) * 1000, 3)
    total_ms = round(decision_latency_ms + embedding_extraction_ms, 3)

    # 5. Seal into unified cryptographic hash chain (record_type: "identity")
    log_identity_event(
        session_id=sid,
        cosine_similarity=cos_sim,
        registry_velocity=velocity,
        decision=decision,
        decision_latency_ms=decision_latency_ms,
        kin_token=kin_token,
        device_id=device_id,
        live_sha256=live_sha256,
        ckyc_sha256=ckyc_sha256,
        ip=ip,
    )

    log.info(
        "identity.evaluated",
        session_id=sid,
        similarity=cos_sim,
        velocity=velocity,
        decision=decision,
        decision_latency_ms=decision_latency_ms,
    )

    return IdentityMatchResult(
        session_id=sid,
        cosine_similarity=cos_sim,
        registry_velocity=velocity,
        decision=decision,
        face_match=face_match,
        velocity_flagged=velocity_flagged,
        decision_latency_ms=decision_latency_ms,
        embedding_extraction_ms=round(embedding_extraction_ms, 3),
        total_processing_ms=total_ms,
        config_version=cfg.get("config_version", "unknown"),
        kin_token=kin_token,
        device_id=device_id,
        live_sha256=live_sha256,
        ckyc_sha256=ckyc_sha256,
    )


def evaluate_identity_images(
    live_image_bytes: bytes,
    ckyc_image_bytes: bytes,
    kin_token: Optional[str] = None,
    device_id: Optional[str] = None,
    session_id: Optional[str] = None,
    ip: str = "unknown",
) -> IdentityMatchResult:
    """
    End-to-end identity match from raw image bytes:
      1. Immediate SHA-256 computation on raw wire bytes.
      2. Storage archival before processing.
      3. Embedding extraction (~15-30ms).
      4. Deterministic decision evaluation (< 2ms).
    """
    sid = session_id or str(uuid.uuid4())
    t_extract_start = time.perf_counter()

    # Step 1: Wire hash computation immediately on received bytes
    live_sha256 = compute_sha256(live_image_bytes)
    ckyc_sha256 = compute_sha256(ckyc_image_bytes)

    # Step 2: Storage archival
    storage = get_storage()
    try:
        storage.write(
            f"{sid}_live",
            live_image_bytes,
            metadata={"sha256": live_sha256, "type": "live_capture", "session_id": sid},
        )
        storage.write(
            f"{sid}_ckyc",
            ckyc_image_bytes,
            metadata={"sha256": ckyc_sha256, "type": "ckyc_reference", "session_id": sid},
        )
    except Exception as exc:
        log.warning("identity.image_archival_failed", error=str(exc))

    # Step 3: Pretrained embedding extraction
    live_emb = _extractor.extract_from_bytes(live_image_bytes)
    ckyc_emb = _extractor.extract_from_bytes(ckyc_image_bytes)
    extraction_ms = round((time.perf_counter() - t_extract_start) * 1000, 3)

    # Step 4: Deterministic evaluation
    return evaluate_identity_embeddings(
        live_embedding=live_emb,
        ckyc_embedding=ckyc_emb,
        kin_token=kin_token,
        device_id=device_id,
        session_id=sid,
        ip=ip,
        live_sha256=live_sha256,
        ckyc_sha256=ckyc_sha256,
        embedding_extraction_ms=extraction_ms,
    )
