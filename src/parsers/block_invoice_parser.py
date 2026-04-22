import re
from typing import List, Dict
from src.schemas.invoice import Invoice
from src.schemas.invoice_item import InvoiceItem
from src.parsers.invoice_table_parser import parse_items_from_table, safe_parse_float
from src.utils.text_extractors import extract_phone


# Vietnamese number words to digits converter
def vietnamese_words_to_number(text: str) -> float:
    """
    Convert Vietnamese number words to numeric value.
    Example: "Ba trăm bảy mươi triệu bốn trăm bốn mươi nghìn đồng" -> 370440000
    """
    if not text:
        return 0
    
    text = text.lower().strip()
    # Remove common prefixes/suffixes
    text = re.sub(r'^[\*\s]+', '', text)
    text = text.replace('đồng', '').replace('chẵn', '').replace('.', '').replace(',', '').strip()
    
    # Number word mappings - digits 0-9
    digits = {
        'không': 0, 'một': 1, 'hai': 2, 'ba': 3, 'bốn': 4, 'năm': 5,
        'sáu': 6, 'bảy': 7, 'tám': 8, 'chín': 9,
        'linh': 0, 'lẻ': 0, 'mốt': 1, 'lăm': 5, 'tư': 4
    }
    
    # Large multipliers
    large_mult = {
        'nghìn': 1000, 'ngàn': 1000,
        'triệu': 1000000,
        'tỷ': 1000000000, 'tỉ': 1000000000
    }
    
    words = text.split()
    result = 0
    current_group = 0  # Current group value (before nghìn/triệu/tỷ)
    
    i = 0
    while i < len(words):
        word = words[i]
        
        # Check if it's a digit
        if word in digits:
            digit = digits[word]
            # Look ahead for trăm/mươi/mười
            if i + 1 < len(words):
                next_word = words[i + 1]
                if next_word == 'trăm':
                    current_group += digit * 100
                    i += 2
                    continue
                elif next_word in ['mươi', 'mười']:
                    current_group += digit * 10
                    i += 2
                    continue
            # Just a unit digit
            current_group += digit
        
        # Handle standalone "mười" (10)
        elif word == 'mười':
            current_group += 10
        
        # Handle standalone "mươi" after a digit (should not happen normally)
        elif word == 'mươi':
            pass  # Already handled in lookahead
        
        # Handle "trăm" after a digit (should not happen normally)
        elif word == 'trăm':
            pass  # Already handled in lookahead
        
        # Handle large multipliers
        elif word in large_mult:
            mult = large_mult[word]
            if current_group == 0:
                current_group = 1  # "một triệu" without "một"
            result += current_group * mult
            current_group = 0
        
        i += 1
    
    # Add remaining group
    result += current_group
    
    return float(result) if result > 0 else 0


def clean_invoice_total_in_word(text: str) -> str:
    """
    Clean invoiceTotalInWord by removing garbage text like:
    - Markdown separators: |||||
    - Footer text: Người mua hàng, Tra cứu, Phát hành bởi, etc.
    - URLs and signatures
    """
    if not text:
        return ""
    
    # Remove markdown table separators
    text = text.replace('|', ' ')
    
    # Remove \n and multiple spaces
    text = re.sub(r'\\n', ' ', text)
    text = re.sub(r'\n', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    
    # Stop at common footer/garbage markers
    stop_markers = [
        'người mua hàng', 'người bán hàng', 'tra cứu', 'website', 
        'phát hành bởi', 'chữ ký', 'misa', 'viettel', 'vnpt',
        'cần kiểm tra', 'đối chiếu', 'https://', 'http://', 'www.',
        '(ký,', '_', '*', 'customer', 'seller', 'buyer'
    ]
    
    text_lower = text.lower()
    for marker in stop_markers:
        pos = text_lower.find(marker)
        if pos > 10:  # Only cut if marker is after some content
            text = text[:pos]
            text_lower = text.lower()
    
    # Clean up
    text = text.strip().rstrip('.,:;')
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Remove trailing garbage like "chẵn" duplicates
    text = re.sub(r'(chẵn)\s*\.?\s*$', r'\1', text, flags=re.I)
    
    return text


def number_to_vietnamese_words(number: float) -> str:
    """
    Convert numeric value to Vietnamese number words.
    Example: 370440000 -> "Ba trăm bảy mươi triệu bốn trăm bốn mươi nghìn đồng"
    """
    if not number or number <= 0:
        return ""
    
    number = int(number)
    
    # Guard: số quá lớn (> 999 tỷ) → likely misparse, skip
    if number > 999_999_999_999:
        return ""
    
    # Digit words
    digits = ['không', 'một', 'hai', 'ba', 'bốn', 'năm', 'sáu', 'bảy', 'tám', 'chín']
    
    def convert_group(n: int) -> str:
        """Convert a 3-digit group to words"""
        if n == 0:
            return ""
        
        result = []
        hundreds = n // 100
        tens = (n % 100) // 10
        units = n % 10
        
        # Hundreds
        if hundreds > 0:
            result.append(digits[hundreds])
            result.append("trăm")
        
        # Tens
        if tens > 0:
            if tens == 1:
                result.append("mười")
            else:
                result.append(digits[tens])
                result.append("mươi")
            
            # Units after tens
            if units > 0:
                if units == 1 and tens > 1:
                    result.append("mốt")
                elif units == 5 and tens >= 1:
                    result.append("lăm")
                elif units == 4 and tens > 1:
                    result.append("tư")
                else:
                    result.append(digits[units])
        elif units > 0:
            # Units only (no tens)
            if hundreds > 0:
                result.append("lẻ")
            result.append(digits[units])
        
        return " ".join(result)
    
    # Split into groups: tỷ, triệu, nghìn, đơn vị
    ty = number // 1000000000
    trieu = (number % 1000000000) // 1000000
    nghin = (number % 1000000) // 1000
    donvi = number % 1000
    
    parts = []
    
    if ty > 0:
        parts.append(convert_group(ty) + " tỷ")
    
    if trieu > 0:
        parts.append(convert_group(trieu) + " triệu")
    elif ty > 0 and (nghin > 0 or donvi > 0):
        # Need placeholder "không trăm" if skipping triệu
        pass
    
    if nghin > 0:
        parts.append(convert_group(nghin) + " nghìn")
    elif (ty > 0 or trieu > 0) and donvi > 0:
        # Need placeholder for nghìn if skipping
        pass
    
    if donvi > 0:
        parts.append(convert_group(donvi))
    
    result = " ".join(parts).strip()
    
    # Capitalize first letter
    if result:
        result = result[0].upper() + result[1:]
        result += " đồng"
    
    return result


def number_to_english_words(number: float) -> str:
    """
    Convert numeric value to English number words.
    Example: 1234.56 -> "One thousand two hundred thirty-four and fifty-six cents"
    """
    if not number or number <= 0:
        return ""

    ones = ["", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
            "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"]
    tens = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
    thousands = ["", "thousand", "million", "billion", "trillion"]

    def convert_to_words(n: int) -> str:
        if n == 0:
            return ""
        elif n < 20:
            return ones[n]
        elif n < 100:
            return tens[n // 10] + (("-" + ones[n % 10]) if n % 10 != 0 else "")
        elif n < 1000:
            return ones[n // 100] + " hundred" + ((" and " + convert_to_words(n % 100)) if n % 100 != 0 else "")
        else:
            for i, unit in enumerate(thousands):
                if i == 0: continue
                if n < 1000**(i+1):
                    return convert_to_words(n // 1000**i) + " " + unit + ((" , " + convert_to_words(n % 1000**i)) if n % 1000**i != 0 and i > 0 else ((" " + convert_to_words(n % 1000**i)) if n % 1000**i != 0 else ""))
            return str(n) # Fallback for extremely large numbers

    # Handle large numbers safely
    if number > 999_999_999_999_999:
        return ""

    int_part = int(number)
    decimal_part = int(round((number - int_part) * 100))

    result = convert_to_words(int_part).strip()
    if result:
        result = result[0].upper() + result[1:]

    if decimal_part > 0:
        dec_words = convert_to_words(decimal_part).strip()
        if result:
            result += f" and {dec_words} cents"
        else:
            result = f"{dec_words[0].upper() + dec_words[1:]} cents"
    elif result:
        result += " only"

    return result.replace(" , ", ", ")


def english_words_to_number(text: str) -> float:
    """
    Convert English number words to numeric value.
    Example: "twenty five thousand six hundred thirty four and cents twenty eight" -> 25634.28
    """
    if not text:
        return 0.0
    
    ones = {'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
            'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
            'eleven': 11, 'twelve': 12, 'thirteen': 13, 'fourteen': 14,
            'fifteen': 15, 'sixteen': 16, 'seventeen': 17, 'eighteen': 18, 'nineteen': 19}
    tens_map = {'twenty': 20, 'thirty': 30, 'forty': 40, 'fifty': 50,
                'sixty': 60, 'seventy': 70, 'eighty': 80, 'ninety': 90}
    scales = {'hundred': 100, 'thousand': 1000, 'million': 1_000_000, 'billion': 1_000_000_000}
    
    # Clean and normalize
    text = text.lower().strip()
    # Remove currency prefixes
    text = re.sub(r'^(?:us\s+)?(?:dollars?|vnd|eur|gbp|usd)\s*', '', text, flags=re.I).strip()
    
    # Split on "and cents" or "point" for decimal
    int_text = text
    dec_val = 0
    # Pattern A: "cents twenty six" (cents before number words)
    m_cents = re.search(r'\b(?:and\s+)?cents?\s+(.+?)(?:\s+only)?$', text, re.I)
    # Pattern B: Split on currency word + "and" (e.g., "five euros and twenty cents")
    m_currency_split = re.search(r'\b(?:dollars?|euros?|pounds?)\s+and\s+', text, re.I)
    # Pattern C: "and twenty six cents" (number words before cents) — only match last 1-3 words before "cents"
    m_cents2 = re.search(r'\b(?:and\s+)?((?:(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)\s*){1,3})\s+cents?(?:\s+only)?$', text, re.I)
    # Priority: currency split > cents-before-words > words-before-cents
    if m_currency_split:
        int_text = text[:m_currency_split.start()].strip()
        dec_text = text[m_currency_split.end():].strip()
        dec_text = re.sub(r'\s+only\s*$', '', dec_text, flags=re.I).strip()
        dec_text = re.sub(r'\s*cents?\s*$', '', dec_text, flags=re.I).strip()
        dec_val = _parse_word_group(dec_text, ones, tens_map, scales)
    elif m_cents:
        int_text = text[:m_cents.start()].strip()
        dec_text = m_cents.group(1).strip()
        dec_val = _parse_word_group(dec_text, ones, tens_map, scales)
    elif m_cents2:
        int_text = text[:m_cents2.start()].strip()
        dec_text = m_cents2.group(1).strip()
        dec_val = _parse_word_group(dec_text, ones, tens_map, scales)
    
    # Remove "only" suffix
    int_text = re.sub(r'\s+only\s*$', '', int_text, flags=re.I).strip()
    # Remove trailing "and"
    int_text = re.sub(r'\s+and\s*$', '', int_text).strip()
    
    int_val = _parse_word_group(int_text, ones, tens_map, scales)
    
    if dec_val > 0:
        return int_val + dec_val / 100.0
    return float(int_val)


def _parse_word_group(text: str, ones: dict, tens_map: dict, scales: dict) -> int:
    """Parse a group of English number words into an integer."""
    text = text.lower().strip()
    text = re.sub(r'[,\-]', ' ', text)
    words = text.split()
    
    current = 0
    result = 0
    
    for word in words:
        word = word.strip()
        if not word or word in ('and', 'a'):
            continue
        if word in ones:
            current += ones[word]
        elif word in tens_map:
            current += tens_map[word]
        elif word == 'hundred':
            current *= 100
        elif word == 'thousand':
            current *= 1000
            result += current
            current = 0
        elif word == 'million':
            current *= 1_000_000
            result += current
            current = 0
        elif word == 'billion':
            current *= 1_000_000_000
            result += current
            current = 0
    
    return result + current


SELLER_LABEL_KEYS = {
    "sellerName": ["tên đơn vị bán", "đơn vị bán", "đơn vị bán hàng", "comname", "dơn vị bán hàng",
                   "bên a (bên bán)", "bên bán", "bên a",
                   "người bán",  # Case 171: "Người bán: Tan TinCay Partners"
                   # EN Commercial Invoice labels
                   "the seller", "shipper", "beneficiary", "exporter",
                   "sender", "sender name", "sender/exporter", "vendor/exporter",
                   "ship from", "bill from", "shipper/exporter",
                   "company name", "exporter name", "signatory company",
                   "shipper name", "from",
                   # Customs/shipping FROM: section labels
                   "full name"],
    "sellerTaxCode": ["mã số thuế", "tax code", "mst", "vat:",
                      # EN labels
                      "tax id", "tax id/vat", "vat reg no", "vat reg no.",
                      "eori", "gst no"],
    "sellerAddress": ["địa chỉ", "address",
                      # EN labels
                      "street address", "company address", "registered address",
                      # Customs/shipping labels
                      "adresse line", "adresse", "address line"],
    "sellerPhoneNumber": ["điện thoại", "tel", "số điện thoại", "phone", "phone number"],
    "sellerBankAccountNumber": ["số tài khoản", "bankno", "account no", "ac no", "stk",
                                "beneficiary's account", "account number"],
    "sellerBank": ["ngân hàng", "bankname", "tại ngân hàng", "bank:",
                   "beneficiary's bank", "bank name"],
    "sellerEmail": ["email"],
}

BUYER_LABEL_KEYS = {
    "buyerName": ["tên đơn vị mua", "đơn vị mua", "buyer", "cusname", "tên đơn vị",
                  "company's name", "the buyer", "đơn vị (co. name)", "co. name",
                  "bên b (bên mua)", "bên mua", "bên b",
                  # EN Commercial Invoice labels
                  "consignee", "consigned to", "sold to", "bill to",
                  "ship to", "importer", "importer name",
                  "recipient", "recipient/ship to",
                  "customer", "customer name",
                  "invoice to", "delivery details", "notify party",
                  # Customs/shipping TO: section labels
                  "full name", "company name"],
    "buyerTaxCode": ["mã số thuế", "tax code", "mst",
                     # EN labels
                     "importer vat reg no", "importer eori", "tax id"],
    "buyerAddress": ["địa chỉ", "address",
                     # EN labels
                     "delivery address", "ship-to address", "shipping address",
                     "ship to add",
                     # Customs/shipping labels
                     "adresse line", "adresse", "address line"],
    "buyerEmail": ["email"],
    "buyerPhoneNumber": ["điện thoại", "tel", "số điện thoại", "phone", "phone number"],
}



def clean_lines(raw_text: str) -> List[str]:
    lines = []
    
    # Xử lý escape sequences từ OCR output
    # Replace escaped \\n with actual newlines
    text = raw_text.replace('\\n', '\n')
    
    # Remove OCR metadata tags: <|ref|>...<|/ref|><|det|>...<|/det|>
    text = re.sub(r'<\|ref\|>.*?<\|/ref\|><\|det\|>.*?<\|/det\|>', '', text)
    
    # Remove remaining OCR tags
    text = re.sub(r'<\|[^>]+\|>', '', text)
    
    # Remove markdown bold markers **text**
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    
    # Remove markdown headers ## 
    text = re.sub(r'^#+\s*', '', text, flags=re.MULTILINE)
    
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        # bỏ markdown/table separator
        if re.fullmatch(r"\|[-\s|]+\|", line):
            continue
        
        # Skip quote marks at start/end
        if line in ['"', "'"]:
            continue

        # Strip leading/trailing quote characters (OCR artifact from text wrapped in quotes)
        # Only strip if the quote is NOT matched (i.e., orphan quote at start or end)
        if line.startswith('"') and not line.endswith('"'):
            line = line[1:].strip()
        elif line.endswith('"') and not line.startswith('"'):
            line = line[:-1].strip()
        
        if not line:
            continue

        lines.append(line)
    return lines

def detect_blocks(lines: List[str]) -> Dict[str, List[str]]:
    blocks = {
        "seller": [],
        "header": [],
        "buyer": [],
        "table": [],
        "total": [],
        "signature": [],
    }
    
    # Filter out ZOOM TEXT section — it duplicates data and causes double items
    filtered_lines = []
    for line in lines:
        if '--- ZOOM TEXT ---' in line or '---ZOOM TEXT---' in line:
            break  # Stop processing at ZOOM TEXT marker
        if '--- ZOOM RIGHT ---' in line or '---ZOOM RIGHT---' in line:
            break  # Stop processing at ZOOM RIGHT marker (Case 171)
        filtered_lines.append(line)
    lines = filtered_lines
    
    # Filter out subsequent pages — they typically contain certificates, not invoice data
    page1_lines = []
    for line in lines:
        if re.search(r'^---\s*PAGE\s+[2-9]\d*\s*---', line.strip(), re.I):
            break
        page1_lines.append(line)
    lines = page1_lines

    current = "seller"
    seen_header = False
    seen_table = False
    seen_buyer = False  # Track if we've entered buyer section
    seen_seller_after_buyer = False  # Track if seller appeared after buyer
    
    for line in lines:
        l = line.lower().strip()

        # ===== HEADER (CHỈ KHI GẶP HÓA ĐƠN hoặc PHIẾU) =====
        # Note: Title may be split across lines like "# HÓA ĐƠN\nGIÁ TRỊ GIA TĂNG"
        # GUARD: Do NOT reclassify pipe-table rows as header when already in table mode
        # (e.g. product name "Kỳ hóa đơn" contains "hóa đơn" but is a data row)
        if current != "table" and not (seen_table and l.startswith("|")) and (any(k in l for k in [
            "hóa đơn",                  # Added: partial match for multi-line titles
            "hòa đơn",                  # Case 171: OCR misspelling with grave accent
            "phiếu xuất kho",            # Added: Internal transfer slips
            "phiếu nhập kho",            # Added: Internal receipt slips
            "phiếu bán hàng",             # Added: Sales slips
            "biên bản hủy",               # Added: Invoice cancellation documents
            "biên bản",                   # Added: General documents
            "vat invoice",
            "commercial invoice",         # EN: COMMERCIAL INVOICE
            "proforma invoice",           # EN: PROFORMA INVOICE
            "pro forma invoice",          # EN: PRO FORMA INVOICE
            "tax invoice",                # EN: TAX INVOICE
            "kí hiệu",
            "ký hiệu",
            "mẫu số",
            "invoice no",
            "inv. no",                    # EN: INV. NO.
            "invoice number",             # EN: Invoice Number
            "invoice #",                  # EN: Invoice #
            "serial no",
            "s/c no",                     # Added for Case 4
            "inv. date",                  # Added for Case 4
        ]) or (
            # Standalone "## INVOICE" heading (markdown format, no prefix like COMMERCIAL/TAX)
            l.lstrip('#').strip() == 'invoice'
        )):
            current = "header"
            seen_header = True

        # ===== SELLER (sau header - format header-first) =====
        # Khi thấy "đơn vị bán hàng" sau header, chuyển về seller block
        # HOẶC nếu đang ở Header mà thấy MST/Địa chỉ/SĐT (dấu hiệu seller info) thì chuyển sang Seller
        # Support English: "THE Seller:", "SHIPPER" and Vietnamese: "BÊN A (Bên bán)"
        elif any(k in l for k in ["đơn vị bán hàng", "seller:", "seller :", "the seller:", "bên a (bên bán)", "bên bán)", "bên a:",
                                    "người bán:",  # Case 171: "Người bán: Tan TinCay Partners"
                                    "shipper", "寄货人",
                                    # EN Commercial Invoice seller section labels
                                    "exporter:", "exporter details", "sender/exporter",
                                    "ship from", "bill from", "shipper/exporter",
                                    "vendor/exporter", "sender name",
                                    # Customs/shipping invoice FROM: section
                                    "from:", "from :"]):
            current = "seller"
            if seen_buyer:
                seen_seller_after_buyer = True

        # ===== BUYER (KHÔNG CẦN SEEN_HEADER) =====
        # Chuyển sang buyer khi gặp keywords chỉ người mua
        # Support English: "THE Buyer:", "CONSIGNEE" and Vietnamese: "Người mua (Buyer):", "Khách hàng:", "BÊN B (Bên mua)"
        elif any(k in l for k in [
            "khách hàng",           # Added: Vietnamese for "Customer"
            "họ tên người mua",
            "tên người mua",       # Added: "Tên người mua:"
            "người mua hàng",
            "người mua:",          # Case 171: exact match with colon to avoid matching "người mua hàng"
            "người mua",
            "buyer:",
            "buyer :",
            "the buyer:",
            "customer's name",
            "customer:",
            "bill to",              # Added: English "Bill to:" pattern
            # Customs/shipping invoice TO: section
            "to :", "to:",
            "nhập tại kho",        # Added: For internal transfer slips
            "bên b (bên mua)",     # Added: For BIÊN BẢN HỦY HÓA ĐƠN
            "bên mua)",            # Added: Partial match
            "bên b:",              # Added: For BIÊN BẢN
            "consignee",           # EN: CONSIGNEE = Buyer
            "consigned to",        # EN: Consigned to = Buyer
            "收货人",               # CN: 收货人 = Consignee
            # EN Commercial Invoice buyer section labels
            "sold to",
            "ship to",
            "importer:",
            "importer details",
            "recipient",
            "invoice to",
            "notify party",
            "delivery details",
            "customer's details",
            "applicant:",
            "the applicant",
            "for account and risk",       # L/C: "For account and risk of Messrs:"
            "messrs:",
        ]):
            current = "buyer"
            seen_buyer = True

        # ===== TOTAL (High Priority) =====
        # Check this BEFORE Table block to ensure summary rows with pipes (e.g. |Tổng tiền:|) switch to Total
        elif seen_table and (
            any(k in l for k in [
                "tông cộng", "tổng tiền", "số tiền viết bằng chữ", "cộng tiền hàng", "total amount", "khách hàng đã thanh toán", "thuế suất",
                "total unit", "total value", "total qty", "grand total"
            ]) or (re.search(r'\btotal\b', l) and not l.startswith('|'))
        ):
            current = "total"
            
        # ===== TABLE (Identify by HTML or Markdown) =====
        elif "<table>" in l or l.startswith("|"):
            # Only switch to table if we are NOT already in total/signature
            # AND not in buyer/seller mode (pipe-table rows continuing seller/buyer content)
            if current not in ["total", "signature"]:
                if current in ["buyer", "seller"]:
                    # Stay in buyer/seller mode for pipe-table continuation
                    # Only switch to table if line looks like a real table header
                    _has_table_header_kw = any(k in l for k in [
                        "description", "quantity", "unit price", "amount",
                        "tên hàng", "đơn vị", "đơn giá", "thành tiền",
                        "marks", "package", "weight", "total price"
                    ])
                    if _has_table_header_kw:
                        current = "table"
                        seen_table = True
                    # else: stay in current buyer/seller mode
                else:
                    # Before defaulting to table, check if this pipe row contains
                    # seller/buyer keywords (e.g. L/C-style numbered-label tables)
                    _pipe_seller_kws = ["beneficiary", "exporter", "seller", "shipper",
                                        "người bán", "đơn vị bán"]
                    _pipe_buyer_kws = ["applicant", "importer", "buyer", "consignee",
                                       "người mua", "đơn vị mua"]
                    if any(k in l for k in _pipe_seller_kws):
                        current = "seller"
                    elif any(k in l for k in _pipe_buyer_kws):
                        current = "buyer"
                        seen_buyer = True
                    else:
                        current = "table"
                        seen_table = True

        # ===== SIGNATURE (CHỈ CUỐI) =====
        elif seen_table and any(k in l for k in [
            "signature valid",
            "ký bởi",
            "signed",
            "(ký, ghi rõ họ tên)",
            "tra cứu",
            "website:",
            "phát hành bởi",
            "được ký bởi",
            "mã số bí mật",
            "chuỗi xác thực",
            "trang 1/1"
        ]):
            current = "signature"

        elif (current == "header" and any(k in l for k in ["mã số thuế", "địa chỉ", "điện thoại", "tax code", "address", "website",
                                                            "phone", "tel:", "fax:", "email"])) \
              and not seen_buyer:
            current = "seller"
            # Retroactively move preceding header lines (company name, address) to seller
            # Move lines back to the last '---' separator or header keyword
            header_block = blocks.get("header", [])
            move_lines = []
            for j in range(len(header_block) - 1, -1, -1):
                hl = header_block[j].strip().lower()
                if hl == '---' or hl == '' or any(k in hl for k in ['invoice', 'logo', 'hóa đơn', 'phiếu']):
                    break
                move_lines.insert(0, header_block.pop(j))
            blocks["seller"].extend(move_lines)

        # ===== STAY IN BUYER BLOCK if we've seen buyer marker =====
        # Các dòng sau "Họ tên người mua" thuộc buyer block
        elif seen_buyer and current == "seller" and not seen_seller_after_buyer:
            current = "buyer"

        blocks[current].append(line)
        

    return blocks


def extract_email(text: str) -> str:
    """Extract email from text"""
    m = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
    return m.group(0) if m else None


def parse_serial_form_no(value: str) -> tuple:
    """
    Tách Serial Number: "1C25THO" → (invoiceSerial="1", invoiceFormNo="C25THO")
    Pattern: số đầu + phần còn lại (bắt đầu bằng chữ)
    """
    if not value:
        return None, None
    
    value = value.strip()
    
    # Pattern: số đầu + chữ cái + phần còn lại
    # Ví dụ: 1C25THO, 1C25TTD, 1K25MDT
    m = re.match(r'^(\d+)([A-Za-z].*)$', value)
    if m:
        return m.group(1), m.group(2)
    
    # Fallback: trả về nguyên giá trị cho invoiceSerial
    return value, None


def parse_header(block: List[str], invoice: Invoice):
    serial_parsed = False  # Track if we already parsed the main serial
    _prev_line = ''
    
    for line in block:
        up = line.upper()
        low = line.lower()

        # Tên hóa đơn - chỉ lấy dòng chính
        # Note: Title may be split like "# HÓA ĐƠN" then "GIÁ TRỊ GIA TĂNG"
        # Tên hóa đơn - chỉ lấy dòng chính
        # Note: Title may be split like "# HÓA ĐƠN" then "GIÁ TRỊ GIA TĂNG"
        # FIX: Allow lines containing "GIÁ TRỊ" to be appended even if they don't have "HÓA ĐƠN"
        # Match invoice types: HÓA ĐƠN, PHIẾU XUẤT KHO, VAT INVOICE, etc.
        invoice_type_keywords = ["HÓA ĐƠN", "VAT INVOICE", "PHIẾU XUẤT KHO", "PHIẾU NHẬP KHO", "PHIẾU BÁN HÀNG",
                                 "COMMERCIAL INVOICE", "PROFORMA INVOICE", "TAX INVOICE"]
        is_invoice_title = any(kw in up for kw in invoice_type_keywords)
        is_continuation = "GIÁ TRỊ" in up and invoice.invoiceName
        # Reject footer/disclaimer lines that happen to contain "hóa đơn"
        _footer_kws = ["kiểm tra", "đối chiếu", "tra cứu", "phát hành bởi",
                       "cần kiểm tra", "giao nhận", "thay thế", "mã nhận",
                       "trang trả cứu", "bản thể hiện"]
        _is_footer = any(fk in low for fk in _footer_kws)
        
        if (is_invoice_title or is_continuation) and "thay thế" not in low and not _is_footer:
            # Clean markdown header markers
            name = line.strip().lstrip("# ").strip()
            # For "COMMERCIAL INVOICE - No20250321003", strip the No... part for invoiceName
            name_clean = re.sub(r'\s*[-–—]\s*No\.?\s*[A-Z0-9]+$', '', name, flags=re.I).strip()
            if name_clean:
                # Clean pipe-table formatting: "| THE SELLER: | PROFORMA INVOICE |" → "PROFORMA INVOICE"
                if '|' in name_clean:
                    _pipe_cells = [c.strip() for c in name_clean.split('|') if c.strip()]
                    _inv_keywords = ['INVOICE', 'HÓA ĐƠN', 'PHIẾU', 'VAT INVOICE']
                    for _pc in _pipe_cells:
                        if any(kw in _pc.upper() for kw in _inv_keywords):
                            name_clean = _pc.strip()
                            break
                if not invoice.invoiceName:
                    invoice.invoiceName = name_clean
                elif "GIÁ TRỊ" in up and "GIÁ TRỊ" not in invoice.invoiceName.upper():
                    # Concatenate second line of split title
                    invoice.invoiceName = invoice.invoiceName + " " + name_clean
                elif "KIÊM" in up and "KIÊM" not in invoice.invoiceName.upper():
                    # Handle "PHIẾU XUẤT KHO" + "KIÊM VẬN CHUYỂN NỘI BỘ"
                    invoice.invoiceName = invoice.invoiceName + " " + name_clean
            
            # Extract invoiceID from "INVOICE - No20250321003" format
            if not invoice.invoiceID:
                m_inv = re.search(r'INVOICE\s*[-–—]\s*No\.?\s*([A-Z0-9]+)', name, re.I)
                if m_inv:
                    invoice.invoiceID = m_inv.group(1)
        
        # Standalone alphanumeric ID line after invoice title (e.g. "1156/LY")
        if not invoice.invoiceID and invoice.invoiceName:
            val_clean = line.strip().strip('*').strip('#').strip()
            # Must look like an ID: alphanumeric with / or -, 3-15 chars, not a date
            # Also reject if previous line was a L/C or tracking label
            _prev_low = _prev_line.lower().strip('*').strip() if _prev_line else ''
            _is_lc_or_tracking = any(k in _prev_low for k in [
                'letter of credit', 'l/c number', 'l/c no', 'awb', 'tracking',
                'air waybill', 'bill of lading', 'b/l no', 'currency',
                'account number', 'account no', 'swift', 'iban', 'reference'
            ])
            # Reject values that start with known non-invoice prefixes
            _is_non_invoice_prefix = bool(re.match(r'^(?:AWB|BL|LC|B/L)\d', val_clean, re.I))
            if (val_clean and re.match(r'^[A-Za-z0-9][\w\-/]{2,14}$', val_clean)
                    and re.search(r'\d', val_clean)
                    and not re.match(r'^\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}$', val_clean)
                    and val_clean.lower() not in ('original', 'copy', 'page', 'draft')
                    and 'invoice' not in val_clean.lower()
                    and not _is_lc_or_tracking
                    and not _is_non_invoice_prefix):
                invoice.invoiceID = val_clean

        # Date: Ngày 18 tháng 12 năm 2025
        # Date: Ngày (date) 20 tháng (month) 10 năm (year) 2025
        # Date: Ngày 23...tháng...03...năm 20...21... (handwritten with dots)
        m = re.search(r"Ngày.*?(\d{1,2}).*?tháng.*?(\d{1,2}).*?năm.*?(\d{2,4})[\.\.\s]*(\d{0,2})", line, re.I)
        if m and not invoice.invoiceDate:
            year = m.group(3) + (m.group(4) or '')
            if len(year) == 4:
                invoice.invoiceDate = f"{m.group(1).zfill(2)}/{m.group(2).zfill(2)}/{year}"
        
        # English date patterns: Date: 2025/12/1, Date: 2025-12-01
        if not invoice.invoiceDate:
            m = re.search(r"[Dd]ate[:\s]+(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})", line)
            if m:
                invoice.invoiceDate = f"{m.group(3).zfill(2)}/{m.group(2).zfill(2)}/{m.group(1)}"
        
        # English date: Date: MM/DD/YYYY or Date: DD/MM/YYYY
        if not invoice.invoiceDate:
            m = re.search(r"[Dd]ate[:\s]+(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})", line)
            if m:
                p1, p2, yyyy = int(m.group(1)), int(m.group(2)), m.group(3)
                if p1 > 12:  # p1 must be day
                    invoice.invoiceDate = f"{str(p1).zfill(2)}/{str(p2).zfill(2)}/{yyyy}"
                else:  # assume MM/DD/YYYY (US format)
                    invoice.invoiceDate = f"{str(p2).zfill(2)}/{str(p1).zfill(2)}/{yyyy}"
        
        # English date: DEC. 01, 2025 or Dec 1, 2025
        if not invoice.invoiceDate:
            months = {'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04', 'may': '05', 'jun': '06',
                      'jul': '07', 'aug': '08', 'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12'}
            m = re.search(r"([A-Za-z]{3})\.?\s*(\d{1,2}),?\s*(\d{4})", line)
            if m:
                month_abbr = m.group(1).lower()[:3]
                if month_abbr in months:
                    invoice.invoiceDate = f"{m.group(2).zfill(2)}/{months[month_abbr]}/{m.group(3)}"
        
        # English date: 10.JULY.2014 or 10-July-2014 (DD.MONTH.YYYY)
        if not invoice.invoiceDate:
            months_full = {'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04', 'may': '05', 'jun': '06',
                           'jul': '07', 'aug': '08', 'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12'}
            m = re.search(r"(\d{1,2})[.\-/]([A-Za-z]{3,9})[.\-/](\d{4})", line)
            if m:
                month_abbr = m.group(2).lower()[:3]
                if month_abbr in months_full:
                    invoice.invoiceDate = f"{m.group(1).zfill(2)}/{months_full[month_abbr]}/{m.group(3)}"


        # Form No (mẫu số) - ít dùng trong hóa đơn điện tử mới
        # Skip lines containing "hóa đơn bị hủy" - these reference cancelled invoices
        # Skip lines containing "điều chỉnh" - these reference the original invoice, not the current one
        if ("mẫu số" in low and "hóa đơn bị hủy" not in low 
                and "hoá đơn bị huỷ" not in low and "điều chỉnh" not in low):
            m = re.search(r":\s*(\S+)", line)
            if m:
                invoice.invoiceFormNo = m.group(1)

        # Serial - ĐÂY LÀ TRƯỜNG QUAN TRỌNG
        # Pattern: Ký hiệu (Serial No): 1C25TTD, Kí hiệu(Serial): 1C25THO
        # Pattern variations: "Ký hiệu: 1C24THO", "Ký hiệu 1C24THO", "Ký hiệu:1C24THO"
        # BỎ QUA dòng "Thay thế cho Hóa đơn...", "Hóa đơn bị hủy", "Điều chỉnh" vì đây không phải serial chính
        if (("ký hiệu" in low or "kí hiệu" in low or "serial" in low) and 
            not serial_parsed and 
            "hóa đơn bị hủy" not in low and "hoá đơn bị huỷ" not in low
            and "điều chỉnh" not in low):
            # Skip các dòng thay thế
            if "thay thế" in low:
                continue
            
            # Tìm pattern: Ký hiệu (Serial No)[: ]+ VALUE
            # \s*[:\s]+ means match colon or spaces acting as separator
            m = re.search(r"(?:ký hiệu|kí hiệu|serial)[^:\d]*[:\s]+([A-Z0-9/\-]+)", line, re.I)
            if m:
                serial_value = m.group(1).strip()
                # Additional check: Serial usually has at least 3 chars and contains letters
                if len(serial_value) >= 3:
                    serial, form_no = parse_serial_form_no(serial_value)
                    invoice.invoiceSerial = serial
                    if form_no and not invoice.invoiceFormNo:
                        invoice.invoiceFormNo = form_no
                    serial_parsed = True

        if not invoice.invoiceID:
            # Pattern: Số (No.): 1004 or Số: 3
            # Allow "Số", "So", "NO", "No."
            # EXCLUDE: STT (No.), table headers, "Mẫu số"
            clean_line = line.strip()
            is_table_header = "stt" in low or "|" in line or "mẫu số" in low or "mẫu" in low
            if re.match(r'^(?:Số|So|No\.?)\b', clean_line, re.I) and "tài khoản" not in low and "tiền" not in low and not is_table_header:
                # Handle markdown formatting: **00000438** and alphanumeric IDs like INV-40885
                m = re.search(r"(?:Số|So|No\.?)[^:]*[:\s]+\*{0,2}([A-Za-z0-9][\w\-/]*)\*{0,2}", clean_line, re.I)
                if m:
                    # Reject if followed by address text (e.g. "No. 7 Bang Lang 1 Street")
                    _after_id = clean_line[m.end():].strip().lower()
                    _addr_kws = ['street', 'road', 'lane', 'ward', 'district', 'city', 'building',
                                 'floor', 'block', 'avenue', 'blvd', 'bang', 'đường', 'phố', 'ngõ',
                                 'phường', 'quận', 'huyện', 'tầng', 'tòa', 'thôn', 'xã']
                    if not any(ak in _after_id for ak in _addr_kws):
                        invoice.invoiceID = m.group(1)
            elif ("invoice no" in low or "invoice number" in low) and "stt" not in low:
                # Reject instructional text like "Please include invoice number on your payment"
                _instruction_kws = ['include', 'reference', 'quote', 'provide', 'mention', 'state', 'note']
                _is_instruction = any(ik in low for ik in _instruction_kws)
                if not _is_instruction:
                    m = re.search(r"(?<!PROFORMA )(?:Invoice\s*No\.?|Invoice\s*Number)[:\s]*\*{0,2}\s*([A-Za-z0-9][\w\-/]*)\*{0,2}", line, re.I)
                    if m and len(m.group(1)) >= 2:
                        invoice.invoiceID = m.group(1)
                    elif m and len(m.group(1)) == 1:
                        # Single digit likely instruction number — next line has actual ID
                        invoice._pending_invoice_id = True
        
        # Handle pending invoice ID from previous line (value-on-next-line pattern)
        if getattr(invoice, '_pending_invoice_id', False) and not invoice.invoiceID:
            val_clean = line.strip().strip('*').strip()
            if val_clean and re.match(r'^[A-Za-z0-9][\w\-/]+$', val_clean) and len(val_clean) >= 3:
                invoice.invoiceID = val_clean
                invoice._pending_invoice_id = False
        # Fallback Seller Name in Header (for plain text header-first layouts)
        # e.g. "CÔNG TY CỔ PHẦN VẬT LIỆU..." appearing in header block
        if not invoice.sellerName and "CÔNG TY" in up:
             # Exclude signature-related text and buyer/invoice title
             signature_exclude = ["ký bởi", "được ký", "signature", "người mua", "buyer"]
             is_signature = any(kw in low for kw in signature_exclude)
             if "HÓA ĐƠN" not in up and ":" not in line and not is_signature:
                 invoice.sellerName = line.strip()
        
        _prev_line = line


def parse_seller(lines: List[str], invoice: Invoice):
    pending_field = None
    first_line_checked = False
    _prev_line = ''

    for line in lines:
        clean = line.strip().replace("**", "")
        low = clean.lower()
        matched = False
        
        # ===== ĐẶC BIỆT: Dòng đầu tiên có thể là tên công ty (không có label) =====
        if not first_line_checked:
            first_line_checked = True
            is_keyword = any(k in low for k in ["hóa đơn", "phiếu", "mẫu số", "ký hiệu", "liên", "date", "ngày", "số:", "no:",
                                                    "invoice", "from:", "from :", "to:", "to :",
                                                    "sub total", "subtotal", "total amount", "total price",
                                                    "shipping fee", "sales tax", "purpose of",
                                                    "signature", "acknowledge"])
            is_header_label = any(k in low for k in ["information", "寄货人", "资料", "收货人", "shipper", "consignee",
                                                       "shippes", "country of", "seller", "exporter"])
            # Skip table lines (|...|), markdown headers still present, and overly long lines
            is_table_line = clean.startswith("|")
            is_too_long = len(clean) > 80
            # Skip page separator lines like "--- PAGE 1 ---"
            is_page_separator = bool(re.match(r'^---\s*PAGE\s+\d+\s*---$', clean, re.I))
            if (not is_keyword and not is_header_label and not is_table_line and not is_too_long
                    and not is_page_separator
                    and ":" not in clean and len(clean) > 3):
                if not invoice.sellerName:
                    invoice.sellerName = clean
                    pending_field = "sellerAddress"
                    continue
                elif clean.strip() == invoice.sellerName.strip():
                    # First line matches already-set sellerName → address follows
                    pending_field = "sellerAddress"
                    continue

        # ===== EMAIL (có thể xuất hiện trên cùng dòng với phone) =====
        email = extract_email(clean)
        if email and not invoice.sellerEmail:
            invoice.sellerEmail = email

        for field, keys in SELLER_LABEL_KEYS.items():
            if any(k in low for k in keys):
                # Clear pending_field when we match a new labeled field
                pending_field = None


                # ===== PHONE =====
                if field == "sellerPhoneNumber":
                    # Fix: If Email is on the same line, split it out before extracting phone
                    temp_clean = clean
                    if "Email" in clean:
                         temp_clean = clean.split("Email")[0]
                    elif "Website" in clean:
                         temp_clean = clean.split("Website")[0]
                    
                    # FIX: Extract phone AFTER the label keyword to avoid MST confusion
                    # First try: "Phone number: +33-6-56-78-90-67" or "Phone number: 0935868885"
                    if ":" in temp_clean:
                        phone_val_raw = temp_clean.split(":", 1)[-1].strip().lstrip("- ")
                        # Match international format: +XX-X-XX-XX-XX-XX or +XX (X) XXXX-XXXX
                        if re.match(r'\+?[\d\s\-\(\)\.]{7,}$', phone_val_raw):
                            phone_clean = phone_val_raw.strip()
                            if len(re.sub(r'[^\d]', '', phone_clean)) >= 7:
                                invoice.sellerPhoneNumber = phone_clean
                    
                    # Pattern: "Mã số thuế: 0108921542 Số điện thoại: 0935868885"
                    if not invoice.sellerPhoneNumber:
                        phone_match = re.search(r"(?:số điện thoại|điện thoại|tel)[:\s]*(\d{9,11})", temp_clean, re.I)
                        if phone_match:
                            invoice.sellerPhoneNumber = phone_match.group(1)
                    
                    if not invoice.sellerPhoneNumber:
                        # Fallback: Try to get any 10-digit number starting with 0
                        m_phone = re.search(r"(?:^|\D)(0\d{9,10})(?:\D|$)", temp_clean)
                        if m_phone:
                            # Make sure it's not the same as tax code
                            if m_phone.group(1) != invoice.sellerTaxCode:
                                invoice.sellerPhoneNumber = m_phone.group(1)
                    
                    if not invoice.sellerPhoneNumber:
                        # Try international format: (84 - 24) 3 747 6666 or (84-24) 37476666
                        m_intl = re.search(r"\(?\d{2,3}\s*[-\s]\s*\d{2,3}\)?\s*[\d\s]+", temp_clean)
                        if m_intl:
                            phone_val = m_intl.group(0).strip()
                            if len(phone_val.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")) >= 8:
                                invoice.sellerPhoneNumber = phone_val
                    
                    if not invoice.sellerPhoneNumber:
                        phone = extract_phone(temp_clean)
                        if phone and phone != invoice.sellerTaxCode:
                            invoice.sellerPhoneNumber = phone
                    
                    # If nothing was extracted and line has no colon (standalone label "Phone"),
                    # set pending_field so the next line is treated as the phone value
                    if not invoice.sellerPhoneNumber and ":" not in clean:
                        pending_field = "sellerPhoneNumber"
                    
                    matched = True
                    # Continue to next field key, do NOT fall through to NORMAL FIELD
                    continue

                # ===== EMAIL =====
                if field == "sellerEmail":
                    email = extract_email(clean)
                    if email and not invoice.sellerEmail:
                        invoice.sellerEmail = email
                    matched = True
                    # Continue to next field key, do NOT fall through to NORMAL FIELD
                    continue

                # ===== TAX CODE =====
                if field == "sellerTaxCode":
                    m = re.search(r"(\d{10,14}(-\d+)?)", clean)
                    if m:
                        invoice.sellerTaxCode = m.group(1)
                    matched = True
                    if m:
                        invoice.sellerTaxCode = m.group(1)
                    matched = True
                    # Tax Code usually distinct, but safer to allow continuation just in case
                    continue

                # ===== BANK ACCOUNT =====
                if field == "sellerBankAccountNumber":
                    # Pattern: Số tài khoản: 1011000633804 Ngân hàng: ABC
                    # Pattern: Số tài khoản (AC No): 19134220914019 Tại Ngân hàng Techcombank
                    # Pattern: Số tài khoản: 031-01-01-048-3872 - Ngân hàng MSB
                    
                    # Tìm số tài khoản (Updated to ignore (text) before colon)
                    m_acc = re.search(r"(?:số tài khoản|stk|ac no)(?:\s*\(.*?\))?[:\s]*([0-9\.\-]+)", clean, re.I)
                    if m_acc:
                        invoice.sellerBankAccountNumber = m_acc.group(1).replace(".", "")
                    
                    # Tìm tên ngân hàng (Updated to catch "Tại:" and full string)
                    # Use \b to avoid matching "BankNo" as "Bank"
                    m_bank = re.search(r"(?:ngân hàng|tại ngân hàng|\bbank\b(?!no)|\btại\b|\bat\b)[:\s]*([^\n]+)", clean, re.I)
                    if m_bank and not invoice.sellerBank:
                        bank_val = m_bank.group(1).strip(" :-")
                        # Clean common prefixes like "(At)"
                        bank_val = re.sub(r"^\(?At\)?", "", bank_val, flags=re.I).strip(" :-")
                        if bank_val:
                            invoice.sellerBank = bank_val
                    
                    matched = True
                    matched = True
                    # Continue to next field key
                    continue
                    
                # ===== SELLER NAME - Special handling for BÊN A pattern =====
                if field == "sellerName":
                    # Pattern: "BÊN A (Bên bán): CÔNG TY CỔ PHẦN VẬT LIỆU HOME"
                    # Need to extract the company name after the last colon
                    if "bên a" in low or "bên bán" in low:
                        # Find position after last colon
                        colon_idx = clean.rfind(":")
                        if colon_idx != -1:
                            value = clean[colon_idx + 1:].strip()
                            if value and ("công ty" in value.lower() or "doanh nghiệp" in value.lower()):
                                invoice.sellerName = value
                                matched = True
                                break
                    # Also handle standard pattern with single colon
                    value = clean.split(":", 1)[-1].strip()
                    if value and ("công ty" in value.lower() or "doanh nghiệp" in value.lower() or len(value) > 5):
                        if not invoice.sellerName:
                            invoice.sellerName = value
                        matched = True
                        break
                    elif value:
                        if not invoice.sellerName:
                            pending_field = field
                    else:
                        # Empty value after colon (e.g., "Exporter:") → name on next line
                        if not invoice.sellerName:
                            pending_field = field
                    matched = True
                    break

                # ===== NORMAL FIELD =====
                if ":" in clean:
                    value = clean.split(":", 1)[-1].strip()
                    if value:
                        setattr(invoice, field, value)
                        # Keep pending for address fields to allow continuation
                        if "Address" in field:
                            pending_field = field
                    else:
                        pending_field = field
                else:
                    # No colon: this is a standalone label (e.g. "Address" on its own line)
                    # The value will be on the next line
                    pending_field = field

                matched = True
                break

        # ===== CONTINUATION LINE =====
        # Skip markdown separator lines (---) — they are not content
        if not matched and pending_field and clean and re.fullmatch(r'-{2,}', clean.strip()):
            continue
        if not matched and pending_field and clean:
            # Stop at standalone labels (no colon) - re-match for new field
            _seller_standalone_labels = {'phone', 'email', 'tel', 'fax', 'contact person', 'address',
                                         'company name', 'full name', 'phone number', 'adresse',
                                         'invoice', 'bill', 'receipt', 'commercial invoice'}
            if low.strip('- ') in _seller_standalone_labels:
                # This line IS a new label — find which field it maps to
                new_field = None
                for f2, keys2 in SELLER_LABEL_KEYS.items():
                    if any(k in low for k in keys2):
                        new_field = f2
                        break
                pending_field = new_field  # Set new pending, or None if no match
                matched = True
            else:
                current_val = getattr(invoice, pending_field, None) or ""
                # If this line looks like email/phone, don't append to address
                _is_email_phone = ('@' in clean or 'email' in low or '.com' in low or '.org' in low
                                   or re.match(r'^[\[\(]?\s*(?:sender|client)?\.?email', low))
                if _is_email_phone and 'Address' in pending_field:
                    # Set as sellerEmail instead of appending to address
                    if not invoice.sellerEmail and '@' in clean:
                        invoice.sellerEmail = clean
                    pending_field = None
                    matched = True
                elif current_val:
                    # Validate phone values: must contain digits before appending
                    if 'Phone' in pending_field:
                        _digit_count = len(re.sub(r'[^\d]', '', clean))
                        if _digit_count < 7:
                            continue
                    setattr(invoice, pending_field, current_val.rstrip(', ').rstrip(',') + ", " + clean)
                else:
                    # Validate phone values: must contain enough digits
                    if 'Phone' in pending_field:
                        _digit_count = len(re.sub(r'[^\d]', '', clean))
                        if _digit_count < 7:
                            # Not a phone number — skip and keep pending
                            continue
                    setattr(invoice, pending_field, clean)
                    # After setting sellerName via continuation, expect address next
                    if pending_field == "sellerName":
                        pending_field = "sellerAddress"
                        matched = True
                        continue
                # For address fields, keep pending_field to allow multi-line address
                if not matched and "Address" not in pending_field:
                    pending_field = None
                matched = True

        # ===== IGNORE FOOTER GARBAGE IN OPPORTUNISTIC FILLING (Context: unlabeled lines) ===== 
        # Skip lines that look like software signatures, lookup instructions, OR digital signatures
        signature_footer_keywords = [
            "phát hành bởi", "tra cứu", "website", "giải pháp", 
            "vnpt", "viettel", "misa", "invoice display", "bản thể hiện",
            "được ký", "ký bởi", "signature valid", "trang 1/1"  # Signature exclusions
        ]
        if any(k in low for k in signature_footer_keywords):
             continue

        # ===== UNLABELED VALUES (for form-based format like Sample 6) =====
        # Detect standalone values without labels
        if not matched and ":" not in clean:
            # Company name without label
            # Must be CAREFUL not to pick up garbage lines
            if "công ty" in low or "doanh nghiệp" in low or "chi nhánh" in low:
                 # Additional check: unlikely to be a software provider line due to previous checks
                 if not invoice.sellerName:
                     invoice.sellerName = clean
            # Tax code without label (10-14 digits)
            elif re.fullmatch(r"\d{10,14}(-\d+)?", clean) and not invoice.sellerTaxCode:
                invoice.sellerTaxCode = clean
            # Phone number without label
            elif re.fullmatch(r"0\d{9,10}", clean) and not invoice.sellerPhoneNumber:
                invoice.sellerPhoneNumber = clean
            # Bank account without label (long number with possible separators)
            # EXCLUDE international phone numbers like 86-18929233070 (country_code-number)
            elif re.fullmatch(r"[\d\.\-]{10,20}", clean) and not invoice.sellerBankAccountNumber:
                # Check if it looks like an intl phone: 1-2 digit country code + hyphen + 9-11 digits
                # Also check if previous line is L/C-related (not a bank account)
                _prev_low_ctx = _prev_line.lower().strip('*').strip() if _prev_line else ''
                _is_lc_ctx = any(k in _prev_low_ctx for k in ['l/c', 'credit', 'lc number', 'lc no'])
                if not re.fullmatch(r"\d{1,3}-\d{9,11}", clean) and not _is_lc_ctx:
                    invoice.sellerBankAccountNumber = clean.replace(".", "")
            # Bank name without label
            elif "ngân hàng" in low and not invoice.sellerBank:
                # Extract bank name
                m = re.search(r"ngân hàng\s+(.+)", clean, re.I)
                if m:
                    invoice.sellerBank = m.group(1).strip()
                else:
                    invoice.sellerBank = clean
        
        _prev_line = line


def parse_buyer(block: List[str], invoice: Invoice):
    pending_field = None  # Track which field expects continuation on next line
    _prev_line = ''
    
    for line in block:
        clean = line.strip().replace("**", "")
        low = clean.lower()
        matched = False

        # ===== EMAIL =====
        email = extract_email(clean)
        if email and not invoice.buyerEmail:
            invoice.buyerEmail = email

        # BUYER NAME - improved detection for various formats
        # Handle: "Đơn vị (Co. name): X", "Tên đơn vị: X", "Company's name: X"
        # Handle: "BÊN B (Bên mua): CÔNG TY..." - for BIÊN BẢN HỦY HÓA ĐƠN
        # Skip lines with "Người mua (Buyer):" that have CCCD immediately after
        if any(k in low for k in [
            "tên đơn vị",
            "tên người mua hàng",  # Added
            "người mua hàng",      # Added
            "họ tên người mua hàng",
            "khách hàng",
            "company's name",
            "đơn vị (co. name)",
            "co. name",
            "bill to",              # Added for English invoices
            "bên b (bên mua)",  # Added for BIÊN BẢN HỦY HÓA ĐƠN
            "bên mua)",         # Partial match
            "bên b:",           # Direct match
            "consignee",        # EN: CONSIGNEE = Buyer
            "sold to",          # EN: SOLD TO = Buyer
            "delivery details",  # EN: Delivery Details section
            "customer's details",  # EN: Customer's Details section
            "customer:",        # EN: Customer: label
            "company name",     # EN: COMPANY NAME
            "full name",        # Customs/shipping: Full Name
        ]) or low.strip() == "to:":
            pending_field = None
            # Special handling for BÊN B pattern - extract after last colon
            if "bên b" in low or "bên mua" in low:
                colon_idx = clean.rfind(":")
                if colon_idx != -1:
                    value = clean[colon_idx + 1:].strip()
                    if value and ("công ty" in value.lower() or "doanh nghiệp" in value.lower()):
                        invoice.buyerName = value
                        matched = True
                        continue
            
            # For CONSIGNEE/COMPANY NAME/FULL NAME label: value is likely on the NEXT line or after colon
            if any(k in low for k in ["company name", "consignee", "full name",
                                        "delivery details", "customer's details", "customer:"]):
                # Check if there's a value after colon
                if ":" in clean:
                    value = clean.split(":", 1)[-1].strip()
                    # Reject pipe-table garbage (starts with |) and metadata labels
                    if (value and len(value) > 3
                            and not value.startswith('|')
                            and not re.match(r'Country\s+of\s+(?:Origin|Manufacture)', value, re.I)):
                        if not invoice.buyerName:
                            invoice.buyerName = value
                    else:
                        if not invoice.buyerName:
                            pending_field = "buyerName"
                else:
                    # Only set pending if buyerName is not already set
                    if not invoice.buyerName:
                        pending_field = "buyerName"
                matched = True
                continue
            
            # Require colon for standard Label: Value pairs to avoid matching "Người mua hàng" signature title
            if ":" not in clean and not pending_field:
                continue
                
            value = clean.split(":", 1)[-1].strip()
            # Skip if value contains CCCD marker or is empty/junk
            if value and "cccd" not in value.lower() and "(citizen id" not in value.lower():
                if len(value) > 3 and not re.match(r'^[\*\s]+$', value):
                    invoice.buyerName = value
                    pending_field = None  # Clear: name is set
            else:
                pending_field = "buyerName"
            matched = True

        # IMPORTER overrides CONSIGNEE — importer is usually the actual buyer
        # But only match "Importer:", "Importer Name:", NOT "Importer Number:", "Importer EORI:", "Importer VAT:"
        elif re.match(r'^\s*importer\s*(?:name\s*)?:', low) or low.strip() == 'importer':
            if ":" in clean:
                value = clean.split(":", 1)[-1].strip()
                if value and len(value) > 3:
                    invoice.buyerName = value
                    invoice.buyerAddress = None  # Clear consignee address
                else:
                    # Clear existing to allow override from next line
                    invoice.buyerName = None
                    invoice.buyerAddress = None
                    pending_field = "buyerName"
            else:
                invoice.buyerName = None
                invoice.buyerAddress = None
                pending_field = "buyerName"
            matched = True

        #TAX CODE - support MST abbreviation
        elif "mã số thuế" in low or "tax code" in low or "mst" in low:
            m = re.search(r"(\d{10,14}(-\d+)?)", clean)
            if m:
                invoice.buyerTaxCode = m.group(1)
            pending_field = None
            matched = True

        # ADDRESS - "Ship To Add:" or "Ship To Address:" shortcuts
        elif any(k in low for k in ["ship to add", "ship to address", "deliver to address"]):
            value = clean.split(":", 1)[-1].strip() if ":" in clean else ""
            if value and not invoice.buyerAddress:
                invoice.buyerAddress = value
            elif not value and not invoice.buyerAddress:
                pending_field = "buyerAddress"
            matched = True
            
        # ADDRESS (including "Nhập tại kho" for internal transfer slips, "adresse" for French labels, "adress" for common misspelling)
        elif "địa chỉ" in low or "address" in low or "adress" in low or "nhập tại kho" in low or "adresse" in low:
            value = clean.split(":", 1)[-1].strip() if ":" in clean else ""
            if value and not invoice.buyerAddress:
                invoice.buyerAddress = value
            elif value and invoice.buyerAddress and len(value) > len(invoice.buyerAddress):
                # Only overwrite if the new value is more complete
                invoice.buyerAddress = value
            elif not value and not invoice.buyerAddress:
                # Address is on the next line(s)
                pending_field = "buyerAddress"
            matched = True

        # PHONE (FIX TEL + FAX + Phone number)
        elif "điện thoại" in low or "tel" in low or "phone number" in low:
            # First try: extract value after colon for international formats
            if ":" in clean:
                phone_val_raw = clean.split(":", 1)[-1].strip().lstrip("- ")
                if re.match(r'\+?[\d\s\-\(\)\.]{7,}$', phone_val_raw):
                    phone_clean = phone_val_raw.strip()
                    if len(re.sub(r'[^\d]', '', phone_clean)) >= 7:
                        invoice.buyerPhoneNumber = phone_clean
            # Fallback to extract_phone
            if not invoice.buyerPhoneNumber:
                phone = extract_phone(clean)
                if phone:
                    invoice.buyerPhoneNumber = phone
            pending_field = None
            matched = True

        # BANK 
        elif "số tài khoản" in low or "account no" in low or "ac no" in low:
            # Tìm số tài khoản
            m_acc = re.search(r"(?:số tài khoản|stk|ac no)[:\s]*([0-9\.\-]+)", clean, re.I)
            if m_acc:
                invoice.buyerBankAccountNumber = m_acc.group(1).replace(".", "")
            
            # Tìm tên ngân hàng
            if "ngân hàng" in low:
                m_bank = re.search(r"ngân hàng[:\s]*([^\n]+?)(?:\s*-\s*Chi nhánh|\s*$)", clean, re.I)
                if m_bank:
                    invoice.buyerBank = m_bank.group(1).strip(" :-")
            pending_field = None
            matched = True

        # PAYMENT METHOD (Added check for mixed lines or standalone)
        # Check this INDEPENDENTLY of elif chain because it might share line with Phone
        if "hình thức thanh toán" in low or "payment method" in low:
             # Extract text after the label
             # Fix: Handle "(Payment method): TM/CK" -> should extract "TM/CK"
             # Use lookbehind or just split by ':' last occurrence
             
             # Attempt to clean specific garbage prefix "(Payment method)" inside the value
             m_pm = re.search(r"(?:hình thức thanh toán|payment method)[^:]*[:\s]+(.+)", clean, re.I)
             if m_pm:
                 pm_val = m_pm.group(1).strip()
                 # Further cleanup if it starts with "(Payment method)"
                 pm_val = re.sub(r"^\(?Payment method\)?", "", pm_val, flags=re.I).strip(" :")
                 invoice.paymentMethod = pm_val
             pending_field = None
             matched = True



        # CURRENCY
        elif "đồng tiền thanh toán" in low:
            value = clean.split(":", 1)[-1].strip()
            if value:
                invoice.currency = value
            pending_field = None
            matched = True

        # ===== CONTINUATION LINE (for multi-line values like address) =====
        # Skip markdown separator lines (---) — they are not content
        if not matched and pending_field and clean and re.fullmatch(r'-{2,}', clean.strip()):
            continue
        if not matched and pending_field and clean:
            # Stop continuation if this line looks like a new section/label
            is_section = any(k in low for k in ["reason for", "material", "description",
                                                 "\u51fa\u53e3\u539f\u56e0", "\u6750\u8d28", "country of",
                                                 "bank information", "payment term",
                                                 "delivery time", "weight"])
            # Stop at standalone labels (no colon) like "Phone", "Email", "Contact Person"
            _standalone_labels = {'phone', 'email', 'tel', 'fax', 'contact person', 'address',
                                  'company name', 'full name', 'invoice information',
                                  'invoice date', 'invoice number', 'origin country',
                                  'destination country', 'product details', 'financial summary'}
            is_standalone_label = low.strip('- ') in _standalone_labels
            # Stop at table lines, lines with colons (new labels), or if field is already long enough
            is_table_line = clean.startswith("|")
            has_colon = ":" in clean
            current_val = getattr(invoice, pending_field, None) or ""
            # Limit: buyerName max 100 chars, buyerAddress max 150 chars, others max 120
            max_len = 100 if "Name" in pending_field else (150 if "Address" in pending_field else 120)
            is_too_long = len(current_val) >= max_len
            
            if is_section or is_table_line or has_colon or is_too_long or is_standalone_label:
                if is_standalone_label:
                    # Re-match against BUYER_LABEL_KEYS for the new field
                    new_field = None
                    for f2, keys2 in BUYER_LABEL_KEYS.items():
                        if any(k in low for k in keys2):
                            new_field = f2
                            break
                    pending_field = new_field
                else:
                    pending_field = None
            else:
                if current_val:
                    # Don't append if the continuation value is the same as what's already set
                    if current_val.strip() != clean.strip():
                        # Validate phone values: must contain digits before appending
                        if 'Phone' in pending_field:
                            _digit_count = len(re.sub(r'[^\d]', '', clean))
                            if _digit_count < 7:
                                continue
                        setattr(invoice, pending_field, current_val + " " + clean)
                else:
                    # Validate phone values: must contain enough digits
                    if 'Phone' in pending_field:
                        _digit_count = len(re.sub(r'[^\d]', '', clean))
                        if _digit_count < 7:
                            # Not a phone number — skip but keep pending
                            continue
                    setattr(invoice, pending_field, clean)
                # After setting buyerName, switch to buyerAddress for following lines
                if pending_field == "buyerName" and not invoice.buyerAddress:
                    pending_field = "buyerAddress"
                continue

        # ===== UNLABELED VALUES (for form-based format like Sample 6) =====
        elif ":" not in clean:
            # Company name without label
            if any(k in low for k in ["công ty", "doanh nghiệp", "chi nhánh", "corporation", "co.,"]):
                if not invoice.sellerName:
                    invoice.sellerName = clean
                elif not invoice.buyerName:
                    invoice.buyerName = clean

            # Tax code without label
            elif re.fullmatch(r"\d{10,14}(-\d+)?", clean):
                if not invoice.sellerTaxCode:
                    invoice.sellerTaxCode = clean
                elif not invoice.buyerTaxCode:
                    invoice.buyerTaxCode = clean
            
            # Address (heuristic: long line, contains "Phường", "Quận", "Thành phố", "Tỉnh")
            elif len(clean) > 20 and any(k in low for k in ["phường", "quận", "thành phố", "tỉnh", "district", "city"]):
                if not invoice.sellerAddress:
                    invoice.sellerAddress = clean
                elif not invoice.buyerAddress:
                    invoice.buyerAddress = clean
            
            # Phone
            elif re.fullmatch(r"0\d{9,10}", clean):
                if not invoice.sellerPhoneNumber:
                    invoice.sellerPhoneNumber = clean
                elif not invoice.buyerPhoneNumber:
                    invoice.buyerPhoneNumber = clean

            # Bank Account
            # EXCLUDE L/C numbers: check if previous line has 'l/c', 'credit', etc.
            elif re.fullmatch(r"[\d\.\-]{9,20}", clean):
                _prev_low_buyer = _prev_line.lower().strip('*').strip() if _prev_line else ''
                _is_lc_buyer = any(k in _prev_low_buyer for k in ['l/c', 'credit', 'lc number', 'lc no'])
                if not _is_lc_buyer:
                    if not invoice.sellerBankAccountNumber:
                        invoice.sellerBankAccountNumber = clean.replace(".", "")
                    elif not invoice.buyerBankAccountNumber:
                        invoice.buyerBankAccountNumber = clean.replace(".", "")
            
            # Bank Name detection (heuristic)
            elif "ngân hàng" in low:
                bank_val = clean.strip()
                m = re.search(r"ngân hàng\s+(.+)", clean, re.I)
                if m:
                     bank_val = m.group(1).strip()
                
                if not invoice.sellerBank:
                    invoice.sellerBank = bank_val
                elif not invoice.buyerBank:
                    invoice.buyerBank = bank_val

        _prev_line = line


def parse_table(block: List[str], invoice: Invoice):
    """Parse table block - extract items AND summary totals from markdown table"""
    raw_table = "\n".join(block)
    items = parse_items_from_table(raw_table)
    invoice.itemList = items
    
    # Also extract totals from markdown table summary rows
    # These are rows like: |Tổng cộng:|||5.458.320|||436.666|5.894.986|
    for line in block:
        l = line.lower()
        
        # Skip if not a markdown table row
        if "|" not in line:
            continue
        
        # Parse |Tổng cộng:| row - last number is totalAmount (cộng tiền thanh toán)
        if "tổng cộng" in l and not invoice.totalAmount:
            nums = re.findall(r'[\d\.\,]+', line)
            if nums:
                 val = safe_parse_float(nums[-1])
                 if val and val > 1000:
                     invoice.totalAmount = val
        
        # Format Viettel: |Cộng tiền hàng hóa, dịch vụ:||||||14.027.784|1.122.216|15.150.000|
        # Last number is totalAmount (thành tiền sau thuế)
        # Format Viettel: |Cộng tiền hàng hóa, dịch vụ:||||||14.027.784|1.122.216|15.150.000|
        # Last number is totalAmount (thành tiền sau thuế)
        if ("cộng tiền hàng" in l or "cộng tiền dịch vụ" in l or "tổng tiền" in l or "tổng cộng" in l
                or ("exw" in l and not invoice.totalAmount)):
            nums = re.findall(r'[\d\.\,]+', line)
            if nums:
                 parsed_nums = [safe_parse_float(n) for n in nums]
                 parsed_nums = [n for n in parsed_nums if n is not None]
                 
                 if parsed_nums:
                     # 1. Try to set totalAmount
                     val = parsed_nums[-1]
                     if val and val > 1000:
                         if not invoice.totalAmount: invoice.totalAmount = val
                     
                     # 2. Try to extract PreTax and Tax via Summation Check
                     # Logic: PreTax + Tax = Total
                     if len(parsed_nums) >= 3:
                         # Candidate positions: |...|PreTax|Tax|Total|
                         # Total is [-1], Tax usually [-2], PreTax usually [-3]
                         total_cand = parsed_nums[-1]
                         tax_cand = parsed_nums[-2]
                         pre_cand = parsed_nums[-3]
                         
                         if total_cand > 0:
                             # 1% tolerance + 10 units
                             if abs((pre_cand + tax_cand) - total_cand) < (total_cand * 0.01) + 10:
                                 # FOUND IT! Force overwrite logic
                                 invoice.taxAmount = tax_cand
                                 invoice.preTaxPrice = pre_cand
                                 invoice.totalAmount = total_cand # Ensure total matches
                                 # print(f"DEBUG: Found consistent tax row in TABLE: Pre={pre_cand}, Tax={tax_cand}, Total={total_cand}")
        
        if "thuế suất" in l and "%" in l and not invoice.totalAmount:
            nums = re.findall(r'[\d\.]+', line)
            if len(nums) >= 3:
                try:
                    last_num = nums[-1].replace('.', '')
                    if last_num.isdigit() and int(last_num) > 1000:
                        invoice.totalAmount = float(last_num)
                except:
                    pass
        
        if "thành tiền trước thuế" in l and not invoice.preTaxPrice:
            nums = re.findall(r'[\d\.]+', line)
            if nums:
                try:
                    first_num = nums[0].replace('.', '')
                    if first_num.isdigit() and int(first_num) >= 100:
                        invoice.preTaxPrice = float(first_num)
                except:
                    pass
        
        # English TOTAL row in table: | TOTAL | ... | 62,880.00 |
        if "total" in l and "subtotal" not in l and "|" in line:
            # Skip weight/package totals
            _weight_kws = ["weight", "gross", "net weight", "package", "pkgs", "carton", "pallet", "tare"]
            if not any(wk in l for wk in _weight_kws):
                cells = [c.strip() for c in line.split("|") if c.strip()]
                # Only process if first cell is "TOTAL" or starts with "Total"
                if cells and cells[0].strip('* ').lower().startswith('total'):
                    weight_pattern = re.compile(r'\b(?:kg|lb|lbs|g|oz|ton|tons|mt)\b', re.I)
                    monetary_nums = []
                    for cell in cells[1:]:  # skip the "TOTAL" label cell
                        if weight_pattern.search(cell):
                            continue
                        # Also extract currency-prefixed numbers like USD6512, EUR1234
                        _cell_clean = re.sub(r'^(?:USD|EUR|GBP|AUD|CAD|INR|SGD|JPY|CNY|KRW|THB)\s*\$?', '', cell.strip(), flags=re.I)
                        cell_nums = re.findall(r'[\d\.\,]+', _cell_clean)
                        for n in cell_nums:
                            val = safe_parse_float(n)
                            if val is not None:
                                monetary_nums.append(val)
                    if monetary_nums:
                        # Last number is the total amount
                        invoice.totalAmount = monetary_nums[-1]

# TOTAL PARSER
# =========================
def parse_total(block: List[str], invoice: Invoice):
    """Parse total/summary section including markdown table format"""
    for line in block:

        l = line.lower()

        # ===== SKIP ITEM-DETAIL LINES (not summary rows) =====
        # These are sub-rows of item table, not total amounts
        _skip_detail_keywords = [
            "customs tariff", "country of origin", "batch:", "batch no",
            "siret", "n°tva", "rcs ", "s.a.s", "iban:", "swift:",
            "tracking", "fedex", "parcels",
        ]
        if any(k in l for k in _skip_detail_keywords):
            continue
        
        # Skip pure date lines (DD.MM.YYYY or DD/MM/YYYY) that might be in pipe rows
        if re.match(r'^\s*\|?\s*\d{2}[./]\d{2}[./]\d{4}\s*\|?\s*$', line):
            continue
        
        # Skip phone number lines in pipe rows (e.g. "| 02.35.23.19.35 |")
        if re.match(r'^\s*\|?\s*[\d\s.+()\-]{8,}\s*\|?\s*$', line):
            continue

        # Tổng cộng tiền thanh toán (Total payment) - multiple patterns
        # Pattern 1: "Tổng cộng tiền thanh toán:" or "Total payment:"
        # Pattern 2: Markdown table row "|Tổng cộng:|||...|229.997|" - last number is totalAmount
        
        # FIX: Allow overwriting totalAmount because "Total Payment" is authoritative (Post-Tax)
        # Added "tổng tiền", "cộng tiền" for VETC and Viettel cases
        if "tổng cộng" in l or "total payment" in l or "tổng tiền" in l or "cộng tiền" in l or ("total" in l and "subtotal" not in l):
            # Skip weight/package totals — not monetary amounts
            _weight_kws = ["weight", "gross", "net weight", "package", "pkgs", "carton", "pallet", "tare"]
            if any(wk in l for wk in _weight_kws):
                continue
            # Check if markdown table row
            if "|" in line:
                # Extract cells and filter out weight-related values (kg, lb, g, oz, ton)
                cells = [c.strip() for c in line.split("|") if c.strip()]
                monetary_nums = []
                weight_pattern = re.compile(r'\b(?:kg|lb|lbs|g|oz|ton|tons|mt)\b', re.I)
                for cell in cells:
                    # Skip cells that contain weight units
                    if weight_pattern.search(cell):
                        continue
                    # Skip cells that are currency symbols only
                    if re.fullmatch(r'[€$£¥]+', cell.strip()):
                        continue
                    # Also extract currency-prefixed numbers like USD6512, EUR1234
                    _cell_clean = re.sub(r'^(?:USD|EUR|GBP|AUD|CAD|INR|SGD|JPY|CNY|KRW|THB)\s*\$?', '', cell.strip(), flags=re.I)
                    cell_nums = re.findall(r'[\d\.\,]+', _cell_clean)
                    for n in cell_nums:
                        val = safe_parse_float(n)
                        if val is not None:
                            monetary_nums.append(val)
                
                if monetary_nums:
                    parsed_nums = monetary_nums
                else:
                    # Fallback: use all numbers if no monetary ones found
                    nums = re.findall(r'[\d\.\,]+', line)
                    parsed_nums = [safe_parse_float(n) for n in nums]
                    parsed_nums = [n for n in parsed_nums if n is not None]
                    
                if parsed_nums:
                    val = parsed_nums[-1]
                    if val and val > 0:
                        invoice.totalAmount = val
                    else:
                        # If no number on this line, but it's a TOTAL header, look at next line
                        # This handles: | OTHER | TOTAL | \n | GBP 32499 | |
                        # We find which index "TOTAL" is at
                        t_cells = [c.lower().strip() for c in line.split('|')]
                        total_idx = -1
                        for i, c in enumerate(t_cells):
                            if "total" in c:
                                total_idx = i
                                break
                        
                        if total_idx != -1:
                            # Look ahead at next line if it exists
                            current_idx = block.index(line)
                            if current_idx + 1 < len(block):
                                next_line = block[current_idx + 1]
                                if "|" in next_line:
                                    next_cells = [c.strip() for c in next_line.split('|')]
                                    if total_idx < len(next_cells):
                                        num_match = re.search(r'[\d\.\,]+', next_cells[total_idx])
                                        if num_match:
                                            val = safe_parse_float(num_match.group(0))
                                            if val and val > 0:
                                                invoice.totalAmount = val
                    
                    # Try to extract Tax and PreTax if 3 numbers exist (PreTax, Tax, Total)
                    if len(parsed_nums) >= 3:
                        # Example: |8.333|667|9.000| -> 9000 total, 667 tax, 8333 pretax
                        # So: [-1]=Total, [-2]=Tax, [-3]=PreTax
                        
                        tax_cand = parsed_nums[-2]
                        pre_cand = parsed_nums[-3]
                        
                        # Verify Summation: Pre + Tax = Total (approx)
                        if abs((pre_cand + tax_cand) - val) < (val * 0.01) + 10: # 1% tolerance + 10 units
                            # Force overwrite because this summation is strong evidence
                            invoice.taxAmount = tax_cand
                            invoice.preTaxPrice = pre_cand
            else:
                # Non-table format: "Tổng cộng tiền thanh toán: 123,456" OR "Tổng cộng: 2.314.750  185.180  2.499.930"
                nums = re.findall(r'[\d\.\,]+', line)
                if nums:
                    parsed_nums = [safe_parse_float(n) for n in nums]
                    parsed_nums = [n for n in parsed_nums if n is not None and n > 0] # Filter valid numbers
                    
                    if parsed_nums:
                        # 1. Last number is likely Total Amount
                        val = parsed_nums[-1]
                        if val > 0:
                            invoice.totalAmount = val
                        
                        # 2. Try Summation Logic (Pre + Tax = Total)
                        if len(parsed_nums) >= 3:
                            total_cand = parsed_nums[-1]
                            tax_cand = parsed_nums[-2]
                            pre_cand = parsed_nums[-3]
                            
                            # Tolerance check
                            if abs((pre_cand + tax_cand) - total_cand) < (total_cand * 0.01) + 10:
                                invoice.taxAmount = tax_cand
                                invoice.preTaxPrice = pre_cand
                                invoice.totalAmount = total_cand # Ensure consistency
        
        # Also try Total payment pattern
        if any(k in l for k in ["total payment", "total value", "grand total", "net amount"]) and not invoice.totalAmount:
            num = re.sub(r"[^\d]", "", line)
            if num:
                invoice.totalAmount = float(num)

        # Số tiền viết bằng chữ
        if "số tiền viết bằng chữ" in l or "in words" in l:
            # Handle pipe-table format: "| Total in Words | One Hundred... |"
            if '|' in line:
                cells = [c.strip() for c in line.split('|') if c.strip()]
                # Find the cell that is NOT the label (not containing "in words")
                val_cells = [c for c in cells if 'in words' not in c.lower() and 'bằng chữ' not in c.lower()]
                text_val = val_cells[0] if val_cells else line.split(":", 1)[-1].strip()
            else:
                text_val = line.split(":", 1)[-1].strip()
            # Clean markdown table separators and garbage
            text_val = clean_invoice_total_in_word(text_val)
            if text_val:
                invoice.invoiceTotalInWord = text_val
            
            # --- Currency Inference from Words ---
            if not invoice.currency:
                low_val = text_val.lower()
                if any(k in low_val for k in ["đồng", "vietnam dong", "vnđ", "vnd"]):
                    invoice.currency = "VND"
                elif any(k in low_val for k in ["dollar", "usd"]):
                    invoice.currency = "USD"
                elif any(k in low_val for k in ["euro", "eur"]):
                    invoice.currency = "EUR"
                    
        # Explicit Currency Field (Priority 1)
        if "đồng tiền thanh toán" in l:
             parts = line.split(":")
             if len(parts) > 1:
                 cur = parts[1].strip().upper()
                 convert_cur = re.sub(r"[^A-Z]", "", cur)
                 if convert_cur:
                     invoice.currency = convert_cur

        # Thuế suất (VAT Rate)
        # Scan for "Thuế suất", "VAT Rate", "Chịu thuế", "Tiền thuế GTGT" + "%"
        if (any(k in l for k in ["thuế suất", "vat rate", "chịu thuế", "thuế gtgt", "tax rate"])):
             m = re.search(r"(\d+%)", line)
             if m:
                 val = m.group(1)  # e.g. "10%"
                 # Heuristic: Prioritize lines that actually have MONEY values (populatd tax rows)
                 # e.g. "Tổng tiền chịu thuế 8%: 14.000.000" vs "Tổng tiền chịu thuế 10%:" (empty)
                 has_value = False
                 nums = re.findall(r"[\d\.\,]+", line)
                 # Check if any number is "long" enough to be money (> 3 digits/chars, excluding the % itself)
                 for n in nums:
                     # Simple check: length > 2 and not just equal to the percentage val
                     clean_n = n.replace('.', '').replace(',', '').strip()
                     if len(clean_n) >= 3 or (len(clean_n) >= 1 and clean_n != val and int(clean_n) > 100):
                         has_value = True
                         break
                 
                 # Logic: 
                 # 1. If we found a value line -> FORCE overwrite (this is the active tax)
                 # 2. If no value line -> Only set if empty (fallback)
                 if has_value:
                     invoice.taxPercent = val
                 elif not invoice.taxPercent:
                     invoice.taxPercent = val
             else:
                 # Look ahead for taxPercent (e.g. "Tax Rate \n 10%")
                 current_idx = block.index(line)
                 for offset in range(1, 10):
                     if current_idx + offset < len(block):
                         next_line = block[current_idx + offset]
                         m_perc = re.search(r"(\d+%)", next_line)
                         if m_perc:
                             invoice.taxPercent = m_perc.group(1)
                             break
        
        # Tiền thuế (VAT amount)
        # STRICT CHECK: Must not contain "tiền hàng" or "pre tax" to avoid matching PreTax line
        if (any(k in l for k in ["tiền thuế", "vat amount", "sales tax"])) and "tiền hàng" not in l and "pre tax" not in l:
            # Handle "|Tổng tiền thuế: 4.968.262|" format
            val = None
            if ":" in line:
               val_part = line.split(":")[-1].strip().strip("|")
               nums = re.findall(r'[\d\.\,]+', val_part)
               if nums:
                   val = safe_parse_float(nums[0])
            
            # Fallback to finding all numbers in line
            if not val:
                 nums = re.findall(r"[\d\.\,]+", line)
                 if nums:
                     val = safe_parse_float(nums[-1])

            if val and val > 100:
                invoice.taxAmount = val
            else:
                # Look ahead logic for "Sales Tax \n \n GBP 2,954"
                current_idx = block.index(line)
                # Search next 10 lines for a number
                for offset in range(1, 10):
                    if current_idx + offset < len(block):
                        next_line = block[current_idx + offset]
                        nums = re.findall(r'[\d\.\,]+', next_line)
                        if nums:
                            val = safe_parse_float(nums[0])
                            if val and val > 0:
                                invoice.taxAmount = val
                                break
        
        # Tiền trước thuế (PreTax) - Added specific check for summary table
        if (any(k in l for k in ["tổng tiền hàng", "thành tiền trước thuế", "cộng tiền hàng", "subtotal"])) and "thanh toán" not in l and "total amount" not in l:
             val = None
             if ":" in line:
                val_part = line.split(":")[-1].strip().strip("|")
                nums = re.findall(r'[\d\.\,]+', val_part)
                if nums:
                    val = safe_parse_float(nums[0])
             
             if not val:
                  nums = re.findall(r"[\d\.\,]+", line)
                  if nums:
                      val = safe_parse_float(nums[-1])
             
             if val and val > 0:
                 invoice.preTaxPrice = val
             else:
                 # Look ahead logic
                 current_idx = block.index(line)
                 for offset in range(1, 10):
                     if current_idx + offset < len(block):
                         next_line = block[current_idx + offset]
                         nums = re.findall(r'[\d\.\,]+', next_line)
                         if nums:
                             val = safe_parse_float(nums[0])
                             if val and val > 0:
                                 invoice.preTaxPrice = val
                                 break

    # Default Currency - detect from block context
    if not invoice.currency:
        block_text = '\n'.join(block)
        # Check if invoice contains currency indicators (symbols + codes)
        if re.search(r'€|\(EURO\)|EUR|euro', block_text, re.I):
            invoice.currency = "EUR"
        elif re.search(r'\$|\(USD\)|USD|dollar', block_text, re.I):
            invoice.currency = "USD"
        elif re.search(r'£|\(GBP\)|GBP', block_text, re.I):
            invoice.currency = "GBP"
        elif re.search(r'₹|\(INR\)|INR|rupee', block_text, re.I):
            invoice.currency = "INR"
        elif re.search(r'₩|\bKRW\b|원', block_text, re.I):
            invoice.currency = "KRW"
        elif re.search(r'¥|\bCNY\b|\bRMB\b|人民币', block_text):
            invoice.currency = "CNY"
        elif re.search(r'\bJPY\b|円', block_text):
            invoice.currency = "JPY"
        elif re.search(r'฿|\bTHB\b|\bBaht\b', block_text, re.I):
            invoice.currency = "THB"
        elif re.search(r'₺|\bTRY\b|Türk\s*Lira', block_text, re.I):
            invoice.currency = "TRY"
        elif re.search(r'₽|\bRUB\b|рубл', block_text, re.I):
            invoice.currency = "RUB"
        elif re.search(r'₱|\bPHP\b|[Pp]eso', block_text):
            invoice.currency = "PHP"
        elif re.search(r'\bAUD\b|A\$', block_text):
            invoice.currency = "AUD"
        elif re.search(r'\bCAD\b|CA?\$', block_text):
            invoice.currency = "CAD"
        elif re.search(r'\bSGD\b|S\$', block_text):
            invoice.currency = "SGD"
        elif re.search(r'\bCHF\b|Fr\.|Franken', block_text, re.I):
            invoice.currency = "CHF"
        elif re.search(r'\bHKD\b|HK\$', block_text):
            invoice.currency = "HKD"
        elif re.search(r'\bTWD\b|NT\$', block_text):
            invoice.currency = "TWD"
        elif re.search(r'\bMYR\b|RM\s*\d', block_text):
            invoice.currency = "MYR"
        elif re.search(r'\bIDR\b|Rp\s*[\d.]', block_text):
            invoice.currency = "IDR"
        elif re.search(r'\bSEK\b|kr\b', block_text):
            invoice.currency = "SEK"
        elif re.search(r'\bNOK\b', block_text):
            invoice.currency = "NOK"
        elif re.search(r'\bDKK\b', block_text):
            invoice.currency = "DKK"
        elif re.search(r'\bNZD\b|NZ\$', block_text):
            invoice.currency = "NZD"
        elif re.search(r'\bZAR\b', block_text):
            invoice.currency = "ZAR"
        elif re.search(r'\bAED\b|[Dd]irham', block_text):
            invoice.currency = "AED"
        elif re.search(r'\bSAR\b|﷼|[Rr]iyal', block_text):
            invoice.currency = "SAR"
        elif re.search(r'\bBRL\b|R\$', block_text):
            invoice.currency = "BRL"
        elif re.search(r'\bMXN\b', block_text):
            invoice.currency = "MXN"
        elif re.search(r'\bPLN\b|zł', block_text, re.I):
            invoice.currency = "PLN"
        elif re.search(r'\bCZK\b|Kč', block_text, re.I):
            invoice.currency = "CZK"
        elif re.search(r'VND|VNĐ|đồng', block_text, re.I):
            invoice.currency = "VND"

    # FALLBACK: If totalAmount is still missing or suspiciously small,
    # find the largest number in the table block as totalAmount
    # User insight: "The largest number in the table will definitely be totalAmount"
    
    all_numbers = []
    for line in block:
        low = line.lower()
        # EXCLUDE bank/account lines, phone numbers, postal codes, PO references
        if any(k in low for k in ["beneficiary", "account", "bank", "swift",
                                   "iban", "sort-code", "routing",
                                   "tel", "phone", "fax", "postal", "zip",
                                   " po ", "p.o.", "purchase order",
                                   "tarif", "tariff", "hs code", "lot number",
                                   "cone", "height", "diameter"]):
            continue
        # Extract all number-like strings
        nums = re.findall(r'[\d\.\,]+', line)
        for n in nums:
            parsed = safe_parse_float(n)
            # Reasonable range: > 0 and < 100 million (exclude phone/account numbers)
            if parsed and parsed > 0 and parsed < 100_000_000:
                all_numbers.append(parsed)
    
    if all_numbers:
        max_num = max(all_numbers)
        # Only use fallback if totalAmount is not set
        if not invoice.totalAmount and max_num >= 100:
            # Validate against item amounts if available
            if invoice.itemList:
                item_sum = sum(it.amount or 0 for it in invoice.itemList)
                if item_sum > 0 and max_num > item_sum * 2:
                    # max_num is suspiciously larger than item sum — likely a non-financial number
                    # Use item sum instead
                    invoice.totalAmount = item_sum
                else:
                    invoice.totalAmount = max_num
            else:
                invoice.totalAmount = max_num


# GLOBAL FIELDS PARSER - scan toàn bộ raw text để tìm invoiceID, invoiceFormNo
# =========================
def parse_global_fields(raw_text: str, invoice: Invoice):
    """
    Scan toàn bộ raw text để tìm các trường quan trọng chưa được parse:
    - invoiceID: Số (No.): 00000721 hoặc Số: **00000XXX**
    - invoiceFormNo: Ký hiệu (Serial No): 1C25THO hoặc Ký hiệu: 1C25THO
    """
    
    # ===== INVOICE DATE (fallback) =====
    if not invoice.invoiceDate:
        months = {'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04', 'may': '05', 'jun': '06',
                  'jul': '07', 'aug': '08', 'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12'}

        # Pattern 1: Date: 2025/12/1 or Date: 2025-12-01
        m = re.search(r'[Dd]ate[:\s]+(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})', raw_text)
        if m:
            invoice.invoiceDate = f"{m.group(3).zfill(2)}/{m.group(2).zfill(2)}/{m.group(1)}"
        
        # Pattern 2: DEC. 01, 2025 or Dec 1, 2025 or December 01, 2025
        if not invoice.invoiceDate:
            m = re.search(r'([A-Za-z]{3,9})\.?\s*(\d{1,2}),?\s*(\d{4})', raw_text)
            if m:
                month_abbr = m.group(1).lower()[:3]
                if month_abbr in months:
                    invoice.invoiceDate = f"{m.group(2).zfill(2)}/{months[month_abbr]}/{m.group(3)}"
        
        # Pattern 3: Date: 27-Mar-25 or 27-Dec-2025 (dd-Mon-yy or dd-Mon-yyyy)
        if not invoice.invoiceDate:
            m = re.search(r'[Dd]ate[:\s]+(\d{1,2})[\-/]([A-Za-z]{3,9})[\-/](\d{2,4})', raw_text)
            if m:
                day = m.group(1).zfill(2)
                month_abbr = m.group(2).lower()[:3]
                year = m.group(3)
                if len(year) == 2:
                    year = '20' + year  # 25 → 2025
                if month_abbr in months:
                    invoice.invoiceDate = f"{day}/{months[month_abbr]}/{year}"
        
        # Pattern 4: "Dated : 11 AUGUST, 2009" or "Date: 14 DEC 2021" or "Date: 08TH MAR 2016"
        if not invoice.invoiceDate:
            m = re.search(r'[Dd]ate[d]?\s*:?\s*(\d{1,2})(?:ST|ND|RD|TH)?\s+([A-Za-z]{3,9}),?\s+(\d{4})', raw_text, re.I)
            if m:
                day = m.group(1).zfill(2)
                month_abbr = m.group(2).lower()[:3]
                year = m.group(3)
                if month_abbr in months:
                    invoice.invoiceDate = f"{day}/{months[month_abbr]}/{year}"
    
    # ===== CURRENCY — detect from invoice text, do NOT default to VND =====
    # Strategy: scan for explicit currency signals with confidence scoring.
    # Only assign VND if no other currency is found AND the invoice is clearly VN.
    if not invoice.currency:
        text_upper = raw_text.upper()

        # ----- Confidence scoring per currency -----
        scores = {}

        # USD signals
        usd_score = 0
        usd_score += raw_text.count('$') * 3          # $ symbol (strong)
        usd_score += raw_text.count('USD$') * 2
        if re.search(r'\bUSD\b', text_upper): usd_score += 5
        if re.search(r'\(USD\$?\)', text_upper): usd_score += 4
        if re.search(r'U\.S\.?\s*DOLLAR', text_upper): usd_score += 5
        if re.search(r'DOLLAR', text_upper): usd_score += 2
        # Table header patterns: "USD/MT", "USD/kg", "in USD", "Amount (USD)"
        if re.search(r'USD\s*/\s*\w+', text_upper): usd_score += 4
        if re.search(r'\bIN\s+USD\b', text_upper): usd_score += 5
        if re.search(r'AMOUNT\s*\(?USD', text_upper): usd_score += 5
        if re.search(r'PRICE\s*\(?USD', text_upper): usd_score += 5
        if re.search(r'TOTAL\s*\(?USD', text_upper): usd_score += 5
        if usd_score > 0:
            scores['USD'] = usd_score

        # EUR signals
        eur_score = 0
        eur_score += raw_text.count('€') * 3
        if re.search(r'\bEUR\b', text_upper): eur_score += 5
        if re.search(r'\(EURO\)', text_upper): eur_score += 4
        if re.search(r'\bEURO\b', text_upper): eur_score += 3
        # Table header: "in EUR", "Value in EUR", "Amount (EUR)"
        if re.search(r'\bIN\s+EUR\b', text_upper): eur_score += 5
        if re.search(r'AMOUNT\s*\(?EUR', text_upper): eur_score += 5
        if re.search(r'VALUE\s*\(?.*?EUR', text_upper): eur_score += 5
        if eur_score > 0:
            scores['EUR'] = eur_score

        # CNY / RMB signals
        cny_score = 0
        cny_score += raw_text.count('¥') * 3
        if re.search(r'\bCNY\b|\bRMB\b', text_upper): cny_score += 5
        if re.search(r'人民币', raw_text): cny_score += 5
        if cny_score > 0:
            scores['CNY'] = cny_score

        # GBP signals
        gbp_score = 0
        gbp_score += raw_text.count('£') * 3
        if re.search(r'\bGBP\b', text_upper): gbp_score += 5
        if gbp_score > 0:
            scores['GBP'] = gbp_score

        # JPY signals
        jpy_score = 0
        if re.search(r'\bJPY\b', text_upper): jpy_score += 5
        if jpy_score > 0:
            scores['JPY'] = jpy_score

        # VND signals (explicit label only — do NOT infer from absence)
        vnd_score = 0
        if re.search(r'[Đđ]ơn\s*vị\s*tính[^:]*:\s*VN[DĐ]', raw_text, re.I): vnd_score += 10
        if re.search(r'\bVN[DĐ]\b', text_upper): vnd_score += 3
        if re.search(r'đồng\b', raw_text, re.I): vnd_score += 2
        if re.search(r'nghìn|triệu|tỷ', raw_text, re.I): vnd_score += 1
        if vnd_score > 0:
            scores['VND'] = vnd_score

        # INR signals (Indian Rupee)
        inr_score = 0
        inr_score += raw_text.count('₹') * 3  # ₹ symbol (strong)
        if re.search(r'\bINR\b', text_upper): inr_score += 5
        if re.search(r'\bRupee[s]?\b', raw_text, re.I): inr_score += 3
        if re.search(r'\bGST\b|\bCGST\b|\bSGST\b|\bIGST\b', text_upper): inr_score += 4
        if inr_score > 0:
            scores['INR'] = inr_score

        # KRW signals (Korean Won)
        krw_score = 0
        krw_score += raw_text.count('₩') * 3
        if re.search(r'\bKRW\b', text_upper): krw_score += 5
        if '원' in raw_text: krw_score += 4
        if krw_score > 0:
            scores['KRW'] = krw_score

        # THB signals (Thai Baht)
        thb_score = 0
        thb_score += raw_text.count('฿') * 3
        if re.search(r'\bTHB\b', text_upper): thb_score += 5
        if re.search(r'\bBaht\b', raw_text, re.I): thb_score += 3
        if thb_score > 0:
            scores['THB'] = thb_score

        # TRY signals (Turkish Lira)
        try_score = 0
        try_score += raw_text.count('₺') * 3
        if re.search(r'\bTRY\b', text_upper): try_score += 5
        if re.search(r'Türk\s*Lira|Turkish\s*Lira', raw_text, re.I): try_score += 4
        if try_score > 0:
            scores['TRY'] = try_score

        # RUB signals (Russian Ruble)
        rub_score = 0
        rub_score += raw_text.count('₽') * 3
        if re.search(r'\bRUB\b', text_upper): rub_score += 5
        if re.search(r'рубл', raw_text, re.I): rub_score += 4
        if rub_score > 0:
            scores['RUB'] = rub_score

        # PHP signals (Philippine Peso)
        php_score = 0
        php_score += raw_text.count('₱') * 3
        if re.search(r'\bPHP\b', text_upper): php_score += 5
        if re.search(r'\bPeso\b', raw_text, re.I): php_score += 2
        if php_score > 0:
            scores['PHP'] = php_score

        # AUD signals (Australian Dollar)
        aud_score = 0
        if re.search(r'\bAUD\b', text_upper): aud_score += 5
        if re.search(r'A\$\s*[\d,.]', raw_text): aud_score += 4
        if re.search(r'Australian\s*Dollar', raw_text, re.I): aud_score += 4
        if aud_score > 0:
            scores['AUD'] = aud_score

        # CAD signals (Canadian Dollar)
        cad_score = 0
        if re.search(r'\bCAD\b', text_upper): cad_score += 5
        if re.search(r'CA?\$\s*[\d,.]', raw_text): cad_score += 4
        if re.search(r'Canadian\s*Dollar', raw_text, re.I): cad_score += 4
        if cad_score > 0:
            scores['CAD'] = cad_score

        # SGD signals (Singapore Dollar)
        sgd_score = 0
        if re.search(r'\bSGD\b', text_upper): sgd_score += 5
        if re.search(r'S\$\s*[\d,.]', raw_text): sgd_score += 4
        if re.search(r'Singapore\s*Dollar', raw_text, re.I): sgd_score += 4
        if sgd_score > 0:
            scores['SGD'] = sgd_score

        # CHF signals (Swiss Franc)
        chf_score = 0
        if re.search(r'\bCHF\b', text_upper): chf_score += 5
        if re.search(r'\bFr\.\s*[\d,.]', raw_text): chf_score += 3
        if re.search(r'Franken|Swiss\s*Franc', raw_text, re.I): chf_score += 4
        if chf_score > 0:
            scores['CHF'] = chf_score

        # HKD signals (Hong Kong Dollar)
        hkd_score = 0
        if re.search(r'\bHKD\b', text_upper): hkd_score += 5
        if re.search(r'HK\$\s*[\d,.]', raw_text): hkd_score += 4
        if re.search(r'Hong\s*Kong\s*Dollar', raw_text, re.I): hkd_score += 4
        if hkd_score > 0:
            scores['HKD'] = hkd_score

        # TWD signals (Taiwan Dollar)
        twd_score = 0
        if re.search(r'\bTWD\b', text_upper): twd_score += 5
        if re.search(r'NT\$\s*[\d,.]', raw_text): twd_score += 4
        if re.search(r'Taiwan\s*Dollar|新臺幣', raw_text, re.I): twd_score += 4
        if twd_score > 0:
            scores['TWD'] = twd_score

        # MYR signals (Malaysian Ringgit)
        myr_score = 0
        if re.search(r'\bMYR\b', text_upper): myr_score += 5
        if re.search(r'\bRM\s*[\d,.]', raw_text): myr_score += 4
        if re.search(r'Ringgit', raw_text, re.I): myr_score += 3
        if myr_score > 0:
            scores['MYR'] = myr_score

        # IDR signals (Indonesian Rupiah)
        idr_score = 0
        if re.search(r'\bIDR\b', text_upper): idr_score += 5
        if re.search(r'\bRp\s*[\d.]', raw_text): idr_score += 4
        if re.search(r'Rupiah', raw_text, re.I): idr_score += 3
        if idr_score > 0:
            scores['IDR'] = idr_score

        # Scandinavian currencies
        sek_score = 0
        if re.search(r'\bSEK\b', text_upper): sek_score += 5
        if re.search(r'Swedish\s*Kr', raw_text, re.I): sek_score += 4
        if sek_score > 0:
            scores['SEK'] = sek_score

        nok_score = 0
        if re.search(r'\bNOK\b', text_upper): nok_score += 5
        if re.search(r'Norwegian\s*Kr', raw_text, re.I): nok_score += 4
        if nok_score > 0:
            scores['NOK'] = nok_score

        dkk_score = 0
        if re.search(r'\bDKK\b', text_upper): dkk_score += 5
        if re.search(r'Danish\s*Kr', raw_text, re.I): dkk_score += 4
        if dkk_score > 0:
            scores['DKK'] = dkk_score

        # NZD signals (New Zealand Dollar)
        nzd_score = 0
        if re.search(r'\bNZD\b', text_upper): nzd_score += 5
        if re.search(r'NZ\$\s*[\d,.]', raw_text): nzd_score += 4
        if nzd_score > 0:
            scores['NZD'] = nzd_score

        # ZAR signals (South African Rand)
        zar_score = 0
        if re.search(r'\bZAR\b', text_upper): zar_score += 5
        if re.search(r'\bRand\b', raw_text, re.I): zar_score += 3
        if zar_score > 0:
            scores['ZAR'] = zar_score

        # AED signals (UAE Dirham)
        aed_score = 0
        if re.search(r'\bAED\b', text_upper): aed_score += 5
        if re.search(r'Dirham', raw_text, re.I): aed_score += 3
        if aed_score > 0:
            scores['AED'] = aed_score

        # SAR signals (Saudi Riyal)
        sar_score = 0
        if re.search(r'\bSAR\b', text_upper): sar_score += 5
        if '﷼' in raw_text: sar_score += 3
        if re.search(r'Riyal', raw_text, re.I): sar_score += 3
        if sar_score > 0:
            scores['SAR'] = sar_score

        # BRL signals (Brazilian Real)
        brl_score = 0
        if re.search(r'\bBRL\b', text_upper): brl_score += 5
        if re.search(r'R\$\s*[\d,.]', raw_text): brl_score += 4
        if re.search(r'\bReal\b|\bReais\b', raw_text, re.I): brl_score += 3
        if brl_score > 0:
            scores['BRL'] = brl_score

        # MXN signals (Mexican Peso)
        mxn_score = 0
        if re.search(r'\bMXN\b', text_upper): mxn_score += 5
        if re.search(r'Mexican\s*Peso', raw_text, re.I): mxn_score += 4
        if mxn_score > 0:
            scores['MXN'] = mxn_score

        # PLN signals (Polish Zloty)
        pln_score = 0
        if re.search(r'\bPLN\b', text_upper): pln_score += 5
        if 'zł' in raw_text or 'ZŁ' in raw_text: pln_score += 4
        if re.search(r'Zlot', raw_text, re.I): pln_score += 3
        if pln_score > 0:
            scores['PLN'] = pln_score

        # CZK signals (Czech Koruna)
        czk_score = 0
        if re.search(r'\bCZK\b', text_upper): czk_score += 5
        if 'Kč' in raw_text: czk_score += 4
        if re.search(r'Koruna', raw_text, re.I): czk_score += 3
        if czk_score > 0:
            scores['CZK'] = czk_score

        if scores:
            # Pick the currency with the highest confidence score
            invoice.currency = max(scores, key=lambda c: scores[c])
        # If no signal found → leave currency as None (do not force VND)
    
    # ===== INVOICE ID =====
    if not invoice.invoiceID:
        # Change 2: Global fallback for Vietnamese GTGT "Số:" pattern (before other patterns)
        _m_so = re.search(r'(?:^|\\n|\n)\s*Số\s*(?:\([^)]*\))?\s*[:：]\s*\*{0,2}(\d{3,})\*{0,2}', raw_text, re.I)
        if _m_so:
            # Verify not preceded by address context
            _before_so = raw_text[max(0, _m_so.start()-60):_m_so.start()]
            if not re.search(r'(?:địa chỉ|address|add\.|tài khoản)', _before_so, re.I):
                invoice.invoiceID = _m_so.group(1)
    if not invoice.invoiceID:
        # Pattern 0: BIÊN BẢN HỦY HÓA ĐƠN format - "Hóa đơn bị hủy: ... số 00000324"
        m = re.search(r'(?:hóa đơn bị hủy|hoá đơn bị huỷ)[^,\n]*,\s*(?:ký hiệu\s+)?[^,]+,\s*số\s+(\d{5,})', raw_text, re.I)
        if m:
            invoice.invoiceID = m.group(1)
            # print(f"DEBUG: Found InvoiceID via BIÊN BẢN HỦY format: '{m.group(1)}'")
        
        # Pattern 0.5: COMMERCIAL INVOICE - No20250321003 or INVOICE - No.12345
        if not invoice.invoiceID:
            m = re.search(r'INVOICE\s*[-–—]\s*No\.?\s*([A-Z0-9]+)', raw_text, re.I)
            if m:
                invoice.invoiceID = m.group(1)
                # print(f"DEBUG: Found InvoiceID via COMMERCIAL INVOICE format: '{m.group(1)}'")
        
        # Pattern 1: Explicit line start "Số: 3" or similar (but NOT "Số biên bản")
        # Must NOT be preceded by colon/comma (to avoid "Địa chỉ: Số 10, ngách...")
        if not invoice.invoiceID:
            m = re.search(r'(?:^|\n)\s*(?:Số|So|No\.?)(?!\s*biên bản)(?!\s*\d+\s*,\s*(?:ngách|ngõ|đường|phố|phường))\s*(?:\([^)]*\))?\s*[:\s]+\**(\d+)\**', raw_text, re.I)
            if m:
                # Extra check: reject if preceded by 'Địa chỉ' or 'Address' on same line
                _before_match = raw_text[max(0, m.start()-60):m.start()]
                # Extra check: reject if followed by address text (e.g. "No. 7 Bang Lang 1 Street")
                _after_match = raw_text[m.end():m.end()+80].strip().lower()
                _addr_kws_after = ['street', 'road', 'lane', 'ward', 'district', 'city', 'building',
                                   'floor', 'avenue', 'blvd', 'bang', 'đường', 'phố', 'ngõ',
                                   'phường', 'quận', 'huyện', 'tầng', 'tòa', 'thôn', 'xã']
                _is_address_after = any(ak in _after_match for ak in _addr_kws_after)
                if not re.search(r'(?:địa chỉ|address|add\.)', _before_match, re.I) and not _is_address_after:
                    val = m.group(1).lstrip('0') or m.group(1)
                    # print(f"DEBUG: Found InvoiceID via Regex 1 (Simple): '{val}'")
                    invoice.invoiceID = val
            else:
                # Pattern 2: Old complex pattern fallback (but NOT "Số biên bản")
                m = re.search(r'(?<!biên bản\s)Số\s*(?:\([^)]*\))?\s*[:\s]*\**(\d+)\**', raw_text, re.I)
                if m:
                    # Extra check: reject if preceded by 'Địa chỉ', 'Address', or address context
                    _before_match2 = raw_text[max(0, m.start()-80):m.start()]
                    if not re.search(r'(?:địa chỉ|address|add\.|tầng|phố|phường|đường|ngõ|ngách|thôn|xã|quận|huyện)', _before_match2, re.I):
                        val = m.group(1).lstrip('0') or m.group(1)
                        invoice.invoiceID = val
                
                # Pattern 3: Invoice No: 721 hoặc Invoice No.: 721
                if not invoice.invoiceID:
                     m = re.search(r'(?<!PROFORMA )Invoice\s*No\.?[:\s]*(\d+)', raw_text, re.I)
                     if m:
                         invoice.invoiceID = m.group(1)
                
                # Pattern 4 (No.):...
                if not invoice.invoiceID:
                     m = re.search(r'\(No\.?\)[:\s]*([\d]{3,12})', raw_text, re.I)
                     if m:
                         invoice.invoiceID = m.group(1).lstrip('0') or m.group(1)

                # Pattern 5: Mã của cơ quan thuế: M1-25-7FGBT-00000000315 (Viettel format)
                if not invoice.invoiceID:
                     m = re.search(r'Mã của cơ quan thuế[:\s]*[\w\-]+(\d{8,15})', raw_text, re.I)
                     if m:
                         invoice.invoiceID = m.group(1).lstrip('0') or m.group(1)
    
        # Pattern 6: Number: IVN2025121 or Invoice Number: 12345 (English format)
        # Exclude: Importer Number, Order Number, Account Number, etc.
        if not invoice.invoiceID:
            m = re.search(r'\bNumber\s*[:\s]+([A-Z]{2,5}\d+|\d{2,})', raw_text, re.I)
            if m:
                # Check context: exclude Importer Number, Order Number, Account Number, etc.
                before = raw_text[max(0, m.start()-20):m.start()].lower()
                _excluded_prefixes = ['importer', 'order', 'account', 'phone', 'contact',
                                      'sales order', 'waybill', 'tracking', 'package',
                                      'export', 'eori']
                if not any(before.rstrip().endswith(ep) for ep in _excluded_prefixes):
                    invoice.invoiceID = m.group(1)
        
        # Pattern 7: Invoice #: 67928 or Invoice#: 67928
        if not invoice.invoiceID:
            m = re.search(r'Invoice\s*#[:\s]*(\d+)', raw_text, re.I)
            if m:
                invoice.invoiceID = m.group(1)
    
    # ===== STANDALONE No: AND DATE: PATTERNS (non-pipe lines) =====
    # Only for English commercial invoices to avoid conflict with VN "Số (No.):" format
    if not invoice.invoiceID and _is_en_invoice(raw_text):
        _clean_for_no = re.sub(r'\*\*([^*]+)\*\*', r'\1', raw_text)
        m_no = re.search(r'(?:^|\n)\s*No\.?\s*:\s*([A-Z0-9][A-Za-z0-9\-/]{2,})', _clean_for_no)
        if m_no:
            invoice.invoiceID = m_no.group(1).strip()
    if not invoice.invoiceDate and _is_en_invoice(raw_text):
        _clean_for_date = re.sub(r'\*\*([^*]+)\*\*', r'\1', raw_text)
        m_date = re.search(r'(?:^|\n)\s*DATE\s*:\s*([A-Z]{3,9})\s+(\d{1,2}),?\s+(\d{4})', _clean_for_date, re.I)
        if m_date:
            _months = {'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04', 'may': '05', 'jun': '06',
                       'jul': '07', 'aug': '08', 'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12'}
            _mabbr = m_date.group(1).lower()[:3]
            if _mabbr in _months:
                invoice.invoiceDate = f"{m_date.group(2).zfill(2)}/{_months[_mabbr]}/{m_date.group(3)}"

    # ===== INVOICE FORM NO (Ký hiệu / Serial) =====
    if not invoice.invoiceFormNo:
        # Pattern 0: BIÊN BẢN HỦY HÓA ĐƠN format - "Hóa đơn bị hủy: Mẫu số 1, ký hiệu C25THO"
        # Extract: invoiceSerial = "1", invoiceFormNo = "C25THO"
        m = re.search(r'(?:hóa đơn bị hủy|hoá đơn bị huỷ)[:\s]*[Mm]ẫu\s*(?:số)?\s*(\d+)\s*,\s*ký hiệu\s+([A-Z0-9]+)', raw_text, re.I)
        if m:
            if m.group(1) and not invoice.invoiceSerial:
                invoice.invoiceSerial = m.group(1)
            if m.group(2):
                invoice.invoiceFormNo = m.group(2)
                # print(f"DEBUG: Found FormNo via BIÊN BẢN HỦY format: Serial='{m.group(1)}', FormNo='{m.group(2)}'")
        
        # Pattern 0b: Direct "Mẫu số:" extraction (may be outside header block)
        if not invoice.invoiceFormNo:
            m_mau = re.search(r'[Mm]ẫu\s*số[^:\n]*:\s*(\S+)', raw_text)
            if m_mau:
                _mau_val = m_mau.group(1).strip()
                if len(_mau_val) >= 3:
                    invoice.invoiceFormNo = _mau_val

        # Pattern 1: Ký hiệu: 1C25THO hoặc Kí hiệu (Serial No): 1C25TTD hoặc Ký hiệu (Series): 1C25TLT
        # Skip lines with "thay thế" (replacement invoice references)
        if not invoice.invoiceFormNo:
            lines = raw_text.split('\\n')  # Handle escaped newlines
            for line in lines:
                low = line.lower()
                if ('ký hiệu' in low or 'kí hiệu' in low) and 'thay thế' not in low and 'hóa đơn bị hủy' not in low and 'điều chỉnh' not in low:
                    # Extract value after colon - support Series/Serial keywords
                    m = re.search(r'(?:ký hiệu|kí hiệu)\s*(?:\([^)]*\))?\s*[:\s]+([A-Z0-9/\-]+)', line, re.I)
                    if m:
                        serial_value = m.group(1).strip()
                        serial, form_no = parse_serial_form_no(serial_value)
                        if not invoice.invoiceSerial and serial:
                            invoice.invoiceSerial = serial
                        if not invoice.invoiceFormNo and form_no:
                            invoice.invoiceFormNo = form_no
                        elif not invoice.invoiceFormNo and serial:
                            invoice.invoiceFormNo = serial_value
                        break
        
        # Pattern 2: Mã của cơ quan thuế: M1-25-7FGBT-00000000315 (Viettel format)
        # Use the middle part (7FGBT) as invoiceFormNo
        if not invoice.invoiceFormNo:
            m = re.search(r'Mã của cơ quan thuế[:\s]*([\w\-]+)', raw_text, re.I)
            if m:
                # Extract formNo from pattern like M1-25-7FGBT-00000000315
                parts = m.group(1).split('-')
                if len(parts) >= 3:
                    invoice.invoiceFormNo = parts[2]  # e.g. "7FGBT"
    
    # ===== INVOICE TOTAL — highest priority override =====
    # "Invoice Total (Incoterms® 2010)\nFOB Brisbane USD $50340.00"
    # Always override — "Invoice Total" is the most authoritative total label
    m_inv_total = re.search(r'Invoice\s+Total[^\n]*\n[^\n]*(?:USD\s*)?\$\s*([\d\,\.]+)', raw_text, re.I)
    if m_inv_total:
        val = safe_parse_float(m_inv_total.group(1))
        if val and val > 0:
            invoice.totalAmount = val

    # ===== TOTAL AMOUNT (fallback from raw text) =====
    if not invoice.totalAmount:
        # Pattern 1: Tổng cộng tiền thanh toán (Total payment): 4.811.400 (non-table)
        m = re.search(r'[Tt]ổng cộng tiền thanh toán[^:]*:\s*([\d\.\,]+)', raw_text)
        if m:
            num = m.group(1).replace('.', '').replace(',', '')
            if num.isdigit() and int(num) > 1000:
                invoice.totalAmount = float(num)
        
        # Pattern 2: |Tổng cộng tiền thanh toán:|||||||873.400|| (table format)
        if not invoice.totalAmount:
            m = re.search(r'\|[Tt]ổng cộng tiền thanh toán[^|]*\|[\|\s]*([\d\.\,]+)', raw_text)
            if m:
                num = m.group(1).replace('.', '').replace(',', '')
                if num.isdigit() and int(num) > 1000:
                    invoice.totalAmount = float(num)
        
        # Pattern 3: Total payment: X or Total Amount: X
        if not invoice.totalAmount:
            m = re.search(r'[Tt]otal\s+[Pp]ayment[^:]*:\s*([\d\.\,]+)', raw_text)
            if m:
                num = m.group(1).replace('.', '').replace(',', '')
                if num.isdigit() and int(num) > 1000:
                    invoice.totalAmount = float(num)
        
        # Pattern 4: Tổng tiền thanh toán (Total Amount): X
        if not invoice.totalAmount:
            m = re.search(r'[Tt]ổng tiền thanh toán[^:]*:\s*([\d\.\,]+)', raw_text)
            if m:
                num = m.group(1).replace('.', '').replace(',', '')
                if num.isdigit() and int(num) > 1000:
                    invoice.totalAmount = float(num)
        
        # Pattern 5: **Tổng cộng tiền thanh toán:** 177.993.000 (markdown bold)
        if not invoice.totalAmount:
            m = re.search(r'\*\*[Tt]ổng cộng tiền thanh toán[:\*]*\s*([\d\.\,]+)', raw_text)
            if m:
                num = m.group(1).replace('.', '').replace(',', '')
                if num.isdigit() and int(num) > 1000:
                    invoice.totalAmount = float(num)
        
        # Pattern 6: Tổng cộng (Total payment) | 23.940.000 |
        if not invoice.totalAmount:
            m = re.search(r'[Tt]ổng cộng\s*\([^)]*\)[^|\d]*\|\s*([\d\.\,]+)', raw_text)
            if m:
                num = m.group(1).replace('.', '').replace(',', '')
                if num.isdigit() and int(num) > 1000:
                    invoice.totalAmount = float(num)
        
        # Pattern 7: TỔNG CỘNG TIỀN THANH TOÁN (Total payment): X (uppercase)
        if not invoice.totalAmount:
            m = re.search(r'TỔNG CỘNG[^:]*:\s*([\d\.\,]+)', raw_text)
            if m:
                num = m.group(1).replace('.', '').replace(',', '')
                if num.isdigit() and int(num) > 1000:
                    invoice.totalAmount = float(num)
        
        # Pattern 8: English - "In Total | X | Y.YY |" or "| In Total | X | 605.20 |"
        if not invoice.totalAmount:
            m = re.search(r'\|\s*In\s+Total\s*\|[^|]*\|\s*([\d\.\,]+)\s*\|', raw_text, re.I)
            if m:
                num = m.group(1).replace(',', '')
                try:
                    invoice.totalAmount = float(num)
                except:
                    pass
        
        # Pattern 9: English - "Total Amount (EURO): X" or similar
        if not invoice.totalAmount:
            m = re.search(r'Total\s+Amount\s*\([^)]*\)\s*[:\|]\s*([\d\.\,]+)', raw_text, re.I)
            if m:
                num = m.group(1).replace(',', '')
                try:
                    invoice.totalAmount = float(num)
                except:
                    pass
        
        # Pattern 10: Total Value(总申报价值): $2,614 or "Total Value: 2614"
        #   Also handles pipe-table: "Total Value (总申报价值): | $2,614 |"
        if not invoice.totalAmount:
            m = re.search(r'Total\s+Value[^:\n]*(?:\([^)]*\))?\s*:\s*\|?\s*\$?([\d\.\,]+)', raw_text, re.I)
            if m:
                num = m.group(1).replace(',', '')
                try:
                    val = float(num)
                    if val > 0:
                        invoice.totalAmount = val
                except:
                    pass
        
        # Pattern 11: Fallback - use invoiceTotalInWord if available
        # Convert Vietnamese words to number (e.g. "Ba trăm bảy mươi triệu" -> 370000000)
        if not invoice.totalAmount and invoice.invoiceTotalInWord:
            converted = vietnamese_words_to_number(invoice.invoiceTotalInWord)
            if converted > 0:
                invoice.totalAmount = converted
        
        
        # Pattern 12b: "| Invoice Total ... | ... | USD | $25475.00 |" (pipe table)
        if not invoice.totalAmount:
            m = re.search(r'Invoice\s+Total[^|]*(?:\|[^|]*){2,}\|\s*\$?([\d\,\.]+)', raw_text, re.I)
            if m:
                val = safe_parse_float(m.group(1))
                if val and val > 0:
                    invoice.totalAmount = val

        # Pattern 12: English - "TOTAL: GBP 32499" or "TOTAL: 32,499" (standalone TOTAL line)
        # Exclude "Total This Page" (page subtotal) and "Total Net Weight" etc.
        if not invoice.totalAmount:
            m = re.search(r'\bTOTAL\b(?!\s+(?:This\s+Page|Net\s+Weight|Gross\s+Weight|Volume|Packages?))[:\s]*(?:[A-Z]{3}\s*)?([\d\.\,]+)', raw_text, re.I)
            if m:
                num = m.group(1).replace(',', '')
                try:
                    val = float(num)
                    if val > 0:
                        invoice.totalAmount = val
                except:
                    pass
        
        # Pattern 13: "Total This Page | ... | 25475.00 |" or "Consignment Total | ... | 25475.00 |"
        if not invoice.totalAmount:
            m = re.search(r'(?:Total\s+This\s+Page|Consignment\s+Total|Invoice\s+Total)[^|]*\|[^|]*\|\s*\$?([\d\,\.]+)', raw_text, re.I)
            if m:
                val = safe_parse_float(m.group(1))
                if val and val > 0:
                    invoice.totalAmount = val
    
        
        # Pattern 16: Last/largest $USD value in text as fallback
        if not invoice.totalAmount:
            usd_vals = re.findall(r'\$\s*(?:USD\s*)?([\d\,\.]+)', raw_text, re.I)
            if usd_vals:
                max_val = 0
                for v in usd_vals:
                    parsed = safe_parse_float(v)
                    if parsed and parsed > max_val:
                        max_val = parsed
                if max_val > 10:
                    invoice.totalAmount = max_val
    
    # ===== CURRENCY DETECTION (Auto-detect from raw text) =====
    if not invoice.currency or invoice.currency == "VND":
        # Check if raw text contains non-VND currency prefixes/codes
        currency_patterns = [
            (r'\b(GBP)\s+[\d\.\,]+', 'GBP'),
            (r'\b(USD)\s+[\d\.\,]+', 'USD'),
            (r'\b(EUR)\s+[\d\.\,]+', 'EUR'),
            (r'\b(JPY)\s+[\d\.\,]+', 'JPY'),
            (r'\b(CNY)\s+[\d\.\,]+', 'CNY'),
            (r'\b(SGD)\s+[\d\.\,]+', 'SGD'),
            (r'\b(AUD)\s+[\d\.\,]+', 'AUD'),
            (r'\b(CAD)\s+[\d\.\,]+', 'CAD'),
            (r'\b(KRW)\s+[\d\.\,]+', 'KRW'),
            (r'\b(THB)\s+[\d\.\,]+', 'THB'),
        ]
        for pattern, curr in currency_patterns:
            if re.search(pattern, raw_text, re.I):
                invoice.currency = curr
                break
    
    # ===== SELLER BANK INFO (fallback from BENEFICIARY section) =====
    # For commercial invoices where BANK INFORMATION appears outside seller block
    if not invoice.sellerBankAccountNumber:
        m = re.search(r"BENEFICIARY'?S?\s*ACCOUNT[:\s]*([0-9]+)", raw_text, re.I)
        if m:
            invoice.sellerBankAccountNumber = m.group(1)
    
    if not invoice.sellerBank:
        m = re.search(r"BENEFICIARY'?S?\s*BANK[:\s]*(.+?)(?:\n|$)", raw_text, re.I)
        if m:
            invoice.sellerBank = m.group(1).strip()
    
    # ===== SELLER PHONE (fallback) =====
    if not invoice.sellerPhoneNumber:
        m = re.search(r'TEL[:\s]+(\+?[\d\s\-\(\)\.]{7,})', raw_text, re.I)
        if m:
            phone = re.sub(r'[\s\-\(\)]', '', m.group(1)).strip()
            if len(phone) >= 7:
                invoice.sellerPhoneNumber = m.group(1).strip()
    
    # ===== INVOICE NAME (fallback) =====
    if not invoice.invoiceName:
        # Pattern 1: Standalone "INVOICE" or "PACKING LIST" or "HÓA ĐƠN GTGT"
        m = re.search(r'^(INVOICE|PACKING\s+LIST|HÓA ĐƠN\s*(?:GTGT|GIÁ TRỊ GIA TĂNG)?)\s*$', raw_text, re.I | re.MULTILINE)
        if m:
            invoice.invoiceName = m.group(1).strip()
        
        # Pattern 2: "COMMERCIAL INVOICE", "PROFORMA INVOICE", "TAX INVOICE"
        if not invoice.invoiceName:
            m = re.search(r'(COMMERCIAL\s+INVOICE|PROFORMA\s+INVOICE|TAX\s+INVOICE|PACKING\s+LIST)', raw_text, re.I)
            if m:
                invoice.invoiceName = m.group(1).strip().upper()
        
        # Pattern 3: Final fallback — for English invoices without explicit name, use "INVOICE"
        if not invoice.invoiceName and _is_en_invoice(raw_text):
            invoice.invoiceName = "INVOICE"
    
    # ===== SELLER NAME (fallback + override) =====
    # Pattern 1: "Đơn vị bán:" hoặc "Đơn vị bán hàng:" - ALWAYS search
    # This is the most reliable pattern, so it should override signature-based garbage
    m = re.search(r'[Đđ]ơn vị bán[^:]*:\s*([^\n]+)', raw_text)
    if m:
        val = m.group(1).strip().strip('*')
        if val and len(val) > 5:
            # Only override if current value is missing, too short, or truncated (likely from signature)
            if not invoice.sellerName or len(invoice.sellerName) < 20:
                invoice.sellerName = val
    
    # Pattern 2: English - "THE Seller: Company: TLSH SAS"
    if not invoice.sellerName:
        m = re.search(r'THE\s+Seller[:\s]*\n?Company[:\s]*([^\n]+)', raw_text, re.I)
        if m:
            val = m.group(1).strip().strip('*')
            if val and len(val) > 2:
                invoice.sellerName = val
    
    # Pattern 3: SHIPPER/COMPANY NAME公司名称: → next line is company name
    if not invoice.sellerName:
        m = re.search(r'SHIPPER[^\n]*(?:COMPANY\s*NAME|公司名称)[^\n]*[:\s]*\n([^\n]+)', raw_text, re.I)
        if m:
            val = m.group(1).strip().strip('*')
            if val and len(val) > 2:
                invoice.sellerName = val
    
    # Pattern 4: BENEFICIARY: Gunri Precision Hardware Co., Ltd
    if not invoice.sellerName:
        m = re.search(r'BENEFICIARY\s*:\s*([^\n]+)', raw_text, re.I)
        if m:
            val = m.group(1).strip().strip('*')
            # Should NOT be "BENEFICIARY'S ACCOUNT" or "BENEFICIARY'S BANK"
            if val and len(val) > 2 and "account" not in val.lower() and "bank" not in val.lower():
                invoice.sellerName = val
    
    # Pattern 5: Company: at start of seller section
    if not invoice.sellerName:
        seller_pos = raw_text.lower().find('the seller')
        if seller_pos > 0:
            seller_text = raw_text[seller_pos:seller_pos+300]
            m = re.search(r'Company[:\s]*([^\n]+)', seller_text, re.I)
            if m:
                val = m.group(1).strip().strip('*')
                if val and len(val) > 2:
                    invoice.sellerName = val
    
    # Pattern 6: "Ký bởi:" signature section (final fallback)
    if not invoice.sellerName:
        m = re.search(r'[Kk]ý\s+bởi[:\s]*([^\n]+)', raw_text)
        if m:
            val = m.group(1).strip().strip('*')
            if val and len(val) > 5 and any(company in val.upper() for company in ['CÔNG TY', 'CHI NHÁNH', 'CORPORATION', 'CO.']):
                invoice.sellerName = val
    
    # SANITIZE: If sellerName is a section header label (not actual company), clear it
    if invoice.sellerName:
        seller_lower = invoice.sellerName.lower()
        header_labels = ["information", "寄货人", "资料", "收货人", "shipper", "consignee"]
        if any(lbl in seller_lower for lbl in header_labels):
            invoice.sellerName = None
    
    # ===== SELLER TAX CODE (fallback) =====
    if not invoice.sellerTaxCode:
        # Look for first tax code after seller name or "Mã số thuế" that appears BEFORE buyer section
        # Pattern: Mã số thuế: 0108921542 or MST (Tax Code): 0110265168
        
        # Find buyer section start to limit search area
        buyer_keywords = ["người mua", "tên người mua", "buyer", "the buyer",
                          "consignee", "bill to", "sold to", "ship to", "importer"]
        buyer_pos = len(raw_text)  # Default: end of text
        raw_lower = raw_text.lower()
        for kw in buyer_keywords:
            pos = raw_lower.find(kw)
            if pos > 0 and pos < buyer_pos:
                buyer_pos = pos
        
        # Search only in text BEFORE buyer section
        seller_section = raw_text[:buyer_pos]
        m = re.search(r'(?:[Mm]ã số thuế|MST)[^:]*:\s*(\d[\d\s\-]+)', seller_section)
        if m:
            tax = re.sub(r'\s+', '', m.group(1))  # Remove spaces
            if len(tax) >= 10:
                invoice.sellerTaxCode = tax
        
        # Pattern 2: VAT: FR69848615092 (for European invoices)
        if not invoice.sellerTaxCode:
            seller_pos = raw_text.lower().find('the seller')
            if seller_pos > 0:
                seller_text = raw_text[seller_pos:seller_pos+400]
                m = re.search(r'VAT[:\s]*([A-Z]{2}[\w]+)', seller_text, re.I)
                if m:
                    invoice.sellerTaxCode = m.group(1)
        
        # Pattern 3: "Company Tax ID: 93377112" or "Tax ID: 12345678" (EN invoices)
        if not invoice.sellerTaxCode:
            # Search in seller section only (before buyer/consignee)
            _buyer_kws = ["consignee", "bill to", "sold to", "ship to", "importer",
                          "người mua", "the buyer", "buyer:"]
            _buyer_pos = len(raw_text)
            _raw_low = raw_text.lower()
            for _bk in _buyer_kws:
                _bp = _raw_low.find(_bk)
                if _bp > 0 and _bp < _buyer_pos:
                    _buyer_pos = _bp
            _seller_section = raw_text[:_buyer_pos]
            m = re.search(r'(?:Company\s+)?Tax\s*(?:ID|Code)\s*[:\s]\s*([\w\-]+)', _seller_section, re.I)
            if m:
                tax_val = m.group(1).strip()
                if len(tax_val) >= 5:
                    invoice.sellerTaxCode = tax_val
    
    # ===== SELLER EMAIL (fallback) =====
    if not invoice.sellerEmail:
        # Search for email in seller section (before buyer/consignee)
        _buyer_kws = ["consignee", "bill to", "sold to", "ship to", "importer",
                      "người mua", "the buyer", "buyer:"]
        _buyer_pos = len(raw_text)
        _raw_low = raw_text.lower()
        for _bk in _buyer_kws:
            _bp = _raw_low.find(_bk)
            if _bp > 0 and _bp < _buyer_pos:
                _buyer_pos = _bp
        _seller_section = raw_text[:_buyer_pos]
        m = re.search(r'[\w\.\-+]+@[\w\.\-]+\.\w{2,}', _seller_section)
        if m:
            invoice.sellerEmail = m.group(0)
    # ===== BUYER NAME (fallback) =====
    if not invoice.buyerName:
        # Pattern 1: "Tên đơn vị:" hoặc "Company's name:"
        m = re.search(r'(?:[Tt]ên đơn vị|[Cc]ompany\'?s?\s*name)[^:]*:\s*([^\n]+)', raw_text)
        if m:
            val = m.group(1).strip().strip('*')
            if val and len(val) > 3:
                invoice.buyerName = val
        
        # Pattern 2: "Họ tên người mua hàng:", "Người mua hàng:", "Tên người mua:"
        if not invoice.buyerName:
            m = re.search(r'(?:[Hh]ọ\s*tên\s*người\s*mua|[Nn]gười\s*mua\s*hàng|[Tt]ên\s*người\s*mua|[Bb]uyer)[^:]*:\s*([^\n]+)', raw_text)
            if m:
                val = m.group(1).strip().strip('*')
                if val and len(val) > 3 and not re.match(r'^\*+$', val):
                    if not any(sig in val.lower() for sig in ['ký bởi', 'signed', 'signature', 'người bán']):
                        invoice.buyerName = val
        
        # Pattern 3: "Đơn vị mua hàng:" hoặc "Khách hàng:"
        if not invoice.buyerName:
            m = re.search(r'(?:[Đđ]ơn\s*vị\s*mua\s*hàng|[Kk]hách\s*hàng)[^:]*:\s*([^\n]+)', raw_text)
            if m:
                val = m.group(1).strip().strip('*')
                if val and len(val) > 3:
                    invoice.buyerName = val
        
        # Pattern 4: "Bill to: Pioneer Route Materials" (English invoices)
        if not invoice.buyerName:
            m = re.search(r'[Bb]ill\s+to[:\s]*([^\n]+)', raw_text)
            if m:
                val = m.group(1).strip().strip('*')
                if val and len(val) > 3:
                    invoice.buyerName = val
        
        # Pattern 5: "Customer: Pioneer Route Materials" (English invoices)
        if not invoice.buyerName:
            m = re.search(r'[Cc]ustomer[:\s]*([^\n]+)', raw_text)
            if m:
                val = m.group(1).strip().strip('*')
                if val and len(val) > 3 and 'address' not in val.lower() and '|' not in val:
                    invoice.buyerName = val
        
        # Pattern 6: CONSIGNEE/COMPANY NAME公司名称: → next line is buyer name
        if not invoice.buyerName:
            m = re.search(r'CONSIGNEE[^\n]*(?:COMPANY\s*NAME|公司名称)[^\n]*[:\s]*\n([^\n]+)', raw_text, re.I)
            if m:
                val = m.group(1).strip().strip('*')
                if val and len(val) > 2:
                    invoice.buyerName = val
    
    # ===== BUYER TAX CODE (fallback) =====
    if not invoice.buyerTaxCode:
        # Find tax code AFTER buyer section markers
        buyer_markers = ['người mua', 'buyer', 'khách hàng', 'đơn vị mua', 'tên đơn vị']
        buyer_pos = -1
        for marker in buyer_markers:
            pos = raw_text.lower().find(marker)
            if pos != -1:
                buyer_pos = max(buyer_pos, pos)
        
        if buyer_pos > 0:
            # Search for tax code after buyer section
            buyer_text = raw_text[buyer_pos:]
            m = re.search(r'[Mm]ã\s*số\s*thuế[^:]*:\s*(\d{10,14})', buyer_text)
            if m:
                invoice.buyerTaxCode = m.group(1)
    
    # ===== POST-PROCESS: Extract phone numbers embedded in address fields =====
    _phone_re = re.compile(r'[\+]?\d[\d\s\-\(\)]{7,}')
    for _prefix in ['seller', 'buyer']:
        addr_field = f'{_prefix}Address'
        phone_field = f'{_prefix}PhoneNumber'
        addr_val = getattr(invoice, addr_field, None)
        phone_val = getattr(invoice, phone_field, None)
        if addr_val and not phone_val:
            # Check if address contains a phone number segment
            parts = [p.strip() for p in addr_val.split(',')]
            cleaned_parts = []
            for part in parts:
                if _phone_re.fullmatch(part.strip()):
                    setattr(invoice, phone_field, part.strip())
                else:
                    cleaned_parts.append(part)
            if len(cleaned_parts) < len(parts):
                setattr(invoice, addr_field, ', '.join(cleaned_parts).strip(', '))
    # ===== PRE-TAX PRICE (fallback) =====
    if not invoice.preTaxPrice:
        # Pattern 1: "Cộng tiền hàng:" hoặc "Tiền hàng chưa thuế:"
        patterns = [
            r'[Cc]ộng\s*tiền\s*hàng[^:]*:\s*([\d\.\,]+)',
            r'[Tt]iền\s*(?:hàng\s*)?chưa\s*thuế[^:]*:\s*([\d\.\,]+)',
            r'[Tt]hành\s*tiền\s*chưa\s*thuế[^:]*:\s*([\d\.\,]+)',
            r'[Ss]ubtotal[^:]*:\s*(?:[A-Z]{3}\s*)?([\d\.\,]+)',  # Support "Subtotal: GBP 29,545"
            r'[Ii]nvoice\s*[Ss]ubtotal[^:]*:\s*(?:[A-Z]{3}\s*)?([\d\.\,]+)',  # Invoice Subtotal: GBP 29,545
        ]
        for pattern in patterns:
            m = re.search(pattern, raw_text)
            if m:
                val = safe_parse_float(m.group(1))
                if val and val > 0:
                    invoice.preTaxPrice = val
                    break
    
    # ===== TAX AMOUNT (fallback) =====
    if not invoice.taxAmount:
        # Pattern 1: "Thuế GTGT:" hoặc "Tiền thuế GTGT:"
        patterns = [
            r'[Tt]huế\s*(?:GTGT|giá\s*trị\s*gia\s*tăng)[^:]*:\s*([\d\.\,]+)',
            r'[Tt]iền\s*thuế[^:]*:\s*([\d\.\,]+)',
            # VAT: only when followed by a number, NOT 'VAT Excluded', 'VAT on', 'VAT free'
            r'VAT\s*(?!\s*(?:excluded|on\s|free|rate|amount)[\s|])[^:\n]*:\s*([\d\.\,]+)',
            r'[Ss]ales\s*[Tt]ax[^:]*:\s*(?:[A-Z]{3}\s*)?([\d\.\,]+)',  # Sales Tax: GBP 2,954
        ]
        for pattern in patterns:
            m = re.search(pattern, raw_text)
            if m:
                num = m.group(1).replace('.', '').replace(',', '')
                if num.isdigit() and int(num) > 0:
                    invoice.taxAmount = float(num)
                    break
    
    # ===== TAX PERCENT (fallback) =====
    if not invoice.taxPercent:
        # Pattern 1: "Thuế suất: 8%" hoặc "VAT: 10%"
        patterns = [
            r'[Tt]huế\s*suất[^:]*:\s*(\d{1,2})\s*%',
            r'VAT[^:]*:\s*(\d{1,2})\s*%',
            r'\((\d{1,2})%\s*(?:GTGT|VAT)\)',
            r'[Tt]ax\s*[Rr]ate[^:]*:\s*(\d{1,2})\s*%',   # Tax Rate: 10%
        ]
        for pattern in patterns:
            m = re.search(pattern, raw_text)
            if m:
                invoice.taxPercent = m.group(1)
                break
    
    # ===== DISCOUNT TOTAL (NEW!) =====
    if not invoice.discountTotal:
        # Pattern: "Chiết khấu:", "Giảm giá:", "Discount:" — must be on SAME LINE (no newline crossing)
        patterns = [
            r'[Cc]hiết\s*khấu[^:\n]*:\s*([\d\.\,]+)',
            r'[Gg]iảm\s*giá[^:\n]*:\s*([\d\.\,]+)',
            # Match Discount: with colon — not "Discounts" column header
            r'discount\s*:[\s]*([\d\.\,]+)',
            # Bold label format: "**Discount** -$8.75" or "Discount $8.75"
            r'\bdiscount\b[*]*\s*[-]?\s*\$?\s*([\d,\.]+)',
            # Pipe-table: "| DISCOUNT | -$300.00 |"
            r'\|\s*discount\s*\|\s*[-]?\s*\$?([\d,\.]+)',
        ]
        for pattern in patterns:
            m = re.search(pattern, raw_text, re.I)
            if m:
                val = safe_parse_float(m.group(1))
                if val and val > 0:
                    invoice.discountTotal = val
                    break
    
    # ===== PAYMENT METHOD (fallback) =====
    if not invoice.paymentMethod:
        # Pattern: "Hình thức thanh toán:", "Payment method:", "Payment:"
        patterns = [
            r'[Hh]ình\s*thức\s*thanh\s*toán[^:\n]*[:\s]+([^\n|]+)',  # Relaxed [^:\n]* to match line till colon
            r'[Pp]ayment\s+(?:method|by|terms?)\s*[:\s]+([^\n|]+)',
            r'[Tt]erms?\s+of\s+(?:payment|sale)\s*[:\n]\s*([^\n|]+)',
            r'[Pp]ayment\s*:\s*([^\n|]+)',
        ]
        _pm_text = re.sub(r'\*\*([^*]+)\*\*', r'\1', raw_text)
        for pattern in patterns:
            m = re.search(pattern, _pm_text, re.I)
            if m:
                val = m.group(1).strip().strip('*|')
                # Clean up trailing keywords that might leak into the value
                val = re.split(r'\s+(?:Hạn|Tổng|Số|Đơn|Tại|Thuế)', val, maxsplit=1)[0].strip()
                if val and len(val) >= 2:
                    # Reject bank-related values (not payment methods)
                    _val_low = val.lower()
                    if any(_val_low.startswith(k) for k in [
                        'beneficiary', 'account', 'bank', 'swift', 'iban',
                        'address', 'room ', 'floor ']):
                        continue
                    invoice.paymentMethod = val
                    break
    
    # ===== INVOICE TOTAL IN WORD (fallback) =====
    if not invoice.invoiceTotalInWord:
        # Pattern 1: "Bằng chữ:" hoặc "Số tiền bằng chữ:"
        # Strip markdown bold/italic for cleaner matching
        _word_text = re.sub(r'\*\*([^*]+)\*\*', r'\1', raw_text)
        _word_text = re.sub(r'\*([^*]+)\*', r'\1', _word_text)
        patterns = [
            r'[Bb]ằng\s*chữ[^:]*:\s*([^\n]+)',
            r'[Ss]ố\s*tiền\s*(?:viết\s*)?bằng\s*chữ[^:]*:\s*([^\n]+)',
            r'[Ii]n\s*words?[^:]*:\s*([^\n]+)',
            # EN: "SAY USD TWO THOUSAND..." or "SAY: US DOLLARS..."
            # Capture entire line to avoid catastrophic backtracking
            r'(?i)\bSAY\b[:\s]+([^\n]+)',
            # EN: "Say by word: Twelve thousand... dollars and seventy-six cents only"
            r'(?i)\b(?:Say\s+by\s+word|Say\s+total)[:\s]+([^\n]+)',
            # EN: "Total in Words: One Hundred..."
            r'(?i)Total\s+in\s+Words?\s*[:\|]\s*([^\n]+)',
            # Pipe table: "| US DOLLARS SIXTY FIVE THOUSAND... ONLY |"
            r'(?i)\|\s*((?:US\s+DOLLARS?|UNITED\s+STATES\s+DOLLARS?|EUROS?|POUNDS?\s+STERLING)\s[A-Z ,]+?(?:ONLY|CENTS?\s+\w+\s+ONLY))\s*\|',
            # EN standalone: "(IN WORDS: ...)" or standalone "US DOLLARS ... ONLY"
            r'(?i)\(IN\s+WORDS?\s*:?\s*([^)]+)\)',
        ]
        for pattern in patterns:
            m = re.search(pattern, _word_text)
            if m:
                val = clean_invoice_total_in_word(m.group(1))
                if val and len(val) > 5:
                    invoice.invoiceTotalInWord = val
                    break


# ═══════════════════════════════════════════════════════════════════════════════
# EN COMMERCIAL INVOICE PRE-PARSER
# Runs BEFORE detect_blocks() to extract fields from EN invoice patterns.
# Only activates when VN markers are absent. Does NOT modify VN logic.
# ═══════════════════════════════════════════════════════════════════════════════

def _is_en_invoice(raw_text: str) -> bool:
    """Check if this is an EN commercial invoice (not VN tax invoice)."""
    low = raw_text.lower()
    # VN markers — if ANY present, skip EN pre-parser
    vn_markers = ["hóa đơn giá trị gia tăng", "đơn vị bán hàng", "mã số thuế",
                  "phiếu xuất kho", "phiếu nhập kho", "biên bản hủy",
                  "người mua hàng", "tiền thuế gtgt", "cộng tiền hàng"]
    if any(m in low for m in vn_markers):
        return False
    # EN markers — need at least one
    en_markers = ["commercial invoice", "proforma invoice", "packing list", "invoice",
                  "bill to", "consignee", "shipper", "exporter",
                  "the seller:", "the buyer:", "ship to", "ship from"]
    return any(m in low for m in en_markers)


def _extract_after_label(text: str, label_pattern: str, max_lines: int = 3) -> tuple:
    """Extract name + address lines after a label pattern.
    Returns (name, address) or (None, None).
    """
    m = re.search(label_pattern, text, re.I | re.MULTILINE)
    if not m:
        return None, None
    
    # Check if value is on the same line after ":"
    rest_of_line = text[m.end():].split('\n')[0].strip().strip(':').strip()
    
    # Collect following lines
    after = text[m.end():]
    lines = []
    for line in after.split('\n'):
        line = line.strip().strip('*').strip('#').strip()
        # Remove markdown bold
        line = re.sub(r'\*\*([^*]+)\*\*', r'\1', line)
        if not line or line == '---':
            if lines:
                break
            continue
        # Stop at next section label or table line
        low = line.lower()
        # Check for exact standalone labels (no colon) like "Address", "Phone", "Email"
        _exact_labels = {'address', 'phone', 'email', 'tel', 'fax', 'mobile', 'contact person',
                         'company name', 'full name', 'zip code', 'city', 'country'}
        if low.strip('- :') in _exact_labels and lines:
            break  # Stop if we already have some data and hit a new label
        if any(k in low for k in ['address:', 'phone:', 'tel:', 'fax:', 'email:',
                                    'mobile:', 'contact:', 'website:',
                                    'invoice no', 'inv. no', 'invoice date',
                                    'inv. date', 'date:', 'awb', 'b/l',
                                    'transportation', 'payment', 'terms',
                                    'description', 'the buyer:', 'the seller:',
                                    'consignee', 'shipper', 'importer',
                                    'exporter details', 'importer details',
                                    'bill to', 'ship to', 'ship from',
                                    'sold to', 'bank', 'signature',
                                    'i declare', 'i certify', 'total',
                                    'reason for', 'contents type']):
            # Phone/mobile/tel: skip line but continue (don't break)
            if any(k in low for k in ['phone:', 'mobile:', 'tel:', 'fax:']):
                continue
            # If it's "Address:" extract its value
            if ('address:' in low or 'address :' in low) and ':' in line:
                addr_val = line.split(':', 1)[-1].strip()
                if addr_val and len(addr_val) > 3:
                    if len(lines) == 0 and rest_of_line:
                        lines.append(rest_of_line)
                    lines.append(addr_val)
            break
        # Handle table lines: extract first non-empty cell
        if line.startswith('|'):
            cells = [c.strip() for c in line.split('|') if c.strip()]
            if cells and len(cells[0]) > 2:
                lines.append(cells[0])
            continue
        if re.fullmatch(r'[-|:\s]+', line):
            continue
        lines.append(line)
    
    
    # Sub-labels that should be skipped when they appear as the "name"
    _sub_labels = {'company name', 'full name', 'contact person'}
    
    if rest_of_line and len(rest_of_line) > 2:
        # If rest_of_line is a known sub-label, clear it to fall through to lines processing
        if rest_of_line.lower().strip('- ') in _sub_labels:
            rest_of_line = ''  # Clear so elif lines: is taken
    
    if rest_of_line and len(rest_of_line) > 2:
        # If rest_of_line contains metadata like "INV. NO", ignore it as the name
        if any(k in rest_of_line.upper() for k in ['INV. NO', 'DATE:', 'PAGE:']):
            name = lines[0] if lines else None
            address = ', '.join(lines[1:6]).strip() if len(lines) > 1 else None
        else:
            name = rest_of_line
            # rest_of_line and lines[0] come from the same first line in 'after',
            # so skip lines[0] (the name) to avoid duplicating name in address
            addr_lines = lines[1:] if lines and lines[0].strip() == rest_of_line.strip() else lines
            address = ', '.join(addr_lines[:5]).strip() if addr_lines else None
    elif lines:
        # Skip sub-labels at the start of lines (e.g. "Company Name" is a label, next line is the value)
        _sub_labels = {'company name', 'full name', 'contact person'}
        start_idx = 0
        while start_idx < len(lines) and lines[start_idx].lower().strip('- :') in _sub_labels:
            start_idx += 1
        if start_idx < len(lines):
            name = lines[start_idx]
            address = ', '.join(lines[start_idx+1:start_idx+6]).strip() if len(lines) > start_idx + 1 else None
        else:
            name = lines[0]
            address = ', '.join(lines[1:6]).strip() if len(lines) > 1 else None
    else:
        return None, None
    
    # Clean name: remove markdown, limit length, handle pipe content
    if name:
        name = re.sub(r'^[#\s|]+', '', name).strip()
        if '|' in name:
            cells = [c.strip() for c in name.split('|') if c.strip()]
            if cells:
                name = cells[0]
        if len(name) > 100:
            name = name[:100]
            
    if address:
        if address.startswith('|'):
             cells = [c.strip() for c in address.split('|') if c.strip()]
             address = ', '.join(cells)
        if len(address) > 150:
            address = address[:150]
    
    return (name if name and len(name) > 2 else None), (address if address and len(address) > 2 else None)


def pre_parse_en_commercial(raw_text: str, invoice: Invoice):
    """Pre-parse EN commercial invoice patterns before block detection."""
    if not _is_en_invoice(raw_text):
        return
    
    text = raw_text
    # Strip markdown bold for easier parsing
    clean_text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    low = clean_text.lower()
    
    # ===== INVOICE NAME =====
    if not invoice.invoiceName:
        for pat in [r'(?:^|\n)\s*#*\s*(COMMERCIAL\s+INVOICE(?:[ \t]+\w+)*)',
                    r'(?:^|\n)\s*#*\s*(PROFORMA\s+INVOICE)',
                    r'(?:^|\n)\s*#*\s*(PRO\s+FORMA\s+INVOICE)',
                    r'(?:^|\n)\s*#*\s*(TAX\s+INVOICE)',
                    r'(?:^|\n)\s*#*\s*(INVOICE)']:
            m = re.search(pat, clean_text, re.I)
            if m:
                invoice.invoiceName = m.group(1).strip()
                break
    
    # ===== EARLY No: / DATE: EXTRACTION (standalone bold-label patterns) =====
    # Handles: **No:** 096/NTB/2024 and **DATE:** AUG 11, 2024
    # Note: clean_text already has **bold** markers stripped
    if not invoice.invoiceID:
        _m_no = re.search(r'(?:^|\n)\s*No\.?\s*:\s*([A-Z0-9][A-Za-z0-9\-/]{2,})', clean_text)
        if _m_no:
            _no_val = _m_no.group(1).strip()
            # Reject pure-digit strings of 10+ chars (likely L/C or account numbers)
            if not re.match(r'^\d{10,}$', _no_val):
                invoice.invoiceID = _no_val
    if not invoice.invoiceDate:
        _m_date = re.search(r'(?:^|\n)\s*DATE\s*:\s*([A-Z]{3,9})\s+(\d{1,2}),?\s+(\d{4})', clean_text, re.I)
        if _m_date:
            _months_tmp = {'jan':'01','feb':'02','mar':'03','apr':'04','may':'05','jun':'06',
                           'jul':'07','aug':'08','sep':'09','oct':'10','nov':'11','dec':'12'}
            _mabbr = _m_date.group(1).lower()[:3]
            if _mabbr in _months_tmp:
                invoice.invoiceDate = f"{_m_date.group(2).zfill(2)}/{_months_tmp[_mabbr]}/{_m_date.group(3)}"
    
    # ===== PIPE-TABLE HEADER: Vendor/Exporter | Invoice Number | Date of Shipment =====
    # This handles case 36-style pipe tables where seller, ID, and date are in columns
    _vendor_header_m = re.search(
        r'\|\s*(?:Vendor/Exporter|Exporter/Shipper|Shipper/Exporter|Exporter)\s*\|'
        r'\s*(?:Invoice\s*Number\s*:?|Invoice\s*No\.?\s*:?)\s*\|'
        r'[^\n]*\n'                        # rest of header row
        r'(?:\|[-\s|]+\n)?'                # optional separator |---|---|---|
        r'\|\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)\|',  # data row: seller | ID | date
        clean_text, re.I
    )
    if _vendor_header_m:
        _vend_name = _vendor_header_m.group(1).strip().strip('*').strip()
        _vend_id = _vendor_header_m.group(2).strip().strip('*').strip()
        _vend_date = _vendor_header_m.group(3).strip().strip('*').strip()
        # Extract seller name
        if _vend_name and len(_vend_name) > 2 and not invoice.sellerName:
            invoice.sellerName = _vend_name
        # Extract invoice ID
        if _vend_id and re.search(r'\d', _vend_id) and not invoice.invoiceID:
            invoice.invoiceID = _vend_id
        # Extract invoice date
        if _vend_date and len(_vend_date) >= 6 and not invoice.invoiceDate:
            _months_tmp = {'jan':'01','feb':'02','mar':'03','apr':'04','may':'05','jun':'06',
                           'jul':'07','aug':'08','sep':'09','oct':'10','nov':'11','dec':'12'}
            # "28 April, 2024" → dmy
            _dm = re.match(r'(\d{1,2})\s+([A-Za-z]{3,}),?\s+(\d{4})', _vend_date)
            if _dm:
                _dd, _mon, _yy = _dm.group(1), _dm.group(2)[:3].lower(), _dm.group(3)
                if _mon in _months_tmp:
                    invoice.invoiceDate = f"{_dd.zfill(2)}/{_months_tmp[_mon]}/{_yy}"
            else:
                # "April 28, 2024" → mdy
                _md = re.match(r'([A-Za-z]{3,})\s+(\d{1,2}),?\s+(\d{4})', _vend_date)
                if _md:
                    _mon, _dd, _yy = _md.group(1)[:3].lower(), _md.group(2), _md.group(3)
                    if _mon in _months_tmp:
                        invoice.invoiceDate = f"{_dd.zfill(2)}/{_months_tmp[_mon]}/{_yy}"
        # Extract seller address from subsequent rows (col 0 of pipe table)
        if invoice.sellerName and not invoice.sellerAddress:
            _after_vendor = clean_text[_vendor_header_m.end():]
            _addr_parts = []
            for _vrow in _after_vendor.split('\n')[:5]:
                _vrow = _vrow.strip()
                if not _vrow or set(_vrow).issubset({'|', '-', ' ', ':', '+'}):
                    continue
                if '|' in _vrow:
                    _vcells = [c.strip().strip('*').strip() for c in _vrow.split('|') if c.strip()]
                    if _vcells:
                        _first_cell = _vcells[0]
                        _fl = _first_cell.lower()
                        # Stop at section labels
                        if any(k in _fl for k in ['consignee', 'importer', 'emporter',
                                                   'transportation', 'description',
                                                   'other information', 'total']):
                            break
                        if _first_cell and len(_first_cell) > 2 and ':' not in _first_cell:
                            _addr_parts.append(_first_cell)
                        # Also extract currency from other cells
                        for _vc in _vcells[1:]:
                            _vc_clean = _vc.strip().strip('*').strip()
                            if _vc_clean in ('USD', 'EUR', 'GBP', 'JPY', 'VND', 'AUD', 'CAD', 'SGD',
                                             'CHF', 'HKD', 'TWD', 'KRW', 'THB', 'MYR', 'IDR', 'PHP',
                                             'SEK', 'NOK', 'DKK', 'NZD', 'ZAR', 'AED', 'SAR', 'BRL',
                                             'MXN', 'PLN', 'CZK', 'TRY', 'RUB', 'INR', 'CNY') and not invoice.currency:
                                invoice.currency = _vc_clean
                else:
                    break
            if _addr_parts:
                invoice.sellerAddress = ', '.join(_addr_parts)
    
    # ===== PIPE-TABLE: THE BENEFICIARY: | COMMERCIAL INVOICE NO & DATE: =====
    # L/C trade format: col 0 = seller info, col 1+ = invoice metadata
    _beneficiary_header_m = re.search(
        r'\|\s*(?:THE\s+)?BENEFICIARY\s*:\s*\|.*?INVOICE\s*(?:NO\.?|NUMBER)\s*(?:&|AND)\s*DATE\s*:?\s*\|',
        clean_text, re.I
    )
    if _beneficiary_header_m:
        _after_benef = clean_text[_beneficiary_header_m.end():]
        _benef_rows = _after_benef.split('\n')
        _seller_parts = []
        _inv_id_found = False
        for _brow in _benef_rows[:8]:
            _brow = _brow.strip()
            if not _brow or set(_brow).issubset({'|', '-', ' ', ':', '+'}):
                continue
            if '|' not in _brow:
                break  # End of pipe-table
            _bcells = [c.strip().strip('*').strip() for c in _brow.split('|') if c.strip()]
            if not _bcells:
                continue
            _first = _bcells[0]
            _fl = _first.lower()
            # Stop at new section labels
            if any(k in _fl for k in ['the applicant', 'applicant:', 'consignee',
                                       'description', 'port of', 'total', 'beneficiary name']):
                break
            # Col 0 = seller data
            if _first and len(_first) > 2 and ':' not in _first:
                _seller_parts.append(_first)
            # Col 1+ = invoice metadata (ID, date)
            if not _inv_id_found:
                for _bc in _bcells[1:]:
                    _bc_clean = _bc.strip()
                    # "1110/LY Date 28 Oct 2025" or "1110/LY | Date 28 Oct 2025"
                    _id_date_m = re.match(r'([A-Z0-9/\-]+)\s+(?:Date\s+)?(\d{1,2}\s+\w+\s+\d{4})', _bc_clean, re.I)
                    if _id_date_m:
                        if not invoice.invoiceID:
                            invoice.invoiceID = _id_date_m.group(1).strip()
                        if not invoice.invoiceDate:
                            _months_tmp = {'jan':'01','feb':'02','mar':'03','apr':'04','may':'05','jun':'06',
                                          'jul':'07','aug':'08','sep':'09','oct':'10','nov':'11','dec':'12'}
                            _dm = re.search(r'(\d{1,2})\s+(\w{3})\w*\s+(\d{4})', _id_date_m.group(2))
                            if _dm and _dm.group(2)[:3].lower() in _months_tmp:
                                invoice.invoiceDate = f"{_dm.group(1).zfill(2)}/{_months_tmp[_dm.group(2)[:3].lower()]}/{_dm.group(3)}"
                        _inv_id_found = True
                        break
                    # Just ID: "1110/LY"
                    elif re.match(r'^[A-Z0-9/\-]{3,}$', _bc_clean, re.I) and not invoice.invoiceID:
                        invoice.invoiceID = _bc_clean
                    # "Date 28 Oct 2025"
                    _date_m = re.match(r'Date\s+(\d{1,2})\s+(\w{3})\w*\s+(\d{4})', _bc_clean, re.I)
                    if _date_m and not invoice.invoiceDate:
                        _mon = _date_m.group(2)[:3].lower()
                        _months_tmp = {'jan':'01','feb':'02','mar':'03','apr':'04','may':'05','jun':'06',
                                      'jul':'07','aug':'08','sep':'09','oct':'10','nov':'11','dec':'12'}
                        if _mon in _months_tmp:
                            invoice.invoiceDate = f"{_date_m.group(1).zfill(2)}/{_months_tmp[_mon]}/{_date_m.group(3)}"
        if _seller_parts:
            if not invoice.sellerName:
                invoice.sellerName = _seller_parts[0]
            if not invoice.sellerAddress and len(_seller_parts) > 1:
                invoice.sellerAddress = ', '.join(_seller_parts[1:])
    
    # ===== L/C-STYLE NUMBERED-LABEL PIPE-TABLE EXTRACTOR =====
    # Handles commercial invoices with numbered pipe-table format:
    # | 1. Beneficiary / Exporter / Seller. | 5. No. & Date of Invoice. |
    # | ABC TRADING ... | MHS-PK/2024/06/CI | 12-Aug-2024 |
    _lc_lines = clean_text.split('\n')
    _lc_mode = None
    _seller_data_lines = []
    _buyer_data_lines = []
    _lc_detected = False
    
    for _lc_line in _lc_lines:
        _lc_low = _lc_line.strip().lower()
        if not _lc_line.strip().startswith('|'):
            if _lc_mode:
                _lc_mode = None
            continue
        _cells = [c.strip() for c in _lc_line.split('|') if c.strip()]
        if not _cells:
            continue
        _seller_kws = ['beneficiary', 'exporter', 'seller']
        _buyer_kws = ['applicant', 'importer', 'buyer']
        
        if any(k in _lc_low for k in _seller_kws) and re.search(r'^\d+\.', _cells[0].strip()):
            _lc_mode = 'seller'
            _lc_detected = True
            continue
        elif any(k in _lc_low for k in _buyer_kws) and re.search(r'^\d+\.', _cells[0].strip()):
            _lc_mode = 'buyer'
            continue
        elif re.search(r'^\d+\.\s', _cells[0].strip()):
            _lc_mode = None
            continue
        
        # Skip separator rows (|------|------|)
        if all(re.fullmatch(r'[-\s:+]+', c) for c in _cells):
            continue
        
        if _lc_mode == 'seller':
            _seller_data_lines.append(_cells)
        elif _lc_mode == 'buyer':
            _buyer_data_lines.append(_cells)
    
    if _lc_detected and _seller_data_lines:
        if not invoice.sellerName:
            _s_name = re.sub(r'^\d+\.\s*', '', _seller_data_lines[0][0]).strip()
            if _s_name and len(_s_name) > 5:
                invoice.sellerName = _s_name
            # Extract invoiceID and date from additional cells
            for _cv in _seller_data_lines[0][1:]:
                _cv = _cv.strip()
                if not _cv:
                    continue
                if not invoice.invoiceID and re.match(r'^[A-Z0-9][A-Za-z0-9\-/]+$', _cv) and len(_cv) >= 3:
                    invoice.invoiceID = _cv
                if not invoice.invoiceDate:
                    _months_tmp = {'jan':'01','feb':'02','mar':'03','apr':'04','may':'05','jun':'06',
                                   'jul':'07','aug':'08','sep':'09','oct':'10','nov':'11','dec':'12'}
                    m_d = re.match(r'(\d{1,2})[\-/]([A-Za-z]{3,9})[\-/](\d{4})', _cv)
                    if m_d and m_d.group(2).lower()[:3] in _months_tmp:
                        invoice.invoiceDate = f"{m_d.group(1).zfill(2)}/{_months_tmp[m_d.group(2).lower()[:3]]}/{m_d.group(3)}"
        if not invoice.sellerAddress and len(_seller_data_lines) > 1:
            _s_addr = re.sub(r'^\d+\.\s*', '', _seller_data_lines[1][0]).strip()
            if _s_addr and len(_s_addr) > 5:
                invoice.sellerAddress = _s_addr
    
    if _lc_detected and _buyer_data_lines:
        if not invoice.buyerName:
            _b_name = re.sub(r'^\d+\.\s*', '', _buyer_data_lines[0][0]).strip()
            if _b_name and len(_b_name) > 3:
                invoice.buyerName = _b_name
        if not invoice.buyerAddress and len(_buyer_data_lines) > 1:
            _b_addr = re.sub(r'^\d+\.\s*', '', _buyer_data_lines[1][0]).strip()
            if _b_addr and len(_b_addr) > 5:
                invoice.buyerAddress = _b_addr

    # ===== THE APPLICANT: → buyer =====
    # Support both pipe-table: "| Applicant: | FINE TECH INDUSTRIES |" and plain text
    if not invoice.buyerName:
        # Try pipe-table format first: | Applicant: | NAME |
        _app_pipe_m = re.search(r'\|\s*(?:THE\s+)?APPLICANT\s*:\s*\|\s*([^|\n]+)\|', clean_text, re.I)
        if _app_pipe_m:
            _app_name = _app_pipe_m.group(1).strip().strip('*').strip()
            if (_app_name and len(_app_name) > 2
                    and not _app_name.lower().startswith(('date', 'contract', 'beneficiary', 'bank', 'account', 'swift'))):
                invoice.buyerName = _app_name
                # Extract address from subsequent pipe-table rows
                _after_app_pipe = clean_text[_app_pipe_m.end():]
                _app_addr_parts = []
                for _aprow in _after_app_pipe.split('\n')[:5]:
                    _aprow = _aprow.strip()
                    if not _aprow or set(_aprow).issubset({'|', '-', ' ', ':', '+'}):
                        continue
                    if '|' not in _aprow:
                        break
                    _apcells = [c.strip() for c in _aprow.split('|') if c.strip()]
                    if not _apcells:
                        continue
                    # Stop at new labels
                    _first_low = _apcells[0].lower()
                    if any(k in _first_low for k in ['dated', 'date:', 'contract', 'shipped',
                                                      'from:', 'to:', 'quantity', 'description',
                                                      'bl no', 'lc no']):
                        break
                    # Combine all cells for address
                    _addr_content = ', '.join(c for c in _apcells if c and len(c) > 2 and ':' not in c)
                    if _addr_content:
                        _app_addr_parts.append(_addr_content)
                if _app_addr_parts and not invoice.buyerAddress:
                    invoice.buyerAddress = ', '.join(_app_addr_parts)
        if not invoice.buyerName:
            # Plain text format: THE APPLICANT:\nNAME\nADDRESS
            _applicant_m = re.search(r'(?:THE\s+)?APPLICANT\s*:\s*', clean_text, re.I)
            if _applicant_m:
                _after_app = clean_text[_applicant_m.end():]
                _app_lines = []
                for _aline in _after_app.split('\n'):
                    _al = _aline.strip().strip('*').strip()
                    if not _al or _al == '---':
                        if _app_lines:
                            break
                        continue
                    _al_low = _al.lower()
                    if any(k in _al_low for k in ['beneficiary', 'bank', 'swift', 'account',
                                                    'port of', 'description', 'total', 'shipper']):
                        break
                    if _al.startswith('|'):
                        break
                    _app_lines.append(_al)
                if _app_lines:
                    invoice.buyerName = _app_lines[0]
                    if len(_app_lines) > 1 and not invoice.buyerAddress:
                        invoice.buyerAddress = ', '.join(_app_lines[1:])

    # ===== FOR ACCOUNT AND RISK OF MESSRS: → buyer =====
    if not invoice.buyerName:
        _messrs_m = re.search(r'[Ff]or\s+account\s+and\s+risk\s+of\s+[Mm]essrs\s*:\s*', clean_text)
        if _messrs_m:
            _after_messrs = clean_text[_messrs_m.end():]
            _messrs_lines = []
            for _ml in _after_messrs.split('\n'):
                _mls = _ml.strip()
                if not _mls:
                    if _messrs_lines:
                        break
                    continue
                _mls_low = _mls.lower()
                if any(k in _mls_low for k in ['shipper', 'shipped', 'description', 'quantity',
                                                  'total', 'port of', 'beneficiary']):
                    break
                if _mls.startswith('|'):
                    break
                _messrs_lines.append(_mls)
            if _messrs_lines:
                invoice.buyerName = _messrs_lines[0]
                if len(_messrs_lines) > 1 and not invoice.buyerAddress:
                    invoice.buyerAddress = ', '.join(_messrs_lines[1:])
    
    # ===== SELLER =====
    # Generic skip words for extracted names
    _skip_names = {'name', 'address', 'phone', 'email', 'from', 'to', 'date',
                   'invoice', 'commercial invoice', 'proforma invoice',
                   'exporter', 'shipper', 'consignee', 'importer',
                   'ship to', 'ship from', 'bill to', 'bill from',
                   'sold to', 'delivery details', 'customer\'s details',
                   'street address', 'city', 'country', 'postal code',
                   'city, state, postal code', 'city, state, zip'}
    def _is_skip_name(val):
        """Check if value is a generic label/template placeholder."""
        v = val.lower().strip().rstrip(':')
        return v in _skip_names or v.endswith(' address') or v.startswith('city,')
    
    # ===== SELLER =====
    seller_patterns = [
        # Case 4 style: regex must skip the | COMMERCIAL INVOICE | part
        r'THE SELLER\s*:\s*\|\s*([^|\n]+)',
        r'(?:THE[ \t]+SELLER|SHIP[ \t]+FROM|BILL[ \t]+FROM|EXPORTER)[ \t]*[:\n]',
        r'(?:^|\n)\s*(?:Seller|Exporter[ \t]+Details|Exporter[ \t]+Name|Sender/Exporter|Sender[ \t]+Name|Shipper/Exporter|Vendor/Exporter|Exporter/Shipper|Sender)[ \t]*[:\n]',
        r'Shipper(?:[ \t]+by)?(?!/)[ \t]*[:\n]',
    ]
    # Pipe-table Exporter pattern: | Exporter | ... |\n|---|\n| CompanyName ... | ... |
    if not invoice.sellerName:
        m_exp = re.search(
            r'\|\s*Exporter\s*\|[^\n]*\n'        # Header row: | Exporter | ... |
            r'(?:\|[-\s|]+\|\s*\n)?'               # Optional separator: |---|---|
            r'\|\s*([^|\n]+)',                      # Data row first cell
            clean_text, re.I
        )
        if m_exp:
            val = m_exp.group(1).strip().strip('*').strip()
            if val and not _is_skip_name(val) and len(val) > 3:
                # The cell may contain "Company Address City Country" all in one
                # Try to split: company name is before first digit (address usually has numbers)
                _addr_split = re.search(r'^(.+?)\s+(\d+\s+.+)$', val)
                if _addr_split:
                    invoice.sellerName = _addr_split.group(1).strip()
                    if not invoice.sellerAddress:
                        invoice.sellerAddress = _addr_split.group(2).strip()
                else:
                    invoice.sellerName = val
    for pat in seller_patterns:
        if not invoice.sellerName:
            m = re.search(pat, clean_text, re.I)
            if m:
                if m.groups():
                    val = m.group(1).strip()
                    if val and not _is_skip_name(val):
                        invoice.sellerName = val
                else:
                    name, addr = _extract_after_label(clean_text, pat)
                    if name and len(name) > 2:
                        if not _is_skip_name(name) and not name.startswith('|'):
                            invoice.sellerName = name
                            # Strip label prefixes like "Company: " from seller name
                            _sn_labels = re.match(r'^(?:Company|Name|Vendor)\s*:\s*', invoice.sellerName, re.I)
                            if _sn_labels:
                                invoice.sellerName = invoice.sellerName[_sn_labels.end():].strip()
                            if addr and not invoice.sellerAddress:
                                invoice.sellerAddress = addr
    
    # Special pattern: "Invoice Address" in pipe-table → seller data in first column of data rows
    if not invoice.sellerName:
        m_inv_addr = re.search(r'(?:^|\n)[^\n]*Invoice\s+Address[^\n]*\n', clean_text, re.I)
        if m_inv_addr:
            after = clean_text[m_inv_addr.end():]
            seller_lines = []
            for tline in after.split('\n'):
                tline = tline.strip()
                if not tline or set(tline).issubset({'|', '-', ' ', ':', '+'}):
                    continue
                if '|' in tline:
                    cells = [c.strip().strip('*') for c in tline.split('|') if c.strip()]
                    if cells:
                        first = cells[0].strip()
                        if first and len(first) > 2:
                            flow = first.lower()
                            if any(k in flow for k in ['ship to', 'description', 'total', 'packing',
                                                        'container', 'origin', 'manufacturer']):
                                break
                            seller_lines.append(first)
                else:
                    break
            if seller_lines:
                invoice.sellerName = seller_lines[0]
                if len(seller_lines) > 1:
                    addr_parts = []
                    for sl in seller_lines[1:]:
                        sl_low = sl.lower()
                        if any(k in sl_low for k in ['tel', 'fax', 'email', 'website', 'www.']):
                            continue
                        addr_parts.append(sl)
                    if addr_parts and not invoice.sellerAddress:
                        invoice.sellerAddress = ', '.join(addr_parts)
    
    # Fallback: company name before INVOICE header (e.g., "MICRODYN-NADIR..." then "INVOICE")
    if not invoice.sellerName:
        m = re.search(r'^([A-Z][A-Za-z \t&.,\'-]+?(?:CO\.?,?[ \t]*LTD\.?|INC\.?|CORP\.?|PTE[ \t]+LTD\.?|LLC|COMPANY(?:\s+LIMITED)?|GMBH|SAS|S\.A\.?)[. \t]*)', clean_text, re.M)
        if m:
            val = m.group(1).strip().rstrip('.')
            if len(val) > 3 and 'invoice' not in val.lower():
                invoice.sellerName = val
    
    # Fallback 2: "Full Name:\n  Xxx" or "Company Name:\n  Xxx" pattern
    if not invoice.sellerName:
        # Try Full Name first (prioritize person name over company)
        m = re.search(r'Full\s+Name\s*[:\n]\s*(.+)', clean_text, re.I)
        if m:
            val = m.group(1).strip().strip('*')
            if val and len(val) > 2 and val.lower().strip() not in _skip_names:
                invoice.sellerName = val
    if not invoice.sellerName:
        m = re.search(r'(?:^|\n)\s*Company\s+Name\s*[:\n]\s*(.+)', clean_text, re.I)
        if m:
            val = m.group(1).strip().strip('*')
            # Skip if value looks like an address (has house numbers + street words)
            _looks_like_address = bool(re.search(r'\d+\s+\w+\s+(?:St|Street|Rd|Road|Ave|Lane|Blvd|Dr|Drive)', val, re.I))
            if (val and len(val) > 2
                    and val.lower().strip() not in _skip_names
                    and not _looks_like_address):
                invoice.sellerName = val
    
    # Fallback 3: "FROM :\n Full Name : Xxx" or "FROM\n\nABC Seller" pattern
    if not invoice.sellerName:
        m = re.search(r'\bFROM\s*:?\s*\n\s*\n?\s*(?:Full\s+Name\s*:\s*)?(.+)', clean_text, re.I)
        if m:
            val = m.group(1).strip().strip('*')
            if val and len(val) > 2 and val.lower().strip() not in _skip_names:
                invoice.sellerName = val
                # Extract address, email, phone from following lines
                _rest = clean_text[m.end():]
                _addr_parts = []
                _got_data = False
                for _fl in _rest.split('\n'):
                    _fl = _fl.strip()
                    if not _fl:
                        if _got_data:
                            break  # stop at blank line AFTER data
                        continue  # skip leading blank lines
                    _got_data = True
                    _fl_low = _fl.lower()
                    # Stop at next section labels
                    if any(k in _fl_low for k in ["client's details", "client details",
                                                   "invoice no", "invoice date", "bill to",
                                                   "details:"]):
                        break
                    if _fl_low in ('to', 'to:'):
                        break
                    if re.search(r'@\S+\.\S+', _fl):
                        if not invoice.sellerEmail:
                            invoice.sellerEmail = _fl
                    elif re.match(r'^[+\d\(\[][\d\s\-\(\)\.+]{6,}$', _fl):
                        if not invoice.sellerPhoneNumber:
                            invoice.sellerPhoneNumber = _fl
                    else:
                        _addr_parts.append(_fl)
                if _addr_parts and not invoice.sellerAddress:
                    invoice.sellerAddress = ', '.join(_addr_parts)
    
    # Fallback 4: "Ship-from address:\nCompany Name" pattern
    if not invoice.sellerName:
        m = re.search(r'Ship[\-\s]+from\s+address\s*:\s*\n\s*(.+)', clean_text, re.I)
        if m:
            val = m.group(1).strip().strip('*')
            if val and len(val) > 3 and val.lower().strip() not in _skip_names:
                invoice.sellerName = val
                # Try to get address from following lines (skip blank lines)
                rest = clean_text[m.end():]
                addr_lines = []
                for line in rest.split('\n')[:6]:
                    line = line.strip()
                    if not line:
                        continue  # skip blank lines
                    if line.startswith('**') or any(k in line.lower() for k in ['terms of', 'delivery', 'shipping', 'payment', 'condition']):
                        break
                    addr_lines.append(line)
                if addr_lines and not invoice.sellerAddress:
                    invoice.sellerAddress = ', '.join(addr_lines)
    
    # Fallback 4b: "For and on behalf of\nCOMPANY NAME" (L/C trade signature)
    if not invoice.sellerName:
        m = re.search(r'[Ff]or\s+and\s+on\s+behalf\s+of\s*\n', clean_text)
        if m:
            _after = clean_text[m.end():]
            _next_line = _after.split('\n')[0].strip() if _after else ''
            if _next_line and len(_next_line) > 5:
                # Check if the next line looks like a company name
                _company_suffixes = ['LIMITED', 'LTD', 'LTD.', 'INC', 'INC.', 'CORP',
                                     'CORP.', 'COMPANY', 'LLC', 'CO. LTD', 'CO., LTD',
                                     'COMPANY LIMITED', 'JSC', 'JOINT STOCK COMPANY']
                if any(_next_line.upper().endswith(s) for s in _company_suffixes):
                    invoice.sellerName = _next_line
    # Fallback 5: Markdown heading (## CompanyName) after invoice title — but only if separated by blank line
    # and the heading looks like a company name (not a single word like software name)
    if not invoice.sellerName:
        m = re.search(r'(?:COMMERCIAL\s+INVOICE|PROFORMA\s+INVOICE|TAX\s+INVOICE|INVOICE)[^\n]*\s*\n\s*\n\s*#+\s*(.+)', clean_text, re.I)
        if m:
            val = m.group(1).strip().strip('*')
            if val and len(val) > 2 and val.lower().strip() not in _skip_names and ' ' in val:
                # Exclude document subtitles like "Sample Commercial Invoice"
                _title_words = {'invoice', 'sample', 'instructions', 'template', 'example', 'proforma'}
                if not any(tw in val.lower() for tw in _title_words):
                    invoice.sellerName = val
    
    # Seller address fix: extract from ADDRESS label after SHIPPER/SELLER section
    if not invoice.sellerAddress or invoice.sellerAddress.startswith('#') or invoice.sellerAddress.startswith('|'):
        # Try finding address lines after SELLER/SHIPPER keywords
        m = re.search(r'(?:SELLER|SHIPPER)[^\n]*\n(?:[^\n]*\n){0,10}[^\n]*ADDRESS\s*:[^\n]*\n\|\s*([^|]+)', clean_text, re.I)
        if not m:
             # Case 4 specific: table format with rows:
             # | THE SELLER: | COMMERCIAL INVOICE |
             # |------------|---------------------|
             # | COMPANY NAME | |
             # | ADDRESS ROW | |
             # Capture group 1 = company name row, group 2 = address row after separator
             m = re.search(
                 r'THE SELLER[^\n]*\n'                    # THE SELLER line
                 r'\|[-\s|]+\|\s*\n'                      # skip separator row
                 r'\|\s*([^|\n]+?)\s*\|[^\n]*\n'          # group 1 = company name row
                 r'\|\s*([^|\n]+)',                        # group 2 = address row
                 clean_text, re.I
             )
        if m:
            # group(1) is company name, group(2) is address
            # Only use group(2) (address row) to avoid overwriting with company name
            addr_val = m.group(2).strip() if m.lastindex >= 2 else m.group(m.lastindex).strip()
            # Reject separator-looking values (all dashes)
            if addr_val and len(addr_val) > 5 and not re.fullmatch(r'[-\s|]+', addr_val):
                # Also update sellerName if not set yet OR if it wrongly equals the invoice name
                if m.lastindex >= 2:
                    name_cand = m.group(1).strip()
                    _seller_is_invoice_name = (
                        invoice.sellerName and invoice.invoiceName and
                        invoice.sellerName.strip().upper() == invoice.invoiceName.strip().upper()
                    )
                    if name_cand and len(name_cand) > 3 and (not invoice.sellerName or _seller_is_invoice_name):
                        invoice.sellerName = name_cand
                invoice.sellerAddress = addr_val
    
    # ===== BUYER =====
    buyer_patterns = [
        # Case 4 style: THE BUYER: | INV. NO.: |
        r'THE BUYER\s*:\s*\|\s*([^|\n]+)',
        r'(?:THE[ \t]+BUYER|CONSIGNED[ \t]+TO|SOLD[ \t]+TO|BILL[ \t]+TO)[ \t]*[:\n]',
        # Standalone "Buyer" — common in L/C trade invoices
        r'(?:^|\n)\s*Buyer[ \t]*[:\n]',
        # Invoice To has buyer name — check BEFORE Ship To (which often has address only)
        r'(?:Invoice[ \t]+To|Importer[ \t]+Details|Importer[ \t]+Name|Consignee[ \t]+Name)[ \t]*[:\n]',
        # NOTIFY PARTY is the actual buyer when CONSIGNEE is a bank order
        r'(?:NOTIFY\s+PARTY)[ \t]*[:\n]',
        r'(?:CONSIGNEE|SHIP[ \t]+TO|IMPORTER|RECEIVER)[ \t]*[:\n]',
        r'(?:Recipient/Ship[ \t]+To)[ \t]*[:\n]',
        r"CONSIGNEE'S\s+(?:MEMBER|COMPANY)[ \t]*[:\n]",
    ]
    _buyer_skip = _skip_names | {'same as consignee', 'same as above',
                                 '(if other than recipient)',
                                 'customer po no.', 'customer po no', 'reference no.',
                                 'permanent', 'account number', 'account payable',
                                 'the order of'}
    # Regex to reject "Country of Origin: XXX" values that are NOT buyer names
    _country_origin_re = re.compile(r'^Country\s+of\s+(?:Origin|Manufacture)', re.I)
    # Regex to detect invoice header labels that should NOT be stored as buyerName
    _invoice_label_re = re.compile(
        r'(?:inv\.?\s*no|inv\.?\s*date|invoice\s*no|invoice\s*date|payment\s*term|s/c\s*no|transportation)',
        re.I
    )
    for pat in buyer_patterns:
        if not invoice.buyerName:
            m = re.search(pat, clean_text, re.I)
            if m:
                if m.groups():
                    val = m.group(1).strip()
                    # Reject if value looks like an invoice header label (e.g. "INV. NO.:"), not a buyer name
                    # Also reject "Country of Origin: XXX" values
                    if (val and val.lower().strip() not in _buyer_skip
                            and not _invoice_label_re.search(val)
                            and not _country_origin_re.match(val)):
                        invoice.buyerName = val
                    else:
                        # Value was rejected (e.g. "INV. NO.:") — look at next pipe-table rows
                        # Pattern: | THE BUYER: | INV. NO.: | ... |\n| BuyerName | | |\n| Address | | |
                        _after_buyer = clean_text[m.end():]
                        _buyer_rows_name = None
                        _buyer_rows_addr = []
                        for _brow in _after_buyer.split('\n')[:6]:
                            _brow = _brow.strip()
                            if not _brow or set(_brow).issubset({'|', '-', ' ', ':', '+'}):
                                continue
                            if not _brow.startswith('|'):
                                break
                            _bcells = [c.strip() for c in _brow.split('|') if c.strip()]
                            if _bcells:
                                _first = _bcells[0].strip()
                                _fl = _first.lower()
                                # Stop at section boundaries
                                if any(k in _fl for k in ['description', 'total', 'qty', 'amount',
                                                           'unit price', 'h.s. code', 'item']):
                                    break
                                # Skip label-only cells
                                if _invoice_label_re.search(_first):
                                    continue
                                if not _buyer_rows_name:
                                    _buyer_rows_name = _first
                                else:
                                    _buyer_rows_addr.append(_first)
                        if _buyer_rows_name and _buyer_rows_name.lower().strip() not in _buyer_skip:
                            invoice.buyerName = _buyer_rows_name
                            if _buyer_rows_addr and not invoice.buyerAddress:
                                invoice.buyerAddress = ', '.join(_buyer_rows_addr)
                else:
                    name, addr = _extract_after_label(clean_text, pat)
                    if name and len(name) > 2:
                        if (name.lower().strip() not in _buyer_skip
                                and not name.startswith('|')
                                and not name.startswith('PO No')
                                and 'to the order of' not in name.lower()
                                and not _country_origin_re.match(name)):
                            invoice.buyerName = name
                            # Strip label prefixes like "Customer : " from buyer name
                            _name_labels = re.match(r'^(?:Customer|Company|Name|Client)\s*:\s*', invoice.buyerName, re.I)
                            if _name_labels:
                                invoice.buyerName = invoice.buyerName[_name_labels.end():].strip()
                            # Check if addr is a company name continuation (not a real address)
                            if addr:
                                _addr_first = addr.split(',')[0].strip()
                                _company_suffixes = ['COMPANY', 'CORPORATION', 'CORP', 'CO.', 'LTD', 'LLC',
                                                      'INC', 'JSC', 'JOINT STOCK', 'GROUP', 'PTE', 'GMBH']
                                _is_name_cont = (
                                    any(s in _addr_first.upper() for s in _company_suffixes)
                                    and not re.search(r'\d', _addr_first)  # addresses have numbers
                                )
                                if _is_name_cont:
                                    invoice.buyerName = invoice.buyerName + ' ' + _addr_first
                                    # Remaining parts become address
                                    _rest_parts = addr.split(',')[1:]
                                    addr = ', '.join(_rest_parts).strip() if _rest_parts else None
                            if addr and not invoice.buyerAddress:
                                # Strip "Address :" prefix and stop at Phone/Email
                                addr_clean = re.sub(r'^(?:Address|Addr\.?)\s*:\s*', '', addr, flags=re.I)
                                # Remove Phone/Email parts from address
                                addr_clean = re.split(r',\s*(?:Phone|Tel|Email|Mobile)\s*:', addr_clean, flags=re.I)[0].strip().rstrip(',')
                                if addr_clean:
                                    invoice.buyerAddress = addr_clean
                            # Extract buyer phone from nearby Mobile:/Phone:/Tel: lines
                            if not invoice.buyerPhoneNumber:
                                after_label = clean_text[m.end():m.end()+300]
                                phone_m = re.search(r'(?:Mobile|Phone|Tel)[/Fax]*\s*:\s*([\+\d\(][\d \-\(\)\.]{6,})', after_label, re.I)
                                if phone_m:
                                    invoice.buyerPhoneNumber = phone_m.group(1).strip()
                            if not invoice.buyerEmail:
                                after_label = clean_text[m.end():m.end()+300]
                                email_m = re.search(r'Email\s*:\s*([\w\.\-+]+@[\w\.\-]+\.\w{2,})', after_label, re.I)
                                if email_m:
                                    invoice.buyerEmail = email_m.group(1).strip()
    
    # Buyer fallback: "To:\nCOMPANY NAME" or "TO\n\nXYZ Buyer"
    if not invoice.buyerName:
        m = re.search(r'\bTO\s*:?\s*\n\s*\n?\s*(.+)', clean_text)
        if m:
            val = m.group(1).strip().strip('*')
            # Only accept if it looks like a company name (uppercase or has CO./LTD)
            if val and len(val) > 3 and (val[0].isupper() or 'co.' in val.lower()):
                if val.lower().strip() not in _buyer_skip:
                    invoice.buyerName = val
                    # Extract buyer address and email from following lines
                    _rest = clean_text[m.end():]
                    _addr_parts = []
                    _got_data = False
                    for _fl in _rest.split('\n'):
                        _fl = _fl.strip()
                        if not _fl:
                            if _got_data:
                                break
                            continue
                        _got_data = True
                        _fl_low = _fl.lower()
                        if any(k in _fl_low for k in ['invoice no', 'invoice date',
                                                       'due date', 'payment', 'from']):
                            break
                        if _fl.startswith('|'):
                            break
                        if re.search(r'@\S+\.\S+', _fl):
                            if not invoice.buyerEmail:
                                invoice.buyerEmail = _fl
                        elif re.match(r'^[+\d\(\[][\d\s\-\(\)\.+]{6,}$', _fl):
                            if not invoice.buyerPhoneNumber:
                                invoice.buyerPhoneNumber = _fl
                        else:
                            _addr_parts.append(_fl)
                    if _addr_parts and not invoice.buyerAddress:
                        invoice.buyerAddress = ', '.join(_addr_parts)
    
    # Buyer fallback: "Ship to...\nCompanyName Address: street..." format
    if not invoice.buyerName:
        m = re.search(r'Ship\s+to[^\n]*:\s*\n\s*(.+?)\s+Address\s*:\s*(.+)', clean_text, re.I)
        if m:
            bname = m.group(1).strip()
            baddr = m.group(2).strip()
            if bname and len(bname) > 2 and bname.lower() not in _buyer_skip:
                invoice.buyerName = bname
                if baddr and not invoice.buyerAddress:
                    invoice.buyerAddress = baddr
    
    # Buyer fallback: "For Account and Risk of : XXX" or "For Account & Risk of Messrs.\nXXX"
    if not invoice.buyerName:
        m = re.search(r'For\s+Account\s+(?:(?:and|&)\s+Risk\s+)?of\s+(?:Messrs\.?\s*)?[:\n]\s*(.+)', clean_text, re.I)
        if m:
            val = m.group(1).strip().strip('*')
            if val and len(val) > 2:
                invoice.buyerName = val
                # Extract buyerAddress from following lines
                if not invoice.buyerAddress:
                    rest = clean_text[m.end():]
                    _addr_parts = []
                    for aline in rest.split('\n')[:6]:
                        aline = aline.strip()
                        if not aline:
                            if _addr_parts:
                                break
                            continue
                        alow = aline.lower()
                        # Stop at next label/section
                        if any(k in alow for k in ['commodity', 'contract', 'country', 'gross',
                                                     'container', 'port', 'b/l', 'delivery',
                                                     'description', 'invoice', '|',
                                                     'notify party', 'sailing']):
                            break
                        # Stop at phone/fax/tel lines
                        if re.match(r'^(?:tel|fax|phone)', alow):
                            # Extract phone
                            _ph = re.search(r'(?:tel|phone)\s*:\s*([\+\d][\d\s\-\(\)\.]{6,})', aline, re.I)
                            if _ph and not invoice.buyerPhoneNumber:
                                invoice.buyerPhoneNumber = _ph.group(1).strip()
                            break
                        if len(aline) > 3:
                            _addr_parts.append(aline)
                    if _addr_parts:
                        invoice.buyerAddress = ', '.join(_addr_parts)
    
    # Buyer fallback: "Billed to\nXxx" or "Bill-to address:\nXxx"
    if not invoice.buyerName:
        m = re.search(r'Bill(?:ed)?[\s-]+to(?:\s+address)?\s*[:\n]\s*(.+)', clean_text, re.I)
        if m:
            val = m.group(1).strip().strip('*')
            if val and len(val) > 2 and val.lower().strip() not in _buyer_skip:
                invoice.buyerName = val
                # Also extract buyerAddress from following lines
                if not invoice.buyerAddress:
                    rest = clean_text[m.end():]
                    addr_lines = []
                    for line in rest.split('\n')[:6]:
                        line = line.strip()
                        if not line:
                            continue
                        if line.startswith('**') or line.startswith('|') or any(k in line.lower() for k in ['parcel', 'fedex', 'tracking', 'item', 'material']):
                            break
                        addr_lines.append(line)
                    if addr_lines:
                        invoice.buyerAddress = ', '.join(addr_lines)
    
    # Buyer fallback: CONSIGNEE'S MEMBER/COMPANY in pipe-table format
    # "| CONSIGNEE'S MEMBER: |...|...| \n| COMPANY NAME |...|...|"
    if not invoice.buyerName:
        m = re.search(r"CONSIGNEE.S\s+(?:MEMBER|COMPANY)\s*:.*?\n\|\s*([^|]+)", clean_text, re.I)
        if m:
            val = m.group(1).strip()
            if val and len(val) > 3 and val.lower().strip() not in _buyer_skip:
                invoice.buyerName = val
    
    # Buyer fallback: Ultimate Consignee in pipe-table format
    # "| **Ultimate Consignee** | | |\n| Abc Company | ... | ... |"
    if not invoice.buyerName:
        m = re.search(r'Ultimate\s+Consignee[^|]*\|[^|]*\|[^\n]*\n\|\s*([^|]+)', clean_text, re.I)
        if m:
            val = m.group(1).strip()
            if val and len(val) > 2 and val.lower().strip() not in _buyer_skip:
                invoice.buyerName = val
                # Try to extract address from subsequent pipe-table rows
                if not invoice.buyerAddress:
                    rest = clean_text[m.end():]
                    _skip_addr = {'consignee', 'phone', 'carrier', 'terminal',
                                  'pier', 'contact', 'origination', 'destination',
                                  'exporter', 'account', 'customer'}
                    for row_m in re.finditer(r'\n\|\s*([^|]+?)\s*\|', rest):
                        addr_val = row_m.group(1).strip()
                        if (addr_val and len(addr_val) > 3
                                and not addr_val.startswith('---')
                                and not any(k in addr_val.lower() for k in _skip_addr)):
                            invoice.buyerAddress = addr_val
                            break
    
    # Buyer address fix: extract from ADDRESS label after BUYER section
    if not invoice.buyerAddress or invoice.buyerAddress.startswith('|'):
        m = re.search(r'ADDRESS\s*[:\s]*\|\s*([^|]+)', clean_text, re.I)
        if m:
            addr_val = m.group(1).strip()
            # Reject values that look like invoice labels (side-by-side table layout)
            _reject_labels = ['invoice', 'number', 'date', 'terms', 'order', 'payment']
            if not any(rl in addr_val.lower() for rl in _reject_labels):
                invoice.buyerAddress = addr_val
    
    # Buyer fallback: "Customer Name" in pipe-table header
    # Format: | Customer Name | ... |\n|---|\n| John Doe | ... |\n| 456 Lane | ... |
    if not invoice.buyerName:
        m_cust = re.search(r'\|\s*Customer\s+Name\s*\|[^\n]*\n(?:\|[-\s|]+\n)?', clean_text, re.I)
        if m_cust:
            after = clean_text[m_cust.end():]
            buyer_parts = []
            for trow in after.split('\n')[:5]:
                trow = trow.strip()
                if not trow or set(trow).issubset({'|', '-', ' ', '+'}):
                    continue
                if '|' in trow:
                    cells = [c.strip() for c in trow.split('|') if c.strip()]
                    if cells:
                        first = cells[0]
                        flow = first.lower()
                        # Stop at section keywords or item table
                        if any(k in flow for k in ['#', 'item', 'description', 'total',
                                                     'invoice', 'email:', 'payment']):
                            # Extract email if present
                            if 'email:' in flow:
                                em = re.search(r'[\w.+-]+@[\w.-]+', first)
                                if em and not invoice.buyerEmail:
                                    invoice.buyerEmail = em.group(0)
                            break
                        if first and len(first) > 2:
                            buyer_parts.append(first)
                else:
                    break
            if buyer_parts:
                invoice.buyerName = buyer_parts[0]
                if len(buyer_parts) > 1 and not invoice.buyerAddress:
                    invoice.buyerAddress = ', '.join(buyer_parts[1:])
    
    # Buyer fallback: second **BoldName** block after seller
    # Pattern: **SellerName**\nAddress\nPhone\n\n**BuyerName**\nAddress\nPhone
    if not invoice.buyerName and invoice.sellerName:
        bold_blocks = list(re.finditer(r'\*\*([^*]+)\*\*', text))
        _skip_labels = {'terms of sale', 'terms of payment', 'terms', 'notes',
                        'invoice number', 'date', 'due', 'description',
                        'subtotal', 'amount due', 'bank', 'payment'}
        # Pattern for invoice IDs that should NOT be treated as buyer names
        _invoice_id_pattern = re.compile(r'^(?:INV|INVOICE|PO|SO|ORDER|REF|NO)[.\s#\-]*[\d\-/]+', re.I)
        seller_found = False
        for bm in bold_blocks:
            val = bm.group(1).strip()
            low_val = val.lower()
            if low_val in _skip_labels or any(k in low_val for k in _skip_labels):
                continue
            # Skip values that look like invoice IDs
            if _invoice_id_pattern.match(val):
                continue
            # Skip values embedded in pipe-table cells (preceded by | within 3 chars)
            _before_bold = text[max(0, bm.start()-5):bm.start()]
            if '|' in _before_bold:
                continue
            # Skip date-like values (e.g. "28 April, 2024")
            if re.match(r'^\d{1,2}\s+[A-Za-z]{3,},?\s+\d{4}$', val):
                continue
            if not seller_found:
                # Check if this is the seller block
                if (val.lower().rstrip('.') == invoice.sellerName.lower().rstrip('.')
                        or invoice.sellerName.lower() in val.lower()):
                    seller_found = True
                continue
            # This is the first bold name after seller → buyer
            if len(val) > 2 and val.lower().strip() not in _buyer_skip:
                invoice.buyerName = val
                # Get address from next line
                rest = clean_text[bm.end():]
                lines_after = rest.strip().split('\n')
                if lines_after and not invoice.buyerAddress:
                    addr_line = lines_after[0].strip()
                    if (addr_line and len(addr_line) > 5
                            and not addr_line.startswith('**')
                            and not addr_line.startswith('|')
                            and 'phone' not in addr_line.lower()[:6]):
                        invoice.buyerAddress = addr_line
                break
    
    # ===== INVOICE ID & DATE =====
    if not invoice.invoiceID or not invoice.invoiceDate:
         # Generic pipe-table header extraction
         # | INV. NO.: | INV250405 |
         m_id = re.search(r'INV\.\s*NO\..*?\|\s*([^|]+)', clean_text, re.I)
         if m_id and not invoice.invoiceID:
             invoice.invoiceID = m_id.group(1).strip()
             
         m_date = re.search(r'INV\.\s*DATE.*?\|\s*([^|]+)', clean_text, re.I)
         if m_date and not invoice.invoiceDate:
             raw_date = m_date.group(1).strip()
             # Use date parser logic...
             invoice.invoiceDate = raw_date # Simplified for now, pre_parse_en_commercial will re-parse later
         
         # Pipe-table: "| Date | 2 Sep 2025 |" (exclude "Due Date", "Shipment Date", etc.)
         if not invoice.invoiceDate:
             m_pipe_date = re.search(r'\|\s*(?:Invoice\s+)?Date\s*\|\s*([^|]+)\|', clean_text, re.I)
             if m_pipe_date:
                 raw_d = m_pipe_date.group(1).strip()
                 if raw_d and len(raw_d) >= 6:
                     # Parse "2 Sep 2025" or "09/02/2025" etc.
                     months = {'jan':'01','feb':'02','mar':'03','apr':'04','may':'05','jun':'06',
                               'jul':'07','aug':'08','sep':'09','oct':'10','nov':'11','dec':'12'}
                     m_dmy = re.match(r'(\d{1,2})\s+([A-Za-z]{3,})\s+(\d{4})', raw_d)
                     m_mdy = re.match(r'([A-Za-z]{3,})\s+(\d{1,2}),?\s+(\d{4})', raw_d)
                     if m_dmy:
                         dd, mon, yyyy = m_dmy.group(1), m_dmy.group(2)[:3].lower(), m_dmy.group(3)
                         if mon in months:
                             invoice.invoiceDate = f"{dd.zfill(2)}/{months[mon]}/{yyyy}"
                     elif m_mdy:
                         mon, dd, yyyy = m_mdy.group(1)[:3].lower(), m_mdy.group(2), m_mdy.group(3)
                         if mon in months:
                             invoice.invoiceDate = f"{dd.zfill(2)}/{months[mon]}/{yyyy}"
                     elif re.match(r'\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{4}', raw_d):
                         invoice.invoiceDate = raw_d
    
    # ===== INVOICE ID =====
    if not invoice.invoiceID:
        id_patterns = [
            # L/C trade: "No. & Date of Invoice\nS.W-2019043 Feb 14, 2019"
            r'No\.?\s*(?:&|and)\s*Date\s+of\s+Invoice\s*\n\s*([A-Za-z0-9][\w\.\-/]+)',
            r'(?<!PROFORMA )(?:INV\.?\s*NO\.?|Invoice\s*No\.?|Invoice\s*#|Invoice\s*Number)[:\s]*[#]?\s*([A-Za-z0-9][\w\-/]+(?:\s+\d{4})?)',
            r'(?:INVOICE\s*#)[:\s]*([\w\-/]+)',
            # "Export Invoice No & Date" in pipe table: header row → next row first cell
            r'Export\s+Invoice\s+No[^\n]*\n\|\s*([A-Za-z0-9][\w\-/]+)',
            r'(?:Export\s+Invoice\s+No)[^:|\n]*?[:|\s]\s*([A-Za-z0-9][\w\-/]+)',
            r'(?:^|\n)\s*#(\d{4,})\s*(?:\n|$)',  # "#000001" pattern
            # "Invoice Number:\n\nINV-2024-0892" (bold label, value on next line)
            r'Invoice\s*Number\s*[:]*\s*\n\s*\n?\s*([A-Za-z0-9][\w\-/]+)',
            # "EXPORT REFERENCES (i.e., order no., invoice no.)\n2786"
            r'EXPORT\s+REFERENCES[^\n]*\n\s*([A-Za-z0-9][\w\-/]+)',
            # "**Number:** INC 2025121" — standalone Number label (exclude Account Number, Phone Number, etc.)
            r'(?<!Account\s)(?<!Phone\s)(?<!Fax\s)(?<!Serial\s)(?<!Tracking\s)(?<!IncoDocs\s)(?<!Importer\s)(?<!Exporter\s)(?<!Order\s)(?<!Customer\s)(?<!Sales\s)(?<![A-Za-z])Number\s*:\s*([A-Za-z0-9][\w \-/]{2,30})',
            # "My Reference: REF11421" or "Reference: INV-2024" (fallback, only after all specific patterns)
            r'(?:My\s+)?Reference\s*:\s*([A-Za-z][\w\-/]{3,30})',
        ]
        # Also try pipe-table format: "| Invoice Number | ... |\n|---|---|\n| 25003750 | ... |"
        m_pipe = re.search(r'Invoice\s+Number[^|]*\|.*?\n(?:\|[-\s|]+\n)?\|\s*([\w\-/]+)', clean_text, re.I)
        if m_pipe:
            val = m_pipe.group(1).strip()
            if val and len(val) >= 3 and re.search(r'\d', val):
                invoice.invoiceID = val
        # Pipe-table: "| Export Invoice No & Date | ... |\n|---|---|\n| 1892 | 10 Jan 2018 |"
        if not invoice.invoiceID:
            m_pipe2 = re.search(r'Export\s+Invoice\s+No[^|]*\|.*?\n(?:\|[-\s|]+\n)?\|\s*(\d{3,})', clean_text, re.I)
            if m_pipe2:
                invoice.invoiceID = m_pipe2.group(1).strip()
        # Pipe-table key-value: "| Invoice # | 82 |" or "| Invoice No | INV-001 |"
        if not invoice.invoiceID:
            m_pipe3 = re.search(r'\|\s*(?:Invoice\s*(?:#|No\.?|Number))\s*\|\s*([^|]+)\|', clean_text, re.I)
            if m_pipe3:
                val = m_pipe3.group(1).strip()
                if val and re.search(r'\d', val):
                    invoice.invoiceID = val
        # Words that are NOT valid invoice IDs
        _bad_ids = {'shipper', 'exporter', 'consignee', 'importer', 'invoice',
                    'commercial', 'proforma', 'number', 'date', 'serial'}
        for pat in id_patterns:
            m = re.search(pat, clean_text, re.I)
            if m:
                val = m.group(1).strip().strip('*').strip('#')
                if val and len(val) >= 1 and not re.fullmatch(r'\d{1,2}', val):
                    # Reject pure words, words with slashes like 'Shipper/Exporter'
                    clean_val = val.replace('/', '').replace('-', '').replace('.', '').replace(' ', '')
                    if (val.lower() not in _bad_ids
                            and not re.fullmatch(r'[A-Za-z]+', clean_val)
                            and not re.fullmatch(r'[A-Za-z]+/[A-Za-z]+', val)):
                        invoice.invoiceID = val
                        break
    
    # ===== INVOICE DATE =====
    if not invoice.invoiceDate:
        # Vietnamese fallback: Ngày DD tháng MM năm YYYY (also handles 20...21... split year)
        m_vn = re.search(r"Ngày.*?(\d{1,2}).*?tháng.*?(\d{1,2}).*?năm.*?(\d{2,4})[\.\s]*(\d{0,2})", clean_text, re.I)
        if m_vn:
            year = m_vn.group(3) + (m_vn.group(4) or '')
            if len(year) == 4:
                invoice.invoiceDate = f"{m_vn.group(1).zfill(2)}/{m_vn.group(2).zfill(2)}/{year}"
        # Vietnamese short: Ngày lập: DD/MM/YYYY
        if not invoice.invoiceDate:
            m_vn2 = re.search(r"[Nn]gày(?:\s+lập)?[:\s]+(\d{1,2})/(\d{1,2})/(\d{4})", clean_text)
            if m_vn2:
                invoice.invoiceDate = f"{m_vn2.group(1).zfill(2)}/{m_vn2.group(2).zfill(2)}/{m_vn2.group(3)}"
    if not invoice.invoiceDate:
        months = {'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04', 'may': '05', 'jun': '06',
                  'jul': '07', 'aug': '08', 'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12',
                  'january': '01', 'february': '02', 'march': '03', 'april': '04',
                  'june': '06', 'july': '07', 'august': '08', 'september': '09',
                  'october': '10', 'november': '11', 'december': '12'}
        
        date_patterns = [
            # "Date: 20-Nov-2017" or "INV. DATE: APR 4TH,2025"
            (r'(?:INV\.?\s*)?DATE\s*[:\s]+(\d{1,2})[\s\-/.](\w{3,9})[\s\-/.,]*(\d{2,4})', 'dmy_name'),
            # "Date: October 26, 2028" or "DEC 14th 2021" or "Date of Shipment:\n04/24/2024"
            (r'(?:INV\.?\s*)?DATE[^:]*[:\s]+(\w{3,9})\.?\s*(\d{1,2})(?:st|nd|rd|th)?,?\s*(\d{4})', 'mdy_name'),
            # "Date: 08TH MAR 2016" / "1ST January 2025" (day-first with ordinal suffix)
            (r'(?:INV\.?\s*)?DATE\s*[:\s]+(\d{1,2})(?:ST|ND|RD|TH)\s+(\w{3,9})\.?\s*,?\s*(\d{4})', 'dmy_name_ord'),
            # Pipe-table header: "| DATE OF EXPORT |...\n|---|...|\n| 12/1/2013 |..."
            (r'\|\s*DATE\s+OF\s+\w+\s*\|[^\n]*\n\|[-|\s]+\|\n\|\s*(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})\s*\|', 'mdy_num'),
            # "DATE OF EXPORTATION\n06/11/2019"
            (r'DATE\s+OF\s+\w+\s*\n\s*(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})', 'mdy_num'),
            # Standalone "October 26, 2028" or "March 28, 2024"
            (r'(\w{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})', 'mdy_name'),
            # "Date: mm/dd/yyyy" or "Date: dd/mm/yyyy"
            (r'(?:INV\.?\s*)?DATE\s*[:\s]+(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})', 'mdy_num'),
            # "Date: 2025-12-01"
            (r'(?:INV\.?\s*)?DATE\s*[:\s]+(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})', 'ymd'),
            # DD.MM.YYYY format (European): "24.03.2025" or "12.2.2022"
            (r'(\d{1,2})\.(\d{1,2})\.(\d{4})', 'dmy_dot'),
            # "10 Jan 2018" pattern
            (r'(\d{1,2})\s+(\w{3,9})\s+(\d{4})', 'dmy_name'),
            # Standalone dd/mm/yyyy without label (less specific, lower priority)
            (r'(\d{2})[/\-](\d{2})[/\-](\d{4})', 'mdy_num'),
        ]
        
        for pat, fmt in date_patterns:
            m = re.search(pat, clean_text, re.I)
            if m:
                try:
                    if fmt == 'dmy_name' or fmt == 'dmy_name_ord':
                        day = m.group(1).zfill(2)
                        month_name = m.group(2).lower().rstrip('.,')
                        # Strip ordinal suffixes
                        month_name = re.sub(r'(st|nd|rd|th)$', '', month_name)
                        year = m.group(3)
                        if len(year) == 2:
                            year = '20' + year
                        mn = months.get(month_name, months.get(month_name[:3]))
                        if mn:
                            invoice.invoiceDate = f"{day}/{mn}/{year}"
                    elif fmt == 'mdy_name':
                        month_name = m.group(1).lower().rstrip('.,')
                        mn = months.get(month_name, months.get(month_name[:3]))
                        day = m.group(2).zfill(2)
                        year = m.group(3)
                        if mn:
                            invoice.invoiceDate = f"{day}/{mn}/{year}"
                    elif fmt == 'mdy_num':
                        p1, p2, yyyy = m.group(1), m.group(2), m.group(3)
                        # If first number > 12, it must be day (not month) → DD/MM/YYYY
                        if int(p1) > 12:
                            dd, mm = p1, p2
                        else:
                            mm, dd = p1, p2
                        invoice.invoiceDate = f"{dd.zfill(2)}/{mm.zfill(2)}/{yyyy}"
                    elif fmt == 'ymd':
                        yyyy, mm, dd = m.group(1), m.group(2), m.group(3)
                        invoice.invoiceDate = f"{dd.zfill(2)}/{mm.zfill(2)}/{yyyy}"
                    elif fmt == 'dmy_dot':
                        dd, mm, yyyy = m.group(1), m.group(2), m.group(3)
                        invoice.invoiceDate = f"{dd.zfill(2)}/{mm.zfill(2)}/{yyyy}"
                except (ValueError, KeyError):
                    pass
                if invoice.invoiceDate:
                    break
    
    # ===== CURRENCY =====
    if not invoice.currency:
        # Check for EUR in table headers (e.g. "Value in EUR") before $->USD fallback
        if re.search(r'(?:Value|Amount|Price|Total)\s+(?:in\s+)?EUR\b', clean_text, re.I) or re.search(r'\bEUR\s*[\d\.\,]+', clean_text, re.I) or '€' in clean_text:
            invoice.currency = 'EUR'
        elif 'USD' in clean_text or '$' in clean_text or re.search(r'U\.?S\.?\s+EXPORT', clean_text, re.I):
            invoice.currency = 'USD'
    
    # ===== TOTAL AMOUNT (EN patterns) =====
    if not invoice.totalAmount:
        total_patterns = [
            r'EXW[:\s].*?([\d,\.]+)\s*$',
            r'(?:Grand\s+Total|Total\s+Invoice\s*Value|Total\s+Net\s+Value)[:\s]*\$?([\d,\.]+)',
            # "Amount Due (USD) | $2,280.00" or "Balance Due: $500"
            r'(?:Amount|Balance)\s+Due[\s|()\w]*[$£€]\s*([\d,\.]+)',
            # "Total Amount\n$23,275" or "Total Amount: $23,275"
            r'Total\s+Amount(?:\s*\([^)]*\))?[:\s]*\n\s*[$£€]?\s?([\d,\.]+)',
            r'Total\s+Amount(?:\s*\([^)]*\))?\s*[:\s]+[$£€]?\s?([\d,\.]+)',
            # TOTAL line with currency prefix: "TOTAL\n46,000KG CNF HAIPHONG USD 29,900"
            r'\bTOTAL\b[:\s]*[^\n]*?(?:USD|EUR|GBP|JPY|CNY|AUD|CAD|CHF)\s+([\d,\.]+)',
            r'\bTOTAL[:\s]+[$£€]?\s?([\d,\.]+)',
            # Pipe-table: first cell is TOTAL — "| TOTAL | GBP 32499 |" (TOTAL as first cell only)
            r'^\|\s*TOTAL\s*\|\s*[A-Za-z]{0,3}\s?[$£€]?\s?([\d,\.]+)',
            # Next-row: "| TOTAL |\n---\n| GBP 32499 |"  (TOTAL as first cell only)
            r'^\|\s*TOTAL\s*\|[^\n]*\n(?:\|[-\s|]+\|\n)?\|\s*[A-Za-z]{0,3}\s?[$£€]?\s?([\d,\.]+)',
            # Standalone number on its own line near TOTAL section
            r'\bTOTAL[:\s][^\n]*\n[^\n]*\n\s*([\d,\.]+)',
        ]
        for pat in total_patterns:
            m = re.search(pat, clean_text, re.I | re.M)
            if m:
                val = safe_parse_float(m.group(1))
                if val and val > 10:  # Minimum guard: totalAmount should be > 10
                    invoice.totalAmount = val
                    break
    
    # ===== TAX/SUBTOTAL (EN patterns) =====
    # SPECIAL: Stacked labels pattern — labels on separate lines, values on separate lines
    # e.g. "Invoice Subtotal\nTax Rate\nSales Tax\n\nGBP 29,545\n10%\nGBP 2,954"
    if not invoice.preTaxPrice or not invoice.taxAmount:
        m_stacked = re.search(
            r'Invoice\s+Subtotal\s*\n\s*Tax\s+Rate\s*\n\s*Sales\s+Tax\s*\n+'
            r'\s*[A-Za-z]{0,3}\s?[$£€]?\s?([\d,\.]+)\s*\n'  # subtotal value
            r'\s*(\d+(?:\.\d+)?)\s*%\s*\n'                    # tax rate
            r'\s*[A-Za-z]{0,3}\s?[$£€]?\s?([\d,\.]+)',        # tax amount
            clean_text, re.I
        )
        if m_stacked:
            sub_val = safe_parse_float(m_stacked.group(1))
            pct_val = float(m_stacked.group(2))
            tax_val = safe_parse_float(m_stacked.group(3))
            if sub_val and sub_val > 0 and not invoice.preTaxPrice:
                invoice.preTaxPrice = sub_val
            if pct_val and not invoice.taxPercent:
                invoice.taxPercent = str(int(pct_val)) + '%' if pct_val == int(pct_val) else str(pct_val) + '%'
            if tax_val and tax_val > 0 and not invoice.taxAmount:
                invoice.taxAmount = tax_val

    if not invoice.taxPercent:
        # "Tax (8%): $188" or "VAT: 14%" or "Tax Rate: 10%" or "Taxes (10%) $40"
        # Also handle pipe-table: "| VAT | 14% |"
        m = re.search(r'(?:Tax(?:es)?|VAT|Sales\s+Tax)(?:\s+Rate)?[\s|]*\(?\s*(\d+(?:\.\d+)?)\s*%', clean_text, re.I)
        if m:
            try:
                _pct_raw = m.group(1)
                invoice.taxPercent = _pct_raw + '%'
            except ValueError:
                pass
    
    if not invoice.preTaxPrice:
        # "Subtotal: $2,350" or "Sub Total: 44,780" or "Invoice Subtotal: GBP 29,545"
        # Tighten: use separator to allow pipe tables like "| Subtotal | $21,775 |"
        m = re.search(r'(?:Sub\s*total|Invoice\s+Subtotal|Total\s+HT|Total\s+Ex\s+Tax)(?:\s*\([^)]*\))?[:\s|]{1,10}[A-Za-z]{0,3}\s?[$£€]?\s?([\d,\.]+)', clean_text, re.I)
        if m:
            val = safe_parse_float(m.group(1))
            if val and val > 0:
                invoice.preTaxPrice = val
    
    if not invoice.taxAmount:
        # "Tax Due: $3.00" or "Sales Tax: GBP 2,954" or "Tax (10%): $40" or "Export Tax: $650"
        m = re.search(r'(?:Tax\s+Due|Sales\s+Tax|Export\s+Tax|Import\s+Tax|Total\s+TVA|(?:Tax(?:es)?|VAT)\s*\([^)]*\))(?:\s*\([^)]*\))?[:\s|]{1,10}[A-Za-z]{0,3}\s?[$£€]?\s?([\d,\.]+)', clean_text, re.I)
        if m:
            val = safe_parse_float(m.group(1))
            if val and val > 0:
                invoice.taxAmount = val
    
    # Fallback: standalone "Tax $38.24" or "Tax: $38.24" (bold label without parens)
    if not invoice.taxAmount:
        m = re.search(r'\b(?:Tax|VAT)\b(?!\s*(?:Rate|Percent|Code|ID|Number|Invoice))[:\s]*\$?\s?([\d,\.]+)', clean_text, re.I)
        if m:
            val = safe_parse_float(m.group(1))
            if val and val > 0:
                invoice.taxAmount = val

    # ===== TAX AMOUNT FALLBACK: Calculate from preTaxPrice * taxPercent =====
    if not invoice.taxAmount and invoice.preTaxPrice and invoice.taxPercent:
        _tax_pct_val = re.search(r'([\d.]+)', invoice.taxPercent)
        if _tax_pct_val:
            invoice.taxAmount = round(invoice.preTaxPrice * float(_tax_pct_val.group(1)) / 100, 2)

    # ===== TOTAL FALLBACK: Subtotal + Tax when no explicit Total =====
    if not invoice.totalAmount and invoice.preTaxPrice:
        tax = invoice.taxAmount or 0
        invoice.totalAmount = invoice.preTaxPrice + tax


# Hàm gọi trong API_server.py
def parse_invoice_block_based(raw_text: str) -> Invoice:
    invoice = Invoice()

    # ===== EN COMMERCIAL INVOICE PRE-PARSER (runs first, VN-safe) =====
    pre_parse_en_commercial(raw_text, invoice)

    lines = clean_lines(raw_text)
    blocks = detect_blocks(lines)

    parse_header(blocks["header"], invoice)
    parse_seller(blocks["seller"], invoice)
    parse_buyer(blocks["buyer"], invoice)
    parse_table(blocks["table"], invoice)
    parse_total(blocks["total"], invoice)
    
    # ===== Vietnamese date fallback =====
    # When date line (Ngày...tháng...năm) ends up outside header block (e.g., buyer block
    # due to keyword routing like "Liên 2 Giao cho người mua"), parse_header misses it.
    if not invoice.invoiceDate:
        _text_for_date = raw_text.split('--- ZOOM TEXT ---')[0]
        _clean_date = re.sub(r'\*\*([^*]+)\*\*', r'\1', _text_for_date)
        # Full VN: Ngày DD tháng MM năm YYYY (also 20...21... split year)
        _m_vn = re.search(r"Ngày.*?(\d{1,2}).*?tháng.*?(\d{1,2}).*?năm.*?(\d{2,4})[\.\s]*(\d{0,2})", _clean_date, re.I)
        if _m_vn:
            _yr = _m_vn.group(3) + (_m_vn.group(4) or '')
            if len(_yr) == 4:
                invoice.invoiceDate = f"{_m_vn.group(1).zfill(2)}/{_m_vn.group(2).zfill(2)}/{_yr}"
        # Short VN: Ngày lập: DD/MM/YYYY
        if not invoice.invoiceDate:
            _m_vn2 = re.search(r"[Nn]gày(?:\s+lập)?[:\s]+(\d{1,2})/(\d{1,2})/(\d{4})", _clean_date)
            if _m_vn2:
                invoice.invoiceDate = f"{_m_vn2.group(1).zfill(2)}/{_m_vn2.group(2).zfill(2)}/{_m_vn2.group(3)}"
    
    # Deduction-based total: if a pipe-table row with "DEDUCTION" exists,
    # the last monetary value is the net payable total
    _deduction_text = raw_text.split('--- ZOOM TEXT ---')[0]
    _deduction_m = re.search(r'\|\s*DEDUCTION\b[^|]*\|([^|]*\|)+', _deduction_text, re.I)
    if _deduction_m:
        _ded_line = _deduction_m.group(0)
        _ded_cells = [c.strip() for c in _ded_line.split('|') if c.strip()]
        # Get the last monetary value from the last cell
        if _ded_cells:
            _last_cell = _ded_cells[-1]
            _ded_amt = re.search(r'([\d,.]+)', _last_cell)
            if _ded_amt:
                _ded_val = safe_parse_float(_ded_amt.group(1))
                if _ded_val and _ded_val > 0:
                    invoice.totalAmount = _ded_val
    # Fallback: if itemList is empty after block-based parsing,
    # try parsing items from the FULL raw text (handles cases where
    # items end up in total/header blocks due to keyword routing)
    if not invoice.itemList:
        from src.parsers.invoice_table_parser import parse_items_from_table
        # Only scan text before ZOOM TEXT marker to avoid duplicates
        text_for_items = raw_text.split('--- ZOOM TEXT ---')[0]
        invoice.itemList = parse_items_from_table(text_for_items)
    
    # Fallback: Section-based items (e.g. Description/Quantity/Price/Amount in separate numbered sections)
    if not invoice.itemList:
        from src.schemas.invoice import InvoiceItem
        text_for_sections = raw_text.split('--- ZOOM TEXT ---')[0]
        _desc_vals, _qty_vals, _price_vals, _amt_vals = [], [], [], []
        _section_header = None
        for line in text_for_sections.split('\n'):
            stripped = line.strip()
            # Detect section headers like "14. Description of Goods" or "16. Unit price (USD)"
            m_sec = re.match(r'^\d+\.\s+(.+)', stripped)
            if m_sec:
                _section_header = m_sec.group(1).lower()
                continue
            if not stripped or not _section_header:
                if not stripped:
                    _section_header = None
                continue
            # Classify content by section header (skip TOTAL sections)
            if 'total' in _section_header and 'unit' not in _section_header:
                continue  # Skip standalone TOTAL sections
            if any(k in _section_header for k in ['description', 'goods', 'commodity']):
                _desc_vals.append(stripped)
            elif any(k in _section_header for k in ['quantity', 'qty']):
                _qty_vals.append(re.sub(r'[^\d.,]', '', stripped))
            elif any(k in _section_header for k in ['unit price', 'unit cost', 'price']):
                _price_vals.append(re.sub(r'[^\d.,]', '', stripped))
            elif any(k in _section_header for k in ['amount', 'am count']):
                _amt_vals.append(re.sub(r'[^\d.,]', '', stripped))
        # Build items from parallel arrays
        if _desc_vals or _qty_vals or _price_vals or _amt_vals:
            n = max(len(_desc_vals), len(_qty_vals), len(_price_vals), len(_amt_vals))
            items = []
            for i in range(n):
                item = InvoiceItem()
                if i < len(_desc_vals):
                    item.productName = _desc_vals[i]
                if i < len(_qty_vals):
                    try: item.quantity = float(_qty_vals[i].replace(',', ''))
                    except: pass
                if i < len(_price_vals):
                    try: item.unitPrice = float(_price_vals[i].replace(',', ''))
                    except: pass
                if i < len(_amt_vals):
                    try: item.amount = float(_amt_vals[i].replace(',', ''))
                    except: pass
                if item.productName or item.quantity or item.unitPrice or item.amount:
                    items.append(item)
            if items:
                invoice.itemList = items
    
    # Fallback 3: Numbered item descriptions (1., 2.) + separate Qty/Price blocks
    # e.g. DHL template: "1. Populated PCB..." then later "10 Pcs." / "$USD 100.00"
    if not invoice.itemList:
        from src.schemas.invoice import InvoiceItem
        text_for_items = raw_text.split('--- ZOOM TEXT ---')[0]
        clean_text = re.sub(r'\*{1,2}', '', text_for_items)
        
        # Extract numbered item descriptions (multiline: collect until next number or separator)
        item_descs = []
        current_desc = None
        for line in clean_text.split('\n'):
            s = line.strip()
            m_num = re.match(r'^(\d+)\.\s+(.+)', s)
            if m_num:
                if current_desc:
                    item_descs.append(current_desc.strip())
                current_desc = m_num.group(2)
            elif current_desc and s and not s.startswith('---') and not re.match(r'^[\d,.$]+$', s):
                # Continue multiline description (skip separators and pure numbers)
                if not any(k in s.lower() for k in ['total', 'subtotal', 'pcs', 'shipping']):
                    current_desc += ' ' + s
        if current_desc:
            item_descs.append(current_desc.strip())
        
        # Extract quantities: only match "X Pcs." at line start to avoid field reference numbers
        qty_vals = []
        price_vals = []
        for line in clean_text.split('\n'):
            s = line.strip()
            m_qty = re.match(r'^(\d+)\s*(?:Pcs\.?|pcs\.?|units?|pieces?)\b', s, re.I)
            if m_qty:
                qty_vals.append(m_qty.group(1))
            m_price = re.match(r'^\$\s*(?:USD\s*)?([\d,]+\.?\d*)$', s, re.I)
            if m_price:
                price_vals.append(m_price.group(1))
        
        # Only build items if we have descriptions AND at least qty or price
        if item_descs and (qty_vals or price_vals):
            # Filter out prices that match known totals/subtotals
            filtered_prices = list(price_vals)
            if invoice.totalAmount and filtered_prices:
                filtered_prices = [p for p in filtered_prices if safe_parse_float(p) != invoice.totalAmount]
            
            items = []
            for i, desc in enumerate(item_descs):
                item = InvoiceItem()
                item.productName = desc
                if i < len(qty_vals):
                    try: item.quantity = float(qty_vals[i])
                    except: pass
                if i < len(filtered_prices):
                    try: item.unitPrice = safe_parse_float(filtered_prices[i])
                    except: pass
                if item.quantity and item.unitPrice:
                    item.amount = item.quantity * item.unitPrice
                items.append(item)
            if items:
                invoice.itemList = items
    
    # Fallback 4: Bold-label item blocks (e.g. "**Description of Goods**\nBAR STOOL\n**Unit Quantity**\n150 EACH")
    if not invoice.itemList:
        from src.schemas.invoice import InvoiceItem
        text_for_items = raw_text.split('--- ZOOM TEXT ---')[0]
        # Extract bold-labeled blocks
        _desc_m = re.search(r'\*\*Description\s+of\s+Goods\*\*\s*\n(.*?)(?=\n\s*\*\*|\n\s*---|\n\s*$)', text_for_items, re.I | re.S)
        _qty_m = re.search(r'\*\*(?:Unit\s+)?Quantity\*\*\s*\n(.*?)(?=\n\s*\*\*|\n\s*---|\n\s*$)', text_for_items, re.I | re.S)
        _price_m = re.search(r'\*\*(?:Unit\s+(?:Type|Price)|Price)\*\*\s*\n(.*?)(?=\n\s*\*\*|\n\s*---|\n\s*$)', text_for_items, re.I | re.S)
        _amount_m = re.search(r'\*\*Amount\*\*\s*\n(.*?)(?=\n\s*\*\*|\n\s*---|\n\s*$)', text_for_items, re.I | re.S)
        
        if _desc_m:
            _desc_lines = [l.strip() for l in _desc_m.group(1).strip().split('\n') if l.strip()]
            _desc = ' '.join(_desc_lines)
            if _desc and len(_desc) > 2:
                item = InvoiceItem()
                item.productName = _desc
                # Extract quantity
                if _qty_m:
                    _qty_text = _qty_m.group(1).strip()
                    _qm = re.search(r'([\d,]+(?:\.\d+)?)\s*', _qty_text)
                    if _qm:
                        try: item.quantity = safe_parse_float(_qm.group(1))
                        except: pass
                # Extract price
                if _price_m:
                    _price_text = _price_m.group(1).strip()
                    # Price may be on second line (first line is "Price" label)
                    _price_lines = [l.strip() for l in _price_text.split('\n') if l.strip()]
                    for _pl in _price_lines:
                        _pm = re.search(r'[\$]?\s*([\d,]+\.\d+)', _pl)
                        if _pm:
                            try: item.unitPrice = safe_parse_float(_pm.group(1))
                            except: pass
                            break
                # Extract amount
                if _amount_m:
                    _amt_text = _amount_m.group(1).strip()
                    _am = re.search(r'[\$]?\s*([\d,]+\.\d+)', _amt_text)
                    if _am:
                        try: item.amount = safe_parse_float(_am.group(1))
                        except: pass
                if not item.amount and item.quantity and item.unitPrice:
                    item.amount = item.quantity * item.unitPrice
                invoice.itemList = [item]

    # Fallback 5: Pipe-table rows with description + amount  
    # e.g. "| DESCRIPTION | qty | price | (amount) |"
    if not invoice.itemList:
        from src.schemas.invoice import InvoiceItem
        text_for_items = raw_text.split('--- ZOOM TEXT ---')[0]
        # Limit to page 1
        _page_m = re.search(r'---\s*PAGE\s+[2-9]', text_for_items, re.I)
        if _page_m:
            text_for_items = text_for_items[:_page_m.start()]
        
        _pipe_items = []
        for _pline in text_for_items.split('\n'):
            _pline = _pline.strip()
            if not _pline.startswith('|') or set(_pline).issubset({'|', '-', ' ', ':'}):
                continue
            _cells = [c.strip() for c in _pline.split('|') if c.strip()]
            if len(_cells) < 2:
                continue
            _first = _cells[0]
            # Skip header rows and total/deduction rows
            if re.match(r'^(description|quantity|unit|amount|price|total|deduction|stt|no\.|qty)', _first, re.I):
                continue
            # Skip separator rows and metadata rows
            if all(c in ('-', ':', ' ', '|') for c in _first):
                continue
            # Extract amount from last cells  
            _amt = None
            for _c in reversed(_cells[1:]):
                _am = re.search(r'[\$]?\s*([\d,]+\.[\d]+)', _c)
                if _am:
                    _amt = safe_parse_float(_am.group(1))
                    break
            if _first and len(_first) > 3 and not _first.lower().startswith(('dated', 'contract', 'shipped', 'from', 'to:', 'bl no', 'lc no', 'applicant')):
                item = InvoiceItem()
                item.productName = _first[:100]
                item.amount = _amt
                _pipe_items.append(item)
        if _pipe_items:
            invoice.itemList = _pipe_items

    # Change 4: invoiceName fallback — if still missing after block parsing
    if not invoice.invoiceName:
        _m_invname = re.search(r'(?:HÓA ĐƠN\s+GIÁ TRỊ GIA TĂNG|HÓA ĐƠN\s+BÁN HÀNG)', raw_text, re.I)
        if _m_invname:
            invoice.invoiceName = _m_invname.group(0).strip()
        else:
            _m_invname_en = re.search(r'(?:COMMERCIAL\s+INVOICE|PROFORMA\s+INVOICE|PRO\s+FORMA\s+INVOICE|TAX\s+INVOICE)', raw_text, re.I)
            if _m_invname_en:
                invoice.invoiceName = _m_invname_en.group(0).strip()
            else:
                # Standalone "INVOICE" (only if no other prefix match)
                _m_inv_standalone = re.search(r'(?:^|\n)\s*#*\s*(INVOICE)\s*(?:\n|$)', raw_text, re.I)
                if _m_inv_standalone:
                    invoice.invoiceName = _m_inv_standalone.group(1).strip()

    # Fallback: scan toàn bộ raw text cho các trường còn thiếu
    parse_global_fields(raw_text, invoice)
    
    # ---- BUYER FALLBACK: second **BoldName** block after seller ----
    if not invoice.buyerName and invoice.sellerName and _is_en_invoice(raw_text):
        _buyer_skip_labels = {'terms of sale', 'terms of payment', 'terms', 'notes',
                              'invoice number', 'date', 'due', 'description',
                              'subtotal', 'amount due', 'bank', 'payment'}
        _buyer_skip_names = {'name', 'address', 'phone', 'email', 'from', 'to', 'date',
                             'invoice', 'total', 'amount', 'tax'}
        bold_blocks = list(re.finditer(r'\*\*([^*]+)\*\*', raw_text))
        _invoice_id_re = re.compile(r'^(?:INV|INVOICE|PO|SO|ORDER|REF|NO)[.\s#\-]*[\d\-/]+', re.I)
        seller_found = False
        for bm in bold_blocks:
            val = bm.group(1).strip()
            low_val = val.lower()
            if low_val in _buyer_skip_labels or any(k in low_val for k in _buyer_skip_labels):
                continue
            # Skip invoice ID patterns and pipe-table values
            if _invoice_id_re.match(val):
                continue
            _before = raw_text[max(0, bm.start()-5):bm.start()]
            if '|' in _before:
                continue
            if re.match(r'^\d{1,2}\s+[A-Za-z]{3,},?\s+\d{4}$', val):
                continue
            if not seller_found:
                if (val.lower().rstrip('.') == invoice.sellerName.lower().rstrip('.')
                        or invoice.sellerName.lower() in val.lower()):
                    seller_found = True
                continue
            if len(val) > 2 and val.lower().strip() not in _buyer_skip_names:
                invoice.buyerName = val
                # Get address from next line
                rest = raw_text[bm.end():]
                lines_after = rest.strip().split('\n')
                if lines_after and not invoice.buyerAddress:
                    addr_line = lines_after[0].strip()
                    if (addr_line and len(addr_line) > 5
                            and not addr_line.startswith('**')
                            and not addr_line.startswith('|')
                            and 'phone' not in addr_line.lower()[:6]):
                        invoice.buyerAddress = addr_line
                break
    
    # ---- BUYER FALLBACK: second text block before invoice header ----
    # Pattern: SellerBlock\n\nBuyerBlock\n\n# INVOICE
    if not invoice.buyerName and invoice.sellerName and _is_en_invoice(raw_text):
        # Only search in text before ZOOM TEXT section
        _text_for_buyer = raw_text.split('--- ZOOM TEXT ---')[0]
        # Find the invoice title position
        _inv_title_m = re.search(r'^[^\S\n]*#*[^\S\n]*(?:COMMERCIAL\s+)?(?:PRO\s*FORMA\s+)?INVOICE', _text_for_buyer, re.I | re.M)
        if _inv_title_m:
            pre_header_text = _text_for_buyer[:_inv_title_m.start()].strip()
            # Split into blocks by blank lines or ---
            _blocks = re.split(r'\n\s*\n|\n---\n', pre_header_text)
            _blocks = [b.strip() for b in _blocks if b.strip()]
            # If we have at least 2 blocks, the last one before the header is the buyer
            if len(_blocks) >= 2:
                buyer_block = _blocks[-1]
                buyer_lines = [l.strip() for l in buyer_block.split('\n') if l.strip()]
                if buyer_lines:
                    # First line = buyer name, rest = address
                    bname = buyer_lines[0]
                    # Strip markdown bold markers
                    bname = re.sub(r'\*\*([^*]+)\*\*', r'\1', bname).strip()
                    # Reject if it looks like invoice metadata
                    _meta_labels = [
                        r'^(?:Invoice|Order|Purchase)\s*(?:No|Number|#)',
                        r'^(?:Invoice|P\.?O\.?)\s*(?:No|Number)',
                        r'^Term\s*:', r'^Date\s*:', r'^Reference\s*:',
                        r'^Payment\s', r'^Shipping\s', r'^Tracking\s',
                    ]
                    _is_meta = any(re.match(p, bname, re.I) for p in _meta_labels)
                    if len(bname) > 2 and bname.lower() != invoice.sellerName.lower() and not _is_meta:
                        invoice.buyerName = bname
                        if len(buyer_lines) > 1 and not invoice.buyerAddress:
                            invoice.buyerAddress = ', '.join(buyer_lines[1:])
    
    # ---- POST-PROCESS: Clean markdown/table garbage from string fields ----
    _clean_fields = ['sellerName', 'sellerAddress', 'buyerName', 'buyerAddress']
    for field in _clean_fields:
        val = getattr(invoice, field, None)
        if not val:
            continue
        # Strip markdown headers
        cleaned = re.sub(r'^[#]+\s*', '', val).strip()
        # Strip markdown bold
        cleaned = re.sub(r'\*\*([^*]+)\*\*', r'\1', cleaned)
        # Reject pure table lines (|...|) but keep partial pipe content
        if re.fullmatch(r'\|[^|]*\|(?:\s*\|[^|]*\|)*', cleaned):
            # Extract first non-empty cell
            cells = [c.strip() for c in cleaned.split('|') if c.strip()]
            if cells and len(cells[0]) > 3:
                cleaned = cells[0]
            else:
                setattr(invoice, field, None)
                continue
        # Remove leading pipe
        if cleaned.startswith('|'):
            cleaned = cleaned.lstrip('|').strip()
        # Remove trailing pipe
        if cleaned.endswith('|'):
            cleaned = cleaned.rstrip('|').strip()
        setattr(invoice, field, cleaned if cleaned else None)
    
    # ---- POST-PROCESS: Reject label-like values in buyer/seller fields ----
    _label_reject_patterns = re.compile(
        r'^(?:Country\s+of\s+(?:Origin|Manufacture|Destination)|'
        r'Gross\s+Weight|Net\s+Weight|Transportation|'
        r'Number\s+of\s+Packages|Total\s+Invoice)',
        re.I
    )
    for _lf in ['buyerName', 'buyerAddress', 'sellerName', 'sellerAddress']:
        _lv = getattr(invoice, _lf, None)
        if _lv and _label_reject_patterns.match(_lv):
            setattr(invoice, _lf, None)
    
    # ---- POST-PROCESS: Split name when it contains embedded address ----
    # e.g. "ABC Company Ltd. 456 Industrial Ave. City, State 67890" → name only
    for name_field, addr_field in [('buyerName', 'buyerAddress'), ('sellerName', 'sellerAddress')]:
        name_val = getattr(invoice, name_field, None)
        if name_val:
            # Look for house number pattern in the middle of the name
            m_addr = re.search(r'[.\s]\s*(\d{2,})\s+(?:[A-Z][a-z]+\s+)?(?:St|Street|Ave|Avenue|Blvd|Boulevard|Rd|Road|Lane|Dr|Drive|Way|Place|Pl)\b', name_val, re.I)
            if m_addr and m_addr.start() > 3:
                # Split: before = name, from match = address
                new_name = name_val[:m_addr.start()].strip().rstrip('.,')
                new_addr = name_val[m_addr.start():].strip().lstrip('., ')
                if new_name and len(new_name) > 2 and new_addr:
                    setattr(invoice, name_field, new_name)
                    if not getattr(invoice, addr_field, None):
                        setattr(invoice, addr_field, new_addr)
    
    # ---- POST-PROCESS: Clean template labels from addresses ----
    _addr_template_labels = [
        r'City,?\s*State,?\s*(?:Postal\s*Code|Zip(?:\s*Code)?)\s*:?',
        r'(?:^|,\s*)Country\s*:(?:\s*,)?',
        r'(?:^|,\s*)Post\s*Code\s*:(?:\s*,)?',
        r'(?:^|,\s*)Address\s*:?(?:\s*,)?',
        r'(?:^|,\s*)(?:City|State|Zip)\s*:(?:\s*,)?',
        r'City,\s*State,\s*Zip\s*:',
    ]
    for addr_field in ('sellerAddress', 'buyerAddress'):
        addr = getattr(invoice, addr_field, None)
        if addr:
            cleaned_addr = addr
            for tpl in _addr_template_labels:
                cleaned_addr = re.sub(tpl, '', cleaned_addr, flags=re.I).strip()
            # Clean redundant commas and whitespace
            cleaned_addr = re.sub(r',\s*,', ',', cleaned_addr)
            cleaned_addr = re.sub(r'^\s*,\s*', '', cleaned_addr)
            cleaned_addr = re.sub(r'\s*,\s*$', '', cleaned_addr)
            cleaned_addr = re.sub(r'\s{2,}', ' ', cleaned_addr).strip()
            setattr(invoice, addr_field, cleaned_addr if cleaned_addr else None)
    
    # ---- Validate invoiceDate format (dd/mm/yyyy) ----
    if invoice.invoiceDate:
        _date_parts = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{4})$', invoice.invoiceDate)
        if _date_parts:
            _dd, _mm, _yyyy = int(_date_parts.group(1)), int(_date_parts.group(2)), int(_date_parts.group(3))
            if _dd < 1 or _dd > 31 or _mm < 1 or _mm > 12 or _yyyy < 1900 or _yyyy > 2100:
                invoice.invoiceDate = None  # Invalid date
    
    # ---- Reject garbage addresses ----
    _garbage_addr_patterns = [
        r'^-{2,}$',         # just dashes "---"
        r'^-{2,}\s*$',      # dashes with whitespace
        r'ZOOM\s*TEXT',      # zoom text marker contamination
        r'^LOGO$',           # placeholder text
    ]
    for addr_field in ('sellerAddress', 'buyerAddress'):
        addr = getattr(invoice, addr_field, None)
        if addr and any(re.search(p, addr, re.I) for p in _garbage_addr_patterns):
            setattr(invoice, addr_field, None)
    
    # ---- Reject garbage buyer/seller names ----
    _garbage_name_patterns = [
        r'^bill\s+to\s+information$',
        r'^send\s+payment\s+to$',
        r'^payment\s+instructions?$',
        r'^put\s+your\s+own\b',
        r'^client\s+details?$',
        r'^my\s+details?$',
        r'^-{2,}$',
        r'^\.{2,}$',             # dots-only placeholder ("......" )
        r'^[.\s]+$',             # dots and spaces only
        # Invoice metadata labels — not buyer/seller names
        r'^(?:Invoice|Order|Purchase)\s*(?:No|Number|#)',
        r'^(?:P\.?O\.?)\s*(?:No|Number)',
        r'^Term\s*:', r'^Date\s*:', r'^Reference\s*:',
        # Footer/signature lines
        r'^thank\s+you\b',
        r'^(?:signature|signed|authorized\s+signature|for)\s*:',
        r'^(?:signatory|exporter)\s+(?:company|signature)',
        r'^logo$',
    ]
    for name_field in ('sellerName', 'buyerName'):
        name = getattr(invoice, name_field, None)
        if name and any(re.search(p, name.strip(), re.I) for p in _garbage_name_patterns):
            setattr(invoice, name_field, None)
            # Also clear address when name is rejected — same block, likely garbage too
            addr_field = name_field.replace('Name', 'Address')
            addr = getattr(invoice, addr_field, None)
            if addr:
                # Clear if address looks like metadata (invoice number, PO, etc.)
                _addr_is_meta = any(re.search(p, addr.strip(), re.I) for p in _garbage_name_patterns)
                _addr_is_code = bool(re.match(r'^[A-Za-z]*\s*[A-Z]{1,3}[\-][\d\-]+$', addr.strip()))
                if _addr_is_meta or _addr_is_code:
                    setattr(invoice, addr_field, None)
    
    # ---- VN BUYER NAME FALLBACK: "Họ tên người mua hàng: NAME" ----
    if not invoice.buyerName:
        _text_before_zoom = raw_text.split('--- ZOOM TEXT ---')[0]
        _clean_bfz = re.sub(r'\*\*([^*]+)\*\*', r'\1', _text_before_zoom)
        m_vn_buyer = re.search(r'[Hh]ọ tên người mua hàng[:\s]+([^\n]+)', _clean_bfz)
        if m_vn_buyer:
            _bname = m_vn_buyer.group(1).strip().strip(':').strip()
            # Reject placeholder values
            if _bname and not re.match(r'^[.\s]+$', _bname) and len(_bname) > 2:
                invoice.buyerName = _bname

    # ---- BUYER FALLBACK: "CLIENT DETAILS" / "Client:" section (runs after garbage rejection) ----
    if not invoice.buyerName and _is_en_invoice(raw_text):
        _text_before_zoom = raw_text.split('--- ZOOM TEXT ---')[0]
        _clean_bfz = re.sub(r'\*\*([^*]+)\*\*', r'\1', _text_before_zoom)
        # Pattern: "Client:\nCompanyName" or "Client: CompanyName"
        m_client = re.search(
            r'(?:CLIENT\s+DETAILS|Bill\s+To|Billed\s+To)\s*\n+\s*(?:Client\s*:\s*\n?\s*)([^\n*#|]+)',
            _clean_bfz, re.I
        )
        if m_client:
            cname = m_client.group(1).strip()
            if cname and len(cname) > 2:
                invoice.buyerName = cname
    
    # Clean paymentMethod: strip leading bullet markers "- " or "* "
    if invoice.paymentMethod:
        pm = invoice.paymentMethod.strip()
        pm = re.sub(r'^[-*]\s+', '', pm).strip()
        invoice.paymentMethod = pm if pm else None
    
    # ---- POST-PROCESS: Fix OCR-truncated seller names ----
    # If a longer company name appears in the text that ends with the current sellerName,
    # use the longer version (OCR sometimes drops leading characters)
    if invoice.sellerName and raw_text:
        sn = invoice.sellerName.strip()
        # Look for **CompanyName** or standalone company name in text
        for m in re.finditer(r'\*\*([^*]{5,})\*\*', raw_text):
            candidate = m.group(1).strip()
            # Check if candidate ends with sellerName and is longer (has more leading chars)
            if (candidate.endswith(sn) and len(candidate) > len(sn)
                    and candidate.lower() != sn.lower()):
                invoice.sellerName = candidate
                break
            # Also check if sellerName is a suffix of candidate (OCR dropped first chars)
            if (sn in candidate and len(candidate) > len(sn) + 1
                    and len(candidate) < len(sn) + 10):
                # Verify it's the same company (shares significant overlap)
                if candidate.endswith(sn[1:]):  # At least shares all but first char
                    invoice.sellerName = candidate
                    break
    
    # ---- FILTER GARBAGE ITEMS FROM itemList ----
    # Remove items that have:
    # 1. No quantity AND no unitPrice AND no amount (all 3 null)
    # 2. Suspicious/placeholder keywords in productName
    GARBAGE_KEYWORDS = [
        "thời điểm", "thuế suất", "tổng cộng", "cộng tiền", "thành tiền trước thuế",
        "không kê khai", "không chịu thuế", "tiền thuế", "số tiền viết bằng chữ",
        "người mua", "người bán", "chữ ký", "signature",
        # Shipping/logistics metadata — not line items (use specific patterns)
        "incoterm", "ex works",
        "despatch mode", "parcel nr", "gross weight",
    ]
    # Also filter items where productName is just a currency code
    CURRENCY_CODES = {"usd", "eur", "gbp", "vnd", "jpy", "cny", "inr",
                       "aud", "cad", "sgd", "chf", "hkd", "twd", "krw", "thb",
                       "myr", "idr", "php", "sek", "nok", "dkk", "nzd", "zar",
                       "aed", "sar", "brl", "mxn", "pln", "czk", "try", "rub"}
    # Summary/total row labels that should not be line items
    SUMMARY_KEYWORDS = [
        "sub total", "subtotal", "grand total", "total", "tax total",
        "taxal", "vat", "net total", "balance due", "amount due",
        "tổng cộng", "cộng tiền", "thuế",
    ]
    
    if invoice.itemList:
        cleaned_items = []
        for item in invoice.itemList:
            # Check if all numeric fields are null
            has_no_data = (item.quantity is None and item.unitPrice is None and item.amount is None)
            
            # Check for garbage keywords
            name_lower = (item.productName or "").lower()
            has_garbage_keyword = any(kw in name_lower for kw in GARBAGE_KEYWORDS)
            
            # Check if productName is just a currency code (e.g. "USD" from pipe table)
            is_currency = name_lower.strip() in CURRENCY_CODES
            
            # Check for summary/total rows (e.g., "Sub Total", "-", blank name)
            name_stripped = name_lower.strip().strip('-').strip()
            # Delivery term total/summary lines (EXW:, FOB:, CIF:, etc.)
            _delivery_terms = ['exw', 'fob', 'cif', 'cfr', 'cip', 'cnf', 'dap', 'ddp', 'fca']
            is_delivery_total = any(name_stripped.rstrip(':').strip() == dt for dt in _delivery_terms)
            is_summary_row = (
                name_stripped in {s for s in SUMMARY_KEYWORDS} or
                any(name_stripped == kw for kw in SUMMARY_KEYWORDS) or
                (not name_stripped and item.unitPrice is None) or  # blank/dash name with no price
                is_delivery_total
            )
            
            # Filter purely numeric short names (metadata from footer tables)
            is_numeric_name = (name_stripped.replace('.', '').replace(',', '').isdigit()
                              and len(name_stripped) <= 5)
            
            # Filter short names that are shipping carriers/modes (not real products)
            _shipping_prefixes = ['fedex', 'dhl ', 'ups ', 'forwarder', 'transporteur']
            is_shipping_mode = (len(name_stripped) < 30 and
                               any(name_stripped.startswith(sp) for sp in _shipping_prefixes))
            
            # Filter absurdly large amounts (likely parsing errors)
            is_absurd_amount = (item.amount is not None and abs(item.amount) > 1e12)
            
            # Skip if garbage
            if has_no_data or has_garbage_keyword or is_currency or is_summary_row or is_numeric_name or is_absurd_amount or is_shipping_mode:
                # print(f"DEBUG: Skipping garbage item: {item.productName}")
                continue
            
            cleaned_items.append(item)
        
        invoice.itemList = cleaned_items
    
    # ---- DEDUPLICATE itemList (handles OCR double-table issue) ----
    if invoice.itemList and len(invoice.itemList) >= 4:
        n = len(invoice.itemList)
        # Check if list is exactly doubled (first half == second half by qty+amount)
        if n % 2 == 0:
            half = n // 2
            first_half = invoice.itemList[:half]
            second_half = invoice.itemList[half:]
            is_dup = True
            for a, b in zip(first_half, second_half):
                # Compare amounts — other fields may differ due to different column headers
                if a.amount != b.amount:
                    is_dup = False
                    break
            if is_dup:
                invoice.itemList = first_half

    # ---- APPLY HS CODE TO ITEMS (from raw text) ----
    # L/C invoices often have "HS NUMBER : 2836.50.90" outside the items table
    if invoice.itemList:
        _hs_code = None
        _hs_m = re.search(r'(?:HS\s*(?:NUMBER|CODE|NO\.?))\s*:\s*([0-9][0-9\.]+)', raw_text, re.I)
        if _hs_m:
            _hs_code = _hs_m.group(1).strip().rstrip('.')
        if _hs_code:
            for item in invoice.itemList:
                if not item.productCode:
                    item.productCode = _hs_code

    # FINAL FALLBACK: "Max Number Strategy"
    # If totalAmount is missing or suspiciously equal to Tax Amount (e.g. 79400 vs 794000)
    # Check max number in raw text (or key blocks)
    # User insight: "The largest number in the table will definitely be totalAmount"
    if not invoice.totalAmount or (invoice.taxAmount and invoice.totalAmount <= invoice.taxAmount * 1.5):
        all_nums = []
        # Scan table and total blocks for numbers
        scan_lines = blocks["table"] + blocks["total"]
        
        # Also get numbers from header to EXCLUDE them (like invoiceID)
        header_nums = set()
        for h_line in blocks["header"]:
            for n in re.findall(r'[\d\.\,]+', h_line):
                val = safe_parse_float(n)
                if val: header_nums.add(val)
        
        # Extract digits from invoiceID to specifically exclude them
        id_digits = "".join(re.findall(r'\d', invoice.invoiceID or ""))
        id_val = safe_parse_float(id_digits) if id_digits else None

        for line in scan_lines:
            # EXCLUDE lines with transaction codes, phone numbers, postal codes
            low = line.lower()
            if any(k in low for k in ["mã gd", "mã giao dịch", "tel", "phone", "fax",
                                       "(+84)", "(+86)", "(+1)", "swift",
                                       "account", "tài khoản", "postal",
                                       "zip", "100000", "242000",
                                       "beneficiary", "bank information", "bank name",
                                       "iban", "sort-code", "routing",
                                       "customs tariff", "siret", "rcs ",
                                       "invoice number", "ship-to", "ship to",
                                       "hs code", "tariff no", "product code",
                                       "hts code", "harm.code"]):
                continue
            
            # Skip lines that contain HS code format numbers (e.g. 5403.20.00)
            if re.search(r'\b\d{4}\.\d{2}\.\d{2}\b', line):
                continue
            
            # Skip phone-number format lines: XX.XX.XX.XX.XX (e.g. "02.35.23.19.35")
            # These have 4+ dot-separated 2-digit groups
            if re.search(r'\b\d{2}\.\d{2}\.\d{2}\.\d{2}', line):
                continue
            
            nums = re.findall(r'[\d\.\,]+', line)
            for n in nums:
                val = safe_parse_float(n)
                # Filter: > 1000 (minimum amount)
                # Lower limit for non-VN invoices to avoid phone numbers/long IDs
                upper_limit = 10_000_000 if _is_en_invoice(raw_text) else 100_000_000_000
                if val and val > 1000 and val < upper_limit:
                    # Exclude if it matches a header number or the invoiceID digits
                    if val not in header_nums and val != id_val:
                        # Exclude year-like numbers (1900-2100, integer)
                        if val == int(val) and 1900 <= val <= 2100:
                            continue
                        all_nums.append(val)
        
        if all_nums:
            max_val = max(all_nums)
            
            # Heuristic: If we have totalAmount in word, use it to validate the max number
            word_val = 0
            if invoice.invoiceTotalInWord:
                from src.parsers.block_invoice_parser import vietnamese_words_to_number
                word_val = vietnamese_words_to_number(invoice.invoiceTotalInWord)
            
            # Also check if max_val is a known quantity in itemList
            is_quantity = False
            if invoice.itemList:
                for item in invoice.itemList:
                    if item.quantity == max_val and (item.amount is None or item.amount < max_val):
                        is_quantity = True
                        break
            
            if not is_quantity and (not word_val or abs(max_val - word_val) < 10):
                # Also validate against item amounts — if max_val is much larger
                # than item sum, it's likely a non-financial number (MARKS/NOS, etc.)
                _item_sum_ok = True
                if invoice.itemList:
                    _isum = sum(it.amount or 0 for it in invoice.itemList)
                    if _isum > 0 and max_val > _isum * 2:
                        _item_sum_ok = False
                        # Use item sum as totalAmount fallback
                        if not invoice.totalAmount:
                            invoice.totalAmount = _isum
                if _item_sum_ok and max_val > (invoice.totalAmount or 0):
                    invoice.totalAmount = max_val

    # Reject totalAmount that looks like a year (1900-2100, integer)
    if invoice.totalAmount and invoice.totalAmount == int(invoice.totalAmount):
        if 1900 <= invoice.totalAmount <= 2100:
            invoice.totalAmount = None

    # FINAL ITEM-SUM FALLBACK: if totalAmount is still missing, use sum of item amounts
    if not invoice.totalAmount and invoice.itemList:
        _item_total = sum(it.amount or 0 for it in invoice.itemList)
        if _item_total > 0:
            invoice.totalAmount = _item_total
    
    # FIX: if totalAmount matches a single item's amount but item sum is different and we have 2+ items
    if invoice.totalAmount and invoice.itemList and len(invoice.itemList) >= 2:
        _item_total = sum(it.amount or 0 for it in invoice.itemList)
        if _item_total > 0 and _item_total != invoice.totalAmount:
            # Check if current totalAmount equals one of the item amounts
            _item_amounts = [it.amount for it in invoice.itemList if it.amount]
            if invoice.totalAmount in _item_amounts and _item_total > invoice.totalAmount:
                invoice.totalAmount = _item_total

    # AUTHORITATIVE TOTAL: scan raw text for "Invoice Total" with currency amount
    # This overrides non-monetary "totals" like "Consignment Total: 556" (item count)
    _text_for_total = raw_text.split('--- ZOOM TEXT ---')[0]
    _invoice_total_m = re.search(
        r'(?:Invoice\s+Total|Grand\s+Total|Total\s+Amount\s+Due|Amount\s+Due|Balance\s+Due)'
        r'.{0,200}?'
        r'(?:USD|EUR|GBP|\$|€|£)\s*\$?([\d,]+\.\d{2})',
        _text_for_total, re.I | re.DOTALL
    )
    if not _invoice_total_m:
        # Also try same-line: "Invoice Total: $51,725.00"
        _invoice_total_m = re.search(
            r'(?:Invoice\s+Total|Grand\s+Total|Total\s+Amount\s+Due|Amount\s+Due|Balance\s+Due)'
            r'[^\n]*?(?:USD|EUR|GBP|\$|€|£)\s*\$?([\d,]+\.\d{2})',
            _text_for_total, re.I
        )
    if _invoice_total_m:
        _inv_total_val = float(_invoice_total_m.group(1).replace(',', ''))
        if _inv_total_val > 0:
            invoice.totalAmount = _inv_total_val
            # Regenerate invoiceTotalInWord to match the corrected total
            if (invoice.currency or "").upper() == "VND":
                invoice.invoiceTotalInWord = number_to_vietnamese_words(_inv_total_val)
            else:
                invoice.invoiceTotalInWord = number_to_english_words(_inv_total_val)

    if invoice.invoiceTotalInWord:
        _en_word_val = english_words_to_number(invoice.invoiceTotalInWord)
        if _en_word_val > 0:
            if not invoice.totalAmount:
                # totalAmount is missing — use word value
                invoice.totalAmount = _en_word_val
            elif (invoice.totalAmount < _en_word_val * 0.5) or (invoice.totalAmount > _en_word_val * 1.5):
                # Current totalAmount differs significantly from words value.
                # Validate: if current totalAmount matches item sum, trust the numeric total
                _item_sum_for_word_check = sum(it.amount or 0 for it in (invoice.itemList or []))
                _total_matches_items = (_item_sum_for_word_check > 0 and
                                        abs(invoice.totalAmount - _item_sum_for_word_check) < (_item_sum_for_word_check * 0.05) + 10)
                if not _total_matches_items:
                    # Only override if current total does NOT match item amounts
                    invoice.totalAmount = _en_word_val

    # Reverse fallback: if we have totalAmount but no invoiceTotalInWord, generate it
    if invoice.totalAmount and not invoice.invoiceTotalInWord:
        if (invoice.currency or "").upper() == "VND":
            invoice.invoiceTotalInWord = number_to_vietnamese_words(invoice.totalAmount)
        else:
            invoice.invoiceTotalInWord = number_to_english_words(invoice.totalAmount)

    # INDIAN GST TAX FALLBACK: extract CGST/SGST/IGST tax from pipe tables
    if not invoice.taxAmount:
        _gst_amounts = []
        _gst_percent = None
        for m in re.finditer(r'(\d+)%\s*\|\s*(?:CGST|SGST|IGST|GST)\s*\|\s*[₹]?([\d,\.]+)', raw_text, re.I):
            _pct = int(m.group(1))
            _amt = safe_parse_float(m.group(2))
            if _amt:
                _gst_amounts.append(_amt)
                if not _gst_percent:
                    _gst_percent = _pct
        if _gst_amounts:
            invoice.taxAmount = sum(_gst_amounts)
            if _gst_percent and not invoice.taxPercent:
                # Total GST% = individual rate × number of tax components
                # e.g., 9% CGST + 9% SGST = 18% total
                invoice.taxPercent = str(_gst_percent * len(_gst_amounts)) + '%'

    # FINAL CONSISTENCY CHECK: PreTax + Tax = Total
    # If we have all 3 but they don't add up, try to find a consistent pair
    if invoice.totalAmount:
        total = invoice.totalAmount
        pre = invoice.preTaxPrice
        tax = invoice.taxAmount
        
        # Scenario 1: Pre + Tax != Total, but maybe one of them is wrong?
        if pre and tax and abs(pre + tax - total) > (total * 0.01) + 10:
            # Check if any other numbers in the block make it consistent
            # Or if pre and tax are actually (Total - Tax) and (Tax)
            # In Case 03: pre=29545, tax=29545, total=32499 -> wrong.
            # But maybe we can find 2,954 somewhere?
            
            # Step: scan block again for a number 'x' such that pre + x = total or x + tax = total
            scan_lines = blocks["table"] + blocks["total"]
            all_block_nums = []
            for line in scan_lines:
                f_nums = re.findall(r'[\d\.\,]+', line)
                for n in f_nums:
                    v = safe_parse_float(n)
                    if v and v > 0: all_block_nums.append(v)
            
            # Try to fix tax first (Total - Pre)
            target_tax = total - (pre or 0)
            if target_tax > 0:
                for v in all_block_nums:
                    if abs(v - target_tax) < (target_tax * 0.01) + 5:
                        invoice.taxAmount = v
                        tax = v
                        break
            
            # Try to fix pre (Total - Tax)
            if abs(pre + tax - total) > (total * 0.01) + 10:
                target_pre = total - (tax or 0)
                if target_pre > 0:
                    for v in all_block_nums:
                        if abs(v - target_pre) < (target_pre * 0.01) + 5:
                            invoice.preTaxPrice = v
                            pre = v
                            break


    # FINAL: reject totalAmount that looks like a year (1900-2100, integer)
    # These come from text like "ICC 2020" or "April 24, 2024"
    if invoice.totalAmount and invoice.totalAmount == int(invoice.totalAmount):
        if 1900 <= invoice.totalAmount <= 2100:
            invoice.totalAmount = None
            invoice.invoiceTotalInWord = None

    # ===== Fallback: derive tax fields from item-level data when total block is empty =====
    # Change 1: Extended to multi-item cases (was single-item only).
    # Handles GTGT template invoices where tax data is only in the item table.
    if invoice.itemList:
        # Derive preTaxPrice from sum of item amounts
        if not invoice.preTaxPrice:
            _item_sum = sum(it.amount or 0 for it in invoice.itemList)
            if _item_sum > 0:
                invoice.preTaxPrice = _item_sum
        # Derive taxAmount from totalAmount - preTaxPrice
        if not invoice.taxAmount and invoice.totalAmount and invoice.preTaxPrice:
            _tax_calc = invoice.totalAmount - invoice.preTaxPrice
            if _tax_calc > 0:
                invoice.taxAmount = round(_tax_calc, 2)
        # Derive taxPercent from the raw text table (look for % in header-mapped tax_rate column)
        if not invoice.taxPercent:
            _raw_before_zoom = raw_text.split('--- ZOOM TEXT ---')[0].split('--- ZOOM RIGHT ---')[0]
            _tax_pct_m = re.search(r'(?<!\d)(\d{1,2})%', _raw_before_zoom)
            if _tax_pct_m:
                invoice.taxPercent = _tax_pct_m.group(1) + '%'

    # Change 5: Derive taxPercent from taxAmount/preTaxPrice when both are available
    if not invoice.taxPercent and invoice.taxAmount and invoice.preTaxPrice and invoice.preTaxPrice > 0:
        _calc_pct = round(invoice.taxAmount / invoice.preTaxPrice * 100)
        if _calc_pct in (1, 2, 3, 5, 8, 10, 15, 20):  # Common VAT rates worldwide
            invoice.taxPercent = f"{_calc_pct}%"

    # Change 3: For commercial invoices with no tax info, preTaxPrice = totalAmount
    if not invoice.preTaxPrice and invoice.totalAmount and not invoice.taxAmount:
        invoice.preTaxPrice = invoice.totalAmount

    return invoice
