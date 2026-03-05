
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
        # Indian invoice
        "sold by",
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
        "notify party", "customer:", "issued to", "addressed to",
        # Indian invoice
        "billing address", "shipping address",
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
        "date issued", "due date", "invoice date",
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
        # Check markdown headers — skip section labels but keep company name headings
        if stripped.startswith('#'):
            _heading = stripped.lstrip('#').strip()
            _section_kws = ['shipper', 'exporter', 'consignee', 'importer', 'buyer',
                            'seller', 'invoice', 'bill', 'ship to', 'details',
                            'commercial', 'proforma', 'summary']
            if any(sk in _heading.lower() for sk in _section_kws):
                continue  # Section label — skip
            # Skip pure numbers — they are invoice IDs (#123144), not company names
            if _heading.replace('-', '').replace('/', '').isdigit():
                continue
            # Company name heading — this is first content
            if _heading and len(_heading) > 2:
                first_content_idx = i
                break
            continue
        # Split on 2+ spaces and check the FIRST part
        first_part = re.split(r'\s{2,}', stripped)[0].strip()
        first_part_clean = first_part.lstrip('#').strip()
        if first_part_clean and ":" not in first_part_clean:
            # Skip invoice type keywords — they're document titles, not company names
            _fp_low = first_part_clean.lower()
            if _fp_low in INVOICE_TYPE_KEYWORDS:
                continue
            # Skip ZOOM TEXT markers (section separators, not content)
            if 'zoom text' in _fp_low or _fp_low.startswith('--'):
                continue
            # Skip header/metadata labels that aren't company names
            if any(hk in _fp_low for hk in HEADER_TRIGGERS):
                continue
            # Skip date values (e.g., "05 April 2023", "JAN-9-2026")
            if re.match(r'^\d{1,2}\s+[A-Za-z]+\s+\d{4}$', first_part_clean) or \
               re.match(r'^[A-Za-z]{3,}\s+\d{1,2},?\s+\d{4}$', first_part_clean) or \
               re.match(r'^[A-Za-z]{3}[\-]\d{1,2}[\-]\d{4}$', first_part_clean):
                continue
            first_content_idx = i
            break

    for idx, line in enumerate(lines):
        l = line.lower().strip()

        # Skip ZOOM TEXT markers
        if 'zoom text' in l and l.strip('-').strip().replace('zoom text', '').strip() == '':
            continue

        # SELLER triggers (highest priority on this line)
        if any(k in l for k in SELLER_TRIGGERS):
            current = "seller"
        # BUYER triggers
        elif any(k in l for k in BUYER_TRIGGERS):
            current = "buyer"
        # Regex buyer trigger: lines ending with " to:" (e.g., "ISS.I60 To:", "Issued To:")
        elif re.search(r'\bto\s*:\s*\**\s*$', l):
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
                                   "company name:", "sold by:"]):
            # Handle pipe-table lines: extract value from the cell with the label
            if clean.startswith('|'):
                cells = [c.strip() for c in clean.split('|')]
                val = ''
                for ci, cell in enumerate(cells):
                    cell_low = cell.lower()
                    if any(k.rstrip(':') in cell_low for k in ["seller:", "shipper:", "exporter:",
                                                                 "beneficiary:", "sender:",
                                                                 "company name:"]):
                        # Check for value after colon in this cell
                        if ':' in cell:
                            cv = cell.split(':', 1)[-1].strip()
                            if cv and len(cv) > 2 and not cv.startswith('|'):
                                val = cv
                        # If no value in this cell, check the next cell
                        if not val and ci + 1 < len(cells):
                            next_cell = cells[ci + 1].strip()
                            if next_cell and len(next_cell) > 2:
                                val = next_cell
                        break
            else:
                val = clean.split(":", 1)[-1].strip()
            if val and not invoice.sellerName:
                invoice.sellerName = val
            elif not val and not invoice.sellerName:
                # Label has no value - next non-empty line is the seller name
                first_line = True  # Reset so next line is treated as first (company name)
            elif not val and invoice.sellerName and not invoice.sellerAddress:
                # Label with no value, sellerName already set but no address yet
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
                           "the seller", "from", "sold by"}
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
            # Handle pipe-table lines for seller name
            if clean.startswith('|'):
                cells = [c.strip() for c in clean.split('|') if c.strip()]
                # Skip separator rows (|---|---|)
                if cells and not all(set(c).issubset({'-', ' ', ':'}) for c in cells):
                    # First non-empty cell that doesn't contain labels
                    for cell in cells:
                        cl = cell.lower()
                        if len(cell) > 2 and ':' not in cell and not any(
                            k in cl for k in ['shipper', 'exporter', 'seller', 'consignee',
                                               'importer', 'buyer', 'address', 'add.']):
                            invoice.sellerName = cell
                            first_line = False
                            break
                continue
            # Take part before 2+ spaces as seller name
            name_part = re.split(r'\s{2,}', clean)[0].strip()
            # Skip markdown headers (## Shipper/Exporter) — they are section labels, not company names
            name_part_stripped = name_part.lstrip('#').strip()
            if clean.startswith('#'):
                # Markdown header — check if it's a section label or a company name
                _heading_text = clean.lstrip('#').strip()
                _section_kws = ['shipper', 'exporter', 'consignee', 'importer', 'buyer',
                                'seller', 'invoice', 'bill', 'ship to', 'details',
                                'commercial', 'proforma', 'summary']
                if any(sk in _heading_text.lower() for sk in _section_kws):
                    # Section label — skip it, keep first_line = True
                    continue
                # Company name heading — use it
                if _heading_text and len(_heading_text) > 2:
                    invoice.sellerName = _heading_text
                    first_line = False
                    continue
            if name_part_stripped and ":" not in name_part_stripped:
                # Skip generic VN commerce terms that aren't real company names
                _generic_vn = {'xuất nhập khẩu', 'nhập khẩu', 'xuất khẩu', 
                              'thương mại', 'dịch vụ', 'sản xuất'}
                if name_part_stripped.lower() not in _generic_vn:
                    invoice.sellerName = name_part_stripped
                else:
                    # Generic term — skip it, keep first_line=True for next line
                    continue
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
            # Handle pipe-table lines
            _addr_clean = clean
            if clean.startswith('|'):
                cells = [c.strip() for c in clean.split('|') if c.strip()]
                # Skip separator rows
                if not cells or all(set(c).issubset({'-', ' ', ':', '+'}) for c in cells):
                    continue
                # Check for address label (Add.: ...)
                for cell in cells:
                    cl = cell.lower()
                    if cl.startswith('add.') or cl.startswith('add ') or 'address' in cl or 'địa chỉ' in cl:
                        if ':' in cell:
                            addr_val = cell.split(':', 1)[-1].strip()
                            if addr_val and len(addr_val) > 3:
                                invoice.sellerAddress = addr_val
                                pending_seller_address = False
                        break
                else:
                    # No address label found — check if first cell is seller name repeat
                    _first_cell = cells[0] if cells else ''
                    _addr_clean = _first_cell
                if pending_seller_address == False:
                    continue
            # If this line matches existing sellerName (it's a repeat), skip it
            if _addr_clean.rstrip('.').strip().lower() == (invoice.sellerName or '').rstrip('.').strip().lower():
                continue  # Skip the company name repeat
            # Otherwise this IS the address
            and_not_phone = not any(k in _addr_clean.lower() for k in ["tel:", "fax:", "phone:"])
            skip_kws = ["commercial invoice", "proforma", "tax invoice",
                        "inv.", "s/c", "payment", "transportation",
                        "hóa đơn", "phiếu", "ngày"]
            if and_not_phone and not any(k in _addr_clean.lower() for k in skip_kws) and len(_addr_clean) > 5:
                invoice.sellerAddress = _addr_clean
                pending_seller_address = False
                continue

        # Address: "địa chỉ:" or "address:" or "add.:" (abbreviated)
        if "address:" in low or "địa chỉ:" in low or "add.:" in low or "add :" in low:
            # Handle pipe-table lines
            if clean.startswith('|'):
                cells = [c.strip() for c in clean.split('|') if c.strip()]
                for cell in cells:
                    cl = cell.lower()
                    if 'address' in cl or 'địa chỉ' in cl or cl.startswith('add.') or cl.startswith('add '):
                        if ':' in cell:
                            val = cell.split(':', 1)[-1].strip()
                            val = re.sub(r'\s{2,}S[oố][:\s]+\d+\s*$', '', val).strip()
                            if val and not invoice.sellerAddress:
                                invoice.sellerAddress = val
                        break
            else:
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

        # Email
        if "email:" in low or "e-mail:" in low:
            em = re.search(r'[\w.+-]+@[\w.-]+', clean)
            if em and not invoice.sellerEmail:
                invoice.sellerEmail = em.group(0)
            continue

        # Unlabeled continuation — if seller has name but no address yet (or address is being built)
        if invoice.sellerName and ":" not in clean and not _addr_done:
            skip_keywords = ["commercial invoice", "proforma", "tax invoice",
                             "invoice",
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
                                    "recipient:", "customer:", "issued to:", "addressed to:",
                                   # Indian invoice
                                   "billing address:", "shipping address:"]):
            # Handle pipe-table lines: extract value from within the cell, not entire line
            if clean.startswith('|'):
                # Split into cells and find the one with the buyer label
                cells = [c.strip() for c in clean.split('|')]
                val = ''
                for cell in cells:
                    cell_low = cell.lower()
                    if any(k in cell_low for k in ["buyer:", "consignee:", "bill to:", "billed to:",
                                                    "sold to:", "ship to:", "importer:",
                                                    "consigned to:", "invoice to:",
                                                    "recipient:", "customer:", "issued to:"]):
                        # Extract value after the label colon within this cell
                        if ':' in cell:
                            val = cell.split(':', 1)[-1].strip()
                        break
            else:
                val = clean.split(":", 1)[-1].strip()
            # Reject "Country of Origin" and similar metadata values
            if val and not re.match(r'^Country\s+of\s+(?:Origin|Manufacture|Destination)', val, re.I):
                invoice.buyerName = val
            elif not val:
                # Label with no value — next non-empty unlabeled line is the buyer name
                invoice._pending_buyer_name = True
            continue

        # Regex fallback: line ending with " to:" (OCR-garbled labels like "ISS.I60 To:")
        if re.search(r'\bto\s*:\s*$', low):
            val = clean.split(":", 1)[-1].strip()
            if val and len(val) > 2:
                invoice.buyerName = val
            else:
                invoice._pending_buyer_name = True
            continue

        # EN section headers without colon (e.g. "## Recipient/Ship To", "## Sold to")
        # Also handle non-markdown headers like "Billed to" (without #)
        clean_no_hash = clean.lstrip('#').strip()
        low_no_hash = clean_no_hash.lower()
        _buyer_headers = ["recipient", "ship to", "sold to", "consignee",
                          "bill to", "billed to", "importer", "buyer",
                          "billing address", "shipping address"]
        _non_md_buyer_hdrs = {"billed to", "bill to", "sold to", "ship to", "consignee", "recipient",
                              "billing address", "shipping address"}
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
        if "address:" in low or "địa chỉ:" in low or "địa chỉ (" in low:
            # Handle pipe-table lines
            if clean.startswith('|'):
                # Find the cell with address label
                cells = [c.strip() for c in clean.split('|') if c.strip()]
                for cell in cells:
                    cl = cell.lower()
                    if 'address' in cl or 'địa chỉ' in cl:
                        if ':' in cell:
                            val = cell.split(':', 1)[-1].strip().rstrip(')')
                            if val and not invoice.buyerAddress:
                                invoice.buyerAddress = val
                        break
            else:
                val = clean.split(":", 1)[-1].strip()
                if val and not invoice.buyerAddress:
                    invoice.buyerAddress = val
            continue

        # Tax code: "Mã số thuế (Tax ID): 0107013883"
        if "mã số thuế" in low or "tax id" in low or "tax code" in low:
            # Extract tax code from pipe-table or regular line
            _tax_line = clean
            if clean.startswith('|'):
                cells = [c.strip() for c in clean.split('|') if c.strip()]
                for cell in cells:
                    if 'mã số thuế' in cell.lower() or 'tax id' in cell.lower() or 'tax code' in cell.lower():
                        _tax_line = cell
                        break
            m_tax = re.search(r'(?:Mã số thuế|Tax\s*(?:ID|Code))[^:]*:\s*([\d\-\s]+)', _tax_line, re.I)
            if m_tax:
                tax_val = re.sub(r'\s+', '', m_tax.group(1))
                if len(tax_val) >= 10 and not invoice.buyerTaxCode:
                    invoice.buyerTaxCode = tax_val
            continue

        # Phone: "Số điện thoại (Phone): 0984587968"
        if "phone" in low or "số điện thoại" in low or "tel:" in low:
            _phone_line = clean
            if clean.startswith('|'):
                cells = [c.strip() for c in clean.split('|') if c.strip()]
                for cell in cells:
                    if 'phone' in cell.lower() or 'số điện thoại' in cell.lower() or 'tel' in cell.lower():
                        _phone_line = cell
                        break
            m_ph = re.search(r'[\d\+][\d\s\-\(\)\.\/]{6,}', _phone_line)
            if m_ph and not invoice.buyerPhoneNumber:
                invoice.buyerPhoneNumber = m_ph.group(0).strip()
            continue

        # Pending buyer name from label-without-value (e.g. "THE BUYER:" alone on a line)
        if getattr(invoice, "_pending_buyer_name", False) and not invoice.buyerName and ":" not in clean and len(clean) > 2:
            skip_keywords = ["commercial invoice", "proforma", "inv.", "s/c", "payment", "transportation"]
            # Handle pipe-table lines: extract cell content
            _name_val = clean
            if clean.startswith('|'):
                cells = [c.strip() for c in clean.split('|') if c.strip()]
                # Skip separator rows (|---|---|)
                if not cells or all(set(c).issubset({'-', ' ', ':', '+'}) for c in cells):
                    continue
                if cells and len(cells[0]) > 2:
                    _name_val = cells[0]
                else:
                    continue  # Empty pipe-table row, skip
            if not any(k in _name_val.lower() for k in skip_keywords):
                invoice.buyerName = _name_val
                invoice._pending_buyer_name = False
                continue

        # Unlabeled continuation: buyer has name but address not yet set or still building
        if invoice.buyerName and ":" not in clean and not _buyer_addr_done:
            skip_keywords = ["commercial invoice", "proforma", "inv.", "s/c", "payment",
                             "invoice no", "invoice date", "date", "tracking"]
            # Handle pipe-table lines: extract cell content
            _cont_val = clean
            _from_pipe = False
            if clean.startswith('|'):
                _from_pipe = True
                cells = [c.strip() for c in clean.split('|') if c.strip()]
                # Skip separator rows
                if not cells or all(set(c).issubset({'-', ' ', ':', '+'}) for c in cells):
                    continue
                if cells and len(cells[0]) > 2 and ':' not in cells[0]:
                    _cont_val = cells[0]
                else:
                    continue  # Empty or label cell, skip
            # Skip markdown headers (## Section Name)
            if _cont_val.lstrip('#').strip().lower() != _cont_val.lower():  # has leading #
                _buyer_addr_done = True
                continue
            if any(k in _cont_val.lower() for k in skip_keywords):
                _buyer_addr_done = True
                continue
            # Skip --- separators
            if re.match(r'^-{2,}$', _cont_val.strip()):
                _buyer_addr_done = True
                continue
            # Detect phone/email stoppers
            _is_phone = bool(re.match(r'^[\+\d][\d\s\-\(\)\.]{6,}$', _cont_val))
            _is_email = '@' in _cont_val or 'email' in _cont_val.lower()
            if _is_phone or _is_email:
                _buyer_addr_done = True
                if _is_phone and not invoice.buyerPhoneNumber:
                    invoice.buyerPhoneNumber = _cont_val
                continue
            # Skip date-like patterns (e.g. "02/27/2024")
            if re.match(r'^\d{1,2}[/\.\-]\d{1,2}[/\.\-]\d{2,4}$', _cont_val):
                _buyer_addr_done = True
                continue
            # For pipe-table content: check if this is a company name continuation
            # (contains COMPANY, CORPORATION, LTD, JSC, etc.)
            if _from_pipe:
                _company_re = re.compile(
                    r'\b(?:COMPANY|CORPORATION|CORP|CO\b|LTD|LLC|JSC|INC|JOINT\s+STOCK|'
                    r'CONSTRUCTION|INVESTMENT|DEVELOPMENT|INDUSTRY|INDUSTRIES|'
                    r'ENTERPRISE|GROUP|TRADING|IMPORT|EXPORT)\b', re.I
                )
                if _company_re.search(_cont_val):
                    # This is company name continuation — don't set as address
                    continue
            if not invoice.buyerAddress and len(_cont_val) >= 2:
                # Don't set table header content as address
                if _from_pipe:
                    _buyer_addr_done = True
                    continue
                invoice.buyerAddress = clean
            elif invoice.buyerAddress and len(invoice.buyerAddress) < 80 and len(clean) >= 2:
                # Don't append pipe-table content to address
                if _from_pipe:
                    _buyer_addr_done = True
                    continue
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

    _pending_invoice_id = False
    for line in lines:
        # Strip markdown bold markers before parsing
        clean = re.sub(r'\*\*([^*]+)\*\*', r'\1', line.strip()).strip()
        low = clean.lower()

        # Invoice ID: INV. NO.: INV250405 or "Invoice Number:\s+XXX"
        if not invoice.invoiceID:
            m = re.search(
                r"(?:inv\.?\s*no\.?|invoice\s*no\.?|invoice\s*number|invoice\s*#)\s*[:\s]\s*([A-Z0-9][\w\-/]+(?:\s+\d{4})?)",
                clean, re.I
            )
            if m:
                invoice.invoiceID = m.group(1).strip()
                _pending_invoice_id = False
            # Pattern: "Nº: JW-202609001-1" or "N°: XXX" (European/intl format)
            if not invoice.invoiceID:
                m_no = re.search(r'(?:N[ºo°]|No\.)\s*:\s*([A-Za-z0-9][\w\-/]+)', clean)
                if m_no:
                    # Reject if preceded by non-invoice context (CUSTOMER, DELIVERY, note, parcel)
                    _pre_ctx = clean[:m_no.start()].strip().lower()
                    if not any(k in _pre_ctx for k in ['customer', 'delivery', 'note', 'parcel', 'iban', 'bic']):
                        invoice.invoiceID = m_no.group(1).strip()
                        _pending_invoice_id = False
            # Pattern: "Invoice Number & Date" (or similar) with value on next line
            if not invoice.invoiceID and re.match(r'(?:Invoice\s*Number\s*(?:&|and)\s*Date|Invoice\s*Number|Invoice\s*#)', clean, re.I):
                _pending_invoice_id = True
                continue

        # Pending invoice ID: next non-empty line with digits is the ID
        if _pending_invoice_id and not invoice.invoiceID:
            val = clean.strip()
            if val and re.match(r'^[A-Za-z0-9][\w\-/]*$', val) and len(val) >= 2:
                invoice.invoiceID = val
                _pending_invoice_id = False
                continue
            elif val:
                # Combined format: "234 30 Jan 2018" → ID + Date
                _combined_m = re.match(
                    r'^([A-Za-z0-9][\w\-/]*)\s+(\d{1,2})\s+'
                    r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+'
                    r'(\d{4})$', val, re.I
                )
                if _combined_m:
                    invoice.invoiceID = _combined_m.group(1)
                    _months = {'jan':'01','feb':'02','mar':'03','apr':'04',
                               'may':'05','jun':'06','jul':'07','aug':'08',
                               'sep':'09','oct':'10','nov':'11','dec':'12'}
                    _mon = _months.get(_combined_m.group(3).lower(), '01')
                    if not invoice.invoiceDate:
                        invoice.invoiceDate = f"{_combined_m.group(2).zfill(2)}/{_mon}/{_combined_m.group(4)}"
                _pending_invoice_id = False  # Not an ID-like value, stop waiting

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
            # Pattern: APR 4TH, 2025 / APR. 04, 2025 / JAN-9-2026
            m = re.search(r"([A-Za-z]{3})\.?[\s\-]*(\d{1,2})(?:ST|ND|RD|TH)?[,\s\-]*(\d{4})", clean, re.I)
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

        # Payment Method: "PAYMENT: T/T" or "Payment method: Wire Transfer"
        if not invoice.paymentMethod:
            m_pm = re.search(
                r'(?:payment\s*(?:method|terms?|by)?|terms?\s+of\s+payment)\s*[:\s]\s*([^\n|]+)',
                clean, re.I
            )
            if m_pm:
                pm_val = m_pm.group(1).strip().strip('*|')
                pm_low = pm_val.lower()
                # Reject bank-related values
                if pm_val and len(pm_val) >= 2 and not any(
                    pm_low.startswith(k) for k in [
                        'beneficiary', 'account', 'bank', 'swift', 'iban',
                        'address', 'room ', 'floor ']):
                    invoice.paymentMethod = pm_val


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

    # ── Two-column pipe-table: Exporter/Shipper | Importer/Consignee ────────
    # Detect side-by-side seller/buyer table and extract fields
    _full_text = '\n'.join(lines)
    _two_col_m = re.search(
        r'\|[ \t]*\*{0,2}(?:Exporter|Shipper|Seller)[/: \t]*(?:Exporter|Shipper|Seller)?\*{0,2}[ \t]*\|'
        r'[ \t]*\*{0,2}(?:Importer|Consignee|Buyer)[/: \t]*(?:Importer|Consignee|Buyer)?\*{0,2}[ \t]*\|',
        _full_text, re.I
    )
    # Also try: | EXPORTER/SHIPPER: | <company_name> | (buyer name in header col1)
    _two_col_header_name = None
    if not _two_col_m:
        _two_col_m2 = re.search(
            r'\|[ \t]*\*{0,2}(?:Exporter|Shipper|Seller)[/: \t]*(?:Exporter|Shipper|Seller)?:?\*{0,2}[ \t]*\|'
            r'[ \t]*([^|\n]+?)[ \t]*\|',
            _full_text, re.I
        )
        if _two_col_m2:
            _two_col_header_name = _two_col_m2.group(1).strip()
            _two_col_m = _two_col_m2  # use this match
    if _two_col_m:
        _after = _full_text[_two_col_m.end():]
        _seller_vals = []
        _buyer_vals = []
        for _tcrow in _after.split('\n'):
            _tcrow = _tcrow.strip()
            if not _tcrow:
                if _seller_vals or _buyer_vals:
                    break  # Empty line after data = end of this table section
                continue  # Skip initial empty lines before data starts
            if not _tcrow.startswith('|'):
                break
            if set(_tcrow).issubset({'|', '-', ' ', ':', '+'}):
                continue
            _tccells = [c.strip().strip('*').strip() for c in _tcrow.split('|')]
            _tccells = [c for c in _tccells if c is not None]
            # Need at least 2 real cells (after splitting, empty strings from leading/trailing |)
            _real = [c for c in _tccells if c != '']
            if len(_real) >= 2:
                _seller_vals.append(_real[0])
                _buyer_vals.append(_real[1])
            elif len(_real) == 1:
                _seller_vals.append(_real[0])
        
        # Classify each value: name, address, phone, email
        if _seller_vals:
            _s_name = None; _s_addr = []; _s_phone = None; _s_email = None
            for v in _seller_vals:
                if re.search(r'@\S+\.\S+', v):
                    _s_email = re.sub(r'^Email:\s*', '', v, flags=re.I).strip()
                elif re.match(r'^(?:Phone:\s*)?[\+]?[\d()][\d()\s\-]{6,18}\d$', v):
                    _s_phone = re.sub(r'^Phone:\s*', '', v).strip()
                elif not _s_name:
                    _s_name = v
                else:
                    # Skip person names (2-word, no digits/commas): "Jane Smith"
                    _words = v.split()
                    _is_person_name = (len(_words) <= 3 and not re.search(r'[\d,]', v)
                                       and not any(k in v.lower() for k in ['street', 'road', 'ave', 'drive', 'blvd', 'suite', 'floor']))
                    if not _is_person_name:
                        _s_addr.append(v)
            if _s_name:
                invoice.sellerName = _s_name
            if _s_addr:
                _new_addr = ', '.join(_s_addr)
                _existing_bad = (not invoice.sellerAddress
                    or '---' in (invoice.sellerAddress or '')
                    or _two_col_header_name  # fallback pattern = block parser data likely wrong
                    or len(_new_addr) > len(invoice.sellerAddress or ''))
                if _existing_bad:
                    invoice.sellerAddress = _new_addr
            if _s_phone and not invoice.sellerPhoneNumber:
                invoice.sellerPhoneNumber = _s_phone
            if _s_email and not invoice.sellerEmail:
                invoice.sellerEmail = _s_email
        
        if _buyer_vals:
            _b_name = None; _b_addr = []; _b_phone = None; _b_email = None
            for v in _buyer_vals:
                if re.search(r'@\S+\.\S+', v):
                    _b_email = re.sub(r'^Email:\s*', '', v, flags=re.I).strip()
                elif re.match(r'^(?:Phone:\s*)?[\+]?[\d()][\d()\s\-]{6,18}\d$', v):
                    _b_phone = re.sub(r'^Phone:\s*', '', v).strip()
                elif not _b_name:
                    _b_name = v
                else:
                    # Skip person names (2-word, no digits/commas): "John Doe"
                    _words = v.split()
                    _is_person_name = (len(_words) <= 3 and not re.search(r'[\d,]', v)
                                       and not any(k in v.lower() for k in ['street', 'road', 'ave', 'drive', 'blvd', 'suite', 'floor']))
                    if not _is_person_name:
                        _b_addr.append(v)
            if _b_name:
                invoice.buyerName = _b_name
            if _b_addr:
                _new_addr = ', '.join(_b_addr)
                if not invoice.buyerAddress or len(_new_addr) > len(invoice.buyerAddress):
                    invoice.buyerAddress = _new_addr
            if _b_phone and not invoice.buyerPhoneNumber:
                invoice.buyerPhoneNumber = _b_phone
            if _b_email and not invoice.buyerEmail:
                invoice.buyerEmail = _b_email

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
        # Only override address if zoom seller name matches existing seller name
        # (prevents zoom text company header from overriding correct address)
        _names_match = (
            _tmp.sellerName and invoice.sellerName and
            (_tmp.sellerName.lower().strip() == invoice.sellerName.lower().strip()
             or _tmp.sellerName.lower() in invoice.sellerName.lower()
             or invoice.sellerName.lower() in _tmp.sellerName.lower())
        )
        # Also reject if zoom address starts with a different company name
        _addr_has_diff_company = False
        if _tmp.sellerAddress and invoice.sellerName:
            _addr_first_part = _tmp.sellerAddress.split(',')[0].strip()
            _sn = invoice.sellerName.lower().strip()
            # If the first address part looks like a company name and doesn't match seller
            if (len(_addr_first_part) > 10 and _addr_first_part.lower() != _sn
                    and _sn not in _addr_first_part.lower()
                    and any(k in _addr_first_part.upper() for k in ['COMPANY', 'CORPORATION', 'CO.', 'LTD',
                                                                      'GROUP', 'JSC', 'INC', 'LLC'])):
                _addr_has_diff_company = True
        if (_tmp.sellerAddress and len(_tmp.sellerAddress) > len(invoice.sellerAddress)
                and _names_match and not _addr_has_diff_company):
            # Don't override if existing address looks like a real address (has digits)
            # and zoom address doesn't have digits (likely company tagline)
            _existing_has_digits = bool(re.search(r'\d', invoice.sellerAddress))
            _zoom_has_digits = bool(re.search(r'\d', _tmp.sellerAddress))
            # Also check if existing address has street-type keywords (real address)
            _street_kw = ['boulevard', 'street', 'road', 'avenue', 'drive', 'lane',
                          'blvd', 'st.', 'rd.', 'ave.', 'dr.', 'block', 'zone',
                          'industrial', 'floor', 'building', 'no.', 'no ']
            _existing_is_street = _existing_has_digits and any(
                k in invoice.sellerAddress.lower() for k in _street_kw
            )
            if not (_existing_has_digits and not _zoom_has_digits) and not _existing_is_street:
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
