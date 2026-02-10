# src/ocr_engines/header_fallback.py
"""
Header Fallback Logic - Uses OCRS (Engine 2) when DeepSeek header fields are null.
Also attempts to recover invoiceDate from signature if missing.
"""

from typing import List, Optional
import re
from datetime import date
from src.ocr_engines.ocrs_engine import OcrsEngine
from src.schemas.invoice import Invoice
from src.utils.date_utils import parse_vn_date


# Critical header fields that trigger fallback if ANY is missing (OR logic)
HEADER_FIELDS = [
    "invoiceName",
    "invoiceID",
    "invoiceDate",
    "invoiceSerial", 
    "invoiceFormNo",
]

# Trigger fallback if strict count of null fields >= this value
MIN_NULL_FIELDS_TO_TRIGGER = 1


def get_null_header_fields(invoice: Invoice) -> List[str]:
    """Get list of header fields that are null or empty."""
    null_fields = []
    for field in HEADER_FIELDS:
        value = getattr(invoice, field, None)
        if value is None or value == "":
            null_fields.append(field)
    return null_fields


def recover_date_from_signature(raw_text: str) -> date | None:
    """
    Attempt to find date from signature section (usually at the end).
    Matches: 'Ngày ... tháng ... năm ...'
    """
    if not raw_text:
        return None
        
    # Find all matches of Vietnamese full date format
    # Case insensitive, handles spaces
    matches = list(re.finditer(
        r"Ngày\s*(\d{1,2})\s*tháng\s*(\d{1,2})\s*năm\s*(\d{4})", 
        raw_text, 
        re.IGNORECASE
    ))
    
    if not matches:
        return None
        
    # Heuristic: Signature date is usually the LAST date in the document
    last_match = matches[-1]
    
    try:
        d, m, y = map(int, last_match.groups())
        return date(y, m, d)
    except ValueError:
        return None


def needs_header_fallback(invoice: Invoice) -> bool:
    """
    Check if header fallback should be triggered.
    Returns True if at least MIN_NULL_FIELDS_TO_TRIGGER (1) header field is null.
    """
    null_count = len(get_null_header_fields(invoice))
    return null_count >= MIN_NULL_FIELDS_TO_TRIGGER


def parse_header_from_ocrs_text(raw_text: str, invoice: Invoice) -> Invoice:
    """
    Parse header fields from OCRS raw text and fill null fields in invoice.
    Uses existing parser logic.
    """
    from src.parsers.block_invoice_parser import parse_global_fields
    
    # parse_global_fields modifies invoice in-place
    parse_global_fields(raw_text, invoice)
    
    return invoice


def apply_header_fallback(
    image_path: str,
    invoice: Invoice,
    raw_text: str = "", # Added raw_text from Engine 1
    ocrs_path: str = "d:\\AI_project\\OCR_CPU\\ocrs-main\\target\\release\\ocrs.exe",
    detect_model_path: Optional[str] = None,
    rec_model_path: Optional[str] = None,
) -> Invoice:
    """
    Apply fallback strategies to fill missing header fields.
    
    Strategy 1: Recover missing invoiceDate from signature in raw_text.
    Strategy 2: If critical fields still missing, run OCRS (Engine 2).
    """
    
    # --- Strategy 1: Recover Date from Signature ---
    if invoice.invoiceDate is None and raw_text:
        recovered_date = recover_date_from_signature(raw_text)
        if recovered_date:
            print(f"[Fallback] Recovered invoiceDate from signature: {recovered_date}")
            invoice.invoiceDate = recovered_date

    # --- Strategy 2: OCRS Engine ---
    # Check if fallback is still needed after Strategy 1
    if not needs_header_fallback(invoice):
        return invoice
    
    null_fields = get_null_header_fields(invoice)
    print(f"[OCRS Fallback] Triggered - Missing critical fields: {null_fields}")
    
    try:
        # Initialize OCRS engine
        # TODO: Consider setting default model paths from config if they are fixed
        ocrs = OcrsEngine(
            ocrs_path=ocrs_path,
            detect_model_path=detect_model_path,
            rec_model_path=rec_model_path,
        )
        
        # Check if OCRS is available
        if not ocrs.is_available():
            print("[OCRS Fallback] OCRS CLI not available, skipping fallback")
            return invoice
        
        # Run OCRS on image
        ocrs_text = ocrs.get_raw_text(image_path)
        
        if not ocrs_text.strip():
            print("[OCRS Fallback] OCRS returned empty text, skipping")
            return invoice
            
        print(f"[OCRS Fallback] Got {len(ocrs_text)} chars from OCRS")
        
        # Parse header fields from OCRS text
        invoice = parse_header_from_ocrs_text(ocrs_text, invoice)
        
        # Log results
        still_null = get_null_header_fields(invoice)
        filled = set(null_fields) - set(still_null)
        if filled:
            print(f"[OCRS Fallback] Successfully filled: {list(filled)}")
        else:
            print("[OCRS Fallback] No new fields filled.")
        
    except Exception as e:
        print(f"[OCRS Fallback] Error: {e}")
    
    return invoice
