"""
LangGraph Detection Graph
─────────────────────────
Nodes (in order):
  1. preprocess  — decode bytes → numpy frame(s), resize, normalize
  2. detect      — run detector model → raw logits / probability
  3. analyze     — extract artifacts (frequency, texture, blending seams)
  4. report      — build structured output dict

State is a TypedDict so every node receives and returns the full state.
"""

from __future__ import annotations

import asyncio
import io
from typing import TypedDict, Optional, List

import numpy as np
from PIL import Image

from langgraph.graph import StateGraph, END
from app.models.detector import DeepfakeDetector
from app.utils.logging import get_logger

log = get_logger(__name__)

# ─── Singleton detector (loaded once) ─────────────────────────────────────────
_detector: Optional[DeepfakeDetector] = None


def get_detector() -> DeepfakeDetector:
    global _detector
    if _detector is None:
        _detector = DeepfakeDetector()
    return _detector


# ─── Graph State ──────────────────────────────────────────────────────────────

class DetectionState(TypedDict):
    # Inputs
    request_id: str
    filename: str
    file_bytes: bytes
    content_type: str

    # Intermediate
    frame: Optional[np.ndarray]
    raw_score: float

    # Outputs
    is_deepfake: bool
    confidence: float
    label: str
    artifacts: List[str]
    agent_summary: Optional[str]
    error: Optional[str]


# ─── Node Functions ───────────────────────────────────────────────────────────

def node_preprocess(state: DetectionState) -> DetectionState:
    """Decode raw bytes into a numpy RGB frame."""
    try:
        img = Image.open(io.BytesIO(state["file_bytes"])).convert("RGB")
        img = img.resize((224, 224), Image.LANCZOS)
        frame = np.array(img, dtype=np.float32) / 255.0
        log.debug("preprocess.ok", request_id=state["request_id"], shape=str(frame.shape))
        return {**state, "frame": frame, "error": None}
    except Exception as exc:
        log.error("preprocess.failed", request_id=state["request_id"], error=str(exc))
        return {**state, "frame": None, "error": str(exc)}


def node_detect(state: DetectionState) -> DetectionState:
    """Run the detector model on the preprocessed frame."""
    if state.get("error") or state.get("frame") is None:
        return {**state, "raw_score": 0.5}

    detector = get_detector()
    score = detector.predict(state["frame"])
    log.debug("detect.score", request_id=state["request_id"], score=score)
    return {**state, "raw_score": score}


def node_analyze(state: DetectionState) -> DetectionState:
    """
    Lightweight heuristic artifact analysis.
    Full implementation will add:
      - DCT frequency analysis (GAN fingerprints)
      - Facial landmark consistency
      - Blending boundary detection
    """
    artifacts: List[str] = []
    score = state.get("raw_score", 0.5)

    # Placeholder heuristics (will be replaced with real analysis)
    if score > 0.7:
        artifacts.append("inconsistent_facial_texture")
        artifacts.append("frequency_domain_anomaly")
    if score > 0.85:
        artifacts.append("blending_seam_detected")
        artifacts.append("eye_blink_irregularity")

    return {**state, "artifacts": artifacts}


def node_report(state: DetectionState) -> DetectionState:
    """Build the final structured report."""
    score = state.get("raw_score", 0.5)
    threshold = 0.5

    is_deepfake = score >= threshold
    confidence = round(float(score), 4)

    if score >= 0.75:
        label = "FAKE"
    elif score <= 0.25:
        label = "REAL"
    else:
        label = "UNCERTAIN"

    summary = (
        f"Analysis complete. The media was classified as {label} "
        f"with {confidence * 100:.1f}% deepfake probability. "
        f"Detected artifacts: {', '.join(state.get('artifacts', [])) or 'none'}."
    )

    log.info(
        "report.built",
        request_id=state["request_id"],
        label=label,
        confidence=confidence,
    )
    return {
        **state,
        "is_deepfake": is_deepfake,
        "confidence": confidence,
        "label": label,
        "agent_summary": summary,
    }


# ─── Graph Assembly ───────────────────────────────────────────────────────────

def _build_graph() -> StateGraph:
    graph = StateGraph(DetectionState)

    graph.add_node("preprocess", node_preprocess)
    graph.add_node("detect", node_detect)
    graph.add_node("analyze", node_analyze)
    graph.add_node("report", node_report)

    graph.set_entry_point("preprocess")
    graph.add_edge("preprocess", "detect")
    graph.add_edge("detect", "analyze")
    graph.add_edge("analyze", "report")
    graph.add_edge("report", END)

    return graph.compile()


_graph = _build_graph()


# ─── Public API ───────────────────────────────────────────────────────────────

async def run_detection_graph(
    request_id: str,
    filename: str,
    file_bytes: bytes,
    content_type: str,
) -> dict:
    """
    Async wrapper around the synchronous LangGraph execution.
    Runs in a thread pool to avoid blocking the event loop.
    """
    initial_state: DetectionState = {
        "request_id": request_id,
        "filename": filename,
        "file_bytes": file_bytes,
        "content_type": content_type,
        "frame": None,
        "raw_score": 0.5,
        "is_deepfake": False,
        "confidence": 0.5,
        "label": "UNCERTAIN",
        "artifacts": [],
        "agent_summary": None,
        "error": None,
    }

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, _graph.invoke, initial_state)
    return result
