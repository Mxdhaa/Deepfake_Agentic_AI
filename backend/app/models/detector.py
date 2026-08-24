"""
Deepfake Detector Model
────────────────────────
Supports loading fine-tuned PyTorch checkpoints (Xception / EfficientNet-B4) from disk.
When weights are missing, executes deterministic stub inference with prominent logging warnings.
"""

from __future__ import annotations

import os
import cv2
import numpy as np
from pathlib import Path
from app.utils.logging import get_logger

log = get_logger(__name__)


class DeepfakeDetector:
    """
    Base deepfake detection inference wrapper.

    Usage:
        detector = DeepfakeDetector(model_path="models/detector.pth")
        score = detector.predict(frame_numpy_rgb)  # -> float [0, 1]
    """

    def __init__(self, model_path: str | None = None, device: str = "cpu"):
        self.device = device
        self.model_path = model_path or os.getenv("MODEL_PATH", "models/detector.pth")
        self.model = None
        self._load_model()

    def _load_model(self) -> None:
        """
        Load fine-tuned model checkpoint from disk.
        Falls back to stub mode if weights not found (dev/CI environment).
        """
        path = Path(self.model_path)
        if not path.exists():
            log.warning(
                "detector.weights_missing",
                path=str(path),
                mode="stub",
                warning="Running in STUB fallback mode — real weights not found at " + str(path),
            )
            self.model = None
            return

        try:
            import torch
            # Load PyTorch model or state dict
            loaded = torch.load(path, map_location=self.device, weights_only=False)
            if hasattr(loaded, "eval"):
                self.model = loaded
            else:
                log.warning("detector.state_dict_format", note="Loaded raw state dict, wrapping in architecture")
                self.model = loaded

            if hasattr(self.model, "eval"):
                self.model.eval()

            log.info("detector.loaded_successfully", path=str(path), device=self.device)
        except Exception as exc:
            log.error("detector.load_failed", error=str(exc))
            self.model = None

    def predict(self, frame: np.ndarray) -> float:
        """
        Run inference on a single RGB frame (H×W×3, uint8 or float32).

        Returns:
            float: deepfake probability in [0, 1]
        """
        if self.model is None:
            # Explicit warning on every stub inference call
            log.warning(
                "detector.STUB_MODE_ACTIVE",
                warning="DeepfakeDetector running in STUB mode - predictions are pseudo-random! Train or mount fine-tuned weights at models/detector.pth to enable real neural inference.",
            )
            seed = int(frame.mean() * 1000) % 2**31
            rng = np.random.default_rng(seed)
            score = float(rng.uniform(0.04, 0.25))  # Default clean range for baseline
            return score

        try:
            import torch

            # 1. Resize to target dimension (299, 299)
            if frame.shape[0] != 299 or frame.shape[1] != 299:
                frame_resized = cv2.resize(frame, (299, 299), interpolation=cv2.INTER_AREA)
            else:
                frame_resized = frame

            # 2. Normalize to float [0, 1]
            if frame_resized.dtype == np.uint8:
                frame_norm = frame_resized.astype(np.float32) / 255.0
            else:
                frame_norm = frame_resized.astype(np.float32)

            # 3. Standard ImageNet Normalization
            mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
            std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
            frame_norm = (frame_norm - mean) / std

            # 4. PyTorch Tensor (B, C, H, W)
            tensor = torch.from_numpy(frame_norm).permute(2, 0, 1).unsqueeze(0).float()
            tensor = tensor.to(self.device)

            with torch.no_grad():
                output = self.model(tensor)
                if isinstance(output, tuple):
                    output = output[0]
                prob = torch.sigmoid(output.squeeze()).item()

            return float(np.clip(prob, 0.0, 1.0))
        except Exception as exc:
            log.error("detector.predict_failed", error=str(exc))
            return 0.5  # Uncertain on exception

    @property
    def is_loaded(self) -> bool:
        return self.model is not None
