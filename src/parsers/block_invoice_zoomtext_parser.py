
import re
from typing import List, Tuple
from src.schemas.invoice import Invoice

# Reuse the helper if allowed, otherwise we can copy it.
# Assuming we can import it since it's in the same package usually, 
# but to be safe and independent as requested, I might rewrite or import it.
# Let's import it to avoid duplication if possible.
try:
    from src.parsers.block_invoice_parser import parse_serial_form_no
except ImportError:
    # Fallback implementation if import fails (circular or path issue)
    def parse_serial_form_no(text: str) -> Tuple[str, str]:
        # Simple local version just in case
        return text.strip(), None

def parse_zoom_header(lines: List[str], invoice: Invoice) -> None:
    """
    Parse header fields specifically for the 'Zoom-in' text.
    Uses aggressive regexes and strict exclusions tailored for 
    high-DPI, focused crop inputs which might be chaotic or contain 
    reference values (e.g. 'Adjustment for...').
    """
    
    # 1. First pass: Check known patterns line by line
    serial_parsed = False
    
    for line in lines:
        clean = line.strip()
        low = clean.lower()
        
        # EXCLUSION: Skip lines referring to adjustment/replacement of OTHER invoices.
        # This is critical for preventing False Positives (e.g. ID 896).
        if "điều chỉnh" in low or "thay thế" in low or "liên quan" in low:
            continue
        
        # --- Invoice Name (Title) ---
        # Extract from ZOOM TEXT. Force overwrite because Zoom header is authoritative.
        invoice_type_keywords = ["HÓA ĐƠN", "VAT INVOICE", "PHIẾU XUẤT KHO", "PHIẾU NHẬP KHO", "PHIẾU BÁN HÀNG"]
        up = clean.upper()
        # Fix: "Bản thể hiện..." contains "HÓA ĐƠN" but isn't the title. Exclude it.
        if any(kw in up for kw in invoice_type_keywords) and "THỂ HIỆN" not in up and "BẢN SAO" not in up:
            # Clean markdown markers
            name = clean.lstrip("# ").strip().strip("*")
            # Exclude lines that are likely part of a sentence (unless it's remarkably short)
            # e.g. "Cần kiểm tra đối chiếu khi lập, giao, nhận hóa đơn" -> contains "hóa đơn" but long
            if name and len(name) > 5 and len(name) < 50:
                 # Update if we haven't found a strong title in Zoom yet (or strictly prefer shorter/cleaner ones?)
                 # For now, just overwrite.
                 invoice.invoiceName = name

        
        # --- Invoice ID Parsing ---
        # ALWAYS scan for ID in zoom text because it's higher quality.
        # If found, it supersedes previous findings (often garbage from full scan).
        # Standard Pattern: "Số ...: 123"
        # We relax strict startswith because zoom text might have noise at start.
        # Add print for debugging specific line
        print(f"DEBUG ZOOM LINE: '{line}'") 
        
        contains_keyword = ("số" in low or "no" in low or "so" in low) and ":" in low
        # Exclude common false positives: Account, Money, Tax, Phone, AND ADDRESS (House No)
        is_clean = "tài khoản" not in low and "tiền" not in low and "thuế" not in low and "điện thoại" not in low and \
                   "địa chỉ" not in low and "address" not in low
        print(f"   -> KW: {contains_keyword}, Clean: {is_clean}")
        
        if contains_keyword and is_clean:
            # Broadened regex: So|Số|No, optional dot, optional colon/space
            # Handle markdown formatting: **00000438** or *00000438*
            # FIX: Changed \d{3,} to \d+ to allow single-digit IDs like "3"
            m = re.search(r"(?:Số|So|No).*?[:\s]\s*\*{0,2}(\d+)\*{0,2}", line, re.I)
            if m: 
                invoice.invoiceID = m.group(1)
        elif "invoice no" in low:
            # English pattern - also handle markdown formatting
            m = re.search(r"Invoice No\.?\s*[:\.]?\s*\*{0,2}(\d+)\*{0,2}", line, re.I)
            if m: invoice.invoiceID = m.group(1)

        # --- Invoice Serial Parsing (Labeled) ---
        # Pattern: "Ký hiệu (Serial No): 1C25TTD"
        if not invoice.invoiceSerial and not serial_parsed:
             if "ký hiệu" in low or "kí hiệu" in low or "serial" in low:
                m = re.search(r"(?:ký hiệu|kí hiệu|serial)[^:\d]*[:\s]+([A-Z0-9/\-]+)", line, re.I)
                if m:
                    val = m.group(1).strip()
                    if len(val) >= 3:
                        s, f = parse_serial_form_no(val)
                        invoice.invoiceSerial = s
                        if f and not invoice.invoiceFormNo: invoice.invoiceFormNo = f
                        serial_parsed = True

        # --- Invoice Form No Parsing ---
        if not invoice.invoiceFormNo:
             if "mẫu số" in low or "form no" in low:
                m = re.search(r"(?:Mẫu số|Form No).*?([0-9]+[A-Z0-9/]*)", line, re.I)
                if m: invoice.invoiceFormNo = m.group(1)
        
        # --- Invoice Date ---
        # Force overwrite date from Zoom text as it's cleaner
        # Regex for "Ngày 23 tháng 9 năm 2025" or "Ngày 23/09/2025"
        # Flexible date pattern
        m_date = re.search(r"Ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})", line, re.I)
        if m_date:
            # Format as DD/MM/YYYY string with zfill
            invoice.invoiceDate = f"{m_date.group(1).zfill(2)}/{m_date.group(2).zfill(2)}/{m_date.group(3)}"
        else:
            # Try simple date match DD/MM/YYYY if preceeded by "Ngày" or standalone
            # Use strict lookbehind for 'Ngày' or just simple search if line is short
            m2 = re.search(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", line)
            if m2 and ("ngày" in low or "date" in low):
                 invoice.invoiceDate = f"{m2.group(1).zfill(2)}/{m2.group(2).zfill(2)}/{m2.group(3)}"

        # --- Invoice Serial / Symbol (Force Overwrite) ---
        # Look for "Ký hiệu: 1C25MDT" or "Series: 1C25MDT"
        # Force overwrite because Zoom header is authoritative.
        if "ký hiệu" in low or "series" in low:
            m_sym = re.search(r"(?:ký hiệu|series)[^:]*[:\s*]*([A-Z0-9\-/]+)", line, re.I)
            if m_sym:
                val = m_sym.group(1).strip()
                # Parse standard format 1C25MDT -> Serial 1, Form C25MDT (or full string as FormNo)
                s, f = parse_serial_form_no(val)
                if f:
                     invoice.invoiceFormNo = f
                     if s: invoice.invoiceSerial = s
                # Also support just FormNo raw
                elif len(val) >= 6:
                     invoice.invoiceFormNo = val

        # --- Fallback Seller Name (Header First) ---
        if not invoice.sellerName and "CÔNG TY" in clean.upper():
              if "HÓA ĐƠN" not in clean.upper() and ":" not in line:
                  invoice.sellerName = clean

    # 2. Second pass: Ultra Fallback for Serial (Value Scan) if still missing
    # This is "Ultra Fallback" moved from api_server.py
    if not invoice.invoiceSerial:
        for line in lines:
            low = line.lower()
            if "điều chỉnh" in low or "thay thế" in low or "liên quan" in low: continue
            
            # Pattern: 1C25THO or C25THO (Digit? + Char + 2 Digits + 3 Chars)
            # Scan specifically for the serial syntax which is very distinct in VN invoices.
            m = re.search(r"\b(\d?[A-Z]\d{2}[A-Z]{3})\b", line)
            if m:
                val = m.group(1)
                s, f = parse_serial_form_no(val)
                invoice.invoiceSerial = s
                if f and not invoice.invoiceFormNo: invoice.invoiceFormNo = f
                break
