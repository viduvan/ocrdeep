"""
Test LLM extraction vs Regex parser on commercial invoice cases.
Runs selected cases through both pipelines and compares results.

Usage:
    export FPT_API_KEY='your-key'
    python tests/test_llm_extraction.py
    python tests/test_llm_extraction.py --cases 1,4,10,36,46
"""
import sys
import os
import json
import time
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from src.extractors.llm_extractor import extract_invoice_llm
from src.extractors.invoice_validator import InvoiceValidator
from src.parsers.block_invoice_parser import parse_invoice_block_based
from src.parsers.block_invoice_zoomtext_parser import parse_zoom_header
from datetime import date as date_type


def normalize_date(val):
    if isinstance(val, date_type):
        return val.strftime("%d/%m/%Y")
    if isinstance(val, str) and "-" in val:
        p = val.split("-")
        if len(p) == 3 and len(p[0]) == 4:
            return f"{p[2]}/{p[1]}/{p[0]}"
    return val


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


def run_regex_parser(raw_text, zoom_text):
    """Run existing regex parser."""
    invoice = parse_invoice_block_based(raw_text)
    if zoom_text and zoom_text.strip():
        zoom_lines = zoom_text.splitlines()
        parse_zoom_header(zoom_lines, invoice)
    d = invoice.model_dump()
    if d.get("invoiceDate"):
        d["invoiceDate"] = normalize_date(d["invoiceDate"])
    return d


def run_llm_extractor(raw_text, zoom_text):
    """Run LLM-based extractor."""
    result = extract_invoice_llm(raw_text, zoom_text)
    if result is None:
        return None
    
    # Normalize date for comparison
    if result.get("invoiceDate"):
        result["invoiceDate"] = normalize_date(result["invoiceDate"])
    
    return result


def compare_results(case_id, regex_result, llm_result, raw_text, zoom_text=""):
    """Compare regex vs LLM results field by field."""
    if llm_result is None:
        print(f"  ❌ LLM extraction FAILED (returned None)")
        return
    
    # Validate LLM result
    validator = InvoiceValidator()
    llm_validated = validator.validate(llm_result, raw_text, zoom_text)
    summary = validator.get_summary(llm_validated)
    
    print(f"\n{'─'*90}")
    print(f"  COMPARISON: Case {case_id:02d}")
    print(f"{'─'*90}")
    print(f"  {'Field':<30} {'Regex Parser':<30} {'LLM (Qwen3-32B)':<30}")
    print(f"  {'─'*28:30} {'─'*28:30} {'─'*28:30}")
    
    matches = 0
    mismatches = 0
    llm_only = 0
    regex_only = 0
    
    for field in ALL_FIELDS:
        r_val = regex_result.get(field)
        l_val = llm_result.get(field)
        
        # Skip both null
        if r_val is None and l_val is None:
            continue
        
        r_str = str(r_val) if r_val is not None else "∅"
        l_str = str(l_val) if l_val is not None else "∅"
        
        # Truncate long values
        r_str = r_str[:28] if len(r_str) > 28 else r_str
        l_str = l_str[:28] if len(l_str) > 28 else l_str
        
        if r_val is not None and l_val is not None:
            # Both have values - compare (normalize numeric types)
            r_cmp = str(r_val).strip()
            l_cmp = str(l_val).strip()
            # Normalize float vs int: "6909000.0" == "6909000"
            try:
                if float(r_cmp) == float(l_cmp):
                    r_cmp = l_cmp  # force match
            except (ValueError, TypeError):
                pass
            if r_cmp == l_cmp:
                marker = "✅"
                matches += 1
            else:
                marker = "⚠️"
                mismatches += 1
        elif r_val is not None and l_val is None:
            marker = "🔵"  # Regex has it, LLM doesn't
            regex_only += 1
        else:
            marker = "🟢"  # LLM has it, Regex doesn't
            llm_only += 1
        
        print(f"  {marker} {field:<28} {r_str:<30} {l_str:<30}")
    
    # Item list comparison
    r_items = regex_result.get("itemList", []) or []
    l_items = llm_result.get("itemList", []) or []
    print(f"\n  📦 Items: Regex={len(r_items)}, LLM={len(l_items)}")
    
    max_items = max(len(r_items), len(l_items))
    for i in range(min(max_items, 5)):
        r_item = r_items[i] if i < len(r_items) else {}
        l_item = l_items[i] if i < len(l_items) else {}
        
        r_name = (r_item.get("productName") or "-")[:25]
        l_name = (l_item.get("productName") or "-")[:25]
        r_amt = r_item.get("amount", "-")
        l_amt = l_item.get("amount", "-")
        r_qty = r_item.get("quantity", "-")
        l_qty = l_item.get("quantity", "-")
        
        # Normalize float vs int for item amounts
        try:
            amt_match = (r_amt != "-" and l_amt != "-" 
                        and float(r_amt) == float(l_amt))
        except (ValueError, TypeError):
            amt_match = str(r_amt) == str(l_amt)
        match = "✅" if amt_match else "⚠️"
        print(f"    [{i+1}] {match} R: {r_name:<25} qty={r_qty} amt={r_amt}")
        print(f"         L: {l_name:<25} qty={l_qty} amt={l_amt}")
    
    # Summary
    print(f"\n  📊 Summary:")
    print(f"     ✅ Matches: {matches}")
    print(f"     ⚠️  Mismatches: {mismatches}")
    print(f"     🔵 Regex-only: {regex_only}")
    print(f"     🟢 LLM-only: {llm_only}")
    print(f"     🏷️  Confidence: H={summary['confidence_high']} "
          f"M={summary['confidence_medium']} L={summary['confidence_low']}")
    if summary["total_flags"] > 0:
        print(f"     ⚠️  Flags: {summary['flags']}")
    if summary["low_confidence_fields"]:
        print(f"     🔴 Low confidence: {summary['low_confidence_fields']}")
    
    return {
        "matches": matches,
        "mismatches": mismatches,
        "llm_only": llm_only,
        "regex_only": regex_only,
        "flags": summary["total_flags"],
    }


def load_case_functions(invoice_type="commercial"):
    """Dynamically load test case functions from test_cases modules."""
    if invoice_type == "gtgt":
        import tests.test_cases_gtgt as tc
    else:
        import tests.test_cases_commercial as tc
    
    cases = {}
    for i in range(1, 200):
        raw_fn = f"rawtext_{i:02d}"
        zoom_fn = f"zoomtext_{i:02d}"
        if hasattr(tc, raw_fn):
            cases[i] = {
                "raw_fn": getattr(tc, raw_fn),
                "zoom_fn": getattr(tc, zoom_fn) if hasattr(tc, zoom_fn) else lambda: "",
            }
    return cases


def main():
    parser = argparse.ArgumentParser(description="Test LLM extraction")
    parser.add_argument(
        "--cases",
        type=str,
        default="1,4,7,10,36",
        help="Comma-separated case IDs to test (default: 1,4,7,10,36)",
    )
    parser.add_argument(
        "--type",
        type=str,
        default="commercial",
        choices=["commercial", "gtgt"],
        help="Invoice type: 'commercial' or 'gtgt' (default: commercial)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all available cases",
    )
    args = parser.parse_args()
    
    # Check API key
    if not os.getenv("FPT_API_KEY"):
        print("❌ FPT_API_KEY not set!")
        print("   Run: export FPT_API_KEY='your-api-key'")
        sys.exit(1)
    
    cases = load_case_functions(args.type)
    
    if args.all:
        case_ids = sorted(cases.keys())
    else:
        case_ids = [int(c.strip()) for c in args.cases.split(",")]
    
    type_label = "HÓA ĐƠN GTGT" if args.type == "gtgt" else "COMMERCIAL INVOICE"
    print(f"{'='*90}")
    print(f"  LLM Extraction Test — Qwen3-32B on FPT Cloud")
    print(f"  Type: {type_label} | Testing {len(case_ids)} cases: {case_ids}")
    print(f"{'='*90}")
    
    all_stats = []
    
    for case_id in case_ids:
        if case_id not in cases:
            print(f"\n⚠️  Case {case_id} not found, skipping")
            continue
        
        case = cases[case_id]
        raw_text = case["raw_fn"]()
        zoom_text = case["zoom_fn"]()
        
        print(f"\n{'═'*90}")
        print(f"  CASE {case_id:02d}")
        print(f"{'═'*90}")
        
        # Run regex parser
        print("  ⏳ Running regex parser...")
        t0 = time.time()
        regex_result = run_regex_parser(raw_text, zoom_text)
        regex_time = time.time() - t0
        print(f"  ✅ Regex done in {regex_time:.2f}s")
        
        # Run LLM extractor
        print("  ⏳ Running LLM extractor (Qwen3-32B)...")
        t0 = time.time()
        llm_result = run_llm_extractor(raw_text, zoom_text)
        llm_time = time.time() - t0
        print(f"  {'✅' if llm_result else '❌'} LLM done in {llm_time:.2f}s")
        
        # Compare
        stats = compare_results(case_id, regex_result, llm_result, raw_text, zoom_text)
        if stats:
            stats["case_id"] = case_id
            stats["regex_time"] = regex_time
            stats["llm_time"] = llm_time
            all_stats.append(stats)
    
    # Overall summary
    if all_stats:
        print(f"\n{'═'*90}")
        print(f"  OVERALL SUMMARY")
        print(f"{'═'*90}")
        total_matches = sum(s["matches"] for s in all_stats)
        total_mismatches = sum(s["mismatches"] for s in all_stats)
        total_llm_only = sum(s["llm_only"] for s in all_stats)
        total_regex_only = sum(s["regex_only"] for s in all_stats)
        avg_llm_time = sum(s["llm_time"] for s in all_stats) / len(all_stats)
        avg_regex_time = sum(s["regex_time"] for s in all_stats) / len(all_stats)
        
        print(f"  Cases tested: {len(all_stats)}")
        print(f"  ✅ Total matches: {total_matches}")
        print(f"  ⚠️  Total mismatches: {total_mismatches}")
        print(f"  🟢 LLM extracted but regex missed: {total_llm_only}")
        print(f"  🔵 Regex extracted but LLM missed: {total_regex_only}")
        print(f"  ⏱️  Avg time — Regex: {avg_regex_time:.3f}s, LLM: {avg_llm_time:.1f}s")


if __name__ == "__main__":
    main()
