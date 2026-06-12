"""
Test script: Verify _process_invoice_page() works with LLM pipeline.
Bypasses OCR step — directly passes raw_text + zoom_text from test cases.
"""
import sys, os, json, logging

# Setup logging to see [LLM] messages
logging.basicConfig(level=logging.INFO, format='%(name)s - %(levelname)s - %(message)s')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load .env
from pathlib import Path
env_file = Path(__file__).parent / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, val = line.split("=", 1)
            os.environ[key.strip()] = val.strip().strip('"').strip("'")

from src.api_server import _process_invoice_page
from tests.test_cases_gtgt import rawtext_04, zoomtext_04

print("=" * 70)
print("TEST: _process_invoice_page() with Case 04 (GTGT invoice)")
print("=" * 70)

raw = rawtext_04()
zoom = zoomtext_04()

print(f"\nInput: raw_text={len(raw)} chars, zoom_text={len(zoom)} chars")
print("Calling _process_invoice_page()...\n")

invoice, metadata = _process_invoice_page(raw, zoom, page_label="test_case_04")

print("\n" + "=" * 70)
print(f"extraction_method: {metadata['extraction_method']}")
print(f"validation: {json.dumps(metadata.get('validation', {}), indent=2)}")
print("=" * 70)

# Print key fields
d = invoice.model_dump()
fields = [
    "invoiceName", "invoiceID", "invoiceDate", "invoiceSerial", "invoiceFormNo",
    "sellerName", "sellerTaxCode", "buyerName", "buyerTaxCode",
    "paymentMethod", "currency",
    "preTaxPrice", "taxPercent", "taxAmount", "totalAmount",
    "invoiceTotalInWord",
]
print("\n--- Invoice Fields ---")
for f in fields:
    val = d.get(f)
    print(f"  {f}: {val}")

items = d.get("itemList", [])
print(f"\n--- Items ({len(items)}) ---")
for i, item in enumerate(items[:5]):
    name = (item.get('productName') or '-')[:50]
    qty = item.get('quantity', '-')
    price = item.get('unitPrice', '-')
    amt = item.get('amount', '-')
    print(f"  [{i+1}] {name} | qty={qty} | price={price} | amt={amt}")

print("\n✅ TEST COMPLETE")
