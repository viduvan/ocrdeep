import re
from typing import List, Dict
from src.schemas.invoice import Invoice
from src.schemas.invoice_item import InvoiceItem
from src.parsers.invoice_table_parser import parse_items_from_table
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


SELLER_LABEL_KEYS = {
    "sellerName": ["tên đơn vị bán", "đơn vị bán", "đơn vị bán hàng", "comname", "dơn vị bán hàng", "the seller",
                   "bên a (bên bán)", "bên bán", "bên a",
                   "shipper", "beneficiary"],  # EN: SHIPPER/BENEFICIARY = Seller
    "sellerTaxCode": ["mã số thuế", "tax code", "mst", "vat:"],  # Added MST abbreviation & VAT
    "sellerAddress": ["địa chỉ", "address"],
    "sellerPhoneNumber": ["điện thoại", "tel", "số điện thoại"],
    "sellerBankAccountNumber": ["số tài khoản", "bankno", "account no", "ac no", "stk",
                                "beneficiary's account"],  # EN: BENEFICIARY'S ACCOUNT
    "sellerBank": ["ngân hàng", "bankname", "tại ngân hàng", "bank:",
                   "beneficiary's bank"],  # EN: BENEFICIARY'S BANK
    "sellerEmail": ["email"],
}

BUYER_LABEL_KEYS = {
    "buyerName": ["tên đơn vị mua", "đơn vị mua", "buyer", "cusname", "tên đơn vị", "company's name", "the buyer", "đơn vị (co. name)", "co. name",
                  "bên b (bên mua)", "bên mua", "bên b",
                  "consignee"],  # EN: CONSIGNEE = Buyer
    "buyerTaxCode": ["mã số thuế", "tax code", "mst"],
    "buyerAddress": ["địa chỉ", "address"],
    "buyerEmail": ["email"],
    "buyerPhoneNumber": ["điện thoại", "tel", "số điện thoại"],
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

        # ===== TOTAL (High Priority) =====
        # Check this BEFORE Table block to ensure summary rows with pipes (e.g. |Tổng tiền:|) switch to Total
        if seen_table and any(k in l for k in [
            "tổng cộng", "tổng tiền", "số tiền viết bằng chữ", "cộng tiền hàng", "total amount", "khách hàng đã thanh toán", "thuế suất",
            "total unit", "total value", "total qty", "grand total"
        ]):
            current = "total"
            
        # ===== TABLE (Identify by HTML or Markdown) =====
        elif "<table>" in l or l.startswith("|"): # Changed to elif
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

        # ===== HEADER (CHỈ KHI GẶP HÓA ĐƠN hoặc PHIẾU) =====
        # Note: Title may be split across lines like "# HÓA ĐƠN\nGIÁ TRỊ GIA TĂNG"
        elif any(k in l for k in [
            "hóa đơn",                  # Added: partial match for multi-line titles
            "phiếu xuất kho",            # Added: Internal transfer slips
            "phiếu nhập kho",            # Added: Internal receipt slips
            "phiếu bán hàng",             # Added: Sales slips
            "biên bản hủy",               # Added: Invoice cancellation documents
            "biên bản",                   # Added: General documents
            "vat invoice",
            "commercial invoice",         # EN: COMMERCIAL INVOICE
            "proforma invoice",           # EN: PROFORMA INVOICE
            "tax invoice",                # EN: TAX INVOICE
            "kí hiệu",
            "ký hiệu",
            "mẫu số",
            "invoice no",
            "serial no",
        ]):
            current = "header"
            seen_header = True

        # ===== SELLER (sau header - format header-first) =====
        # Khi thấy "đơn vị bán hàng" sau header, chuyển về seller block
        # HOẶC nếu đang ở Header mà thấy MST/Địa chỉ/SĐT (dấu hiệu seller info) thì chuyển sang Seller
        # Support English: "THE Seller:", "SHIPPER" and Vietnamese: "BÊN A (Bên bán)"
        elif (any(k in l for k in ["đơn vị bán hàng", "seller:", "the seller:", "bên a (bên bán)", "bên bán)", "bên a:",
                                    "shipper", "寄货人"]) or 
              (current == "header" and any(k in l for k in ["mã số thuế", "địa chỉ", "điện thoại", "tax code", "address", "website"]))) \
              and not seen_buyer:
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
            "nhập tại kho",        # Added: For internal transfer slips
            "bên b (bên mua)",     # Added: For BIÊN BẢN HỦY HÓA ĐƠN
            "bên mua)",            # Added: Partial match
            "bên b:",              # Added: For BIÊN BẢN
            "consignee",           # EN: CONSIGNEE = Buyer
            "收货人",               # CN: 收货人 = Consignee
        ]):
            current = "buyer"
            seen_buyer = True

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
            elif "invoice no" in low and "stt" not in low:
                m = re.search(r":\s*\*{0,2}([\d]+)\*{0,2}", line)
                if m:
                    invoice.invoiceID = m.group(1)

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
        # Pattern: "CÔNG TY CỔ PHẦN VẬT LIỆU HOME" ở dòng đầu
        if not first_line_checked:
            first_line_checked = True
            # Nếu dòng đầu KHÔNG chứa keywords loại trừ và không có dấu ":" → đây là tên seller (fallback)
            # Relax check: "Chau Huu Materials" doesn't have "CÔNG TY"
            is_keyword = any(k in low for k in ["hóa đơn", "phiếu", "mẫu số", "ký hiệu", "liên", "date", "ngày", "số:", "no:"])
            # Also exclude section header labels (SHIPPER INFORMATION, 寄货人资料 etc.)
            is_header_label = any(k in low for k in ["information", "寄货人", "资料", "收货人", "shipper", "consignee",
                                                       "shippes", "country of"])
            if not is_keyword and not is_header_label and ":" not in clean and len(clean) > 3 and not invoice.sellerName:
                invoice.sellerName = clean
                # Mark next unlabeled line as potential address
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
                    
                    # FIX: Extract phone AFTER the "điện thoại" or "tel" keyword to avoid MST confusion
                    # Pattern: "Mã số thuế: 0108921542 Số điện thoại: 0935868885"
                    phone_match = re.search(r"(?:số điện thoại|điện thoại|tel)[:\s]*(\d{9,11})", temp_clean, re.I)
                    if phone_match:
                        invoice.sellerPhoneNumber = phone_match.group(1)
                    else:
                        # Fallback: Try to get any 10-digit number starting with 0
                        m_phone = re.search(r"(?:^|\D)(0\d{9,10})(?:\D|$)", temp_clean)
                        if m_phone:
                            # Make sure it's not the same as tax code
                            if m_phone.group(1) != invoice.sellerTaxCode:
                                invoice.sellerPhoneNumber = m_phone.group(1)
                        else:
                            # Try international format: (84 - 24) 3 747 6666 or (84-24) 37476666
                            m_intl = re.search(r"\(?\d{2,3}\s*[-\s]\s*\d{2,3}\)?\s*[\d\s]+", temp_clean)
                            if m_intl:
                                # Clean up spaces and format
                                phone_val = m_intl.group(0).strip()
                                if len(phone_val.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")) >= 8:
                                    invoice.sellerPhoneNumber = phone_val
                            else:
                                phone = extract_phone(temp_clean)
                                if phone and phone != invoice.sellerTaxCode:
                                    invoice.sellerPhoneNumber = phone
                    
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
                        invoice.sellerName = value
                        matched = True
                        break
                    elif value:
                        pending_field = field
                    matched = True
                    break

                # ===== NORMAL FIELD =====
                value = clean.split(":", 1)[-1].strip()
                if value:
                    setattr(invoice, field, value)
                else:
                    pending_field = field

                matched = True
                break

        # ===== CONTINUATION LINE =====
        if not matched and pending_field and clean:
            setattr(invoice, pending_field, clean)
            pending_field = None

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
            "company name",     # EN: COMPANY NAME
        ]):
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
            
            # For CONSIGNEE/COMPANY NAME label: value is likely on the NEXT line
            if "company name" in low or "consignee" in low:
                # Check if there's a value after colon
                if ":" in clean:
                    value = clean.split(":", 1)[-1].strip()
                    if value and len(value) > 3:
                        invoice.buyerName = value
                    else:
                        pending_field = "buyerName"
                else:
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

        #TAX CODE - support MST abbreviation
        elif "mã số thuế" in low or "tax code" in low or "mst" in low:
            m = re.search(r"(\d{10,14}(-\d+)?)", clean)
            if m:
                invoice.buyerTaxCode = m.group(1)
            pending_field = None
            matched = True

        # ADDRESS (including "Nhập tại kho" for internal transfer slips)
        elif "địa chỉ" in low or "address" in low or "nhập tại kho" in low:
            value = clean.split(":", 1)[-1].strip() if ":" in clean else ""
            if value:
                invoice.buyerAddress = value
            else:
                # Address is on the next line(s)
                pending_field = "buyerAddress"
            matched = True

        # PHONE (FIX TEL + FAX)
        elif "điện thoại" in low or "tel" in low:
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
            if is_section:
                pending_field = None
            else:
                current_val = getattr(invoice, pending_field, None)
                if current_val:
                    setattr(invoice, pending_field, current_val + " " + clean)
                else:
                    setattr(invoice, pending_field, clean)
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
                 from src.parsers.invoice_table_parser import safe_parse_float
                 val = safe_parse_float(nums[-1])
                 if val and val > 1000:
                     invoice.totalAmount = val
        
        # Format Viettel: |Cộng tiền hàng hóa, dịch vụ:||||||14.027.784|1.122.216|15.150.000|
        # Last number is totalAmount (thành tiền sau thuế)
        # Format Viettel: |Cộng tiền hàng hóa, dịch vụ:||||||14.027.784|1.122.216|15.150.000|
        # Last number is totalAmount (thành tiền sau thuế)
        if ("cộng tiền hàng" in l or "cộng tiền dịch vụ" in l or "tổng tiền" in l or "tổng cộng" in l):
            nums = re.findall(r'[\d\.\,]+', line)
            if nums:
                 from src.parsers.invoice_table_parser import safe_parse_float
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

        # Tổng cộng tiền thanh toán (Total payment) - multiple patterns
        # Pattern 1: "Tổng cộng tiền thanh toán:" or "Total payment:"
        # Pattern 2: Markdown table row "|Tổng cộng:|||...|229.997|" - last number is totalAmount
        
        # FIX: Allow overwriting totalAmount because "Total Payment" is authoritative (Post-Tax)
        # Added "tổng tiền", "cộng tiền" for VETC and Viettel cases
        if "tổng cộng" in l or "total payment" in l or "tổng tiền" in l or "cộng tiền" in l:
            # Check if markdown table row
            if "|" in line:
                nums = re.findall(r'[\d\.\,]+', line)
                if nums:
                    # Parse last number as totalAmount (cộng tiền thanh toán)
                    # Use safe_parse_float for Vietnamese format handling
                    from src.parsers.invoice_table_parser import safe_parse_float
                    
                    parsed_nums = [safe_parse_float(n) for n in nums]
                    parsed_nums = [n for n in parsed_nums if n is not None]
                    
                    if parsed_nums:
                        val = parsed_nums[-1]
                        if val and val > 0:
                            invoice.totalAmount = val
                            
                        # Try to extract Tax and PreTax if 3 numbers exist (PreTax, Tax, Total)
                        if len(parsed_nums) >= 3:
                            pre_tax = parsed_nums[-2] # Wait, usually last is Total, 2nd last is Tax?
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
                    from src.parsers.invoice_table_parser import safe_parse_float
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
        if (any(k in l for k in ["thuế suất", "vat rate", "chịu thuế", "thuế gtgt"]) and "%" in l):
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
        
        # Tiền thuế (VAT amount)
        # STRICT CHECK: Must not contain "tiền hàng" or "pre tax" to avoid matching PreTax line
        if ("tiền thuế" in l or "vat amount" in l) and "tiền hàng" not in l and "pre tax" not in l:
            # Handle "|Tổng tiền thuế: 4.968.262|" format
            val = None
            if ":" in line:
               val_part = line.split(":")[-1].strip().strip("|")
               nums = re.findall(r'[\d\.\,]+', val_part)
               if nums:
                   from src.parsers.invoice_table_parser import safe_parse_float
                   val = safe_parse_float(nums[0])
            
            # Fallback to finding all numbers in line
            if not val:
                 nums = re.findall(r"[\d\.\,]+", line)
                 if nums:
                     from src.parsers.invoice_table_parser import safe_parse_float
                     val = safe_parse_float(nums[-1])

            if val and val > 100:
                invoice.taxAmount = val
        
        # Tiền trước thuế (PreTax) - Added specific check for summary table
        if ("tổng tiền hàng" in l or "thành tiền trước thuế" in l or "cộng tiền hàng" in l) and "thanh toán" not in l and "total amount" not in l:
             val = None
             if ":" in line:
                val_part = line.split(":")[-1].strip().strip("|")
                nums = re.findall(r'[\d\.\,]+', val_part)
                if nums:
                    from src.parsers.invoice_table_parser import safe_parse_float
                    val = safe_parse_float(nums[0])
             
             if not val:
                  nums = re.findall(r"[\d\.\,]+", line)
                  if nums:
                      from src.parsers.invoice_table_parser import safe_parse_float
                      val = safe_parse_float(nums[-1])
             
             if val and val > 0:
                 invoice.preTaxPrice = val

    # Default Currency - detect from block context
    if not invoice.currency:
        block_text = '\n'.join(block)
        # Check if invoice contains EURO indicators
        if re.search(r'\(EURO\)|EUR|euro', block_text, re.I):
            invoice.currency = "EUR"
        elif re.search(r'\(USD\)|USD|dollar', block_text, re.I):
            invoice.currency = "USD"
        else:
            invoice.currency = "VND"  # Default for Vietnamese invoices

    # FALLBACK: If totalAmount is still missing or suspiciously small,
    # find the largest number in the table block as totalAmount
    # User insight: "The largest number in the table will definitely be totalAmount"
    from src.parsers.invoice_table_parser import safe_parse_float
    
    all_numbers = []
    for line in block:
        # Extract all number-like strings
        nums = re.findall(r'[\d\.\,]+', line)
        for n in nums:
            parsed = safe_parse_float(n)
            if parsed and parsed > 0:
                all_numbers.append(parsed)
    
    if all_numbers:
        max_num = max(all_numbers)
        # Only use fallback if:
        # 1. totalAmount is not set, OR
        # 2. totalAmount is significantly smaller than max (likely a parsing error)
        if not invoice.totalAmount or (max_num > invoice.totalAmount * 5):
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
        if usd_score > 0:
            scores['USD'] = usd_score

        # EUR signals
        eur_score = 0
        eur_score += raw_text.count('€') * 3
        if re.search(r'\bEUR\b', text_upper): eur_score += 5
        if re.search(r'\(EURO\)', text_upper): eur_score += 4
        if re.search(r'\bEURO\b', text_upper): eur_score += 3
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
    
        # Pattern 6: Number: IVN2025121 (English format)
        if not invoice.invoiceID:
            m = re.search(r'Number[:\s]+([A-Z]{2,5}\d+|\d+)', raw_text, re.I)
            if m:
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
        if not invoice.totalAmount:
            m = re.search(r'Total\s+Value[^:)]*(?:\([^)]*\))?\s*[:\s]*\$?([\d\.\,]+)', raw_text, re.I)
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
                if val and len(val) > 3 and 'address' not in val.lower():
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
                num = m.group(1).replace('.', '').replace(',', '')
                if num.isdigit() and int(num) > 100:
                    invoice.preTaxPrice = float(num)
                    break
    
    # ===== TAX AMOUNT (fallback) =====
    if not invoice.taxAmount:
        # Pattern 1: "Thuế GTGT:" hoặc "Tiền thuế GTGT:"
        patterns = [
            r'[Tt]huế\s*(?:GTGT|giá\s*trị\s*gia\s*tăng)[^:]*:\s*([\d\.\,]+)',
            r'[Tt]iền\s*thuế[^:]*:\s*([\d\.\,]+)',
            r'VAT[^:]*:\s*([\d\.\,]+)',
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
        # Pattern: "Chiết khấu:", "Giảm giá:", "Discount:"
        patterns = [
            r'[Cc]hiết\s*khấu[^:]*:\s*([\d\.\,]+)',
            r'[Gg]iảm\s*giá[^:]*:\s*([\d\.\,]+)',
            r'[Dd]iscount[^:]*:\s*([\d\.\,]+)',
        ]
        for pattern in patterns:
            m = re.search(pattern, raw_text)
            if m:
                num = m.group(1).replace('.', '').replace(',', '')
                if num.isdigit() and int(num) > 0:
                    invoice.discountTotal = float(num)
                    break
    
    # ===== PAYMENT METHOD (fallback) =====
    if not invoice.paymentMethod:
        # Pattern: "Hình thức thanh toán:", "Payment method:", "Payment:"
        patterns = [
            r'[Hh]ình\s*thức\s*thanh\s*toán[^:\n]*[:\s]+([^\n|]+)',  # Relaxed [^:\n]* to match line till colon
            r'[Pp]ayment\s*(?:method)?[^:\n]*[:\s]+([^\n|]+)',
        ]
        for pattern in patterns:
            m = re.search(pattern, raw_text)
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
        ]
        for pattern in patterns:
            m = re.search(pattern, raw_text)
            if m:
                val = clean_invoice_total_in_word(m.group(1))
                if val and len(val) > 5:
                    invoice.invoiceTotalInWord = val
                    break


# Hàm gọi trong API_server.py
def parse_invoice_block_based(raw_text: str) -> Invoice:
    invoice = Invoice()

    lines = clean_lines(raw_text)
    blocks = detect_blocks(lines)

    parse_header(blocks["header"], invoice)
    parse_seller(blocks["seller"], invoice)
    parse_buyer(blocks["buyer"], invoice)
    parse_table(blocks["table"], invoice)
    parse_total(blocks["total"], invoice)
    
    # Fallback: scan toàn bộ raw text cho các trường còn thiếu
    parse_global_fields(raw_text, invoice)
    
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
    
    # Reverse fallback: if we have totalAmount but no invoiceTotalInWord, generate it
    if invoice.totalAmount and not invoice.invoiceTotalInWord:
        invoice.invoiceTotalInWord = number_to_vietnamese_words(invoice.totalAmount)

    # FINAL FALLBACK: "Max Number Strategy"
    # If totalAmount is missing or suspiciously equal to Tax Amount (e.g. 79400 vs 794000)
    # Check max number in raw text (or key blocks)
    # User insight: "The largest number in the table will definitely be totalAmount"
    if not invoice.totalAmount or (invoice.taxAmount and invoice.totalAmount <= invoice.taxAmount * 1.5):
         from src.parsers.invoice_table_parser import safe_parse_float
         all_nums = []
         # Scan table and total blocks for numbers
         scan_lines = blocks["table"] + blocks["total"]
         for line in scan_lines:
             # EXCLUDE lines with transaction codes, phone numbers, postal codes
             low = line.lower()
             if any(k in low for k in ["mã gd", "mã giao dịch", "tel", "phone", "fax",
                                        "(+84)", "(+86)", "(+1)", "swift",
                                        "account", "tài khoản", "postal",
                                        "zip", "100000", "242000"]):
                 continue
             
             nums = re.findall(r'[\d\.\,]+', line)
             for n in nums:
                 val = safe_parse_float(n)
                 # Filter: > 1000 (minimum amount) and < 10 million (reasonable upper bound for fallback)
                 # Tightened from 100B to 10M to exclude phone numbers (9+ digits)
                 if val and val > 1000 and val < 10_000_000:
                     all_nums.append(val)
         
         if all_nums:
             max_val = max(all_nums)
             if max_val > (invoice.totalAmount or 0):
                 # print(f"DEBUG: Max Number Override: {invoice.totalAmount} -> {max_val}")
                 invoice.totalAmount = max_val

    return invoice
