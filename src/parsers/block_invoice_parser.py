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


SELLER_LABEL_KEYS = {
    "sellerName": ["tên đơn vị bán", "đơn vị bán", "đơn vị bán hàng", "comname", "dơn vị bán hàng",
                   "bên a (bên bán)", "bên bán", "bên a",
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
                      "eori", "gst no", "roc"],
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
        filtered_lines.append(line)
    lines = filtered_lines

    current = "seller"
    seen_header = False
    seen_table = False
    seen_buyer = False  # Track if we've entered buyer section
    
    for line in lines:
        l = line.lower().strip()

        # ===== HEADER (CHỈ KHI GẶP HÓA ĐƠN hoặc PHIẾU) =====
        # Note: Title may be split across lines like "# HÓA ĐƠN\nGIÁ TRỊ GIA TĂNG"
        if any(k in l for k in [
            "hóa đơn",                  # Added: partial match for multi-line titles
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
        ]):
            current = "header"
            seen_header = True

        # ===== SELLER (sau header - format header-first) =====
        # Khi thấy "đơn vị bán hàng" sau header, chuyển về seller block
        # HOẶC nếu đang ở Header mà thấy MST/Địa chỉ/SĐT (dấu hiệu seller info) thì chuyển sang Seller
        # Support English: "THE Seller:", "SHIPPER" and Vietnamese: "BÊN A (Bên bán)"
        elif any(k in l for k in ["đơn vị bán hàng", "seller:", "the seller:", "bên a (bên bán)", "bên bán)", "bên a:",
                                    "shipper", "寄货人",
                                    # EN Commercial Invoice seller section labels
                                    "exporter:", "exporter details", "sender/exporter",
                                    "ship from", "bill from", "shipper/exporter",
                                    "vendor/exporter", "sender name",
                                    # Customs/shipping invoice FROM: section
                                    "from:", "from :"]):
            current = "seller"

        # ===== BUYER (KHÔNG CẦN SEEN_HEADER) =====
        # Chuyển sang buyer khi gặp keywords chỉ người mua
        # Support English: "THE Buyer:", "CONSIGNEE" and Vietnamese: "Người mua (Buyer):", "Khách hàng:", "BÊN B (Bên mua)"
        elif any(k in l for k in [
            "khách hàng",           # Added: Vietnamese for "Customer"
            "họ tên người mua",
            "tên người mua",       # Added: "Tên người mua:"
            "người mua hàng",
            "người mua",
            "buyer:",
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
            if current not in ["total", "signature"]:
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
        elif seen_buyer and current == "seller":
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
        
        if (is_invoice_title or is_continuation) and "thay thế" not in low:
            # Clean markdown header markers
            name = line.strip().lstrip("# ").strip()
            # For "COMMERCIAL INVOICE - No20250321003", strip the No... part for invoiceName
            name_clean = re.sub(r'\s*[-–—]\s*No\.?\s*[A-Z0-9]+$', '', name, flags=re.I).strip()
            if name_clean:
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

        # Date: Ngày 18 tháng 12 năm 2025
        # Date: Ngày (date) 20 tháng (month) 10 năm (year) 2025
        m = re.search(r"Ngày.*?(\d{1,2}).*?tháng.*?(\d{1,2}).*?năm.*?(\d{4})", line, re.I)
        if m and not invoice.invoiceDate:
            invoice.invoiceDate = f"{m.group(1).zfill(2)}/{m.group(2).zfill(2)}/{m.group(3)}"
        
        # English date patterns: Date: 2025/12/1, Date: 2025-12-01
        if not invoice.invoiceDate:
            m = re.search(r"[Dd]ate[:\s]+(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})", line)
            if m:
                invoice.invoiceDate = f"{m.group(3).zfill(2)}/{m.group(2).zfill(2)}/{m.group(1)}"
        
        # English date: DEC. 01, 2025 or Dec 1, 2025
        if not invoice.invoiceDate:
            months = {'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04', 'may': '05', 'jun': '06',
                      'jul': '07', 'aug': '08', 'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12'}
            m = re.search(r"([A-Za-z]{3})\.?\s*(\d{1,2}),?\s*(\d{4})", line)
            if m:
                month_abbr = m.group(1).lower()[:3]
                if month_abbr in months:
                    invoice.invoiceDate = f"{m.group(2).zfill(2)}/{months[month_abbr]}/{m.group(3)}"


        # Form No (mẫu số) - ít dùng trong hóa đơn điện tử mới
        # Skip lines containing "hóa đơn bị hủy" - these reference cancelled invoices
        if "mẫu số" in low and "hóa đơn bị hủy" not in low and "hoá đơn bị huỷ" not in low:
            m = re.search(r":\s*(\S+)", line)
            if m:
                invoice.invoiceFormNo = m.group(1)

        # Serial - ĐÂY LÀ TRƯỜNG QUAN TRỌNG
        # Pattern: Ký hiệu (Serial No): 1C25TTD, Kí hiệu(Serial): 1C25THO
        # Pattern variations: "Ký hiệu: 1C24THO", "Ký hiệu 1C24THO", "Ký hiệu:1C24THO"
        # BỎ QUA dòng "Thay thế cho Hóa đơn..." và "Hóa đơn bị hủy" vì đây không phải serial chính
        if (("ký hiệu" in low or "kí hiệu" in low or "serial" in low) and 
            not serial_parsed and 
            "hóa đơn bị hủy" not in low and "hoá đơn bị huỷ" not in low):
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
                # Handle markdown formatting: **00000438**
                m = re.search(r"(?:Số|So|No\.?)[^:]*[:\s]+\*{0,2}(\d+)\*{0,2}", clean_line, re.I)
                if m:
                    invoice.invoiceID = m.group(1)
            elif ("invoice no" in low or "invoice number" in low) and "stt" not in low:
                m = re.search(r":\s*\*{0,2}\s*([\d]+)\*{0,2}", line)
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


def parse_seller(lines: List[str], invoice: Invoice):
    pending_field = None
    first_line_checked = False

    for line in lines:
        clean = line.strip().replace("**", "")
        low = clean.lower()
        matched = False
        
        # ===== ĐẶC BIỆT: Dòng đầu tiên có thể là tên công ty (không có label) =====
        if not first_line_checked:
            first_line_checked = True
            is_keyword = any(k in low for k in ["hóa đơn", "phiếu", "mẫu số", "ký hiệu", "liên", "date", "ngày", "số:", "no:",
                                                    "invoice", "from:", "from :", "to:", "to :"])
            is_header_label = any(k in low for k in ["information", "寄货人", "资料", "收货人", "shipper", "consignee",
                                                       "shippes", "country of", "seller", "exporter"])
            # Skip table lines (|...|), markdown headers still present, and overly long lines
            is_table_line = clean.startswith("|")
            is_too_long = len(clean) > 80
            if (not is_keyword and not is_header_label and not is_table_line and not is_too_long
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
                    if email:
                        invoice.sellerEmail = email
                    matched = True
                    if email:
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
                    matched = True
                    break

                # ===== NORMAL FIELD =====
                if ":" in clean:
                    value = clean.split(":", 1)[-1].strip()
                    if value:
                        setattr(invoice, field, value)
                    else:
                        pending_field = field
                else:
                    # No colon: this is a standalone label (e.g. "Address" on its own line)
                    # The value will be on the next line
                    pending_field = field

                matched = True
                break

        # ===== CONTINUATION LINE =====
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
                    setattr(invoice, pending_field, current_val.rstrip(', ').rstrip(',') + ", " + clean)
                else:
                    setattr(invoice, pending_field, clean)
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
                if not re.fullmatch(r"\d{1,3}-\d{9,11}", clean):
                    invoice.sellerBankAccountNumber = clean.replace(".", "")
            # Bank name without label
            elif "ngân hàng" in low and not invoice.sellerBank:
                # Extract bank name
                m = re.search(r"ngân hàng\s+(.+)", clean, re.I)
                if m:
                    invoice.sellerBank = m.group(1).strip()
                else:
                    invoice.sellerBank = clean


def parse_buyer(block: List[str], invoice: Invoice):
    pending_field = None  # Track which field expects continuation on next line
    
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
                    if value and len(value) > 3:
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
            if ":" not in clean:
                continue
                
            value = clean.split(":", 1)[-1].strip()
            # Skip if value contains CCCD marker or is empty/junk
            if value and "cccd" not in value.lower() and "(citizen id" not in value.lower():
                if len(value) > 3 and not re.match(r'^[\*\s]+$', value):
                    invoice.buyerName = value
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
            
        # ADDRESS (including "Nhập tại kho" for internal transfer slips, "adresse" for French labels)
        elif "địa chỉ" in low or "address" in low or "nhập tại kho" in low or "adresse" in low:
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
                        setattr(invoice, pending_field, current_val + " " + clean)
                else:
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
            elif re.fullmatch(r"[\d\.\-]{9,20}", clean):
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
                    if first_num.isdigit():
                        invoice.preTaxPrice = float(first_num)
                except:
                    pass

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
                    # Extract numbers from this cell
                    cell_nums = re.findall(r'[\d\.\,]+', cell)
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
        elif re.search(r'VND|VNĐ|đồng', block_text, re.I):
            invoice.currency = "VND"

    # FALLBACK: If totalAmount is still missing or suspiciously small,
    # find the largest number in the table block as totalAmount
    # User insight: "The largest number in the table will definitely be totalAmount"
    
    all_numbers = []
    for line in block:
        low = line.lower()
        # EXCLUDE bank/account lines, phone numbers, postal codes
        if any(k in low for k in ["beneficiary", "account", "bank", "swift",
                                   "iban", "sort-code", "routing",
                                   "tel", "phone", "fax", "postal", "zip"]):
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
        if not invoice.totalAmount:
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

        if scores:
            # Pick the currency with the highest confidence score
            invoice.currency = max(scores, key=lambda c: scores[c])
        # If no signal found → leave currency as None (do not force VND)
    
    # ===== INVOICE ID =====
    print(f"DEBUG: Checking InvoiceID. Current val: '{invoice.invoiceID}'")
    if not invoice.invoiceID:
        # Pattern 0: BIÊN BẢN HỦY HÓA ĐƠN format - "Hóa đơn bị hủy: ... số 00000324"
        m = re.search(r'(?:hóa đơn bị hủy|hoá đơn bị huỷ)[^,\n]*,\s*(?:ký hiệu\s+)?[^,]+,\s*số\s+(\d{5,})', raw_text, re.I)
        if m:
            invoice.invoiceID = m.group(1)
            print(f"DEBUG: Found InvoiceID via BIÊN BẢN HỦY format: '{m.group(1)}'")
        
        # Pattern 0.5: COMMERCIAL INVOICE - No20250321003 or INVOICE - No.12345
        if not invoice.invoiceID:
            m = re.search(r'INVOICE\s*[-–—]\s*No\.?\s*([A-Z0-9]+)', raw_text, re.I)
            if m:
                invoice.invoiceID = m.group(1)
                print(f"DEBUG: Found InvoiceID via COMMERCIAL INVOICE format: '{m.group(1)}'")
        
        # Pattern 1: Explicit line start "Số: 3" or similar (but NOT "Số biên bản")
        if not invoice.invoiceID:
            m = re.search(r'(?:^|\n)(?:Số|So|No\.?)(?!\s*biên bản)\s*(?:\([^)]*\))?\s*[:\s]+\**(\d+)\**', raw_text, re.I)
            if m:
                val = m.group(1).lstrip('0') or m.group(1)
                print(f"DEBUG: Found InvoiceID via Regex 1 (Simple): '{val}'")
                invoice.invoiceID = val
            else:
                # Pattern 2: Old complex pattern fallback (but NOT "Số biên bản")
                m = re.search(r'(?<!biên bản\s)Số\s*(?:\([^)]*\))?\s*[:\s]*\**(\d+)\**', raw_text, re.I)
                if m:
                    val = m.group(1).lstrip('0') or m.group(1)
                    invoice.invoiceID = val
                
                # Pattern 3: Invoice No: 721 hoặc Invoice No.: 721
                if not invoice.invoiceID:
                     m = re.search(r'Invoice\s*No\.?[:\s]*(\d+)', raw_text, re.I)
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
                                      'export']
                if not any(before.rstrip().endswith(ep) for ep in _excluded_prefixes):
                    invoice.invoiceID = m.group(1)
        
        # Pattern 7: Invoice #: 67928 or Invoice#: 67928
        if not invoice.invoiceID:
            m = re.search(r'Invoice\s*#[:\s]*(\d+)', raw_text, re.I)
            if m:
                invoice.invoiceID = m.group(1)
    
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
                print(f"DEBUG: Found FormNo via BIÊN BẢN HỦY format: Serial='{m.group(1)}', FormNo='{m.group(2)}'")
        
        # Pattern 1: Ký hiệu: 1C25THO hoặc Kí hiệu (Serial No): 1C25TTD hoặc Ký hiệu (Series): 1C25TLT
        # Skip lines with "thay thế" (replacement invoice references)
        if not invoice.invoiceFormNo:
            lines = raw_text.split('\\n')  # Handle escaped newlines
            for line in lines:
                low = line.lower()
                if ('ký hiệu' in low or 'kí hiệu' in low) and 'thay thế' not in low and 'hóa đơn bị hủy' not in low:
                    # Extract value after colon - support Series/Serial keywords
                    m = re.search(r'(?:ký hiệu|kí hiệu)\s*(?:\([^)]*\))?\s*[:\s]+([A-Z0-9]+)', line, re.I)
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
        
        # Pattern 12: English - "TOTAL: GBP 32499" or "TOTAL: 32,499" (standalone TOTAL line)
        if not invoice.totalAmount:
            m = re.search(r'\bTOTAL\b[:\s]*(?:[A-Z]{3}\s*)?([\d\.\,]+)', raw_text, re.I)
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
        
        # Pattern 14: "| Invoice Total ... | ... | USD | $25475.00 |" (4+ column pipe table)
        if not invoice.totalAmount:
            m = re.search(r'Invoice\s+Total[^|]*(?:\|[^|]*){2,}\|\s*\$?([\d\,\.]+)', raw_text, re.I)
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
                if max_val > 0:
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
        # Pattern 1: Standalone "INVOICE" or "HÓA ĐƠN GTGT"
        m = re.search(r'^(INVOICE|HÓA ĐƠN\s*(?:GTGT|GIÁ TRỊ GIA TĂNG)?)\s*$', raw_text, re.I | re.MULTILINE)
        if m:
            invoice.invoiceName = m.group(1).strip()
        
        # Pattern 2: "COMMERCIAL INVOICE", "PROFORMA INVOICE", "TAX INVOICE"
        if not invoice.invoiceName:
            m = re.search(r'(COMMERCIAL\s+INVOICE|PROFORMA\s+INVOICE|TAX\s+INVOICE)', raw_text, re.I)
            if m:
                invoice.invoiceName = m.group(1).strip().upper()
    
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
        buyer_keywords = ["người mua", "tên người mua", "buyer", "the buyer"]
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
            r'[Dd]iscount\s*:[\s]*([\d\.\,]+)',
            # Bold label format: "**Discount** -$8.75" or "Discount $8.75"
            r'\b[Dd]iscount\b[*]*\s*[-]?\s*\$?\s*([\d,\.]+)',
        ]
        for pattern in patterns:
            m = re.search(pattern, raw_text)
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
                    invoice.paymentMethod = val
                    break
    
    # ===== INVOICE TOTAL IN WORD (fallback) =====
    if not invoice.invoiceTotalInWord:
        # Pattern 1: "Bằng chữ:" hoặc "Số tiền bằng chữ:"
        patterns = [
            r'[Bb]ằng\s*chữ[^:]*:\s*([^\n]+)',
            r'[Ss]ố\s*tiền\s*(?:viết\s*)?bằng\s*chữ[^:]*:\s*([^\n]+)',
            r'[Ii]n\s*words?[^:]*:\s*([^\n]+)',
            # EN: "SAY USD TWO THOUSAND SIX HUNDRED FOURTEEN ONLY" or "SAY: US DOLLARS..."
            r'\bSAY[:\s*]+\s*((?:USD?|EUR|GBP|CNY)?\s*[A-Z][A-Z\s]+(?:ONLY|DOLLARS?|EUROS?|POUNDS?))',
            # EN: "Total in Words: One Hundred..."
            r'[Tt]otal\s+[Ii]n\s+[Ww]ords?\s*[:\|]\s*([^\n]+)',
        ]
        for pattern in patterns:
            m = re.search(pattern, raw_text)
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
    en_markers = ["commercial invoice", "proforma invoice", "invoice",
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
        if low.strip('- ') in _exact_labels and lines:
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
    _sub_labels = {'company name', 'full name', 'contact person', 'name', 'company'}
    
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
        _sub_labels = {'company name', 'full name', 'contact person', 'name', 'company'}
        start_idx = 0
        while start_idx < len(lines) and lines[start_idx].lower().strip('- ') in _sub_labels:
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
    
    # ===== SELLER =====
    # Generic skip words for extracted names
    _skip_names = {'name', 'address', 'phone', 'email', 'from', 'to', 'date',
                   'invoice', 'commercial invoice', 'proforma invoice',
                   'exporter', 'shipper', 'consignee', 'importer',
                   'ship to', 'ship from', 'bill to', 'bill from',
                   'sold to', 'delivery details', 'customer\'s details'}
    
    # ===== SELLER =====
    seller_patterns = [
        # Case 4 style: regex must skip the | COMMERCIAL INVOICE | part
        r'THE SELLER\s*:\s*\|\s*([^|\n]+)',
        r'(?:THE\s+SELLER|SHIP\s+FROM|BILL\s+FROM|EXPORTER)\s*[:\n]',
        r'(?:^|\n)\s*(?:Seller|Exporter\s+Details|Exporter\s+Name|Sender/Exporter|Sender\s+Name|Shipper/Exporter|Vendor/Exporter)\s*[:\n]',
        r'Shipper\s*[:\n]',
    ]
    for pat in seller_patterns:
        if not invoice.sellerName:
            m = re.search(pat, clean_text, re.I)
            if m:
                if m.groups():
                    val = m.group(1).strip()
                    if val and val.lower().strip() not in _skip_names:
                        invoice.sellerName = val
                else:
                    name, addr = _extract_after_label(clean_text, pat)
                    if name and len(name) > 2:
                        if name.lower().strip() not in _skip_names and not name.startswith('|'):
                            invoice.sellerName = name
                            if addr and not invoice.sellerAddress:
                                invoice.sellerAddress = addr
    
    # Fallback: company name before INVOICE header (e.g., "MICRODYN-NADIR..." then "INVOICE")
    if not invoice.sellerName:
        m = re.search(r'^([A-Z][A-Za-z \t&.,\'-]+(?:CO\.?,?[ \t]*LTD|INC|CORP|PTE[ \t]+LTD|LLC|COMPANY|GMBH|SAS|S\.A\.?)[. \t]*)', clean_text, re.M)
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
    
    # Fallback 3: "FROM :\n Full Name : Xxx" pattern
    if not invoice.sellerName:
        m = re.search(r'\bFROM\s*:\s*\n(?:.*?Full\s+Name\s*:\s*)?(.+)', clean_text, re.I)
        if m:
            val = m.group(1).strip().strip('*')
            if val and len(val) > 2 and val.lower().strip() not in _skip_names:
                invoice.sellerName = val
    
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
        m = re.search(r'(?:SELLER|SHIPPER).*?ADDRESS\s*:.*?\n\|\s*([^|]+)', clean_text, re.I | re.S)
        if not m:
             # Case 4 specific: table format with rows:
             # | THE SELLER: | COMMERCIAL INVOICE |
             # |------------|---------------------|
             # | COMPANY NAME | |
             # | ADDRESS ROW | |
             # Capture group 1 = company name row, group 2 = address row after separator
             m = re.search(
                 r'THE SELLER.*?\n\|[-\s|]+\|\s*\n'   # skip separator row
                 r'\|\s*([^|\n]+?)\s*\|[^\n]*\n'       # group 1 = company name row
                 r'\|\s*([^|\n]+)',                     # group 2 = address row
                 clean_text, re.I | re.S
             )
        if m:
            # group(1) is company name, group(2) is address
            # Only use group(2) (address row) to avoid overwriting with company name
            addr_val = m.group(2).strip() if m.lastindex >= 2 else m.group(m.lastindex).strip()
            # Reject separator-looking values (all dashes)
            if addr_val and len(addr_val) > 5 and not re.fullmatch(r'[-\s|]+', addr_val):
                # Also update sellerName if not set yet and group 1 has a plausible company name
                if m.lastindex >= 2:
                    name_cand = m.group(1).strip()
                    if name_cand and len(name_cand) > 3 and not invoice.sellerName:
                        invoice.sellerName = name_cand
                invoice.sellerAddress = addr_val
    
    # ===== BUYER =====
    buyer_patterns = [
        # Case 4 style: THE BUYER: | INV. NO.: |
        r'THE BUYER\s*:\s*\|\s*([^|\n]+)',
        r'(?:THE\s+BUYER|CONSIGNED\s+TO|SOLD\s+TO|BILL\s+TO)\s*[:\n]',
        # Invoice To has buyer name — check BEFORE Ship To (which often has address only)
        r'(?:Invoice\s+To|Importer\s+Details|Importer\s+Name|Consignee\s+Name)\s*[:\n]',
        # NOTIFY PARTY is the actual buyer when CONSIGNEE is a bank order
        r'(?:NOTIFY\s+PARTY)\s*[:\n]',
        r'(?:CONSIGNEE|SHIP\s+TO|IMPORTER)\s*[:\n]',
        r'(?:Recipient/Ship\s+To)\s*[:\n]',
        r"CONSIGNEE'S\s+(?:MEMBER|COMPANY)\s*[:\n]",
    ]
    _buyer_skip = _skip_names | {'same as consignee', '(if other than recipient)',
                                 'customer po no.', 'customer po no', 'reference no.',
                                 'permanent', 'account number', 'account payable',
                                 'the order of'}
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
                    if val and val.lower().strip() not in _buyer_skip and not _invoice_label_re.search(val):
                        invoice.buyerName = val
                else:
                    name, addr = _extract_after_label(clean_text, pat)
                    if name and len(name) > 2:
                        if (name.lower().strip() not in _buyer_skip
                                and not name.startswith('|')
                                and not name.startswith('PO No')
                                and 'to the order of' not in name.lower()):
                            invoice.buyerName = name
                            # Strip label prefixes like "Customer : " from buyer name
                            _name_labels = re.match(r'^(?:Customer|Company|Name|Client)\s*:\s*', invoice.buyerName, re.I)
                            if _name_labels:
                                invoice.buyerName = invoice.buyerName[_name_labels.end():].strip()
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
                                phone_m = re.search(r'(?:Mobile|Phone|Tel)\s*:\s*([\+\d][\d \-\(\)\.]{6,})', after_label, re.I)
                                if phone_m:
                                    invoice.buyerPhoneNumber = phone_m.group(1).strip()
    
    # Buyer fallback: "To:\nCOMPANY NAME" (only if name looks like company)
    if not invoice.buyerName:
        m = re.search(r'\bTo\s*:\s*\n\s*(.+)', clean_text)
        if m:
            val = m.group(1).strip().strip('*')
            # Only accept if it looks like a company name (uppercase or has CO./LTD)
            if val and len(val) > 3 and (val[0].isupper() or 'co.' in val.lower()):
                if val.lower().strip() not in _buyer_skip:
                    invoice.buyerName = val
    
    # Buyer fallback: "For Account and Risk of : XXX" or "For Account of: XXX"
    if not invoice.buyerName:
        m = re.search(r'For\s+Account\s+(?:and\s+Risk\s+)?of\s*:\s*(.+)', clean_text, re.I)
        if m:
            val = m.group(1).strip().strip('*')
            if val and len(val) > 2:
                invoice.buyerName = val
    
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
    
    # Buyer fallback: second **BoldName** block after seller
    # Pattern: **SellerName**\nAddress\nPhone\n\n**BuyerName**\nAddress\nPhone
    if not invoice.buyerName and invoice.sellerName:
        bold_blocks = list(re.finditer(r'\*\*([^*]+)\*\*', text))
        _skip_labels = {'terms of sale', 'terms of payment', 'terms', 'notes',
                        'invoice number', 'date', 'due', 'description',
                        'subtotal', 'amount due', 'bank', 'payment'}
        seller_found = False
        for bm in bold_blocks:
            val = bm.group(1).strip()
            low_val = val.lower()
            if low_val in _skip_labels or any(k in low_val for k in _skip_labels):
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
            r'(?:INV\.?\s*NO\.?|Invoice\s*No\.?|Invoice\s*#|Invoice\s*Number)[:\s]*[#]?\s*([A-Za-z0-9][\w\-/]+)',
            r'(?:INVOICE\s*#)[:\s]*([\w\-/]+)',
            r'(?:Export\s+Invoice\s+No)[^|]*?(\d{3,})',
            r'(?:^|\n)\s*#(\d{4,})\s*(?:\n|$)',  # "#000001" pattern
            # "Invoice Number:\n\nINV-2024-0892" (bold label, value on next line)
            r'Invoice\s*Number\s*[:]*\s*\n\s*\n?\s*([A-Za-z0-9][\w\-/]+)',
            # "EXPORT REFERENCES (i.e., order no., invoice no.)\n2786"
            r'EXPORT\s+REFERENCES[^\n]*\n\s*([A-Za-z0-9][\w\-/]+)',
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
                    clean_val = val.replace('/', '').replace('-', '').replace('.', '')
                    if (val.lower() not in _bad_ids
                            and not re.fullmatch(r'[A-Za-z]+', clean_val)
                            and not re.fullmatch(r'[A-Za-z]+/[A-Za-z]+', val)):
                        invoice.invoiceID = val
                        break
    
    # ===== INVOICE DATE =====
    if not invoice.invoiceDate:
        months = {'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04', 'may': '05', 'jun': '06',
                  'jul': '07', 'aug': '08', 'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12',
                  'january': '01', 'february': '02', 'march': '03', 'april': '04',
                  'june': '06', 'july': '07', 'august': '08', 'september': '09',
                  'october': '10', 'november': '11', 'december': '12'}
        
        date_patterns = [
            # "Date: 20-Nov-2017" or "INV. DATE: APR 4TH,2025"
            (r'(?:INV\.?\s*)?DATE\s*[:\s]+(\d{1,2})[\s\-/](\w{3,9})[\s\-/,]*(\d{2,4})', 'dmy_name'),
            # "Date: October 26, 2028" or "DEC 14th 2021" or "Date of Shipment:\n04/24/2024"
            (r'(?:INV\.?\s*)?DATE[^:]*[:\s]+(\w{3,9})\.?\s*(\d{1,2})(?:st|nd|rd|th)?,?\s*(\d{4})', 'mdy_name'),
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
                    if fmt == 'dmy_name':
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
        if 'USD' in clean_text or '$' in clean_text:
            invoice.currency = 'USD'
    
    # ===== TOTAL AMOUNT (EN patterns) =====
    if not invoice.totalAmount:
        total_patterns = [
            r'EXW[:\s].*?([\d,\.]+)\s*$',
            r'(?:Grand\s+Total|Total\s+Invoice\s*Value|Total\s+Net\s+Value)[:\s]*\$?([\d,\.]+)',
            # "Amount Due (USD) | $2,280.00" or "Balance Due: $500"
            r'(?:Amount|Balance)\s+Due[\s|()\w]*[$£€]\s*([\d,\.]+)',
            # "Total Amount\n$23,275" or "Total Amount: $23,275"
            r'Total\s+Amount[:\s]*\n\s*[$£€]?\s?([\d,\.]+)',
            r'Total\s+Amount\s*[:\s]+[$£€]?\s?([\d,\.]+)',
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
                invoice.taxPercent = pct_val
            if tax_val and tax_val > 0 and not invoice.taxAmount:
                invoice.taxAmount = tax_val

    if not invoice.taxPercent:
        # "Tax (8%): $188" or "VAT: 14%" or "Tax Rate: 10%" or "Taxes (10%) $40"
        # Also handle pipe-table: "| VAT | 14% |"
        m = re.search(r'(?:Tax(?:es)?|VAT|Sales\s+Tax)(?:\s+Rate)?[\s|]*\(?\s*(\d+(?:\.\d+)?)\s*%', clean_text, re.I)
        if m:
            try:
                invoice.taxPercent = float(m.group(1))
            except ValueError:
                pass
    
    if not invoice.preTaxPrice:
        # "Subtotal: $2,350" or "Sub Total: 44,780" or "Invoice Subtotal: GBP 29,545"
        # Tighten: use separator to allow pipe tables like "| Subtotal | $21,775 |"
        m = re.search(r'(?:Sub\s*total|Invoice\s+Subtotal|Total\s+HT|Total\s+Ex\s+Tax)[:\s|]{1,10}[A-Za-z]{0,3}\s?[$£€]?\s?([\d,\.]+)', clean_text, re.I)
        if m:
            val = safe_parse_float(m.group(1))
            if val and val > 0:
                invoice.preTaxPrice = val
    
    if not invoice.taxAmount:
        # "Tax Due: $3.00" or "Sales Tax: GBP 2,954" or "Tax (10%): $40" or "Export Tax: $650"
        m = re.search(r'(?:Tax\s+Due|Sales\s+Tax|Export\s+Tax|Import\s+Tax|Total\s+TVA|(?:Tax(?:es)?|VAT)\s*\([^)]*\))[:\s|]{1,10}[A-Za-z]{0,3}\s?[$£€]?\s?([\d,\.]+)', clean_text, re.I)
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
        invoice.taxAmount = round(invoice.preTaxPrice * invoice.taxPercent / 100, 2)

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
        seller_found = False
        for bm in bold_blocks:
            val = bm.group(1).strip()
            low_val = val.lower()
            if low_val in _buyer_skip_labels or any(k in low_val for k in _buyer_skip_labels):
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
                    if len(bname) > 2 and bname.lower() != invoice.sellerName.lower():
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
        setattr(invoice, field, cleaned if cleaned else None)
    
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
    ]
    # Also filter items where productName is just a currency code
    CURRENCY_CODES = {"usd", "eur", "gbp", "vnd", "jpy", "cny"}
    
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
            
            # Skip if garbage
            if has_no_data or has_garbage_keyword or is_currency:
                # print(f"DEBUG: Skipping garbage item: {item.productName}")
                continue
            
            cleaned_items.append(item)
        
        invoice.itemList = cleaned_items
    

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

    # FINAL ITEM-SUM FALLBACK: if totalAmount is still missing, use sum of item amounts
    if not invoice.totalAmount and invoice.itemList:
        _item_total = sum(it.amount or 0 for it in invoice.itemList)
        if _item_total > 0:
            invoice.totalAmount = _item_total

    # Reverse fallback: if we have totalAmount but no invoiceTotalInWord, generate it
    if invoice.totalAmount and not invoice.invoiceTotalInWord:
        if (invoice.currency or "").upper() == "VND":
            invoice.invoiceTotalInWord = number_to_vietnamese_words(invoice.totalAmount)
        else:
            invoice.invoiceTotalInWord = number_to_english_words(invoice.totalAmount)

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

    return invoice
