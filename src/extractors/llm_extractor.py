"""
LLM-based invoice extraction using FPT Cloud Qwen3-32B.
Replaces regex block parser for OCR text → structured JSON conversion.

Usage:
    from src.extractors.llm_extractor import extract_invoice_llm
    result = extract_invoice_llm(raw_text)
"""
import json
import os
import re
import logging
from typing import Optional

from openai import OpenAI

logger = logging.getLogger(__name__)

# ── FPT Cloud Configuration ──────────────────────────────────────────────────
FPT_API_BASE = os.getenv("FPT_API_BASE", "https://mkp-api.fptcloud.com/v1")
FPT_API_KEY = os.getenv("FPT_API_KEY", "")
FPT_MODEL = os.getenv("FPT_MODEL", "Qwen3-32B")
FPT_TIMEOUT = int(os.getenv("FPT_TIMEOUT", "60"))

# ── System Prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are an expert invoice/commercial document data extractor.
Your task is to extract structured data from OCR text of invoices and commercial documents.

CRITICAL RULES:
1. Extract EXACT numbers, names, and text as they appear in the source. Do NOT calculate, estimate, or modify values.
   - CRITICAL: For totalAmount, preTaxPrice, taxAmount — ALWAYS use the values printed on the invoice (e.g., "Subtotal: $4,700", "TOTAL: 247,830,000").
     NEVER recalculate these by summing items yourself. The printed totals on the invoice are authoritative.
   - If the invoice shows "TOTAL: VND 678,503,000", return totalAmount=678503000, even if your item sum differs.
2. For invoice ID: Look for patterns like "No.", "No:", "Số:", "Invoice No", "Invoice Number", "Number:", "#", "INV.", "Invoice #"
   - Clean the ID value: remove trailing punctuation marks like "!", ".", "," that may be OCR artifacts. E.g., "047!" → "047"
3. For invoice name/title: Look for document title like "COMMERCIAL INVOICE", "INVOICE", "Proforma Invoice", "HÓA ĐƠN GIÁ TRỊ GIA TĂNG"
4. For dates: Convert to YYYY-MM-DD format (ISO 8601). 
   - Date format depends on document type:
     a) Vietnamese invoices (GTGT, "Hóa đơn"): DD/MM/YYYY. "09/05/2025" → "2025-05-09" (May 9th)
     b) English/Commercial invoices ("COMMERCIAL INVOICE", "INVOICE", "Proforma"): MM/DD/YYYY. "09/05/2025" → "2025-09-05" (Sep 5th)
   - Named months are unambiguous: "Feb 14, 2019" → "2019-02-14", "28-Oct-25" → "2025-10-28", "20-Nov-2017" → "2017-11-20"
5. For seller/exporter: Look for "Shipper", "Exporter", "Seller", "FROM", "Đơn vị bán hàng", "Người bán hàng", "Ship From", "THE SELLER", "Beneficiary"
6. For buyer/importer: Look for "Consignee", "Importer", "Buyer", "TO", "Người mua hàng", "Tên đơn vị", "Khách hàng", "Bill To", "THE BUYER", "Applicant", "Ship To"
   - For sellerName/buyerName: Extract ONLY the company name. Remove label prefixes like "Đơn vị bán hàng:", "Đơn vị mua hàng:", "Ký bởi:", etc.
   - Example: "Đơn vị mua hàng: CÔNG TY TNHH FPT IS" → buyerName = "CÔNG TY TNHH FPT IS"
7. For item table: Each row MUST have productName. quantity, unitPrice, amount are numeric or null.
   - IMPORTANT: For items, use "Thành tiền" (pre-tax amount) column, NOT "Thành tiền sau thuế" (after-tax amount).
   - MULTI-PAGE OCR: The OCR text may contain MULTIPLE pages separated by "--- PAGE N ---" markers.
     CRITICAL: Different pages may be DIFFERENT invoices scanned together in one file.
     Always extract from PAGE 1 (the first page). Ignore items, totals, and "Số tiền viết bằng chữ" from later pages.
     If PAGE 1 has its own "Tổng cộng" and "Số tiền viết bằng chữ", use THOSE values only.
   - For UTILITY BILLS (tiền điện): The item table may have tiered pricing rows without standard STT/product name.
     Group all consumption tiers into ONE item with productName="Điện tiêu thụ", quantity=total kWh, amount=total pre-tax amount.
8. For totalAmount: Look for "Tổng cộng tiền thanh toán", "Total payment", "Total Amount", "Grand Total", "Tổng cộng", "TOTAL VALUE", "Amount Due"
   - For Vietnamese GTGT invoices: use "Tổng cộng tiền thanh toán" or the "Cộng tiền thanh toán" row in the tax summary table.
9. For preTaxPrice (IMPORTANT - do NOT skip this field):
   - Look for "Cộng tiền hàng", "Tổng tiền hàng", "Thành tiền trước thuế GTGT", "Total amount", "Subtotal", "Sub Total", "Total Commercial Value", "EXW", "FOB", "CIF"
   - If there is NO separate subtotal line but there IS a total: set preTaxPrice = totalAmount (the pre-tax price equals the total when tax is 0 or not applicable)
   - If you can compute it: preTaxPrice = totalAmount - taxAmount
10. For currency: Look for "$", "USD", "EUR", "GBP", "VND", "₫", "£", "€", "Đồng tiền thanh toán" or explicit "Currency:" labels
11. For tax: Look for "VAT", "Tax", "GST", "CGST", "SGST", "Thuế GTGT", "Thuế suất GTGT"
    - For Vietnamese GTGT: "KCT" or "Không chịu thuế" means tax-exempt → taxPercent = "KCT", taxAmount = 0
     - CRITICAL: Do NOT confuse payment terms with tax percentage!
       "T/T 30%" means 30% deposit payment, NOT 30% tax. "L/C", "30% advance", "30% deposit" are payment terms.
       taxPercent must come from explicit tax/VAT lines like "VAT 10%", "Tax Rate: 5%", "Thuế suất GTGT: 8%".
       If no explicit tax/VAT rate is found, return taxPercent as null or "0%".
12. If a field is genuinely not found in the text, return null — NEVER guess or hallucinate.
     - CRITICAL: Template placeholders are NOT real values. If a field contains patterns like:
       [Invoice.No], [Sender.Company], [Client.Name], {field_name}, {{placeholder}}, [Your Company], etc.
       These are unfilled template variables — return null for that field.
13. For amount fields (preTaxPrice, taxAmount, totalAmount, unitPrice, amount, quantity): return as numbers, NOT strings.
14. Remove currency symbols and thousand separators from numeric values. "3,240.00" → 3240.00, "$25,475.00" → 25475.00
15. For Vietnamese number format: dot (.) is thousand separator, comma (,) is decimal separator.
    - "4.463.014" → 4463014, "10.185,19" → 10185.19, "62.103.270" → 62103270
    - CRITICAL for Vietnamese GTGT invoices — numbers can be VERY AMBIGUOUS:
      a) "3.848,00" in tax summary = 3,848,000 VND (NOT 3848.00). The ",00" means zero hundreds.
      b) "30.555,000" = 30,555,000 VND (NOT 30555.0). The ",000" means zero units.
      c) "8.888,000" = 8,888,000 VND. The ",000" after comma is thousands continuation.
      d) "20.655,00" = 20,655,000 VND (NOT 20655.00).
     - VALIDATION RULE: Always verify amounts by computing quantity × unitPrice.
      Example: qty=2500, unitPrice=12222 → amount MUST be 30,555,000 (not 30555).
      Example: qty=1000, unitPrice=3848 → amount MUST be 3,848,000 (not 3848).
      Example: qty=2000, unitPrice=4444 → amount MUST be 8,888,000 (not 8888).
      Example: qty=5000, unitPrice=26000 → amount MUST be 130,000,000. taxAmount at 8% = 10,400,000.
    - QUANTITY vs AMOUNT distinction:
      * For QUANTITY column: "30,00" = 30 (comma is decimal separator, ,00 = .00). Quantities are typically small numbers (kg, cây, cái).
      * For AMOUNT/PRICE columns: "30.555,000" = 30,555,000 VND. The VN thousands convention applies.
      * For UNIT PRICE column: "67,90" can mean 67,900 VND. Verify: qty × unitPrice should ≈ amount.
        Example: qty=30, unitPrice=67900 → amount=2,037,000. If unitPrice were 67.9, amount would be 2,037 which is too small for VND.
    - STANDALONE DOT-NUMBERS (no comma): CRITICAL — In VND invoices, a number like "399.585" or "369.986"
      is ALWAYS a thousands-separated integer: 399,585 VND and 369,986 VND respectively.
      Similarly "511.730" = 511,730 VND, "29.599" = 29,599 VND.
      NEVER interpret dots in VND amounts as decimal points. VND has NO decimal places.
      If the result would be a non-integer (e.g., 399.585), you are wrong — it should be 399585.
    - If "Số tiền viết bằng chữ" says "ba mươi triệu..." then total is 30,000,000+ range.
    - VND amounts are ALWAYS whole numbers (integers). If your calculation gives decimals for VND, you likely misread the number format.
16. For invoiceTotalInWord: Look for "Số tiền viết bằng chữ", "Total amount in words", "In words", "SAY..."
    - Extract the FULL text as-is.
17. taxPercent should be a string like "10%" or "8%". If GST/VAT is 0% or KCT, return "0%" or "KCT".
18. sellerTaxCode/buyerTaxCode: "Mã số thuế", Tax identification numbers, VAT numbers, GST numbers, EORI numbers
    - IMPORTANT: Use the "Mã số thuế" that appears NEAR the seller/buyer name section (typically lines 5-20 of invoice).
    - Do NOT use MST from footer sections like "Đơn vị cung cấp hóa đơn điện tử" — that is the e-invoice platform provider, NOT the seller.
    - Tax codes may have spaces ("01 07 50 04 14" → "0107500414"). Remove all spaces but KEEP hyphens (e.g., "0300942001-021" stays as-is, the hyphen separates main code from branch code).
19. paymentMethod: Look for "Hình thức thanh toán", "Payment method", "T/T", "L/C", "TM/CK", "Chuyển khoản", "Tiền mặt".
    - Use the value from "Hình thức thanh toán" or "Terms of Payment" labels.
    - Do NOT confuse with "Terms of Sale" (like FOB, CIF, EXW) — those are shipping terms, not payment methods.
20. For Vietnamese GTGT invoices — invoiceSerial and invoiceFormNo:
    There are TWO formats depending on the invoice age:
    
    A) NEW FORMAT (post-2021, e-invoices): "Ký hiệu" is a combined code like "1C25TAA", "1C25THO", "1K25TEF"
       - invoiceFormNo = first character (always "1" for GTGT, "2" for bán hàng)
       - invoiceSerial = remaining characters after the first digit
       - Examples: "Ký hiệu: 1C25TAA" → formNo="1", serial="C25TAA"
                   "Ký hiệu: 1C25THO" → formNo="1", serial="C25THO"
                   "Ký hiệu: 1K25TEF" → formNo="1", serial="K25TEF"
    
    B) OLD FORMAT (pre-2021, paper invoices): "Mẫu số" and "Ký hiệu" are SEPARATE fields
       - invoiceFormNo = "Mẫu số" value (e.g., "01GTKT0/001")
       - invoiceSerial = "Ký hiệu" value (e.g., "AE/18E", "AA/19P")
       - Examples: "Mẫu số: 01GTKT0/001", "Ký hiệu: AE/18E" → formNo="01GTKT0/001", serial="AE/18E"
    
    How to distinguish: If "Mẫu số:" label exists separately → use OLD format. Otherwise → use NEW format.
    
    - invoiceID = "Số" or "Số:" value (e.g., "00007675", "414", "047")
    - "Mã CQT" or "Mã cơ quan thuế" or "MCQT" = Tax authority verification code. IGNORE it completely.
    
21. For Vietnamese GTGT invoices — invoiceDate:
    - Priority 1: "Ngày X tháng Y năm Z" at the top of the invoice (official issue date)
    - Priority 2: "Ký ngày: DD/MM/YYYY" or "Ký ngày: X tháng Y năm Z" (signing date, usually = issue date)
    - Do NOT use: "Từ ngày/Đến ngày" (billing period), dates inside item descriptions (promotional dates), 
      or dates from "Thay thế cho hóa đơn... ngày..." (replacement reference dates)
    
22. sellerBank should be the bank NAME only (e.g., "Ngân hàng MSB - Chi nhánh Đống Đa"), NOT the account number.

Return a JSON object with these exact fields (use null for missing values):
{
  "invoiceID": "string or null - 'Số' value",
  "invoiceName": "string or null - document title",
  "currency": "string or null - e.g. USD, EUR, VND",
  "invoiceDate": "YYYY-MM-DD or null",
  "invoiceFormNo": "string or null - 'Mẫu số': first char of 'Ký hiệu' for GTGT (e.g. '1')",
  "invoiceSerial": "string or null - 'Ký hiệu' without first char for GTGT (e.g. 'C25TAA' from '1C25TAA')",
  "paymentMethod": "string or null",
  "sellerName": "string or null - company name of seller/exporter/shipper",
  "sellerTaxCode": "string or null",
  "sellerEmail": "string or null",
  "sellerAddress": "string or null - single line, comma-separated",
  "sellerPhoneNumber": "string or null",
  "sellerBank": "string or null",
  "sellerBankAccountNumber": "string or null",
  "buyerName": "string or null - company name of buyer/consignee/importer",
  "buyerTaxCode": "string or null",
  "buyerEmail": "string or null",
  "buyerAddress": "string or null - single line, comma-separated",
  "buyerPhoneNumber": "string or null",
  "buyerBank": "string or null",
  "buyerBankAccountNumber": "string or null",
  "preTaxPrice": "number or null - subtotal before tax, or same as totalAmount if no tax",
  "discountTotal": "number or null",
  "taxPercent": "string or null - e.g. '10%', '0%'",
  "taxAmount": "number or null - 0 if tax is explicitly 0%",
  "totalAmount": "number or null",
  "invoiceTotalInWord": "string or null - total in words, extract as-is from text",
  "itemList": [
    {
      "productCode": "string or null",
      "productName": "string or null",
      "unit": "string or null",
      "unitPrice": "number or null",
      "quantity": "number or null",
      "amount": "number or null",
      "discountPercent": "string or null",
      "discountAmount": "number or null",
      "payment": "number or null"
    }
  ]
}

/no_think
IMPORTANT: Return ONLY the JSON object. No markdown, no code fences, no explanation."""


def _get_fpt_client() -> OpenAI:
    """Create OpenAI-compatible client for FPT Cloud."""
    api_key = FPT_API_KEY
    if not api_key:
        raise ValueError(
            "FPT_API_KEY not set. Export it: export FPT_API_KEY='your-key'"
        )
    return OpenAI(
        base_url=FPT_API_BASE,
        api_key=api_key,
        timeout=FPT_TIMEOUT,
    )


def _clean_json_response(text: str) -> str:
    """Strip markdown fences and thinking tags from LLM response."""
    # Remove <think>...</think> blocks (Qwen3 thinking mode)
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    text = text.strip()
    
    # Remove markdown code fences
    if text.startswith("```"):
        # Remove opening fence (```json or ```)
        text = re.sub(r'^```(?:json)?\s*\n?', '', text)
        # Remove closing fence
        text = re.sub(r'\n?```\s*$', '', text)
    
    return text.strip()


def _parse_llm_json(raw_response: str) -> Optional[dict]:
    """Parse LLM response into dict, handling common issues."""
    cleaned = _clean_json_response(raw_response)
    
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.warning(f"JSON parse failed: {e}")
        logger.debug(f"Raw response (first 500 chars): {cleaned[:500]}")
        
        # Try to extract JSON object from the response
        match = re.search(r'\{[\s\S]*\}', cleaned)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        
        return None


# Regex to detect template placeholder values
_PLACEHOLDER_RE = re.compile(r'^\[.*\]$|^\{.*\}$|^\{\{.*\}\}$')


def _clean_placeholder_values(result: dict) -> dict:
    """Remove template placeholder values like [Invoice.No], {field_name}."""
    if not result:
        return result
    
    for key, val in list(result.items()):
        if key == 'itemList':
            continue
        if isinstance(val, str) and _PLACEHOLDER_RE.match(val.strip()):
            result[key] = None
    
    return result


def extract_invoice_llm(
    raw_text: str,
    zoom_text: str = "",
    model: str = None,
    temperature: float = 0.0,
    max_tokens: int = 4096,
) -> Optional[dict]:
    """
    Extract invoice fields from OCR text using FPT Cloud LLM.
    
    Args:
        raw_text: OCR text from DeepSeek-OCR (full page)
        zoom_text: OCR text from zoom-in crop (header area), if available
        model: Override model name (default: FPT_MODEL)
        temperature: LLM temperature (0.0 = deterministic)
        max_tokens: Max output tokens
        
    Returns:
        dict with invoice fields, or None if extraction failed
    """
    model = model or FPT_MODEL
    
    # Combine raw text and zoom text for maximum context
    user_content = f"Extract invoice data from this OCR text:\n\n{raw_text}"
    if zoom_text and zoom_text.strip():
        user_content += f"\n\n--- ADDITIONAL HEADER DETAIL (ZOOMED-IN) ---\n{zoom_text}"
    
    try:
        client = _get_fpt_client()
        
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=1,
            stream=False,
        )
        
        raw_response = response.choices[0].message.content
        if not raw_response:
            logger.error("LLM returned empty response")
            return None
        
        result = _parse_llm_json(raw_response)
        if result is None:
            logger.error("Failed to parse LLM response as JSON")
            return None
        
        # Post-processing: clean template placeholders
        result = _clean_placeholder_values(result)
        
        logger.info(
            f"LLM extraction successful: "
            f"invoiceID={result.get('invoiceID')}, "
            f"totalAmount={result.get('totalAmount')}, "
            f"items={len(result.get('itemList', []))}"
        )
        return result
        
    except Exception as e:
        logger.error(f"LLM extraction failed: {type(e).__name__}: {e}")
        return None


def extract_invoice_llm_to_pydantic(
    raw_text: str,
    zoom_text: str = "",
    **kwargs,
):
    """
    Extract invoice and return as Pydantic Invoice model.
    Falls back to None if extraction or validation fails.
    """
    from src.schemas.invoice import Invoice
    
    result = extract_invoice_llm(raw_text, zoom_text, **kwargs)
    if result is None:
        return None
    
    try:
        # Handle date conversion: LLM returns YYYY-MM-DD, Pydantic expects date
        invoice_date = result.get("invoiceDate")
        if invoice_date and isinstance(invoice_date, str):
            from datetime import datetime
            try:
                result["invoiceDate"] = datetime.strptime(
                    invoice_date, "%Y-%m-%d"
                ).date()
            except ValueError:
                # Try other common formats
                for fmt in ["%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"]:
                    try:
                        result["invoiceDate"] = datetime.strptime(
                            invoice_date, fmt
                        ).date()
                        break
                    except ValueError:
                        continue
                else:
                    result["invoiceDate"] = None
        
        invoice = Invoice(**result)
        return invoice
    except Exception as e:
        logger.warning(f"Pydantic validation failed: {e}")
        return None
