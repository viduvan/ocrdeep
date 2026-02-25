from src.preprocess.rawtext_cleaner import clean_rawtext
from src.parsers.invoice_header_parser import (
    parse_header_info,
    parse_seller_buyer,
)
from src.parsers.invoice_table_parser import parse_items_from_table
from src.parsers.table_text_fallback import parse_table_from_text


def normalize_invoice_output(raw_text: str) -> dict:
    cleaned_text = clean_rawtext(raw_text)
    lines = cleaned_text.splitlines()

    invoice = {
        "invoiceID": None,
        "invoiceName": None,
        "invoiceDate": None,
        "invoiceSerial": None,
        "currency": None,

        "sellerName": None,
        "sellerTaxCode": None,
        "sellerAddress": None,

        "buyerName": None,
        "buyerTaxCode": None,
        "buyerAddress": None,

        "taxPercent": None,
        "taxAmount": None,
        "totalAmount": None,
        "invoiceTotalInWord": None,

        "itemList": [],
    }

    # ---- HEADER / PARTY INFO ----
    parse_header_info(cleaned_text, invoice)
    parse_seller_buyer(cleaned_text, invoice)

    # ---- TABLE (HTML PRIMARY) ----
    invoice["itemList"] = parse_items_from_table(cleaned_text)

    # ---- FALLBACK: TABLE TEXT ----
    if not invoice["itemList"]:
        invoice["itemList"] = parse_table_from_text(lines)

    return invoice
