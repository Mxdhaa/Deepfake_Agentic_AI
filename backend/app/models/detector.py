"""
Deepfake Detector Model
────────────────────────
Architecture stub — Phase 1 will wire in:
  - EfficientNet-B4 (pretrained ImageNet → fine-tuned FaceForensics++)
  - ViT-B/16 (vision transformer alternative)
  - Ensemble voting

The `predict()` method returns a float in [0, 1]:
  0.0 = definitely REAL
  1.0 = definitely FAKE
"""

from __future__ import annotations

import os
import numpy as np
from pathlib import Path
from app.utils.logging import get_logger

log = get_logger(__name__)


class DeepfakeDetector:
    """
    Base detector class.

    Usage:
        detector = DeepfakeDetector(model_path="models/detector.pth")
        score = detector.predict(frame_numpy_rgb)  # → float [0, 1]
    """

    def __init__(self, model_path: str | None = None, device: str = "cpu"):
        self.device = device
        self.model_path = model_path or os.getenv("MODEL_PATH", "models/detector.pth")
        self.model = None
        self._load_model()

    def _load_model(self) -> None:
        """
        Load model weights from disk.
        Falls back to stub mode if weights not found (dev/CI environment).
        """
        path = Path(self.model_path)
        if not path.exists():
            log.warning(
                "detector.weights_missing",
                path=str(path),
                mode="stub",
                note="Running in stub mode — predictions are random. "
                     "Download weights via scripts/download_datasets.sh",
            )
            self.model = None
            return

        try:
            import torch
            self.model = torch.load(path, map_location=self.device)
            self.model.eval()
            log.info("detector.loaded", path=str(path), device=self.device)
        except Exception as exc:
            log.error("detector.load_failed", error=str(exc))
            self.model = None

    def predict(self, frame: np.ndarray) -> float:
        """
        Run inference on a preprocessed RGB frame (H×W×3, float32, [0,1]).

        Returns:
            float: deepfake probability in [0, 1]
        """
        if self.model is None:
            # Stub: return a deterministic-looking random score for dev/testing
            seed = int(frame.mean() * 1000) % 2**31
            rng = np.random.default_rng(seed)
            score = float(rng.uniform(0.0, 1.0))
            log.debug("detector.stub_predict", score=round(score, 4))
            return score

        try:
            import torch
            tensor = torch.from_numpy(frame).permute(2, 0, 1).unsqueeze(0)
            tensor = tensor.to(self.device)
            with torch.no_grad():
                output = self.model(tensor)
                prob = torch.sigmoid(output).item()
            return float(prob)
        except Exception as exc:
            log.error("detector.predict_failed", error=str(exc))
            return 0.5   # uncertain on error

    @property
    def is_loaded(self) -> bool:
        return self.model is not None
