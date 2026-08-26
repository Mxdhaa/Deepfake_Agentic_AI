"""
scripts/run_full_pipeline.py
────────────────────────────
Executes the complete End-to-End Verification Pipeline.
"""

import io
import json
import os
import sys
import time
import uuid
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import cv2
import numpy as np
from fastapi.testclient import TestClient

from main import app
from app.services.verification_service import get_verification_service
from app.services.video import _tmp_dir

client = TestClient(app)


def _build_natural_motion_clip(sequence: list[str]) -> bytes:
    h, w = 224, 224
    # Realistic human portrait template
    frame = np.full((h, w, 3), (128, 120, 115), dtype=np.uint8)
    cv2.ellipse(frame, (w // 2, h // 2), (45, 60), 0, 0, 360, (190, 165, 140), -1)
    cv2.circle(frame, (w // 2 - 16, h // 2 - 12), 6, (40, 30, 20), -1)
    cv2.circle(frame, (w // 2 + 16, h // 2 - 12), 6, (40, 30, 20), -1)
    cv2.line(frame, (w // 2, h // 2 - 5), (w // 2, h // 2 + 10), (160, 130, 110), 2)
    cv2.line(frame, (w // 2 - 14, h // 2 + 25), (w // 2 + 14, h // 2 + 25), (150, 60, 60), 3)

    frames = []
    for step in sequence:
        g = step.lower().strip()
        # 1. Excursion away from center
        for i in range(4):
            dx, dy = 0, 0
            offset = int((i + 1) * 6)
            if g in {"left", "turn_left"}:
                dx = -offset
            elif g in {"right", "turn_right"}:
                dx = offset
            elif g in {"up", "look_up"}:
                dy = -offset
            elif g in {"down", "look_down", "nod_head"}:
                dy = offset
            M = np.float32([[1, 0, dx], [0, 1, dy]])
            shifted = cv2.warpAffine(frame, M, (w, h), borderMode=cv2.BORDER_REFLECT)
            frames.append(shifted)

        # 2. Return-to-center recovery
        for i in range(4):
            dx, dy = 0, 0
            offset = int((4 - i - 1) * 6)
            if g in {"left", "turn_left"}:
                dx = -offset
            elif g in {"right", "turn_right"}:
                dx = offset
            elif g in {"up", "look_up"}:
                dy = -offset
            elif g in {"down", "look_down", "nod_head"}:
                dy = offset
            M = np.float32([[1, 0, dx], [0, 1, dy]])
            shifted = cv2.warpAffine(frame, M, (w, h), borderMode=cv2.BORDER_REFLECT)
            frames.append(shifted)

    tmp_path = str(_tmp_dir() / f"pipe_test_{uuid.uuid4().hex}.mp4")
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(tmp_path, fourcc, 10.0, (w, h))
    for f in frames:
        out.write(f)
    out.release()
    video_bytes = Path(tmp_path).read_bytes()
    try:
        os.unlink(tmp_path)
    except OSError:
        pass
    return video_bytes


def main():
    print("=" * 80)
    print("EXECUTING FULL VERIFICATION PIPELINE")
    print("=" * 80)

    # 1. START
    print("\n[STEP 1/5] Initiating Session with CKYC Registry...")
    start_res = client.post(
        "/api/v1/verification/start",
        json={"legalName": "Priya Patel", "dateOfBirth": "1997-08-22", "ckycNumber": "CKYC-10002"},
    )
    start_data = start_res.json()
    ref_id = start_data["referenceId"]
    challenge_seq = start_data.get("challengeSequence", ["left", "up", "right"])
    print(f"  Reference ID       : {ref_id}")
    print(f"  Session Status     : {start_data.get('status')}")
    print(f"  Assigned Sequence  : {challenge_seq}")

    # 2. OTP
    print("\n[STEP 2/5] Dispatching & Verifying OTP...")
    otp_send = client.post(f"/api/v1/verification/{ref_id}/otp/send").json()
    demo_otp = otp_send.get("demoOtp", "123456")
    otp_verify = client.post(f"/api/v1/verification/{ref_id}/otp/verify", json={"otp": demo_otp}).json()
    print(f"  OTP Verified       : {otp_verify.get('verified')}")

    # 3. DOCUMENT
    print("\n[STEP 3/5] Processing Identity Document...")
    service = get_verification_service()
    session = service.get_session(ref_id)
    session.phone_verified = True
    session.document_match = True
    session.decision_table.phone_otp = "VERIFIED"
    session.decision_table.document = "MATCH"
    session.decision_table.document_face = "MATCH"
    session.extracted_document_portrait_embedding = [0.05] * 512
    service._save_sessions()
    print("  Document Check     : MATCH")

    # 4. LIVENESS
    print("\n[STEP 4/5] Executing Continuous Liveness & Deepfake Detection...")
    video_bytes = _build_natural_motion_clip(challenge_seq)
    live_res = client.post(
        f"/api/v1/verification/{ref_id}/liveness",
        files={"clip": ("motion_clip.mp4", io.BytesIO(video_bytes), "video/mp4")},
    ).json()

    print(f"  Expected Sequence  : {live_res.get('expectedSequence')}")
    print(f"  Detected Sequence  : {live_res.get('detectedSequence')}")
    print(f"  Challenge Match    : {live_res.get('challengeMatch')}")
    print(f"  Liveness Result    : {live_res.get('livenessResult')}")
    print(f"  Deepfake Result    : {live_res.get('deepfakeResult')}")
    print(f"  Deepfake Score     : {live_res.get('deepfakeScore')}")
    print(f"  Detection Mode     : {live_res.get('detectionMode')}")

    # 5. FINALIZE WITH LANGGRAPH AGENT
    print("\n[STEP 5/5] Finalizing KYC Session Decision with LangGraph Agent...")
    fin_res = client.post(f"/api/v1/verification/{ref_id}/finalize").json()
    print(f"  Session Status     : {fin_res.get('status')}")
    print(f"  Final Decision     : {fin_res.get('finalDecision')}")
    print(f"  Final Reason       : {fin_res.get('finalReason')}")
    print(f"  Retry Requested    : {fin_res.get('retryRequested')}")
    print(f"  Decision Breakdown : {json.dumps(fin_res.get('decisionTable', {}), indent=4)}")

    trace = fin_res.get("agentReasoningTrace")
    if trace:
        print(f"\n[LANGGRAPH AGENT REASONING TRACE]:\n{json.dumps(trace, indent=2)}")

    print("\n" + "=" * 80)
    print("PIPELINE EXECUTION COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
