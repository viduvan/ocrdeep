
import re
import unicodedata
from typing import List, Tuple
from src.schemas.invoice import Invoice

def _strip_diacritics(s: str) -> str:
    """Strip Unicode diacritics for fuzzy comparison (e.g., ÔNE → ONE)."""
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')

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
        "the seller:", "seller:", "shipper:", "shipper name", "beneficiary:",
        "đơn vị bán hàng", "bên a", "bên bán",
        # EN Commercial Invoice
        "exporter:", "exporter details", "exporter name", "sender:", "sender name",
        "ship from", "bill from", "billed from", "shipper/exporter",
        "sender/exporter", "vendor/exporter", "from:",
    ]
    # VN buyer labels — phổ biến trong zoom text hóa đơn VN
    BUYER_TRIGGERS = [
        "the buyer:", "buyer:", "consignee:", "consignee", "bill to:", "billed to",
        "khách hàng", "đơn vị mua", "bên b", "bên mua",
        "tên người mua hàng", "họ tên người mua",
        "tên đơn vị mua", "người mua hàng:",
        # EN Commercial Invoice
        "sold to", "ship to", "importer:", "importer details",
        "consigned to", "consignee name", "invoice to", "recipient",
        "notify party", "customer:",
    ]
    HEADER_TRIGGERS = [
        "commercial invoice", "proforma invoice", "pro forma invoice",
        "tax invoice",
        "vat invoice", "hóa đơn", "phiếu",
        "inv. no", "inv no", "invoice no",
        "invoice number", "invoice #",
        "inv. date", "s/c no", "payment",
        "transportation", "ký hiệu", "kí hiệu",
        "ngày:", "date:", "mã cửa hàng", "số đơn hàng",
    ]

    # --- First unlabeled non-empty line → likely seller name ---
    # A line qualifies even if it has inline Ky hieu / So (e.g. "Chau Huu Materials    Ký hiệu: 001")
    # Strategy: take the part BEFORE 2+ consecutive spaces; if that part has no colon → seller name
    INVOICE_TYPE_KEYWORDS = {'invoice', 'commercial invoice', 'proforma invoice',
                              'pro forma invoice', 'tax invoice', 'vat invoice',
                              'hóa đơn', 'phiếu'}
    first_content_idx = None
    for i, line in enumerate(lines):
        stripped = line.strip().strip('*').strip()
        if not stripped or stripped.startswith('|'):
            continue
        # Skip markdown headers entirely — they're section labels, not company names
        if stripped.startswith('#'):
            continue
        # Split on 2+ spaces and check the FIRST part
        first_part = re.split(r'\s{2,}', stripped)[0].strip()
        first_part_clean = first_part.lstrip('#').strip()
        if first_part_clean and ":" not in first_part_clean:
            # Skip invoice type keywords — they're document titles, not company names
            _fp_low = first_part_clean.lower()
            if _fp_low in INVOICE_TYPE_KEYWORDS:
                continue
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
    pending_seller_address = False  # When True: sellerName set, looking for address, skip name repeat
    _addr_done = False  # When True: seller address is complete, stop appending
    for line in lines:
        clean = line.strip()
        # Strip markdown
        clean = re.sub(r'\*\*([^*]+)\*\*', r'\1', clean).strip()
        low = clean.lower()
        if not clean:
            continue

        # EN labeled: "THE SELLER: <name>" or "Exporter: <name>" etc.
        if any(k in low for k in ["the seller:", "seller:", "shipper:", "beneficiary:",
                                   "đơn vị bán hàng:",
                                   # EN Commercial Invoice
                                   "exporter:", "sender:", "sender name:",
                                   "ship from:", "bill from:", "billed from:",
                                   "shipper/exporter:", "sender/exporter:",
                                   "company name:"]):
            val = clean.split(":", 1)[-1].strip()
            if val and not invoice.sellerName:
                invoice.sellerName = val
            elif not val and not invoice.sellerName:
                # Label has no value - next non-empty line is the seller name
                first_line = True  # Reset so next line is treated as first (company name)
            elif not val and invoice.sellerName and not invoice.sellerAddress:
                # Label with no value, sellerName already set but no address yet
                # Next lines: first will be company name (repeat), second will be address
                pending_seller_address = True
            else:
                first_line = False
            continue

        # Skip known section labels without colon (e.g. "Billed from", "Shipper/Exporter")
        # This check runs BEFORE first_line to handle labels appearing mid-block
        _section_labels = {"billed from", "bill from",
                           "shipper/exporter", "sender/exporter", "vendor/exporter",
                           "shipper name", "shipper", "exporter name",
                           "ship from", "exporter",
                           "the seller", "from"}
        _clean_for_label = clean.lstrip('#').strip()
        _label_low = _clean_for_label.lower()
        if _label_low in _section_labels or any(_label_low.startswith(sl + " ") for sl in _section_labels if len(sl) > 2):
            # Section label — next lines are authoritative for name and address
            # Only reset sellerName if it looks like a false positive (single word, generic)
            if invoice.sellerName:
                _sn = invoice.sellerName.strip()
                _is_false_positive = (
                    ' ' not in _sn and len(_sn) < 15 and not any(c.isdigit() for c in _sn)
                )
                if _is_false_positive:
                    first_line = True
                    invoice.sellerName = None
                else:
                    # Name looks legitimate (multi-word, set by block parser) — just reset address
                    pending_seller_address = True
            else:
                first_line = True
            invoice.sellerAddress = None
            _addr_done = False
            continue

        # VN unlabeled first seller line — company name without label
        # e.g. "Chau Huu Materials    Ký hiệu: 001"
        if first_line and not invoice.sellerName:
            # Take part before 2+ spaces as seller name
            name_part = re.split(r'\s{2,}', clean)[0].strip()
            # Skip markdown headers (## Shipper/Exporter) — they are section labels, not company names
            name_part_stripped = name_part.lstrip('#').strip()
            if clean.startswith('#'):
                # Markdown header — skip it but keep first_line = True
                # so the next line can be treated as the company name
                continue
            if name_part_stripped and ":" not in name_part_stripped:
                invoice.sellerName = name_part_stripped
            # Extract inline Ký hiệu / Serial on same line → invoiceSerial
            m_kh = re.search(r'[Kk][ýí]\s*hi[eệ]u[^:]*[:\s]+([A-Z0-9/\-]+)', clean, re.I)
            if m_kh and not invoice.invoiceSerial:
                val_kh = m_kh.group(1).strip()
                if len(val_kh) >= 2:
                    invoice.invoiceSerial = val_kh
            first_line = False
            continue

        first_line = False

        # When pending_seller_address: skip the company name repeat, pick up address next
        if pending_seller_address:
            # If this line matches existing sellerName (it's a repeat), skip it
            if clean.rstrip('.').strip().lower() == (invoice.sellerName or '').rstrip('.').strip().lower():
                continue  # Skip the company name repeat
            # Otherwise this IS the address
            and_not_phone = not any(k in low for k in ["tel:", "fax:", "phone:"])
            skip_kws = ["commercial invoice", "proforma", "tax invoice",
                        "inv.", "s/c", "payment", "transportation",
                        "hóa đơn", "phiếu", "ngày"]
            if and_not_phone and not any(k in low for k in skip_kws) and len(clean) > 5:
                invoice.sellerAddress = clean
                pending_seller_address = False
                continue

        # Address: "địa chỉ:" or "address:"
        if "address:" in low or "địa chỉ:" in low:
            # e.g. "Địa chỉ: 93 Điện Biên Phủ...   Số: 91511"
            # Extract inline Số: XXXX → invoiceID BEFORE stripping it
            m_so = re.search(r'\s{2,}S[oố][:\s]+(\d+)\s*$', clean)
            if m_so and not invoice.invoiceID:
                invoice.invoiceID = m_so.group(1)
            # Strip trailing " Số: XXXX" to clean the address value
            val = clean.split(":", 1)[-1].strip()
            val = re.sub(r'\s{2,}S[oố][:\s]+\d+\s*$', '', val).strip()
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

        # Unlabeled continuation — if seller has name but no address yet (or address is being built)
        if invoice.sellerName and ":" not in clean and not _addr_done:
            skip_keywords = ["commercial invoice", "proforma", "tax invoice",
                             "inv.", "s/c", "payment", "transportation",
                             "hóa đơn", "phiếu", "ngày",
                             "company name", "company address", "shipper", "exporter",
                             "consignee", "buyer", "importer", "bill to", "billed to",
                             "ship to", "sold to", "billed from",
                             "item no", "description of goods", "quantity", "unit price"]
            # Skip markdown headers and lines that match seller name
            clean_stripped = clean.lstrip('#').strip()
            # Also skip lines that look like table headers (multiple 4+ space gaps)
            _is_table_header = len(re.findall(r'\s{4,}', clean)) >= 2
            # Strip diacritics for fuzzy comparison (OCR may produce ÔNE vs ONE)
            _clean_norm = _strip_diacritics(clean_stripped.lower())
            _seller_norm = _strip_diacritics((invoice.sellerName or '').lower())
            # Also normalize whitespace+punctuation for fuzzy match (e.g. "co.,ltd" vs "co., ltd")
            _clean_stripped_ws = re.sub(r'[\s,.\-]+', '', _clean_norm)
            _seller_stripped_ws = re.sub(r'[\s,.\-]+', '', _seller_norm)
            is_seller_repeat = (_clean_norm == _seller_norm
                                or _clean_stripped_ws == _seller_stripped_ws
                                or (_seller_norm and _seller_norm in _clean_norm)
                                or (_clean_norm and _clean_norm in _seller_norm))
            if (not any(k in low for k in skip_keywords)
                    and not clean.startswith('#')
                    and not clean.startswith('|')
                    and not is_seller_repeat
                    and not _is_table_header
                    and len(clean) >= 2):
                if not invoice.sellerAddress:
                    # Check if this looks like a company name continuation (Inc., Ltd, Corp, etc.)
                    _company_suffixes = re.compile(r'\b(?:Inc\.?|Ltd\.?|LLC|Corp\.?|Co\.?|GmbH|S\.?A\.?|PLC|Pty|Pvt|SARL|SRL|BV|NV)\b', re.I)
                    _is_phone_first = bool(re.match(r'^[\+\d\(][\d\s\-\(\)\.]{6,}$', clean))
                    if _company_suffixes.search(clean) and invoice.sellerName:
                        # Append to seller name instead of address
                        invoice.sellerName = invoice.sellerName + ' ' + clean
                    elif clean.lower().startswith('www.'):
                        pass  # Skip website URLs
                    elif '@' in clean:
                        # Email — save and skip
                        if not invoice.sellerEmail:
                            invoice.sellerEmail = clean
                    elif _is_phone_first:
                        # Phone number — save and skip
                        if not invoice.sellerPhoneNumber:
                            invoice.sellerPhoneNumber = clean
                    elif len(clean) <= 5 and clean.replace(',', '').replace('.', '').isdigit():
                        # Short number — store as pending prefix for next line
                        invoice.sellerAddress = clean
                    else:
                        invoice.sellerAddress = clean
                elif len(invoice.sellerAddress) < 80:
                    # Append subsequent address lines (city, state, country, etc.)
                    # Stop at phone/email/pipe/heading lines
                    # Also stop at standalone phone numbers (7+ digits without prefix)
                    _is_phone_num = bool(re.match(r'^[\+\d\(][\d\s\-\(\)\.]{6,}$', clean))
                    _is_separator = bool(re.match(r'^-{2,}$', clean.strip()))
                    _is_stopper = (clean.startswith('Phone')
                                   or clean.startswith('Tel')
                                   or '@' in clean
                                   or 'email' in low
                                   or clean.startswith('|')
                                   or _is_phone_num
                                   or _is_separator)
                    if _is_stopper:
                        _addr_done = True  # Stop address continuation entirely
                        # Save phone number if detected
                        if _is_phone_num and not invoice.sellerPhoneNumber:
                            invoice.sellerPhoneNumber = clean
                    else:
                        invoice.sellerAddress = invoice.sellerAddress.rstrip(', ').rstrip(',') + ', ' + clean


def _parse_en_buyer(lines: List[str], invoice: Invoice) -> None:
    """
    Parse buyer block từ zoom text.
    Hỗ trợ cả EN (THE BUYER:) và VN (Tên người mua hàng:, Tên đơn vị:).
    """
    _buyer_addr_done = False
    for line in lines:
        clean = line.strip()
        clean = re.sub(r'\*\*([^*]+)\*\*', r'\1', clean).strip()
        low = clean.lower()
        if not clean:
            continue

        # EN: THE BUYER: / CONSIGNEE: / SOLD TO: etc.  (authoritative — always overwrite)
        if any(k in low for k in ["the buyer:", "buyer:", "consignee:", "bill to:", "billed to:",
                                   # EN Commercial Invoice
                                   "sold to:", "ship to:", "importer:",
                                   "importer name", "consigned to:", "invoice to:",
                                   "recipient:", "customer:"]):
            val = clean.split(":", 1)[-1].strip()
            if val:
                invoice.buyerName = val
            else:
                # Label with no value — next non-empty unlabeled line is the buyer name
                invoice._pending_buyer_name = True
            continue

        # EN section headers without colon (e.g. "## Recipient/Ship To", "## Sold to")
        # Also handle non-markdown headers like "Billed to" (without #)
        clean_no_hash = clean.lstrip('#').strip()
        low_no_hash = clean_no_hash.lower()
        _buyer_headers = ["recipient", "ship to", "sold to", "consignee",
                          "bill to", "billed to", "importer", "buyer"]
        _non_md_buyer_hdrs = {"billed to", "bill to", "sold to", "ship to", "consignee", "recipient"}
        _is_buyer_header = (
            (clean.startswith('#') and any(k in low_no_hash for k in _buyer_headers)) or
            low_no_hash in _non_md_buyer_hdrs or
            any(low_no_hash.startswith(h + " ") for h in _non_md_buyer_hdrs if len(h) > 2)
        )
        if _is_buyer_header:
            invoice._pending_buyer_name = True
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

        # Pending buyer name from label-without-value (e.g. "THE BUYER:" alone on a line)
        if getattr(invoice, "_pending_buyer_name", False) and not invoice.buyerName and ":" not in clean and len(clean) > 2:
            skip_keywords = ["commercial invoice", "proforma", "inv.", "s/c", "payment", "transportation"]
            if not any(k in low for k in skip_keywords):
                invoice.buyerName = clean
                invoice._pending_buyer_name = False
                continue

        # Unlabeled continuation: buyer has name but address not yet set or still building
        if invoice.buyerName and ":" not in clean and not _buyer_addr_done:
            skip_keywords = ["commercial invoice", "proforma", "inv.", "s/c", "payment",
                             "invoice no", "invoice date", "date", "tracking"]
            # Skip markdown headers (## Section Name) and pipe-table content
            if clean.lstrip('#').strip().lower() != clean.lower():  # has leading #
                _buyer_addr_done = True
                continue
            if any(k in low for k in skip_keywords):
                _buyer_addr_done = True
                continue
            # Skip --- separators
            if re.match(r'^-{2,}$', clean.strip()):
                _buyer_addr_done = True
                continue
            # Detect phone/email stoppers
            _is_phone = bool(re.match(r'^[\+\d][\d\s\-\(\)\.]{6,}$', clean))
            _is_email = '@' in clean or 'email' in low
            if _is_phone or _is_email:
                _buyer_addr_done = True
                if _is_phone and not invoice.buyerPhoneNumber:
                    invoice.buyerPhoneNumber = clean
                continue
            # Skip date-like patterns (e.g. "02/27/2024")
            if re.match(r'^\d{1,2}[/\.\-]\d{1,2}[/\.\-]\d{2,4}$', clean):
                _buyer_addr_done = True
                continue
            if not invoice.buyerAddress and len(clean) >= 2:
                invoice.buyerAddress = clean
            elif invoice.buyerAddress and len(invoice.buyerAddress) < 80 and len(clean) >= 2:
                invoice.buyerAddress = invoice.buyerAddress.rstrip(', ').rstrip(',') + ', ' + clean


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

        # Invoice ID: INV. NO.: INV250405 or "Invoice Number:\s+XXX"
        if not invoice.invoiceID:
            m = re.search(
                r"(?:inv\.?\s*no\.?|invoice\s*no\.?|invoice\s*number|invoice\s*#)\s*[:\s]\s*([A-Z0-9][\w\-/]+)",
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
        # Normalize existing raw dates (e.g. "APR 4TH,2025" set by pre_parse) by checking if current value is non-numeric
        _date_needs_normalize = (
            invoice.invoiceDate and
            not re.match(r'^\d{1,2}/\d{1,2}/\d{4}$', str(invoice.invoiceDate))
        )
        if not invoice.invoiceDate or _date_needs_normalize:
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
    # Also re-parse seller if sellerAddress looks wrong (equals sellerName — company name set as address)
    _seller_addr_is_name = (
        invoice.sellerAddress and invoice.sellerName and
        invoice.sellerAddress.rstrip('.').strip() == invoice.sellerName.rstrip('.').strip()
    )
    if not invoice.sellerName or not invoice.sellerAddress or _seller_addr_is_name:
        if _seller_addr_is_name:
            # Clear the wrong address so _parse_en_seller can set the correct one
            invoice.sellerAddress = None
        _parse_en_seller(seller_lines, invoice)

        # VN fallback: only if seller_lines is empty (EN handler found nothing)
        if not invoice.sellerName and parse_seller is not None and seller_lines:
            parse_seller(seller_lines, invoice)
    elif invoice.sellerName and invoice.sellerAddress and seller_lines:
        # Try zoom parse and keep the longer address version
        from src.schemas.invoice import Invoice as _Inv
        _tmp = _Inv()
        _tmp.sellerName = invoice.sellerName
        _parse_en_seller(seller_lines, _tmp)
        if _tmp.sellerAddress and len(_tmp.sellerAddress) > len(invoice.sellerAddress):
            invoice.sellerAddress = _tmp.sellerAddress
        if _tmp.sellerPhoneNumber and not invoice.sellerPhoneNumber:
            invoice.sellerPhoneNumber = _tmp.sellerPhoneNumber

    # ── Buyer ─────────────────────────────────────────────────────────────────
    if not invoice.buyerName or not invoice.buyerAddress or getattr(invoice, '_pending_buyer_name', False):
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
