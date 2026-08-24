"""
kyc_registry.py — CKYC Registry Storage & Management Service
─────────────────────────────────────────────────────────────
Maintains ~100 seeded CKYC identity records in JSON storage with
auto-seeding on initial boot.
"""

from __future__ import annotations

import json
import os
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from app.models.verification import CkycRecord, VerificationStatus
from app.utils.logging import get_logger

log = get_logger(__name__)

_REGISTRY_FILE = Path(os.getenv("STORAGE_LOCAL_ROOT", "data/storage")) / "ckyc_registry.json"

_INDIAN_FIRST_NAMES = [
    "Aarav", "Priya", "Vikram", "Ananya", "Rohan", "Sneha", "Kavya", "Rahul",
    "Aditya", "Neha", "Ishaan", "Rhea", "Arjun", "Pooja", "Varun", "Tanvi",
    "Siddharth", "Meera", "Karan", "Divya", "Dev", "Isha", "Manish", "Shreya",
    "Sanjay", "Deepika", "Amit", "Simran", "Rajesh", "Anjali", "Gaurav", "Nisha"
]

_INDIAN_LAST_NAMES = [
    "Sharma", "Patel", "Malhotra", "Verma", "Reddy", "Nair", "Kapoor", "Iyer",
    "Mukherjee", "Singh", "Chopra", "Gupta", "Bose", "Joshi", "Deshmukh", "Menon",
    "Rao", "Mehta", "Bhat", "Saxena", "Agarwal", "Chatterjee", "Kulkarni", "Trivedi"
]


class KycRegistryService:
    def __init__(self, storage_path: Path = _REGISTRY_FILE) -> None:
        self._path = storage_path
        self._records: Dict[str, CkycRecord] = {}
        self._initialize()

    def _initialize(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists() or self._path.stat().st_size == 0:
            self._seed_default_records()
        else:
            self._load_records()

    def _seed_default_records(self) -> None:
        """Seed 100 realistic Indian CKYC records."""
        records: Dict[str, CkycRecord] = {}
        now_iso = datetime.now(timezone.utc).isoformat()

        # Deterministic primary test records
        primary_records = [
            ("CKYC-10001", "Aarav Sharma", "1994-05-14", "+91 9876543210", "NOT_STARTED"),
            ("CKYC-10002", "Priya Patel", "1997-08-22", "+91 9812345678", "NOT_STARTED"),
            ("CKYC-10003", "Vikram Malhotra", "1991-11-03", "+91 9765432109", "VERIFIED"),
            ("CKYC-10004", "Ananya Verma", "1999-02-18", "+91 9654321098", "UNDER_REVIEW"),
            ("CKYC-10005", "Rohan Reddy", "1993-09-30", "+91 9543210987", "NOT_STARTED"),
            ("CKYC-10006", "Sneha Nair", "1996-12-05", "+91 9432109876", "VERIFIED"),
            ("CKYC-78901234", "Kavya Iyer", "1995-07-19", "+91 9321098765", "NOT_STARTED"),
        ]

        for ckyc, name, dob, phone, status in primary_records:
            face_ref = None
            if status == "VERIFIED":
                face_ref = {
                    "face_reference": f"ref-face-{ckyc.lower()}",
                    "verified_at": now_iso,
                    "embedding_dimension": 512,
                }
            records[ckyc] = CkycRecord(
                ckyc_number=ckyc,
                legal_name=name,
                date_of_birth=dob,
                registered_phone=phone,
                registered_face_reference=face_ref,
                verification_status=status,
                created_at=now_iso,
                updated_at=now_iso,
            )

        # Generate remaining up to 100 records
        rnd = random.Random(42)  # Deterministic seed for reproducible registry
        for i in range(10007, 10101):
            ckyc = f"CKYC-{i}"
            name = f"{rnd.choice(_INDIAN_FIRST_NAMES)} {rnd.choice(_INDIAN_LAST_NAMES)}"
            year = rnd.randint(1975, 2004)
            month = f"{rnd.randint(1, 12):02d}"
            day = f"{rnd.randint(1, 28):02d}"
            dob = f"{year}-{month}-{day}"
            phone = f"+91 {rnd.randint(9000000000, 9999999999)}"
            
            # ~20% VERIFIED, ~10% UNDER_REVIEW, ~70% NOT_STARTED
            roll = rnd.random()
            if roll < 0.20:
                status = "VERIFIED"
                face_ref = {"face_reference": f"ref-face-{ckyc.lower()}", "verified_at": now_iso, "embedding_dimension": 512}
            elif roll < 0.30:
                status = "UNDER_REVIEW"
                face_ref = None
            else:
                status = "NOT_STARTED"
                face_ref = None

            records[ckyc] = CkycRecord(
                ckyc_number=ckyc,
                legal_name=name,
                date_of_birth=dob,
                registered_phone=phone,
                registered_face_reference=face_ref,
                verification_status=status,
                created_at=now_iso,
                updated_at=now_iso,
            )

        self._records = records
        self._save_records()
        log.info("kyc_registry.seeded", total_records=len(records))

    def _load_records(self) -> None:
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._records = {k: CkycRecord(**v) for k, v in data.items()}
            log.info("kyc_registry.loaded", total_records=len(self._records))
        except Exception as exc:
            log.error("kyc_registry.load_failed", error=str(exc))
            self._seed_default_records()

    def _save_records(self) -> None:
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump({k: v.model_dump() for k, v in self._records.items()}, f, indent=2)

    def lookup(self, ckyc_number: str) -> Optional[CkycRecord]:
        clean_ckyc = ckyc_number.strip().upper()
        return self._records.get(clean_ckyc)

    def match_identity(self, legal_name: str, date_of_birth: str, ckyc_number: str) -> Optional[CkycRecord]:
        """
        Validate legal_name, date_of_birth, and ckyc_number against registry.
        Case-insensitive and whitespace-tolerant.
        """
        record = self.lookup(ckyc_number)
        if not record:
            return None

        clean_req_name = " ".join(legal_name.strip().lower().split())
        clean_rec_name = " ".join(record.legal_name.strip().lower().split())
        clean_req_dob = date_of_birth.strip()
        clean_rec_dob = record.date_of_birth.strip()

        if clean_req_name == clean_rec_name and clean_req_dob == clean_rec_dob:
            return record
        return None

    def update_verification_status(
        self,
        ckyc_number: str,
        status: VerificationStatus,
        face_reference: Optional[Dict[str, Any]] = None,
    ) -> Optional[CkycRecord]:
        clean_ckyc = ckyc_number.strip().upper()
        record = self._records.get(clean_ckyc)
        if not record:
            return None

        record.verification_status = status
        record.updated_at = datetime.now(timezone.utc).isoformat()
        if face_reference is not None:
            record.registered_face_reference = face_reference

        self._records[clean_ckyc] = record
        self._save_records()
        log.info("kyc_registry.status_updated", ckyc=clean_ckyc, status=status)
        return record

    def list_all(self, limit: int = 100) -> List[CkycRecord]:
        return list(self._records.values())[:limit]


_registry_instance: Optional[KycRegistryService] = None


def get_kyc_registry() -> KycRegistryService:
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = KycRegistryService()
    return _registry_instance
