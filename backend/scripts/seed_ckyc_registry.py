"""
seed_ckyc_registry.py — Standalone script to inspect/re-seed 100 CKYC records
"""

import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_path))

from app.services.kyc_registry import get_kyc_registry

if __name__ == "__main__":
    registry = get_kyc_registry()
    records = registry.list_all(limit=100)
    print(f"[OK] Successfully initialized CKYC Registry with {len(records)} seeded records:")
    for r in records[:10]:
        print(f"  * {r.ckyc_number:12} | {r.legal_name:20} | DOB: {r.date_of_birth} | Phone: {r.registered_phone} | Status: {r.verification_status}")
    print(f"  ... and {len(records) - 10} more records.")
