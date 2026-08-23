#!/usr/bin/env python3
"""
generate_synthetic_batch.py
────────────────────────────────────────────────────────────────────────────────
Generates synthetic onboarding records for the Deepfake Agentic AI demo pipeline.

Each record represents one WebRTC-based KYC onboarding session with the following
signals that feed into the fusion decision classifier:

    kin_token              — UUID v4 session token
    legal_name             — realistic name (Faker)
    webrtc_jitter_ms       — network jitter in milliseconds
    cosine_similarity_score— embedding similarity to claimed identity [0, 1]
    registry_velocity_6hr  — new-account attempts from same device/IP in 6hr window
    device_id              — SHA256 fingerprint of device metadata
    challenge_match        — bool: did liveness challenge pass?
    deepfake_score         — frame-level score from pretrained detector [0, 1]
    blink_rate_bpm         — detected blink rate in blinks/min
    av_sync_ms             — audio-video sync offset in milliseconds
    decision               — derived label: pass | borderline | fail

Decision rule (mirrors the fusion classifier's target):
    FAIL       if deepfake_score ≥ 0.75 OR registry_velocity_6hr ≥ 6 OR
                  cosine_similarity_score < 0.35 OR NOT challenge_match
    BORDERLINE if deepfake_score ∈ [0.40, 0.75) OR registry_velocity_6hr ∈ [3, 6) OR
                  cosine_similarity_score ∈ [0.35, 0.60) OR abs(av_sync_ms) > 80
    PASS       otherwise

Usage:
    python scripts/generate_synthetic_batch.py
    python scripts/generate_synthetic_batch.py --n 80 --output data/onboarding_batch.json --seed 42
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sys
import uuid
from pathlib import Path

# Force UTF-8 stdout/stderr on Windows (avoids cp1252 UnicodeEncodeError)
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
if sys.stderr.encoding and sys.stderr.encoding.lower() not in ("utf-8", "utf8"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]


# ─── Optional dependency: Faker ───────────────────────────────────────────────
try:
    from faker import Faker
    _faker = Faker()
    _faker.seed_instance(0)
    def _gen_name() -> str:
        return _faker.name()
except ImportError:
    # Minimal fallback — no extra install required
    _FIRST = ["James", "Maria", "Liam", "Priya", "Chen", "Amara", "Noah", "Sofia",
               "Ethan", "Yuki", "Omar", "Elena", "Lucas", "Fatima", "Samuel"]
    _LAST  = ["Smith", "García", "Kim", "Patel", "Wang", "Johnson", "Müller",
               "Ahmed", "Brown", "Silva", "Nguyen", "Taylor", "Ali", "Lee", "Davis"]
    def _gen_name() -> str:
        return f"{random.choice(_FIRST)} {random.choice(_LAST)}"


# ─── Distribution helpers ──────────────────────────────────────────────────────

def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _normal(mu: float, sigma: float, lo: float = -math.inf, hi: float = math.inf) -> float:
    """Gaussian sample clamped to [lo, hi]."""
    return _clamp(random.gauss(mu, sigma), lo, hi)


def _device_id() -> str:
    raw = f"{random.getrandbits(128):032x}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ─── Per-case generators ───────────────────────────────────────────────────────

def _pass_record() -> dict:
    """Genuine user — all signals nominal."""
    deepfake_score         = _normal(0.08, 0.07, 0.0, 0.39)
    cosine_similarity_score= _normal(0.89, 0.05, 0.60, 0.99)
    registry_velocity_6hr  = random.choices([1, 2, 3], weights=[60, 30, 10])[0]
    challenge_match        = True
    blink_rate_bpm         = _normal(15.5, 2.5, 8.0, 28.0)
    # av_sync_ms: real sessions have codec/buffering variance; ±70ms outer bound
    # keeps pass clearly below the 81ms borderline threshold with realistic overlap
    av_sync_ms             = _normal(0.0, 18.0, -70.0, 70.0)
    webrtc_jitter_ms       = _normal(18.0, 8.0, 2.0, 55.0)
    return dict(
        deepfake_score=deepfake_score,
        cosine_similarity_score=cosine_similarity_score,
        registry_velocity_6hr=registry_velocity_6hr,
        challenge_match=challenge_match,
        blink_rate_bpm=blink_rate_bpm,
        av_sync_ms=av_sync_ms,
        webrtc_jitter_ms=webrtc_jitter_ms,
        decision="pass",
    )


def _borderline_record() -> dict:
    """Marginal case — one or two signals near threshold."""
    # Pick which axis is borderline
    axis = random.choice(["deepfake", "cosine", "velocity", "av_sync", "blink"])

    deepfake_score         = _normal(0.08, 0.07, 0.0, 0.39)
    cosine_similarity_score= _normal(0.89, 0.05, 0.60, 0.99)
    registry_velocity_6hr  = random.choices([1, 2, 3], weights=[60, 30, 10])[0]
    challenge_match        = True
    blink_rate_bpm         = _normal(15.5, 2.5, 8.0, 28.0)
    # Pass baseline: keep av_sync in ±70ms so borderline axis is clearly distinct
    av_sync_ms             = _normal(0.0, 18.0, -70.0, 70.0)
    webrtc_jitter_ms       = _normal(18.0, 8.0, 2.0, 55.0)

    if axis == "deepfake":
        deepfake_score = _normal(0.57, 0.08, 0.40, 0.74)
    elif axis == "cosine":
        cosine_similarity_score = _normal(0.47, 0.06, 0.35, 0.59)
    elif axis == "velocity":
        registry_velocity_6hr = random.randint(3, 5)
    elif axis == "av_sync":
        # Borderline: 81–100ms — clearly above pass threshold but below hard fail cap
        av_sync_ms = random.choice([-1, 1]) * _normal(88.0, 8.0, 81.0, 100.0)
    elif axis == "blink":
        blink_rate_bpm = _normal(5.0, 1.5, 2.0, 7.9)
        deepfake_score = _normal(0.48, 0.08, 0.38, 0.70)

    return dict(
        deepfake_score=deepfake_score,
        cosine_similarity_score=cosine_similarity_score,
        registry_velocity_6hr=registry_velocity_6hr,
        challenge_match=challenge_match,
        blink_rate_bpm=blink_rate_bpm,
        av_sync_ms=av_sync_ms,
        webrtc_jitter_ms=webrtc_jitter_ms,
        decision="borderline",
    )


def _fail_record() -> dict:
    """Synthetic or fraudulent session — at least one hard signal breached."""
    fail_mode = random.choice(["high_deepfake", "velocity_burst", "low_cosine",
                                "challenge_fail", "multi_signal", "high_av_sync"])

    deepfake_score         = _normal(0.08, 0.07, 0.0, 0.39)
    cosine_similarity_score= _normal(0.89, 0.05, 0.60, 0.99)
    registry_velocity_6hr  = random.choices([1, 2, 3], weights=[60, 30, 10])[0]
    challenge_match        = True
    blink_rate_bpm         = _normal(15.5, 2.5, 8.0, 28.0)
    av_sync_ms             = _normal(0.0, 18.0, -60.0, 60.0)
    webrtc_jitter_ms       = _normal(18.0, 8.0, 2.0, 55.0)

    if fail_mode == "high_deepfake":
        deepfake_score  = _normal(0.88, 0.07, 0.75, 0.99)
        blink_rate_bpm  = _normal(4.0, 1.5, 0.5, 7.9)
        # av_sync: stream-injection attacks drift 80–120ms (pre-recorded video,
        # live mic — attacker can't sync them). Capped at 120ms to prevent
        # av_sync from trivially dominating the fusion classifier.
        av_sync_ms      = random.choice([-1, 1]) * _normal(95.0, 12.0, 80.0, 120.0)
    elif fail_mode == "velocity_burst":
        registry_velocity_6hr = random.randint(6, 14)
        deepfake_score  = _normal(0.55, 0.12, 0.30, 0.90)
    elif fail_mode == "low_cosine":
        cosine_similarity_score = _normal(0.22, 0.07, 0.05, 0.34)
        deepfake_score  = _normal(0.65, 0.15, 0.40, 0.99)
    elif fail_mode == "challenge_fail":
        challenge_match = False
        deepfake_score  = _normal(0.70, 0.12, 0.50, 0.99)
    elif fail_mode == "multi_signal":
        deepfake_score         = _normal(0.82, 0.07, 0.75, 0.99)
        cosine_similarity_score= _normal(0.28, 0.08, 0.05, 0.34)
        registry_velocity_6hr  = random.randint(5, 10)
        challenge_match        = False
        blink_rate_bpm         = _normal(3.0, 1.0, 0.5, 5.0)
    elif fail_mode == "high_av_sync":
        # Extreme AV desync: pre-recorded stream injected with buffering delay.
        # All other signals are normal — this tests the av_sync fail tier alone.
        # Range (150, 220ms] puts records firmly above the 150ms fail threshold.
        av_sync_ms = random.choice([-1, 1]) * _normal(175.0, 20.0, 151.0, 220.0)

    return dict(
        deepfake_score=deepfake_score,
        cosine_similarity_score=cosine_similarity_score,
        registry_velocity_6hr=registry_velocity_6hr,
        challenge_match=challenge_match,
        blink_rate_bpm=blink_rate_bpm,
        av_sync_ms=av_sync_ms,
        webrtc_jitter_ms=webrtc_jitter_ms,
        decision="fail",
    )


# ─── Decision re-derivation (ground-truth label) ──────────────────────────────

def _derive_decision(r: dict) -> str:
    """
    Derive a deterministic 3-class label from signal values.

    Evaluation order matters: fail is checked first; borderline is only reached
    if ALL fail conditions are false; pass is the residual.
    Bands are mutually exclusive half-open intervals with no gaps:

    Feature              PASS                BORDERLINE            FAIL
    ──────────────────────────────────────────────────────────────────────
    deepfake_score       [0.00, 0.40)        [0.40, 0.75)          [0.75, 1.00]
    cosine_similarity    (0.60, 1.00]        (0.35, 0.60]          [0.00, 0.35]
    registry_velocity    [1, 3)              [3, 6)                [6, inf)
    abs(av_sync_ms)      [0, 80]             (80, 150]             (150, inf)
    blink_rate_bpm       [8.0, inf)          [0, 8.0)              — (no blink fail)
    challenge_match      True                True                  False

    Any single FAIL column value -> fail (OR logic).
    No FAIL triggered -> any single BORDERLINE column value -> borderline (OR logic).
    No FAIL, no BORDERLINE -> pass.
    """
    # Hard fails (any one sufficient)
    if (
        r["deepfake_score"] >= 0.75
        or r["registry_velocity_6hr"] >= 6
        or r["cosine_similarity_score"] < 0.35
        or not r["challenge_match"]
        or abs(r["av_sync_ms"]) > 150
    ):
        return "fail"
    # Borderline (any one sufficient, only reached when all fail conditions are False)
    if (
        r["deepfake_score"] >= 0.40
        or r["registry_velocity_6hr"] >= 3
        or r["cosine_similarity_score"] < 0.60
        or abs(r["av_sync_ms"]) > 80
        or r["blink_rate_bpm"] < 8.0
    ):
        return "borderline"
    return "pass"


# ─── Main record builder ───────────────────────────────────────────────────────

def build_record(decision_target: str) -> dict:
    generator = {"pass": _pass_record, "borderline": _borderline_record, "fail": _fail_record}
    signals = generator[decision_target]()
    # Re-derive label from actual values (prevents label/signal mismatches)
    signals["decision"] = _derive_decision(signals)

    return {
        "kin_token":               str(uuid.uuid4()),
        "legal_name":              _gen_name(),
        "device_id":               _device_id(),
        "webrtc_jitter_ms":        round(signals["webrtc_jitter_ms"], 2),
        "cosine_similarity_score": round(signals["cosine_similarity_score"], 4),
        "registry_velocity_6hr":   signals["registry_velocity_6hr"],
        "challenge_match":         signals["challenge_match"],
        "deepfake_score":          round(signals["deepfake_score"], 4),
        "blink_rate_bpm":          round(signals["blink_rate_bpm"], 2),
        "av_sync_ms":              round(signals["av_sync_ms"], 2),
        "decision":                signals["decision"],
    }


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--n",      type=int,  default=60, help="Total records to generate (default: 60)")
    parser.add_argument("--output", type=Path, default=Path("data/onboarding_batch.json"))
    parser.add_argument("--seed",   type=int,  default=42)
    parser.add_argument("--pass-frac",       type=float, default=0.50, help="Fraction of PASS cases")
    parser.add_argument("--borderline-frac", type=float, default=0.22, help="Fraction of BORDERLINE cases")
    args = parser.parse_args()

    random.seed(args.seed)

    n_pass       = max(1, round(args.n * args.pass_frac))
    n_borderline = max(1, round(args.n * args.borderline_frac))
    n_fail       = max(1, args.n - n_pass - n_borderline)

    print(f"Generating {args.n} records: {n_pass} pass / {n_borderline} borderline / {n_fail} fail")

    targets = ["pass"] * n_pass + ["borderline"] * n_borderline + ["fail"] * n_fail
    random.shuffle(targets)

    records = []
    label_counts: dict[str, int] = {"pass": 0, "borderline": 0, "fail": 0}

    for t in targets:
        r = build_record(t)
        records.append(r)
        label_counts[r["decision"]] += 1

    # ── Summary stats ──────────────────────────────────────────────────────────
    actual_pass       = label_counts["pass"]
    actual_borderline = label_counts["borderline"]
    actual_fail       = label_counts["fail"]

    # ── Write output ──────────────────────────────────────────────────────────
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(
            {
                "meta": {
                    "total": len(records),
                    "pass": actual_pass,
                    "borderline": actual_borderline,
                    "fail": actual_fail,
                    "seed": args.seed,
                    "note": (
                        "Synthetic onboarding demo data. "
                        "Decision labels are derived deterministically from signal values "
                        "using the same thresholds as the fusion classifier."
                    ),
                },
                "records": records,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

    print(f"\n[OK] Wrote {len(records)} records -> {args.output}")
    print(f"  Actual distribution: pass={actual_pass}, borderline={actual_borderline}, fail={actual_fail}")

    # ── Sanity checks ─────────────────────────────────────────────────────────
    warnings: list[str] = []
    if actual_borderline + actual_fail < 8:
        warnings.append(f"Only {actual_borderline + actual_fail} non-pass cases — increase --n or adjust fractions")
    if actual_fail < 3:
        warnings.append("Very few fail cases — Stage 3/4 demo may be weak")

    for w in warnings:
        print(f"  [WARN] {w}", file=sys.stderr)


if __name__ == "__main__":
    main()
