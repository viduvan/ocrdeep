
import re
from typing import List, Tuple
from src.schemas.invoice import Invoice

# Reuse the helper if allowed, otherwise we can copy it.
try:
    from src.parsers.block_invoice_parser import (
        parse_serial_form_no,
        parse_seller,
        parse_buyer,
        SELLER_LABEL_KEYS,
        BUYER_LABEL_KEYS,
    )
except ImportError:
    # Fallback implementation if import fails (circular or path issue)
    def parse_serial_form_no(text: str) -> Tuple[str, str]:
        return text.strip(), None
    parse_seller = None
    parse_buyer = None
    SELLER_LABEL_KEYS = {}
    BUYER_LABEL_KEYS = {}


def _detect_zoom_blocks(lines: List[str]):
    """
    Phân chia zoom text thành seller / buyer / header blocks.
    Dùng cho commercial invoice (EN) và hóa đơn VN.
    """
    seller_lines = []
    buyer_lines = []
    header_lines = []

    current = "header"

    SELLER_TRIGGERS = [
        "the seller:", "seller:", "shipper:", "beneficiary:",
        "đơn vị bán hàng", "bên a", "bên bán",
    ]
    # VN buyer labels — phổ biến trong zoom text hóa đơn VN
    BUYER_TRIGGERS = [
        "the buyer:", "buyer:", "consignee:", "bill to:",
        "khách hàng", "đơn vị mua", "bên b", "bên mua",
        "tên người mua hàng", "họ tên người mua",
        "tên đơn vị mua", "người mua hàng:",
    ]
    HEADER_TRIGGERS = [
        "commercial invoice", "proforma invoice", "tax invoice",
        "vat invoice", "hóa đơn", "phiếu",
        "inv. no", "inv no", "invoice no",
        "inv. date", "s/c no", "payment",
        "transportation", "ký hiệu", "kí hiệu",
        "ngày:", "date:", "mã cửa hàng", "số đơn hàng",
    ]

    # --- First unlabeled non-empty line → likely seller name ---
    # A line qualifies even if it has inline Ky hieu / So (e.g. "Chau Huu Materials    Ký hiệu: 001")
    # Strategy: take the part BEFORE 2+ consecutive spaces; if that part has no colon → seller name
    first_content_idx = None
    for i, line in enumerate(lines):
        stripped = line.strip().strip('*').strip()
        if not stripped or stripped.startswith('|'):
            continue
        # Split on 2+ spaces and check the FIRST part
        first_part = re.split(r'\s{2,}', stripped)[0].strip()
        if first_part and ":" not in first_part:
            first_content_idx = i
            break

    for idx, line in enumerate(lines):
        l = line.lower().strip()

        # SELLER triggers (highest priority on this line)
        if any(k in l for k in SELLER_TRIGGERS):
            current = "seller"
        # BUYER triggers
        elif any(k in l for k in BUYER_TRIGGERS):
            current = "buyer"
        # First content line with no label part → seller name (check BEFORE HEADER_TRIGGERS)
        elif idx == first_content_idx and current == "header":
            current = "seller"
        # HEADER triggers
        elif any(k in l for k in HEADER_TRIGGERS):
            current = "header"

        if current == "seller":
            seller_lines.append(line)
        elif current == "buyer":
            buyer_lines.append(line)
        else:
            header_lines.append(line)

    return seller_lines, buyer_lines, header_lines


def _parse_en_seller(lines: List[str], invoice: Invoice) -> None:
    """
    Parse seller block từ zoom text.
    Hỗ trợ cả EN (THE SELLER:) và VN (unlabeled first-line company name).
    """
    first_line = True
    for line in lines:
        clean = line.strip()
        # Strip markdown
        clean = re.sub(r'\*\*([^*]+)\*\*', r'\1', clean).strip()
        low = clean.lower()
        if not clean:
            continue

        # EN labeled: "THE SELLER: <name>"
        if any(k in low for k in ["the seller:", "seller:", "shipper:", "beneficiary:",
                                   "đơn vị bán hàng:"]):
            val = clean.split(":", 1)[-1].strip()
            if val and not invoice.sellerName:
                invoice.sellerName = val
            first_line = False
            continue

        # VN unlabeled first seller line — company name without label
        # e.g. "Chau Huu Materials    Ký hiệu: 001"
        # Extract inline Ky hieu / So if present on same line
        if first_line and not invoice.sellerName:
            # Split off inline Ky hieu / So from the name
            name_part = re.split(r'\s{2,}', clean)[0].strip()  # Take part before 2+ spaces
            if name_part and ":" not in name_part:
                invoice.sellerName = name_part
            first_line = False
            continue

        first_line = False

        # Address: "địa chỉ:" or "address:"
        if "address:" in low or "địa chỉ:" in low:
            # Value may be on same line, or after the label
            # e.g. "Địa chỉ: 93 Điện Biên Phủ...   Số: 91511"
            # Strip trailing " Số: XXXX" if present
            val = clean.split(":", 1)[-1].strip()
            val = re.sub(r'\s{2,}Số[:\s]+\d+\s*$', '', val).strip()
            if val and not invoice.sellerAddress:
                invoice.sellerAddress = val
            continue

        # Phone / Tel
        if any(k in low for k in ["tel:", "tel :", "tel/fax:", "phone:", "fax:"]):
            m = re.search(r"[\d\s\-\+\(\)\.]{7,}", clean)
            if m and not invoice.sellerPhoneNumber:
                invoice.sellerPhoneNumber = m.group(0).strip()
            continue

        # Tax code
        if any(k in low for k in ["vat:", "tax code:", "mã số thuế:"]):
            m = re.search(r"[\dA-Z\-]{6,}", clean)
            if m and not invoice.sellerTaxCode:
                invoice.sellerTaxCode = m.group(0).strip()
            continue

        # Unlabeled continuation — if seller has name but no address yet
        if invoice.sellerName and not invoice.sellerAddress and ":" not in clean and len(clean) > 5:
            skip_keywords = ["commercial invoice", "proforma", "tax invoice",
                             "inv.", "s/c", "payment", "transportation",
                             "hóa đơn", "phiếu", "ngày"]
            if not any(k in low for k in skip_keywords):
                invoice.sellerAddress = clean


def _parse_en_buyer(lines: List[str], invoice: Invoice) -> None:
    """
    Parse buyer block từ zoom text.
    Hỗ trợ cả EN (THE BUYER:) và VN (Tên người mua hàng:, Tên đơn vị:).
    """
    for line in lines:
        clean = line.strip()
        clean = re.sub(r'\*\*([^*]+)\*\*', r'\1', clean).strip()
        low = clean.lower()
        if not clean:
            continue

        # EN: THE BUYER: / CONSIGNEE:  (authoritative — always overwrite)
        if any(k in low for k in ["the buyer:", "buyer:", "consignee:", "bill to:"]):
            val = clean.split(":", 1)[-1].strip()
            if val:
                invoice.buyerName = val
            continue

        # VN: Tên người mua hàng: <name> OR Tên đơn vị: <name>
        # ZOOM TEXT is authoritative — always overwrite buyerName if we have explicit label
        if any(k in low for k in ["tên người mua hàng", "họ tên người mua",
                                   "tên đơn vị", "khách hàng:"]):
            val = clean.split(":", 1)[-1].strip()
            if val:  # Always overwrite — explicit label is more reliable than continuation guesses
                invoice.buyerName = val
            continue

        # Address: "địa chỉ:" or "address:"
        if "address:" in low or "địa chỉ:" in low:
            val = clean.split(":", 1)[-1].strip()
            if val and not invoice.buyerAddress:
                invoice.buyerAddress = val
            continue

        # Unlabeled continuation: buyer has name but no address
        if invoice.buyerName and not invoice.buyerAddress and ":" not in clean and len(clean) > 5:
            skip_keywords = ["commercial invoice", "proforma", "inv.", "s/c", "payment"]
            if not any(k in low for k in skip_keywords):
                invoice.buyerAddress = clean


def _parse_en_header(lines: List[str], invoice: Invoice) -> None:
    """
    Parse invoice header fields từ English/VN invoice zoom text.
    Nhận dạng: INV. NO., INV. DATE:, NGÀY:, APR 4TH 2025, M/D/YYYY...
    """
    months = {
        'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
        'may': '05', 'jun': '06', 'jul': '07', 'aug': '08',
        'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12',
    }

    for line in lines:
        # Strip markdown bold markers before parsing
        clean = re.sub(r'\*\*([^*]+)\*\*', r'\1', line.strip()).strip()
        low = clean.lower()

        # Invoice ID: INV. NO.: INV250405
        if not invoice.invoiceID:
            m = re.search(
                r"(?:inv\.?\s*no\.?|invoice\s*no\.?)\s*[:\s]\s*([A-Z0-9\-\/]+)",
                clean, re.I
            )
            if m:
                invoice.invoiceID = m.group(1).strip()

        # Invoice Name — strip markdown ** before storing
        invoice_type_keywords = [
            "COMMERCIAL INVOICE", "PROFORMA INVOICE", "TAX INVOICE",
            "VAT INVOICE", "HÓA ĐƠN", "PHIẾU",
        ]
        up = clean.upper()
        if any(kw in up for kw in invoice_type_keywords) and not invoice.invoiceName:
            name_clean = re.sub(r'\s*[-–—]\s*No\.?\s*[A-Z0-9]+$', '', clean, flags=re.I).strip()
            if name_clean and 5 < len(name_clean) < 80:
                invoice.invoiceName = name_clean

        # Invoice Date — handle multiple formats
        if not invoice.invoiceDate:
            # Pattern: APR 4TH, 2025 / APR. 04, 2025
            m = re.search(r"([A-Za-z]{3})\.?\s*(\d{1,2})(?:ST|ND|RD|TH)?,?\s*(\d{4})", clean, re.I)
            if m:
                month_abbr = m.group(1).lower()[:3]
                if month_abbr in months:
                    invoice.invoiceDate = f"{m.group(2).zfill(2)}/{months[month_abbr]}/{m.group(3)}"

            # Pattern: date: 2025-04-04 or date: 2025/04/04
            if not invoice.invoiceDate:
                m = re.search(r"date[:\s]+(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})", clean, re.I)
                if m:
                    invoice.invoiceDate = f"{m.group(3).zfill(2)}/{m.group(2).zfill(2)}/{m.group(1)}"

            # Pattern: Ngày: M/D/YYYY or Ngày: DD/MM/YYYY (VN short form)
            if not invoice.invoiceDate:
                m = re.search(r"[Nn]gày[:\s]+(\d{1,2})/(\d{1,2})/(\d{4})", clean)
                if m:
                    # Ambiguous: treat as M/D/YYYY if month > 12 swap, else D/M
                    p1, p2, yr = int(m.group(1)), int(m.group(2)), m.group(3)
                    if p1 > 12:  # p1 is day, p2 is month
                        invoice.invoiceDate = f"{str(p1).zfill(2)}/{str(p2).zfill(2)}/{yr}"
                    else:        # treat as M/D/YYYY (US format common in EN invoices)
                        invoice.invoiceDate = f"{str(p2).zfill(2)}/{str(p1).zfill(2)}/{yr}"

            # Pattern: Ngày DD tháng MM năm YYYY (VN full)
            if not invoice.invoiceDate:
                m = re.search(r"Ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})", clean, re.I)
                if m:
                    invoice.invoiceDate = f"{m.group(1).zfill(2)}/{m.group(2).zfill(2)}/{m.group(3)}"


def parse_zoom_header(lines: List[str], invoice: Invoice) -> None:
    """
    Parse header fields specifically for the 'Zoom-in' text.
    Handles both Vietnamese and English (commercial invoice) formats.

    Strategy:
    1. First, detect blocks (seller / buyer / header) within the zoom text.
    2. Parse each block using dedicated handlers.
    3. For Vietnamese invoices, reuse parse_seller() and parse_buyer() from block_invoice_parser.
    4. For English invoices, use EN-specific handlers.
    """

    # ── Block detection ──────────────────────────────────────────────────────
    seller_lines, buyer_lines, header_lines = _detect_zoom_blocks(lines)

    # ── Seller ───────────────────────────────────────────────────────────────
    if not invoice.sellerName or not invoice.sellerAddress:
        _parse_en_seller(seller_lines, invoice)

        # VN fallback: only if seller_lines is empty (EN handler found nothing)
        if not invoice.sellerName and parse_seller is not None and seller_lines:
            parse_seller(seller_lines, invoice)

    # ── Buyer ─────────────────────────────────────────────────────────────────
    if not invoice.buyerName or not invoice.buyerAddress:
        _parse_en_buyer(buyer_lines, invoice)

        # VN fallback: only call if buyer_lines is EMPTY (EN handler already processed non-empty block)
        # This prevents label-only lines like "Mã số thuế:" being stored as buyerName
        if not invoice.buyerName and parse_buyer is not None and not buyer_lines:
            parse_buyer(buyer_lines, invoice)

    # ── Header (invoiceID, invoiceName, invoiceDate, serial…) ─────────────────
    _parse_en_header(header_lines + lines, invoice)  # scan all lines for header fields

    # ── Vietnamese-style header fields (serial, form no, date) ────────────────
    serial_parsed = bool(invoice.invoiceSerial)

    for line in lines:
        clean = line.strip()
        low = clean.lower()

        # EXCLUSION: Skip adjustment/replacement references
        if "điều chỉnh" in low or "thay thế" in low or "liên quan" in low:
            continue

        # --- Invoice Serial (VN format: Ký hiệu / Serial) ---
        if not serial_parsed:
            if "ký hiệu" in low or "kí hiệu" in low or "serial" in low:
                m = re.search(r"(?:ký hiệu|kí hiệu|serial)[^:\d]*[:\s]+([A-Z0-9/\-]+)", line, re.I)
                if m:
                    val = m.group(1).strip()
                    if len(val) >= 3:
                        s, f = parse_serial_form_no(val)
                        invoice.invoiceSerial = s
                        if f and not invoice.invoiceFormNo:
                            invoice.invoiceFormNo = f
                        serial_parsed = True

        # --- Invoice Form No ---
        if not invoice.invoiceFormNo:
            if "mẫu số" in low or "form no" in low:
                m = re.search(r"(?:Mẫu số|Form No).*?([0-9]+[A-Z0-9/]*)", line, re.I)
                if m:
                    invoice.invoiceFormNo = m.group(1)

        # --- Invoice ID (VN: Số ...: ####) ---
        contains_keyword = ("số" in low or "no" in low or "so" in low) and ":" in low
        is_clean = (
            "tài khoản" not in low and "tiền" not in low and
            "thuế" not in low and "điện thoại" not in low and
            "địa chỉ" not in low and "address" not in low
        )
        if contains_keyword and is_clean and not invoice.invoiceID:
            m = re.search(r"(?:Số|So|No).*?[:\s]\s*\*{0,2}(\d+)\*{0,2}", line, re.I)
            if m:
                invoice.invoiceID = m.group(1)

        # --- Fallback Seller Name (VN: CÔNG TY in zoom) ---
        if not invoice.sellerName and "CÔNG TY" in clean.upper():
            if "HÓA ĐƠN" not in clean.upper() and ":" not in line:
                invoice.sellerName = clean

    # ── Ultra Fallback: Serial value scan ────────────────────────────────────
    if not invoice.invoiceSerial:
        for line in lines:
            low = line.lower()
            if "điều chỉnh" in low or "thay thế" in low or "liên quan" in low:
                continue
            m = re.search(r"\b(\d?[A-Z]\d{2}[A-Z]{3})\b", line)
            if m:
                val = m.group(1)
                s, f = parse_serial_form_no(val)
                invoice.invoiceSerial = s
                if f and not invoice.invoiceFormNo:
                    invoice.invoiceFormNo = f
                break
