"""
Benchmark generator - Step 1: Run test cases and output JSON results.
This script adds benchmark output mode to the test files.
Usage: python benchmark_runner.py commercial|gtgt
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from src.parsers.block_invoice_parser import parse_invoice_block_based
from src.parsers.block_invoice_zoomtext_parser import parse_zoom_header
from datetime import date as date_type

def normalize_date(val):
    if isinstance(val, date_type):
        return val.strftime("%d/%m/%Y")
    if isinstance(val, str) and "-" in val:
        p = val.split("-")
        if len(p) == 3:
            return f"{p[2]}/{p[1]}/{p[0]}"
    return val

def run_case(case_id, filename, raw_text, zoom_text):
    invoice = parse_invoice_block_based(raw_text)
    if zoom_text and zoom_text.strip():
        zoom_lines = zoom_text.splitlines()
        parse_zoom_header(zoom_lines, invoice)
    d = invoice.model_dump()
    if d.get("invoiceDate"):
        d["invoiceDate"] = normalize_date(d["invoiceDate"])
    return d

ALL_FIELDS = [
    "invoiceName", "invoiceID", "invoiceDate", "invoiceSerial",
    "invoiceFormNo", "paymentMethod", "currency",
    "sellerName", "sellerTaxCode", "sellerEmail",
    "sellerAddress", "sellerPhoneNumber", "sellerBank", "sellerBankAccountNumber",
    "buyerName", "buyerTaxCode", "buyerEmail",
    "buyerAddress", "buyerPhoneNumber", "buyerBank", "buyerBankAccountNumber",
    "preTaxPrice", "discountTotal", "taxPercent", "taxAmount",
    "totalAmount", "invoiceTotalInWord",
]

mode = sys.argv[1] if len(sys.argv) > 1 else "commercial"

# Dynamically load CASES from the test file by executing it
# but we'll only extract the rawtext/zoomtext function pairs
print(f"Loading {mode} cases...", file=sys.stderr)

if mode == "commercial":
    test_file = os.path.join(os.path.dirname(__file__), "test_cases_commercial.py")
elif mode == "gtgt":
    test_file = os.path.join(os.path.dirname(__file__), "test_cases_gtgt.py")
else:
    print(f"Unknown mode: {mode}", file=sys.stderr)
    sys.exit(1)

# Execute the test file to get CASES
namespace = {'__file__': test_file, '__name__': 'test_module'}
with open(test_file, 'r', encoding='utf-8') as f:
    code = f.read()
exec(compile(code, test_file, 'exec'), namespace)

CASES = namespace['CASES']
print(f"Loaded {len(CASES)} cases", file=sys.stderr)

results = []
for case_id, filename, raw_fn, zoom_fn in CASES:
    try:
        # Suppress parser DEBUG output to stdout
        old_stdout = sys.stdout
        sys.stdout = open(os.devnull, 'w')
        try:
            d = run_case(case_id, filename, raw_fn(), zoom_fn())
        finally:
            sys.stdout.close()
            sys.stdout = old_stdout
        
        items = d.get("itemList", []) or []
        result = {
            "case_id": case_id,
            "filename": filename,
            "fields": {f: d.get(f) for f in ALL_FIELDS},
            "itemList_count": len(items),
        }
        results.append(result)
        print(f"  Case {case_id}: {filename} OK", file=sys.stderr)
    except Exception as e:
        # Restore stdout in case of error
        sys.stdout = old_stdout if 'old_stdout' in dir() else sys.__stdout__
        print(f"  Case {case_id}: {filename} ERROR: {e}", file=sys.stderr)
        results.append({
            "case_id": case_id,
            "filename": filename,
            "fields": {f: None for f in ALL_FIELDS},
            "itemList_count": 0,
        })

# Output JSON
output = {
    "mode": mode,
    "total_cases": len(results),
    "all_fields": ALL_FIELDS,
    "results": results,
}
print(json.dumps(output, ensure_ascii=False, default=str))
print(f"\nDone: {len(results)} cases", file=sys.stderr)
