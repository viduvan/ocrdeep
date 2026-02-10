import re
from typing import Dict

def parse_header_info(text: str, invoice: Dict):
    # Invoice name
    if "HÓA ĐƠN GIÁ TRỊ GIA TĂNG" in text:
        invoice["invoiceName"] = "HÓA ĐƠN GIÁ TRỊ GIA TĂNG"

    # Date
    m = re.search(r"Ngày.*?(\d{2}).*?(\d{2}).*?(\d{4})", text)
    if m:
        invoice["invoiceDate"] = f"{m.group(1)}/{m.group(2)}/{m.group(3)}"

    # Series
    m = re.search(r"Ký hiệu.*?:\s*([A-Z0-9]+)", text)
    if m:
        invoice["invoiceSerial"] = m.group(1)

    # Invoice number
    m = re.search(r"Số.*?:\s*(\d+)", text)
    if m:
        invoice["invoiceID"] = m.group(1)

def parse_seller_buyer(text: str, invoice: Dict):
    # Seller
    m = re.search(r"CÔNG TY.*?\n\d{10}", text, re.S)
    if m:
        block = m.group()
        invoice["sellerName"] = block.splitlines()[0].strip()
        tax = re.search(r"\d{10}", block)
        if tax:
            invoice["sellerTaxCode"] = tax.group()

    # Buyer
    m = re.search(r"CÔNG TY CỔ PHẦN.*?\n\d{10}", text, re.S)
    if m:
        block = m.group()
        invoice["buyerName"] = block.splitlines()[0].strip()
        tax = re.search(r"\d{10}", block)
        if tax:
            invoice["buyerTaxCode"] = tax.group()
