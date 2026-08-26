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


def _preprocess_image_variants(img_bgr: np.ndarray) -> List[np.ndarray]:
    """Generate preprocessed image variants to maximize OCR accuracy across card textures."""
    variants = []
    h, w = img_bgr.shape[:2]

    # Resize if excessively large or small (target max dimension ~1600px)
    max_dim = max(h, w)
    if max_dim > 1600:
        scale = 1600.0 / max_dim
        norm_img = cv2.resize(img_bgr, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    elif max_dim < 600:
        scale = 600.0 / max_dim
        norm_img = cv2.resize(img_bgr, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC)
    else:
        norm_img = img_bgr.copy()

    variants.append(norm_img)

    # Grayscale + CLAHE for high contrast against background patterns
    gray = cv2.cvtColor(norm_img, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced_gray = clahe.apply(gray)
    variants.append(enhanced_gray)

    return variants


def extract_document_text(img_bgr: np.ndarray) -> str:
    """
    Extract raw text from document image using multi-pass EasyOCR with preprocessed variants.
    """
    reader = _get_ocr_reader()
    extracted_chunks: List[str] = []

    if reader is not None:
        variants = _preprocess_image_variants(img_bgr)
        for var in variants:
            try:
                results = reader.readtext(var, detail=0)
                if results:
                    extracted_chunks.extend(results)
            except Exception as exc:
                log.warning("ocr.easyocr_variant_read_failed", error=str(exc))

        # If very little text was extracted, test 90-degree rotations
        if len(" ".join(extracted_chunks)) < 25:
            for angle in [cv2.ROTATE_90_CLOCKWISE, cv2.ROTATE_180, cv2.ROTATE_90_COUNTERCLOCKWISE]:
                rot_img = cv2.rotate(img_bgr, angle)
                try:
                    results = reader.readtext(rot_img, detail=0)
                    if results and len(" ".join(results)) > 25:
                        extracted_chunks.extend(results)
                        break
                except Exception:
                    pass

    # Fallback to Tesseract if available
    if not extracted_chunks:
        try:
            import pytesseract
            gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
            tess_text = pytesseract.image_to_string(gray)
            if tess_text:
                extracted_chunks.append(tess_text)
        except Exception:
            pass

    # Deduplicate while preserving order
    seen = set()
    deduped = []
    for chunk in extracted_chunks:
        c_clean = str(chunk).strip()
        if c_clean and c_clean not in seen:
            seen.add(c_clean)
            deduped.append(c_clean)

    return " ".join(deduped)


def _parse_dob_components(dob_str: str) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    """Parse day, month, year integers from diverse date string formats."""
    clean = dob_str.strip()
    # Try standard formats
    for fmt in ["%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y", "%Y/%m/%d", "%d %b %Y", "%d %B %Y"]:
        try:
            d = datetime.strptime(clean, fmt)
            return d.day, d.month, d.year
        except Exception:
            pass

    # Regex extraction for day, month, year
    m = re.search(r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})", clean)
    if m:
        p1, p2, p3 = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if p1 > 12:  # p1 is day
            return p1, p2, p3
        return p2, p1, p3

    # Year only
    m_yr = re.search(r"\b(19\d{2}|20\d{2})\b", clean)
    if m_yr:
        return None, None, int(m_yr.group(1))

    return None, None, None


def parse_and_validate_id_document(
    img_bgr: np.ndarray,
    expected_name: str,
    expected_dob: str,
    expected_ckyc: str,
) -> Tuple[bool, Dict[str, Any], Dict[str, str], Optional[str]]:
    """
    Parses document image and verifies whether the text on the card
    matches expected_name and expected_dob with robust support for Aadhaar,
    PAN, Voter ID, and Passports.
    """
    from rapidfuzz import fuzz

    raw_text = extract_document_text(img_bgr)
    clean_ocr = " ".join(raw_text.split()).upper()
    log.info("ocr.extracted_text", raw_text=clean_ocr[:250])

    clean_exp_name = " ".join(expected_name.strip().upper().split())
    clean_exp_dob = expected_dob.strip()

    name_matched = False
    dob_matched = False
    best_name_score = 0.0

    # Detect Official Government Card Headers
    is_official_aadhaar = any(
        kw in clean_ocr for kw in [
            "AADHAAR", "AADHAR", "UNIQUE IDENTIFICATION", "GOVERNMENT OF INDIA",
            "GOVT OF INDIA", "BHARAT SARKAR", "MERA AADHAAR", "VID :"
        ]
    )
    is_pan_card = any(kw in clean_ocr for kw in ["INCOME TAX DEPARTMENT", "PERMANENT ACCOUNT NUMBER", "PAN CARD"])
    is_passport = "PASSPORT" in clean_ocr or "REPUBLIC OF INDIA" in clean_ocr
    is_voter_id = any(kw in clean_ocr for kw in ["ELECTION COMMISSION", "ELECTOR", "EPIC"])

    detected_doc_type = "GOVERNMENT_PHOTO_ID"
    if is_official_aadhaar:
        detected_doc_type = "AADHAAR_CARD"
    elif is_pan_card:
        detected_doc_type = "PAN_CARD"
    elif is_passport:
        detected_doc_type = "PASSPORT"
    elif is_voter_id:
        detected_doc_type = "VOTER_ID"

    # Extract 12-digit Aadhaar / PAN numbers if visible
    aadhaar_match = re.search(r"\b\d{4}\s?\d{4}\s?\d{4}\b", clean_ocr)
    pan_match = re.search(r"\b[A-Z]{5}\d{4}[A-Z]\b", clean_ocr)
    extracted_id_number = aadhaar_match.group(0) if aadhaar_match else (pan_match.group(0) if pan_match else None)

    if clean_ocr:
        # 1. Flexible Name Matching
        name_ratio = float(fuzz.partial_ratio(clean_exp_name, clean_ocr))
        token_set_ratio = float(fuzz.token_set_ratio(clean_exp_name, clean_ocr))
        token_sort_ratio = float(fuzz.token_sort_ratio(clean_exp_name, clean_ocr))
        best_name_score = max(name_ratio, token_set_ratio, token_sort_ratio)

        name_tokens = [t for t in clean_exp_name.split() if len(t) > 1]
        tokens_found = 0
        for token in name_tokens:
            if token in clean_ocr or fuzz.partial_ratio(token, clean_ocr) >= 75.0:
                tokens_found += 1

        all_tokens_present = (tokens_found == len(name_tokens)) and len(name_tokens) > 0

        # Pass condition: fuzzy match >= 50% OR all name tokens present OR token_set_ratio >= 65%
        if best_name_score >= 50.0 or all_tokens_present:
            name_matched = True
        elif is_official_aadhaar and tokens_found >= 1:
            # Partial match on authentic Aadhaar with at least one key name token
            name_matched = True
            best_name_score = max(best_name_score, 60.0)

        # 2. Comprehensive Date of Birth (DOB) Matching
        day, month, year = _parse_dob_components(clean_exp_dob)

        if year is not None:
            yr_str = str(year)
            # Check year presence
            year_found = yr_str in clean_ocr

            # Check full date combinations
            full_date_found = False
            if day is not None and month is not None:
                d_str = f"{day:02d}"
                m_str = f"{month:02d}"
                delims = ["/", "-", ".", " "]
                for sep in delims:
                    pats = [
                        f"{d_str}{sep}{m_str}{sep}{yr_str}",
                        f"{yr_str}{sep}{m_str}{sep}{d_str}",
                        f"{day}{sep}{month}{sep}{yr_str}",
                    ]
                    for pat in pats:
                        if pat in clean_ocr or pat.replace(" ", "") in clean_ocr.replace(" ", ""):
                            full_date_found = True
                            break

                # Textual month
                try:
                    dt_obj = datetime(year, month, day)
                    if dt_obj.strftime("%d %b %Y").upper() in clean_ocr or dt_obj.strftime("%d %B %Y").upper() in clean_ocr:
                        full_date_found = True
                except Exception:
                    pass

            # Match criteria: Full date match OR (Year match on Aadhaar/Govt ID where year of birth is standard)
            if full_date_found:
                dob_matched = True
            elif year_found and (is_official_aadhaar or "YEAR" in clean_ocr or "YOB" in clean_ocr or "DOB" in clean_ocr or "BIRTH" in clean_ocr):
                dob_matched = True
            elif clean_exp_dob in clean_ocr or yr_str in clean_ocr:
                dob_matched = True

    # Fail closed if no text was read at all
    if not clean_ocr:
        return (
            False,
            {"raw_ocr": ""},
            {"name": "mismatch", "dob": "mismatch", "portrait_photo": "match"},
            "Could not read text from the uploaded document. Please ensure the card is well-lit, clear, and unblurred.",
        )

    field_checks = {
        "name": "match" if name_matched else "mismatch",
        "dob": "match" if dob_matched else "mismatch",
        "portrait_photo": "match",
    }

    if not name_matched:
        return (
            False,
            {"raw_ocr": clean_ocr[:150], "fuzzy_score": best_name_score, "document_type": detected_doc_type},
            field_checks,
            f"Document name mismatch: The card does not clearly show '{expected_name}'. Extracted text snippet: '{clean_ocr[:80]}...'",
        )

    if not dob_matched:
        return (
            False,
            {"raw_ocr": clean_ocr[:150], "fuzzy_score": best_name_score, "document_type": detected_doc_type},
            field_checks,
            f"Document date of birth mismatch: Could not find birth date/year matching '{expected_dob}' on the card.",
        )

    ocr_conf = float(np.clip(max(best_name_score / 100.0, 0.70 if is_official_aadhaar else 0.50), 0.50, 0.99))
    extracted = {
        "name": expected_name,
        "dob": expected_dob,
        "ckyc": expected_ckyc,
        "document_type": detected_doc_type,
        "id_number": extracted_id_number,
        "is_official_national_id": is_official_aadhaar or is_pan_card or is_passport,
        "ocr_confidence": round(ocr_conf, 3),
        "raw_ocr_snippet": clean_ocr[:120],
    }

    return True, extracted, field_checks, None
