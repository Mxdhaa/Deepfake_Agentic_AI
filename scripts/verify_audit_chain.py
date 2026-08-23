#!/usr/bin/env python3
"""
verify_audit_chain.py
─────────────────────
CLI verification tool for the unified Phase 2 / Phase 5 cryptographic audit chain.

Walks the single append-only hash chain, validates previous hash linkage across
interleaved record types (upload, decision, identity, investigation, human_review, access),
and recomputes canonical SHA-256 digests for each block to prove zero tampering.

Usage:
    python scripts/verify_audit_chain.py
    python scripts/verify_audit_chain.py --path /path/to/audit_chain.jsonl
    python scripts/verify_audit_chain.py --tamper 2   # Safe live tamper demo on disposable copy
"""

import argparse
import json
import shutil
import sys
import uuid
from collections import Counter
from pathlib import Path

# Add backend to sys.path if needed
ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.audit import get_audit_chain_path, verify_chain


def run_verification(chain_path: Path) -> int:
    """Run cryptographic verification against chain_path and print formatted report."""
    if not chain_path.exists():
        print(f"[-] Chain file not found at {chain_path}")
        return 1

    raw_lines = [line.strip() for line in chain_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    total_entries = len(raw_lines)

    is_valid, msg, verified_count = verify_chain(chain_path)

    verified_type_counts = Counter()
    for i in range(verified_count):
        try:
            entry = json.loads(raw_lines[i])
            verified_type_counts[entry.get("record_type", "unknown")] += 1
        except Exception:
            pass

    known_types = ["upload", "decision", "identity", "investigation", "human_review", "access"]

    print("-" * 70)
    if is_valid:
        print(f"Total Blocks Verified : {verified_count} / {total_entries}")
        print(f"  - Upload Events        : {verified_type_counts.get('upload', 0)}")
        print(f"  - Decision Events      : {verified_type_counts.get('decision', 0)}")
        print(f"  - Identity Events      : {verified_type_counts.get('identity', 0)}")
        print(f"  - Investigation Events : {verified_type_counts.get('investigation', 0)}")
        print(f"  - Human Review Events  : {verified_type_counts.get('human_review', 0)}")
        print(f"  - Access Events        : {verified_type_counts.get('access', 0)}")
        for other_type, cnt in verified_type_counts.items():
            if other_type not in known_types:
                print(f"  - {other_type.capitalize() + ' Events':<22} : {cnt}")
        print("-" * 70)
        print(f"[+] VERIFICATION SUCCESS: {msg}")
        print("[+] All blocks are cryptographically sealed, sequential, and unbroken.")
        print("=" * 70)
        return 0
    else:
        print(f"Total Blocks in File     : {total_entries}")
        print(f"Blocks Verified Prior    : {verified_count}")
        print(f"Verified Breakdown       :")
        print(f"  - Upload Events        : {verified_type_counts.get('upload', 0)}")
        print(f"  - Decision Events      : {verified_type_counts.get('decision', 0)}")
        print(f"  - Identity Events      : {verified_type_counts.get('identity', 0)}")
        print(f"  - Investigation Events : {verified_type_counts.get('investigation', 0)}")
        print(f"  - Human Review Events  : {verified_type_counts.get('human_review', 0)}")
        print(f"  - Access Events        : {verified_type_counts.get('access', 0)}")
        for other_type, cnt in verified_type_counts.items():
            if other_type not in known_types:
                print(f"  - {other_type.capitalize() + ' Events':<22} : {cnt}")
        print("-" * 70)
        print(f"[!] VERIFICATION FAILURE: {msg}")
        print("[!] The audit chain has been compromised or modified!")
        print("=" * 70)
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify cryptographic integrity of the unified audit hash chain."
    )
    parser.add_argument(
        "--path",
        type=str,
        default=None,
        help="Path to audit_chain.jsonl file (default: from storage config)",
    )
    parser.add_argument(
        "--tamper",
        type=int,
        default=None,
        help="Simulate a safe tamper demo on target block index (operates on a disposable scratch copy)",
    )
    args = parser.parse_args()

    chain_path = Path(args.path) if args.path else get_audit_chain_path()
    print("=" * 70)
    print(" Deepfake Agentic AI — Audit Hash Chain Verification Tool")
    print("=" * 70)

    # ── Safe Non-Destructive Tamper Simulation ─────────────────────────────────
    if args.tamper is not None:
        tamper_idx = args.tamper
        if not chain_path.exists():
            print(f"[-] Source chain not found at {chain_path}")
            return 1

        lines = [line.strip() for line in chain_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if tamper_idx < 0 or tamper_idx >= len(lines):
            print(f"[-] Invalid tamper index {tamper_idx}. Chain has {len(lines)} blocks (0 to {len(lines)-1}).")
            return 1

        print(f"[SIMULATION DEMO] Creating disposable scratch copy to demonstrate tamper detection on block {tamper_idx}...")
        temp_demo_path = chain_path.parent / f"audit_chain_tamper_demo_{uuid.uuid4().hex[:8]}.jsonl"

        try:
            # Modify target block in the disposable copy
            tampered_entry = json.loads(lines[tamper_idx])
            if "payload" in tampered_entry and isinstance(tampered_entry["payload"], dict):
                tampered_entry["payload"]["TAMPERED_INJECTION"] = "adversarial_payload_override"
            else:
                tampered_entry["session_id"] = "tampered_session_override"

            lines[tamper_idx] = json.dumps(tampered_entry)
            temp_demo_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

            print(f"[SIMULATION DEMO] Running verification on tampered copy ({temp_demo_path.name})...")
            print(f"[NOTE] Working production chain remains 100% pristine at {chain_path}")
            exit_code = run_verification(temp_demo_path)
            return exit_code
        finally:
            if temp_demo_path.exists():
                temp_demo_path.unlink()
                print(f"[SIMULATION DEMO] Disposable copy cleaned up successfully.")

    # ── Standard Clean Verification ───────────────────────────────────────────
    print(f"Target chain path: {chain_path}")
    return run_verification(chain_path)


if __name__ == "__main__":
    sys.exit(main())
