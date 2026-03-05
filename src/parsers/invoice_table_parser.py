from bs4 import BeautifulSoup
from typing import List, Optional
import re

from src.schemas.invoice_item import InvoiceItem


# SAFE PARSE HELPERS
def safe_parse_float(value: str) -> Optional[float]:
    """
    Parse float safely.
    Return None if value is not a clean number.
    Handles formats: 49.000,00 or 49,000.00 or 49000
    """
    if not value:
        return None

    v = value.strip()
    if not v:
        return None

    # Strip common currency symbols before parsing
    v = v.lstrip('$€£¥₹₩฿₺₽₱﷼')
    if not v:
        return None

    # If both . and , exist, detect which is thousand separator vs decimal
    # Vietnamese format: 1.234.567,89 (. = thousand, , = decimal)
    # English format: 1,234,567.89 (, = thousand, . = decimal)
    # EDGE CASE: 24.150,000 - comma followed by 3 digits = both are thousand separators
    
    if '.' in v and ',' in v:
        last_dot = v.rfind('.')
        last_comma = v.rfind(',')
        
        # Check what comes after the last comma
        after_comma = v[last_comma + 1:]
        
        if last_comma > last_dot:
            # Comma is last separator
            # If exactly 3 digits after comma: comma is thousand separator (e.g., 24.150,000)
            # If 1-2 digits after comma: comma is decimal separator (e.g., 24.150,50)
            if len(after_comma) == 3 and after_comma.isdigit():
                # Both . and , are thousand separators: 24.150,000 → 24150000
                v = v.replace('.', '').replace(',', '')
            else:
                # Vietnamese decimal format: 1.234,56 → 1234.56
                v = v.replace('.', '').replace(',', '.')
        else:
            # Dot is last separator (English format): 1,234.56 → 1234.56
            v = v.replace(',', '')
    elif ',' in v:
        # Could be thousand sep (1,234) or decimal (1,5)
        parts = v.split(',')
        if len(parts) == 2 and len(parts[1]) <= 2:
            # Likely decimal: 1,50
            v = v.replace(',', '.')
        else:
            # Likely thousand sep: 1,234,567
            v = v.replace(',', '')
    else:
        # Only . or no separator
        # Check if . is decimal or thousand
        if '.' in v:
            parts = v.split('.')
            # FIX: Vietnamese format uses dot as thousand sep even with single dot
            # Examples: "107.800" (1 dot, 3 digits after) = 107800
            #           "1.234.567" (multiple dots, 3-digit groups) = 1234567
            #           "1.5" (1 dot, less than 3 digits after) = 1.5 (decimal)
            
            # Check the LAST part after the last dot
            last_part = parts[-1]
            
            # If last part is exactly 3 digits, dots are thousand separators
            if len(last_part) == 3 and last_part.isdigit():
                v = v.replace('.', '')
            # If multiple dots exist but last part not 3 digits (e.g. 109.258.00), treat last dot as decimal
            elif len(parts) > 2:
                v = "".join(parts[:-1]) + "." + parts[-1]
            # Otherwise, keep as decimal (e.g. "1.5", "1.50")

    # Remove any remaining non-numeric except .
    v = re.sub(r'[^\d.]', '', v)

    if not v or v == '.':
        return None

    try:
        return float(v)
    except Exception:
        return None


def parse_quantity(value: str) -> Optional[float]:
    """
    Parse quantity as float to handle decimals.
    Examples:
    - 10 → 10.0
    - 1.250 → 1250.0 (thousand separator)
    - 6,00 → 6.0 (decimal)
    - 4 x 5 → 20.0
    """
    if not value:
        return None

    v = value.strip()

    # patterns like: 4 x 5, 4×5
    m = re.search(r"(\d+)\s*[x×]\s*(\d+)", v)
    if m:
        return float(int(m.group(1)) * int(m.group(2)))

    # Use safe_parse_float for decimal handling
    result = safe_parse_float(v)
    return result


# MAIN PARSER

    return items


def parse_markdown_table(lines: List[str]) -> List[InvoiceItem]:
    """
    Parse items from markdown-style table lines.
    Format usually:
    | STT | Tên hàng | ĐVT | SL | Đơn giá | Thành tiền | ... |
    """
    items: List[InvoiceItem] = []
    
    field_keywords = {
        "stt": ["stt", "item no", "item id", "#", "marks", "sl. no", "sl no"],
        "name": ["tên hàng", "description", "tên sản phẩm", "diễn giải", "hàng hóa", "nhãn hiệu", "quy cách", "phẩm chất",
                 "specifications", "specification", "规格", "product", "material description",
                 "goods", "commodity", "items", "item"],
        "code": ["mã số", "mã hàng", "mã sp", "product code", "code", "hs code", "tariff",
                 "harm.code", "hts code"],
        # tax_rate MUST come BEFORE price to avoid "Tax Rate" matching "rate" in price
        "tax_rate": ["thuế suất", "tax rate", "vat rate", "vat%", "tax (%)"],
        # tax_amt MUST come BEFORE amount to avoid "Tax Amount" matching "amount"
        "tax_amt": ["tiền thuế", "tax amount", "vat amount"],
        "price": ["đơn giá", "unit price", "单价", "unit value", "rate",
                  "unit cost", "u.price", "price",
                  "unit (usd)", "unit (eur)", "unit (gbp)", "unit ($)", "unit (€)", "unit (£)",
                  "pate"],
        "amount": ["thành tiền", "amount", "atmount", "trị giá", "总计", "total value",
                   "total price", "line total", "total ($)", "total (£)",
                   "tol.amount", "total gross", "value in", "net value", "value",
                   "total (usd)", "total (eur)", "total (gbp)", "total (€)"],
        # qty MUST come BEFORE unit to avoid "NO.OF UNIT" matching "unit" first
        "qty": ["số lượng", "sl", "quantity", "qty", "数量", "no.of unit", "no. of unit",
                "hrs/qty", "pcs"],
        "unit": ["đvt", "đơn vị", "unit of measure"],
        "payment": ["thành tiền sau thuế", "cộng tiền thanh toán", "tổng cộng"],
        "currency_col": ["currency", "货号"],
        "discount": ["discounts", "discount", "chiết khấu", "giảm giá"],
    }

    # 1. Identify headers to map columns
    header_map = {} # col_index -> field_name
    data_start_idx = 0
    
    # Pre-process: join multi-line table cells
    # When a line starts with | but the next line(s) don't start with |,
    # they are continuation of the same cell. Join them.
    joined_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('|'):
            joined_lines.append(line)
        elif joined_lines and not stripped.startswith('---') and stripped:
            # Only treat as continuation if it looks like cell content (not a heading/label)
            # Section headings like "Invoice Summary" should NOT be merged
            _looks_like_heading = (len(stripped.split()) <= 3 and stripped[0].isupper()
                                   and '|' not in stripped and ':' not in stripped
                                   and not re.search(r'\d', stripped))
            if _looks_like_heading:
                joined_lines.append(line)
            else:
                # Continuation line — append to previous pipe-table row
                joined_lines[-1] = joined_lines[-1].rstrip() + ' ' + stripped
        else:
            joined_lines.append(line)
    lines = joined_lines
    
    # Try to find header row
    for i, line in enumerate(lines):
        if "|" not in line:
            continue
            
        # Clean and split
        # Remove outer pipes if strictly formatted, but be loose
        content = line.strip().strip("|")
        cols = [c.strip() for c in content.split("|")]
        
        matches = 0
        detected_map = {}
        
        logical_idx = 0
        for raw_idx, col in enumerate(cols):
            low = col.lower()
            
            # GHOST COLUMN DETECTION:
            # Skip header columns like "Col3" that are OCR artifacts and don't appear in data rows
            # This aligns the map to the actual data columns
            if re.match(r'^col\d+$', low):
                continue
            
            # If not a ghost column, check keywords
            for field, kws in field_keywords.items():
                if any(kw in low for kw in kws):
                    detected_map[logical_idx] = field
                    matches += 1
                    break
            else:
                # Exact match for standalone "Name" column (not "Customer Name", "Bank Name")
                if low.strip() == 'name' or low.strip() == 'product name':
                    detected_map[logical_idx] = 'name'
                    matches += 1
                # Fallback: "total" in column name → amount (if not weight/qty related)
                elif 'total' in low:
                    _weight_words = {'weight', 'kg', 'lb', 'lbs', 'quantity', 'qty', 'pcs', 'units'}
                    _col_words = set(re.findall(r'\w+', low))
                    # "Subtotal" in first column is typically a description column, not amount
                    _is_subtotal_first = (low.strip() == 'subtotal' and logical_idx == 0)
                    if not _col_words.intersection(_weight_words) and not _is_subtotal_first:
                        detected_map[logical_idx] = 'amount'
                        matches += 1
            
            logical_idx += 1
        
        # If we found at least 2 recognizable columns (e.g. Name+Qty, Qty+Price), assume this is header
        if matches >= 2:
            header_map = detected_map
            data_start_idx = i + 1
            
            # Resolve field mapping conflicts:
            price_cols = [idx for idx, f in header_map.items() if f == 'price']
            amount_cols = [idx for idx, f in header_map.items() if f == 'amount']
            
            if len(price_cols) > 1:
                # Multiple 'price' columns (e.g. "Unit Price" + "Price")
                # Keep the FIRST 'price' (usually "Unit Price"), convert the rest to 'amount'
                for idx in price_cols[1:]:
                    header_map[idx] = 'amount'
            elif len(price_cols) == 1 and not amount_cols:
                # Only one 'price' column and NO 'amount' column
                # Check if there's an unmapped "Total" column — if so, keep Price as price
                # and map Total to amount instead
                _has_total_col = False
                _weight_words = {'weight', 'kg', 'lb', 'lbs', 'quantity', 'qty', 'pcs', 'units'}
                _total_col_idx = None
                _logical_idx_tmp = 0
                for _raw_idx_tmp, _col_tmp in enumerate(cols):
                    _low_tmp = _col_tmp.lower().strip()
                    if re.match(r'^col\d+$', _low_tmp):
                        continue
                    if _logical_idx_tmp not in header_map and 'total' in _low_tmp:
                        _words_tmp = set(re.findall(r'\w+', _low_tmp))
                        if not _words_tmp.intersection(_weight_words):
                            _has_total_col = True
                            _total_col_idx = _logical_idx_tmp
                    _logical_idx_tmp += 1
                
                if _has_total_col and _total_col_idx is not None:
                    # Keep Price as 'price', map Total to 'amount'
                    header_map[_total_col_idx] = 'amount'
                else:
                    # Convert to 'amount' ONLY if the column header is standalone "price"
                    # (NOT "unit price", "u.price", etc. which explicitly mean per-item price)
                    col_text = cols[price_cols[0]].lower().strip() if price_cols[0] < len(cols) else ''
                    is_unit_price = any(kw in col_text for kw in ['unit price', 'u.price', 'unit cost', 'đơn giá', '单价'])
                    if not is_unit_price:
                        header_map[price_cols[0]] = 'amount'
            
            # Map unmapped "Total" columns to 'amount' (but NOT "Total Weight", "Total Quantity", etc.)
            amount_cols_after = [idx for idx, f in header_map.items() if f == 'amount']
            if not amount_cols_after:
                _weight_words = {'weight', 'kg', 'lb', 'lbs', 'quantity', 'qty', 'pcs', 'units'}
                logical_idx2 = 0
                for raw_idx2, col2 in enumerate(cols):
                    low2 = col2.lower().strip()
                    if re.match(r'^col\d+$', low2):
                        continue
                    if logical_idx2 not in header_map and 'total' in low2:
                        # Only map if it's NOT a weight/quantity total
                        words_in_col = set(re.findall(r'\w+', low2))
                        if not words_in_col.intersection(_weight_words):
                            header_map[logical_idx2] = 'amount'
                    logical_idx2 += 1
            
            print(f"DEBUG TABLE PARSER: Header detected at line {i}")
            print(f"  Columns: {cols}")
            print(f"  Header map: {header_map}")
            break
            
    # If no header found, assume standard layout if enough columns
    if not header_map:
        # Check if first row looks like a header (text columns)
        # If not, maybe data starts immediately?
        pass
    
    # POST-PROCESS: If column 0 is unmapped and no 'name' exists, infer col 0 as 'name'
    if header_map and 'name' not in header_map.values() and 0 not in header_map:
        header_map[0] = 'name'
        print(f"  Inferred col 0 as name: {header_map}")
    
    # FIX: Detect header-data column misalignment
    # When header has N cols but data rows consistently have N+1 cols,
    # and first data col is text (name/description), shift header_map right by 1
    if header_map and 'name' not in header_map.values():
        header_col_count = max(header_map.keys()) + 1
        # Sample up to 3 data rows
        _sample_rows = []
        for _sl in lines[data_start_idx:]:
            if '|' not in _sl or set(_sl.strip()).issubset({'|', '-', ' ', ':', '+'}):
                continue
            _sc = [c.strip() for c in _sl.strip().strip('|').split('|')]
            if len(_sc) >= 2:
                _sample_rows.append(_sc)
            if len(_sample_rows) >= 3:
                break
        if _sample_rows:
            _avg_data_cols = sum(len(r) for r in _sample_rows) / len(_sample_rows)
            # If data has 1+ more cols than header, and first col looks like text
            if _avg_data_cols >= header_col_count + 0.8:
                _first_cols_are_text = all(
                    not re.match(r'^[\$€£]?\s*[\d,\.]+$', r[0].strip()) and len(r[0].strip()) > 2
                    for r in _sample_rows if r[0].strip()
                )
                if _first_cols_are_text:
                    # Shift header_map right by 1, add name at 0
                    shifted = {k + 1: v for k, v in header_map.items()}
                    shifted[0] = 'name'
                    header_map = shifted
                    print(f"  Header shifted: {header_map}")

    # 2. Parse data rows
    for line in lines[data_start_idx:]:
        if "|" not in line:
            continue
        
        # Skip separator lines like |---|---|
        if set(line.strip()).issubset({"|", "-", " ", ":", "+"}):
            continue
            
        content = line.strip().strip("|")
        cols = [c.strip() for c in content.split("|")]
        
        # Need at least a few columns
        if len(cols) < 2:
            continue
            
        # Check if this is a summary row (Vietnamese + English + Chinese)
        if len(cols) > 0:
            first_low = cols[0].lower().strip().strip('*').strip()
            summary_keywords = [
                # Vietnamese
                "tổng cộng", "cộng tiền", "thuế suất", "tổng tiền",
                # English
                "total", "subtotal", "sub total", "grand total",
                "total amount", "total value", "total this page",
                "consignment total", "invoice total",
                "shipping", "customs/duties", "insurance",
                "other information",
                # EN summary/note rows
                "total vat", "taxfree", "vat on", "a taxfree",
                "due date", "total net value", "total net",
                "§6 ustg", "$6 ustg", "ustg", "exporter",
                "tax due", "tax (", "payment due", "thank you",
                "message", "balance due",
            ]
            # First column check (broad — this is where summary labels usually appear)
            # Only apply to short label-like columns; long descriptions may contain 'total' embedded
            if len(first_low) < 60 and any(k in first_low for k in summary_keywords):
                continue
            # Also check name column if first column is empty (e.g., |  | In Total | ...)
            _name_col_idx = next((k for k, v in header_map.items() if v == 'name'), None)
            if not first_low and _name_col_idx is not None and _name_col_idx < len(cols):
                _name_low = cols[_name_col_idx].lower().strip().strip('*').strip()
                if len(_name_low) < 60 and any(k in _name_low for k in summary_keywords):
                    continue
            
            # Also scan OTHER columns for specific multi-word summary phrases
            # (specific to avoid false positives when 'total gross' appears in data rows)
            extended_summary_phrases = [
                "total vat excluded", "taxfree export", "a taxfree",
                "total net value", "§6 ustg", "ustg is concerned",
                "total gross value",
            ]
            other_cols_text = [c.lower().strip() for c in cols[1:] if c.strip()]
            if any(any(ph in c for ph in extended_summary_phrases) for c in other_cols_text):
                continue
            
            # Item detail sub-rows: "Batch:", "Customs Tariff:", "Country of Origin:"
            # These are continuation rows within an item, not standalone items
            _detail_prefixes = ["batch:", "customs tariff:", "country of origin:",
                                 "batch no", "origin:", "hs:", "tariff:", "siret"]
            # Only skip if detail prefix is at the START of first/second column
            # (standalone detail row), not when embedded in a multi-line product name
            _skip_detail = False
            for ci in range(min(2, len(cols))):
                cl = cols[ci].lower().strip()
                if any(cl.startswith(p) for p in _detail_prefixes):
                    _skip_detail = True
                    break
            if _skip_detail:
                continue
            
            # Chinese sub-header rows: 详细货品描述 | 数量 | 货号 | 单价 | 总计
            # These are translation headers, not data rows
            chinese_header_chars = ['详细', '数量', '单价', '总计', '货号', '货品', '描述',
                                    '规格', '金额', '合计', '价格']
            all_cols_text = ' '.join(cols).lower()
            if any(ch in all_cols_text for ch in chinese_header_chars):
                continue
            
            # Skip header-like rows: "NO" with all other cols empty
            if first_low in ['no', 'no.'] and all(not c.strip() for c in cols[1:]):
                continue
        
        # SKIP SUB-HEADER ROWS: "Thực nhập", "Thực xuất" - these are column sub-headers, not data
        is_subheader = False
        for c in cols:
            clow = c.lower().strip()
            if clow in ["thực nhập", "thực xuất", "số lượng", "đơn giá", "thành tiền"]:
                is_subheader = True
                break
        if is_subheader:
            continue

        # SKIP SUMMARY/TOTAL ROWS: "TOTAL", "SUBTOTAL", "GRAND TOTAL", etc.
        _first_col = cols[0].strip().strip('*').lower() if cols else ''
        _summary_kws = ['total', 'subtotal', 'sub total', 'grand total', 'tổng cộng',
                        'tổng', 'cộng', 'tổng tiền', 'balance due', 'amount due']
        if _first_col in _summary_kws or (not _first_col and len(cols) > 1 and cols[1].strip().strip('*').lower() in _summary_kws):
            continue
        
        # Skip total-in-words rows: "US DOLLARS SIXTY FIVE THOUSAND..."
        # Skip deduction/pct rows: "DEDUCTION OF ADVANCE PAYMENT", "100 PCT. VALUE..."
        if _first_col and any(_first_col.startswith(k) for k in ['us dollar', 'say:', 'say ', 'in words',
                                                                    'deduction']):
            continue
        if _first_col and re.search(r'\bpct\.?\b', _first_col):
            continue

        # SKIP GARBAGE ROW: (1) | (2) | (3)...
        # Check if all columns are essentially numbers wrapped in parens or just numbers/formulas
        # e.g. (1), 1, (2), 2, (7=4x5)
        is_garbage = True
        for c in cols:
            if not c: continue
            clean_c = c.replace("(", "").replace(")", "").strip()
            lower_c = clean_c.lower()
            
            # Use a slightly complex check to allow "garbage" accumulation
            # It IS garbage if:
            # 1. It is a digit: "1", "2"
            # 2. It looks like a formula: "7=4x5", "9=7+8", "x"
            # 3. It is empty
            if not clean_c.isdigit() and \
               "=" not in lower_c and \
               "x" not in lower_c and \
               "+" not in lower_c and \
               len(clean_c) > 1 and \
               clean_c != "":
                is_garbage = False
                break
        if is_garbage:
            continue
            
        item = InvoiceItem()
        
        # If we have a header map, use it
        if header_map:
            # Check bounds
            for idx, field in header_map.items():
                if idx < len(cols):
                    val = cols[idx]
                    if field == "name":
                        # Concatenate multiple name columns (e.g. Name + Description)
                        if val and val.strip():
                            if item.productName:
                                item.productName = item.productName + ' ' + val
                            else:
                                item.productName = val
                    elif field == "code": item.productCode = val
                    elif field == "unit": 
                        # Sanitize: If unit looks like a number (large), it's likely a misaligned Amount
                        f_unit = safe_parse_float(val)
                        if f_unit is not None and f_unit > 1000:
                             item.unit = None
                        else:
                             item.unit = val
                    elif field == "qty": item.quantity = parse_quantity(val)
                    elif field == "price": item.unitPrice = safe_parse_float(val)
                    elif field == "amount": item.amount = safe_parse_float(val)
                    elif field == "tax_rate": 
                        if not val and idx + 1 < len(cols) and "%" in cols[idx+1]:
                            item.discountPercent = cols[idx+1]
                        else:
                            item.discountPercent = val
                    elif field == "payment": item.payment = safe_parse_float(val)
            
            # Fix: when data row has fewer cells than header (e.g., empty Tax col collapsed),
            # try the last cell as 'amount' if it looks like money
            if not item.amount and 'amount' in header_map.values():
                _amt_idx = [k for k, v in header_map.items() if v == 'amount']
                if _amt_idx and _amt_idx[0] >= len(cols) and len(cols) > 0:
                    _last_cell = cols[-1]
                    _amt_val = safe_parse_float(_last_cell)
                    if _amt_val is not None and _amt_val > 0:
                        item.amount = _amt_val
            
            # Misaligned data fix: if data row has more columns than header,
            # check if trailing extra columns contain price/amount values
            max_header_idx = max(header_map.keys()) if header_map else 0
            if len(cols) > max_header_idx + 1:  # At least 1 extra column
                extra_cols = cols[max_header_idx + 1:]
                # Check if extra cols look like price/amount (contain /KG, $, or are numbers)
                for ec in extra_cols:
                    ec_stripped = ec.strip()
                    if '/' in ec_stripped and re.search(r'\d', ec_stripped):
                        # Looks like unit price: "2.62/KG"
                        price_val = safe_parse_float(re.sub(r'/.*', '', ec_stripped))
                        if price_val is not None:
                            item.unitPrice = price_val
                    else:
                        # Handle European format with space thousands: "1 297,45"
                        _ec_clean = re.sub(r'\s+', '', ec_stripped)  # Remove spaces
                        if re.match(r'^[\$€£¥]?[\d,\.]+$', _ec_clean):
                            amt_val = safe_parse_float(_ec_clean)
                            if amt_val is not None and amt_val > (item.amount or 0):
                                # Move current amount to unitPrice if missing
                                if item.amount and not item.unitPrice:
                                    item.unitPrice = item.amount
                                item.amount = amt_val

        else:
            # Fallback: Assume standard position 
            # 0: STT, 1: Name, 2: Unit, 3: Qty, 4: Price, 5: Amount
            # BUT sometimes Unit is missing or merged. 
            # Heuristic: Check column count
            
            # Simple assumption for 6+ columns
            if len(cols) >= 6:
                item.productName = cols[1]
                f_unit = safe_parse_float(cols[2])
                if f_unit is not None and f_unit > 1000:
                     item.unit = None
                else:
                     item.unit = cols[2]
                item.quantity = parse_quantity(cols[3])
                item.unitPrice = safe_parse_float(cols[4])
                item.amount = safe_parse_float(cols[5])
            
            # For 5 columns: STT | Name | Qty | Price | Amount (Unit missing?)
            elif len(cols) == 5:
                 item.productName = cols[1]
                 item.quantity = parse_quantity(cols[2])
                 item.unitPrice = safe_parse_float(cols[3])
                 item.amount = safe_parse_float(cols[4])

        # Validate item: Must have at least a Name or an Amount
        # AND name shouldn't be just a number (like "1" if STT was misparsed as Name)
        if item.productName or item.amount:
            is_col_number_row = False
            pname = (item.productName or "").strip()
            
            # Skip if name is just a number (STT misparsed as Name)
            if pname and pname.isdigit() and len(pname) < 4:
                is_col_number_row = True
            
            # Skip if name looks like a price ("$50.00", "€100")
            if pname and re.match(r'^[\$€£¥]?[\d,\.]+$', pname):
                is_col_number_row = True
            
            # Skip if name is a summary keyword
            pname_low = pname.lower().strip('*').strip()
            if pname_low in ["total", "subtotal", "sub total", "grand total",
                            "total amount", "tổng cộng", "cộng", "tổng",
                            "in total", "total value", "-", "—"]:
                is_col_number_row = True
            
            if not is_col_number_row:
                 # CONTINUATION ROW MERGE: if previous item has data but a code-name (pure number)
                 # and this row has a real name but no data -> merge
                 if (items and 
                     item.productName and
                     not item.amount and item.quantity is None and item.unitPrice is None and
                     items[-1].productName and re.match(r'^[\d\.\,]+$', items[-1].productName.strip())):
                     # Previous item has a numeric name (product code) — replace with this real name
                     items[-1].productName = item.productName
                 else:
                     items.append(item)
            elif is_col_number_row and item.amount and (item.unitPrice or item.quantity):
                # Item with numeric name (product code) may still carry valid price/qty data
                # But NOT if name is a summary keyword (In Total, Grand Total, etc.)
                _is_summary_name = pname_low in ["total", "subtotal", "sub total", "grand total",
                                                   "total amount", "tổng cộng", "cộng", "tổng",
                                                   "in total", "total value", "-", "—"]
                if not _is_summary_name:
                    # Keep it with the code as name temporarily (continuation row may follow)
                    items.append(item)

    # Deduplicate: remove items with identical (productName, qty, amount, unitPrice)
    seen = set()
    deduped = []
    for item in items:
        key = (item.productName, item.quantity, item.amount, item.unitPrice)
        if key not in seen:
            seen.add(key)
            deduped.append(item)
    
    # Filter out items where ALL numeric fields are None and name is a pure number
    deduped = [
        it for it in deduped
        if not (re.match(r'^[\d\.\,]+$', (it.productName or '').strip()) and
                it.amount is None and it.quantity is None and it.unitPrice is None)
    ]
    
    return deduped
def parse_structured_items(raw_text: str) -> List[InvoiceItem]:
    """
    Parse items from non-table structured text formats.
    Handles:
    1. Bold label+value pairs: **Description**\nProduct 1\n**Quantity**\n1\n**Unit Price**\n50
    2. Inline product lines: ProductName  qty  price  amount (tab/multi-space separated)
    3. Numbered items with qty/price on adjacent lines
    """
    items: List[InvoiceItem] = []
    lines = raw_text.split('\n')

    # --- Pattern 1: Bold label + value pairs ---
    # Look for **Description** / **Quantity** / **Unit Price** / **Total Price** blocks
    desc_labels = ['description', 'product', 'goods']
    qty_labels = ['quantity', 'qty']
    price_labels = ['unit price', 'unit-price', 'price']
    amount_labels = ['total price', 'total', 'amount']

    i = 0
    found_label_pattern = False
    while i < len(lines):
        line = lines[i].strip()
        # Strip markdown bold markers
        clean = re.sub(r'\*\*([^*]+)\*\*', r'\1', line).strip()
        low = clean.lower()

        # Check if this line is a description label
        if any(low == lbl or low == lbl + ':' for lbl in desc_labels):
            found_label_pattern = True
            item = InvoiceItem()
            # Next non-empty line is the product name
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines):
                name_line = re.sub(r'\*\*([^*]+)\*\*', r'\1', lines[j].strip()).strip()
                if name_line and not any(name_line.lower().startswith(lbl) for lbl in qty_labels + price_labels + amount_labels):
                    item.productName = name_line
                    j += 1

            # Look for Quantity, Unit Price, Total Price in subsequent label-value pairs
            while j < len(lines):
                lbl_line = re.sub(r'\*\*([^*]+)\*\*', r'\1', lines[j].strip()).strip()
                lbl_low = lbl_line.lower()

                if any(lbl_low == q or lbl_low == q + ':' for q in qty_labels):
                    j += 1
                    while j < len(lines) and not lines[j].strip():
                        j += 1
                    if j < len(lines):
                        item.quantity = parse_quantity(re.sub(r'\*\*([^*]+)\*\*', r'\1', lines[j].strip()).strip())
                        j += 1
                elif any(lbl_low == p or lbl_low == p + ':' for p in price_labels):
                    j += 1
                    while j < len(lines) and not lines[j].strip():
                        j += 1
                    if j < len(lines):
                        item.unitPrice = safe_parse_float(re.sub(r'\*\*([^*]+)\*\*', r'\1', lines[j].strip()).strip())
                        j += 1
                elif any(lbl_low == a or lbl_low == a + ':' for a in amount_labels):
                    j += 1
                    while j < len(lines) and not lines[j].strip():
                        j += 1
                    if j < len(lines):
                        item.amount = safe_parse_float(re.sub(r'\*\*([^*]+)\*\*', r'\1', lines[j].strip()).strip())
                        j += 1
                elif any(lbl_low.startswith(d) for d in desc_labels):
                    # New item description — stop here
                    break
                elif lbl_low.startswith('---') or lbl_low.startswith('other') or lbl_low.startswith('subtotal') or lbl_low.startswith('tax'):
                    break
                else:
                    j += 1

            if item.productName:
                items.append(item)
            i = j
        else:
            i += 1

    if found_label_pattern and items:
        return items

    # --- Pattern 1b: Columnar bold headers then values ---
    # **Description** / **Quantity** / **Unit Price** / **Total Price** on consecutive lines
    # then blank line, then **Product 1** / 1 / 50 / $50.00 on consecutive lines
    all_field_labels = {
        'name': ['description', 'product', 'goods', 'product name', 'item'],
        'qty': ['quantity', 'qty', 'number of packages'],
        'weight': ['weight', 'net weight', 'gross weight'],
        'price': ['unit price', 'unit-price', 'price', 'rate'],
        'amount': ['total price', 'total', 'amount', 'total amount'],
    }
    
    # Scan for a block of consecutive bold labels
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        clean = re.sub(r'\*\*([^*]+)\*\*', r'\1', line).strip()
        low = clean.lower()
        
        # Check if this looks like a known field label
        matched_type = None
        for ftype, labels in all_field_labels.items():
            if any(low == lbl or low == lbl + ':' for lbl in labels):
                matched_type = ftype
                break
        
        if matched_type:
            # Collect consecutive labels
            col_order = [matched_type]
            j = i + 1
            while j < len(lines):
                lline = lines[j].strip()
                lclean = re.sub(r'\*\*([^*]+)\*\*', r'\1', lline).strip()
                llow = lclean.lower()
                if not lline:
                    break  # blank line = end of header block
                lt = None
                for ftype, labels in all_field_labels.items():
                    if any(llow == lbl or llow == lbl + ':' for lbl in labels):
                        lt = ftype
                        break
                if lt:
                    col_order.append(lt)
                    j += 1
                else:
                    break
            
            # Need at least 2 column headers (e.g., Description + Quantity)
            if len(col_order) >= 2 and 'name' in col_order:
                # Skip blank lines
                while j < len(lines) and not lines[j].strip():
                    j += 1
                
                # Collect data blocks (items separated by blank lines)
                while j < len(lines):
                    data_vals = []
                    while j < len(lines) and lines[j].strip():
                        val_line = re.sub(r'\*\*([^*]+)\*\*', r'\1', lines[j].strip()).strip()
                        # Stop at summary labels
                        vlow = val_line.lower()
                        if any(k in vlow for k in ['other information', 'subtotal', 'tax rate',
                                                     'tax due', 'signature', 'total', 'notes']):
                            break
                        data_vals.append(val_line)
                        j += 1
                    
                    if data_vals and len(data_vals) >= 2:
                        item = InvoiceItem()
                        for idx, col_type in enumerate(col_order):
                            if idx >= len(data_vals):
                                break
                            val = data_vals[idx]
                            if col_type == 'name':
                                item.productName = val
                            elif col_type == 'qty':
                                item.quantity = parse_quantity(val)
                            elif col_type == 'price':
                                item.unitPrice = safe_parse_float(val)
                            elif col_type == 'amount':
                                item.amount = safe_parse_float(val)
                        if item.productName:
                            items.append(item)
                    
                    # Skip blank lines between items
                    while j < len(lines) and not lines[j].strip():
                        j += 1
                    # Check if next block is still data (not a label/summary)
                    if j < len(lines):
                        next_clean = re.sub(r'\*\*([^*]+)\*\*', r'\1', lines[j].strip()).strip().lower()
                        if any(k in next_clean for k in ['other information', 'subtotal', 'tax',
                                                          'signature', 'total', 'notes']):
                            break
                
                if items:
                    return items
        i += 1

    # --- Pattern 1c: Sequential heading-based items after "Product Code" ---
    # Format: ### Product Code\n2216\n### Lightbulb 2 x 37 watt\n1000\n### Elecwire 20m\n450
    # Only fires after finding "Product Code" marker, stops at aggregate labels
    if not items:
        _stop_labels = {'unit quantity', 'quantity', 'price', 'unit price', 'amount',
                        'total', 'total amount', 'total this page', 'consignment total',
                        'invoice total', 'additional information', 'bank details',
                        'place and date of issue', 'signature company', 'signature',
                        'name of authorized signatory'}
        # Find "Product Code" line
        start_idx = None
        for idx, line in enumerate(lines):
            clean_l = re.sub(r'^#+\s*', '', line.strip())
            clean_l = re.sub(r'\*\*([^*]+)\*\*', r'\1', clean_l).strip()
            if clean_l.lower() == 'product code' and idx + 1 < len(lines):
                # Skip the Product Code value line
                start_idx = idx + 2
                break
        
        if start_idx is not None:
            i = start_idx
            while i < len(lines) - 1:
                line = lines[i].strip()
                clean = re.sub(r'^#+\s*', '', line)
                clean = re.sub(r'\*\*([^*]+)\*\*', r'\1', clean).strip()
                low = clean.lower()
                # Stop at aggregate/summary labels
                if low in _stop_labels or line == '---':
                    break
                # Skip pipe table lines
                if line.startswith('|') or not clean:
                    i += 1
                    continue
                # Check if next line is a pure number (the amount)
                next_line = lines[i + 1].strip()
                next_clean = re.sub(r'^#+\s*', '', next_line).strip()
                next_val = safe_parse_float(next_clean)
                if next_val is not None and next_val > 0 and not next_line.startswith('|'):
                    # Only count if the name has letters and isn't a known label
                    if re.search(r'[A-Za-z]', clean) and len(clean) > 2 and low not in _stop_labels:
                        item = InvoiceItem()
                        item.productName = clean
                        item.amount = next_val
                        items.append(item)
                        i += 2
                        continue
                i += 1
            if items:
                return items

    # --- Pattern 2: Freeform product lines with amounts ---
    # Lines like: "COCONUT SAP AND EXTRACT (CLASS A)\n16,200KG\nUSD 0.60/KG\nUSD 9,720"
    # Or: "1. FROZEN CHICKEN MDM\n  20KG × 2,000CARTONS\n  46,000KG\n  USD 0.65\n  USD 29,900"
    product_pattern = re.compile(
        r'^(?:\d+[\.\)]\s*)?(?:\*\*)?([A-Z][A-Z\s,\.\-\(\)\/\&]+?)(?:\*\*)?\s*$'
    )
    amount_pattern = re.compile(
        r'(?:USD|EUR|GBP|£|\$|€)\s*([\d,\.]+(?:\.\d+)?)|'
        r'([\d,\.]+)\s*(?:USD|EUR|GBP)'
    )
    qty_pattern = re.compile(
        r'([\d,\.]+)\s*(?:KG|PCS|SETS?|UNITS?|EACH|CARTONS?|MTS?|ROLLS?|BOXES?|LBS)',
        re.I
    )

    pending_name = None
    pending_item = None

    for line in lines:
        clean = line.strip()
        if not clean:
            if pending_item and pending_item.productName:
                # Don't finalize if still missing amount — item data may continue after blank line
                if pending_item.amount:
                    items.append(pending_item)
                    pending_item = None
                    pending_name = None
                # else: keep pending through blank line
            continue

        # Skip separators, headers, summary rows
        low = clean.lower().strip('*').strip()
        if clean.startswith('---') or clean.startswith('#'):
            continue
        if any(k in low for k in ['total', 'subtotal', 'say:', 'made in', 'signature']):
            if pending_item and pending_item.productName:
                items.append(pending_item)
                pending_item = None
                pending_name = None
            continue

        # Check for product name (uppercase text, possibly numbered)
        pm = product_pattern.match(clean)
        if pm and len(pm.group(1).strip()) > 5:
            if pending_item and pending_item.productName:
                items.append(pending_item)
            pending_item = InvoiceItem(productName=pm.group(1).strip())
            continue

        if pending_item:
            # Try to extract qty
            qm = qty_pattern.search(clean)
            if qm:
                new_qty = parse_quantity(qm.group(1))
                if new_qty and (not pending_item.quantity or new_qty > pending_item.quantity):
                    pending_item.quantity = new_qty

            # Try to extract amount/price
            am = amount_pattern.search(clean)
            if am:
                val = safe_parse_float(am.group(1) or am.group(2))
                if val:
                    if '/' in clean and not pending_item.unitPrice:
                        # "USD 0.65/KG" = unit price
                        pending_item.unitPrice = val
                    elif not pending_item.amount:
                        pending_item.amount = val
                    elif pending_item.amount and val > pending_item.amount * 10:
                        # New value much larger → current amount was actually unitPrice
                        if not pending_item.unitPrice:
                            pending_item.unitPrice = pending_item.amount
                        pending_item.amount = val
                    elif not pending_item.unitPrice:
                        pending_item.unitPrice = val

    if pending_item and pending_item.productName:
        items.append(pending_item)

    # Only return if we found meaningful items (with at least a name + one numeric field)
    meaningful = [it for it in items if it.productName and (it.quantity or it.unitPrice or it.amount)]
    return meaningful


def parse_items_from_table(raw_text: str) -> List[InvoiceItem]:
    items: List[InvoiceItem] = []
    
    # 1. HTML Table
    if "<table" in raw_text:
        soup = BeautifulSoup(raw_text, "html.parser")
        table = soup.find("table")
        if not table:
            return items

        rows = table.find_all("tr")

        # Detect header row to understand column structure
        header_row_idx = 0
        
        # skip đúng 1 header (hoặc 2 nếu có dòng số cột)
        for row in rows[1:]:
            cols = [c.get_text(strip=True) for c in row.find_all("td")]

            if len(cols) < 6:
                continue

            # bỏ dòng đánh số cột (1 | 2 | 3 | 4 | 5) hoặc ((1) | (2) | (3))
            first_col = cols[0].strip("()")
            if first_col.isdigit() and all(c.strip("()").isdigit() or "=" in c or "x" in c.lower() for c in cols[:5]):
                continue

            # Bỏ các dòng tổng hợp
            if any(k in cols[0].lower() for k in ["tổng hợp", "cộng tiền", "thuế suất", "không chịu thuế", "không kê khai"]):
                continue

            # Parse item
            quantity = parse_quantity(cols[3])
            unit_price = safe_parse_float(cols[4])
            amount = safe_parse_float(cols[5])
            
            # Skip if all numerical values are None (empty row)
            if quantity is None and unit_price is None and amount is None:
                continue

            # Sanitize Unit (HTML)
            unit_val = cols[2] if cols[2] else None
            if unit_val:
                 f_unit = safe_parse_float(unit_val)
                 if f_unit is not None and f_unit > 1000:
                     unit_val = None
            
            item = InvoiceItem(
                productName=cols[1] if cols[1] else None,
                unit=unit_val,
                quantity=quantity,
                unitPrice=unit_price,
                amount=amount,
            )

            # Nếu bảng có nhiều hơn 6 cột (có thêm thuế suất, tiền thuế, thành tiền sau thuế)
            if len(cols) >= 8:
                # Cột 6: Thuế suất, Cột 7: Tiền thuế
                tax_percent = cols[6].strip() if cols[6] else None
                tax_amount = safe_parse_float(cols[7])
                
                if tax_percent:
                    item.discountPercent = tax_percent  # Reuse field for tax info display
                
            if len(cols) >= 9:
                # Cột 8: Thành tiền sau thuế = payment
                payment = safe_parse_float(cols[8])
                if payment:
                    item.payment = payment

            items.append(item)
            
    # 2. Markdown Table (if HTML didn't work or wasn't present)
    if not items and "|" in raw_text:
        lines = raw_text.split('\n')
        items = parse_markdown_table(lines)

    # 3. Structured non-table items (fallback for bold-label/value, freeform product lines)
    if not items:
        items = parse_structured_items(raw_text)

    return items

