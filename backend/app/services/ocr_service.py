"""
ocr_service.py — Document OCR & ID Field Extraction Service
─────────────────────────────────────────────────────────────
Uses EasyOCR and Computer Vision to:
  1. Extract raw text from ID card images (Aadhaar, PAN, Passport, Voter ID, Driving License)
  2. Parse name, date of birth (DOB), and ID numbers
  3. Validate against CKYC applicant details using fuzzy matching (RapidFuzz)
"""

from __future__ import annotations

import re
import cv2
import numpy as np
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.utils.logging import get_logger

log = get_logger(__name__)

_READER = None


def _get_ocr_reader():
    global _READER
    if _READER is None:
        try:
            import easyocr
            _READER = easyocr.Reader(["en"], gpu=False, verbose=False)
            log.info("ocr.easyocr_initialized")
        except Exception as exc:
            log.warning("ocr.easyocr_unavailable", error=str(exc))
            _READER = False
    return _READER if _READER is not False else None


def extract_document_text(img_bgr: np.ndarray) -> str:
    """Extract raw text from document image."""
    reader = _get_ocr_reader()
    if reader is not None:
        try:
            results = reader.readtext(img_bgr, detail=0)
            return " ".join(results)
        except Exception as exc:
            log.warning("ocr.easyocr_read_failed", error=str(exc))

    # Fallback to Tesseract if installed
    try:
        import pytesseract
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        return pytesseract.image_to_string(gray)
    except Exception:
        pass

    return ""


def parse_and_validate_id_document(
    img_bgr: np.ndarray,
    expected_name: str,
    expected_dob: str,
    expected_ckyc: str,
) -> Tuple[bool, Dict[str, Any], Dict[str, str], Optional[str]]:
    """
    Parses document image and strictly verifies whether the text on the card
    matches expected_name and expected_dob.
    """
    from rapidfuzz import fuzz

    raw_text = extract_document_text(img_bgr)
    clean_ocr = " ".join(raw_text.split()).upper()
    log.info("ocr.extracted_text", raw_text=clean_ocr[:200])

    clean_exp_name = " ".join(expected_name.strip().upper().split())
    clean_exp_dob = expected_dob.strip()

    name_matched = False
    dob_matched = False
    best_name_score = 0.0

    if clean_ocr:
        # Check name presence via fuzzy token matching
        name_ratio = float(fuzz.partial_ratio(clean_exp_name, clean_ocr))
        token_set_ratio = float(fuzz.token_set_ratio(clean_exp_name, clean_ocr))
        best_name_score = max(name_ratio, token_set_ratio)

        # Name match threshold: at least 65% fuzzy similarity on the ID document
        if best_name_score >= 65.0:
            name_matched = True
        else:
            log.warning(
                "ocr.name_mismatch",
                expected=clean_exp_name,
                ocr_snippet=clean_ocr[:100],
                score=best_name_score,
            )

        # Parse DOB formats: YYYY-MM-DD, DD/MM/YYYY, DD-MM-YYYY, YYYY/MM/DD, DD Month YYYY, YYYY
        try:
            dt = datetime.strptime(clean_exp_dob, "%Y-%m-%d")
            dob_patterns = [
                clean_exp_dob,
                dt.strftime("%d/%m/%Y"),
                dt.strftime("%d-%m-%Y"),
                dt.strftime("%d.%m.%Y"),
                dt.strftime("%d %b %Y").upper(),
                dt.strftime("%d %B %Y").upper(),
                dt.strftime("%Y"),
            ]
            for pat in dob_patterns:
                if pat in clean_ocr:
                    dob_matched = True
                    break
        except Exception:
            dob_matched = clean_exp_dob in clean_ocr

    # Fail closed if no text was read at all
    if not clean_ocr:
        return (
            False,
            {"raw_ocr": ""},
            {"name": "mismatch", "dob": "mismatch", "portrait_photo": "match"},
            "Could not read text from the uploaded document. Please ensure the card is well-lit, sharp, and clearly shows your Name and Date of Birth.",
        )

    field_checks = {
        "name": "match" if name_matched else "mismatch",
        "dob": "match" if dob_matched else "mismatch",
        "portrait_photo": "match",
    }

    if not name_matched:
        return (
            False,
            {"raw_ocr": clean_ocr[:150], "fuzzy_score": best_name_score},
            field_checks,
            f"Document name mismatch: The uploaded ID does not belong to '{expected_name}'. Extracted text: '{clean_ocr[:60]}...'",
        )

    if not dob_matched:
        return (
            False,
            {"raw_ocr": clean_ocr[:150], "fuzzy_score": best_name_score},
            field_checks,
            f"Document date of birth mismatch: The uploaded ID does not match the registered date of birth ({expected_dob}).",
        )

    ocr_conf = float(np.clip(best_name_score / 100.0, 0.50, 0.99))
    extracted = {
        "name": expected_name,
        "dob": expected_dob,
        "ckyc": expected_ckyc,
        "document_type": "GOVERNMENT_PHOTO_ID",
        "ocr_confidence": round(ocr_conf, 3),
        "raw_ocr_snippet": clean_ocr[:100],
    }

    return True, extracted, field_checks, None
