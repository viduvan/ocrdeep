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
    
    # Standard fields - ORDER MATTERS! More specific keywords should come first
    # tax_amt must be checked BEFORE amount because "Tax Amount" contains "amount"
    field_keywords = {
        "stt": ["stt", "no.", "no"],
        "name": ["tên hàng", "description", "tên sản phẩm", "diễn giải", "hàng hóa", "nhãn hiệu", "quy cách", "phẩm chất"],
        "code": ["mã số", "mã hàng", "mã sp", "product code", "code"],
        "price": ["đơn giá", "price", "unit price"],
        "tax_amt": ["tiền thuế", "tax amount", "vat amount"],  # BEFORE amount!
        "amount": ["thành tiền", "amount", "trị giá"],  # After tax_amt
        "unit": ["đvt", "đơn vị", "unit"],
        "qty": ["số lượng", "sl", "quantity", "qty"],
        "tax_rate": ["thuế suất", "tax rate", "vat rate"],
        "payment": ["thành tiền sau thuế", "cộng tiền thanh toán", "tổng cộng"] # Sometimes distinct
    }

    # 1. Identify headers to map columns
    header_map = {} # col_index -> field_name
    data_start_idx = 0
    
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
            
            logical_idx += 1
        
        # If we found at least 3 recognizable columns (e.g. Name, Qty, Price), assume this is header
        if matches >= 3:
            header_map = detected_map
            data_start_idx = i + 1
            print(f"DEBUG TABLE PARSER: Header detected at line {i}")
            print(f"  Columns: {cols}")
            print(f"  Header map: {header_map}")
            break
            
    # If no header found, assume standard layout if enough columns
    if not header_map:
        # Check if first row looks like a header (text columns)
        # If not, maybe data starts immediately?
        pass

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
            
        # Check if this is a summary row
        if len(cols) > 0 and any(k in cols[0].lower() for k in ["tổng cộng", "cộng tiền", "thuế suất", "tổng tiền"]):
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
                    if field == "name": item.productName = val
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
            if item.productName and item.productName.isdigit() and len(item.productName) < 3:
                is_col_number_row = True
            
            if not is_col_number_row:
                 items.append(item)

    return items


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

    return items
