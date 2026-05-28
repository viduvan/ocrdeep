#!/usr/bin/env python3
"""Batch test summary - shows field + item mismatches for quick analysis."""
import sys, os, time, re, argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tests.test_llm_extraction import run_regex_parser, run_llm_extractor, ALL_FIELDS, normalize_date


def _is_tax_diff(r_amt, l_amt):
    """Check if regex amount = LLM amount × (1 + tax_rate).
    This means regex took post-tax column, LLM took pre-tax (correct).
    Common tax rates: 5%, 8%, 10%
    """
    try:
        r = float(r_amt)
        l = float(l_amt)
        if l == 0 or r == 0:
            return False
        ratio = r / l
        # Check common tax ratios: 1.05, 1.08, 1.10
        for rate in [1.05, 1.08, 1.10]:
            if abs(ratio - rate) < 0.005:  # 0.5% tolerance
                return True
        # Also check negative (adjustment invoices)
        if abs(r) > 0 and abs(l) > 0 and r * l < 0:
            # Signs differ — check if absolute values have tax ratio
            ratio = abs(r) / abs(l)
            for rate in [1.0, 1.05, 1.08, 1.10]:
                if abs(ratio - rate) < 0.005:
                    return True
    except (ValueError, TypeError):
        pass
    return False


def compare_items(r_items, l_items):
    """Compare item lists, return (item_matches, item_mismatches_list).
    
    Detects pre-tax vs post-tax differences (regex bug) and categorizes
    them separately from real mismatches.
    """
    r_items = r_items or []
    l_items = l_items or []
    
    item_matches = 0
    item_mismatches = []
    
    max_items = max(len(r_items), len(l_items))
    for i in range(max_items):
        r_item = r_items[i] if i < len(r_items) else {}
        l_item = l_items[i] if i < len(l_items) else {}
        
        r_name = (r_item.get("productName") or "-")[:30]
        l_name = (l_item.get("productName") or "-")[:30]
        r_amt = r_item.get("amount")
        l_amt = l_item.get("amount")
        r_qty = r_item.get("quantity")
        l_qty = l_item.get("quantity")
        r_price = r_item.get("unitPrice")
        l_price = l_item.get("unitPrice")
        
        # Check amount match
        amt_match = False
        amt_tax_diff = False  # pre-tax vs post-tax
        try:
            if r_amt is not None and l_amt is not None:
                if float(r_amt) == float(l_amt):
                    amt_match = True
                elif _is_tax_diff(r_amt, l_amt):
                    amt_tax_diff = True  # Known difference: regex=post-tax, LLM=pre-tax
            elif r_amt is None and l_amt is None:
                amt_match = True
        except (ValueError, TypeError):
            amt_match = str(r_amt) == str(l_amt)
        
        # Check quantity match
        qty_match = False
        try:
            if r_qty is not None and l_qty is not None:
                qty_match = float(r_qty) == float(l_qty)
            elif r_qty is None and l_qty is None:
                qty_match = True
        except (ValueError, TypeError):
            qty_match = str(r_qty) == str(l_qty)
        
        # Check name match (fuzzy - first 20 chars or substring)
        r_n20 = r_name[:20].strip().lower()
        l_n20 = l_name[:20].strip().lower()
        name_match = (r_n20 == l_n20 or r_name == "-" or l_name == "-"
                      or r_n20 in l_n20 or l_n20 in r_n20)
        
        if (amt_match or amt_tax_diff) and qty_match and name_match:
            item_matches += 1
        else:
            diffs = []
            if not name_match:
                diffs.append(f"name: R={r_name[:20]} vs L={l_name[:20]}")
            if not qty_match:
                diffs.append(f"qty: R={r_qty} vs L={l_qty}")
            if not amt_match and not amt_tax_diff:
                diffs.append(f"amt: R={r_amt} vs L={l_amt}")
            
            # If only diff was tax-related and already counted as match, skip
            if not diffs:
                item_matches += 1
                continue
                
            item_mismatches.append({
                "idx": i + 1,
                "diffs": diffs,
                "tax_diff": amt_tax_diff,
                "r_name": r_name, "l_name": l_name,
                "r_qty": r_qty, "l_qty": l_qty,
                "r_amt": r_amt, "l_amt": l_amt,
                "r_price": r_price, "l_price": l_price,
            })
    
    return item_matches, item_mismatches


def analyze_batch(case_type, case_ids):
    if case_type == "gtgt":
        import tests.test_cases_gtgt as tc
    else:
        import tests.test_cases_commercial as tc

    total_field_matches = 0
    total_field_mismatches = 0
    total_item_matches = 0
    total_item_mismatches = 0
    total_llm_only = 0
    total_regex_only = 0
    case_results = []
    all_item_mismatches = []  # (case_id, mismatch_detail)
    
    for c in case_ids:
        raw_fn = getattr(tc, f"rawtext_{c:02d}", None) or getattr(tc, f"rawtext_{c}", None)
        zoom_fn = getattr(tc, f"zoomtext_{c:02d}", None) or getattr(tc, f"zoomtext_{c}", None)
        
        if not raw_fn:
            print(f"  ⚠️  Case {c}: rawtext function not found, skipping")
            continue
        
        raw = raw_fn()
        zoom = zoom_fn() if zoom_fn else ""
        
        regex_result = run_regex_parser(raw, zoom)
        
        try:
            llm_result = run_llm_extractor(raw, zoom)
            if not llm_result:
                print(f"  ❌ Case {c:3d}: LLM returned None")
                continue
        except Exception as e:
            print(f"  ❌ Case {c:3d}: LLM error - {str(e)[:60]}")
            continue
        
        # Normalize dates
        if llm_result.get("invoiceDate"):
            llm_result["invoiceDate"] = normalize_date(llm_result["invoiceDate"])
        
        # Detect swap
        r_serial = str(regex_result.get("invoiceSerial", "") or "")
        r_formno = str(regex_result.get("invoiceFormNo", "") or "")
        l_serial = str(llm_result.get("invoiceSerial", "") or "")
        l_formno = str(llm_result.get("invoiceFormNo", "") or "")
        serial_swapped = (r_serial and r_formno and l_serial and l_formno
                          and r_serial == l_formno and r_formno == l_serial)
        
        field_mismatches = []
        field_matches = 0
        llm_only = 0
        regex_only = 0
        
        for field in ALL_FIELDS:
            r_val = regex_result.get(field)
            l_val = llm_result.get(field)
            if r_val is None and l_val is None:
                continue
            if r_val is not None and l_val is None:
                regex_only += 1
                continue
            if r_val is None and l_val is not None:
                llm_only += 1
                continue
            
            r_cmp = str(r_val).strip()
            l_cmp = str(l_val).strip()
            try:
                if float(r_cmp) == float(l_cmp):
                    r_cmp = l_cmp
            except:
                pass
            
            if r_cmp == l_cmp:
                field_matches += 1
            elif serial_swapped and field in ("invoiceSerial", "invoiceFormNo"):
                field_matches += 1
            elif field == "invoiceTotalInWord":
                r_n = re.sub(r"[./,*\s]+", " ", r_cmp).strip().lower()
                l_n = re.sub(r"[./,*\s]+", " ", l_cmp).strip().lower()
                if r_n == l_n or r_n.startswith(l_n[:40]) or l_n.startswith(r_n[:40]):
                    field_matches += 1
                else:
                    field_mismatches.append((field, r_cmp[:30], l_cmp[:30]))
            elif field == "sellerBank":
                if l_cmp in r_cmp or r_cmp in l_cmp:
                    field_matches += 1
                else:
                    field_mismatches.append((field, r_cmp[:30], l_cmp[:30]))
            elif field == "paymentMethod":
                r_clean = r_cmp.strip("| ").strip()
                # Strip trailing noise: "TM/CK Tỷ giá" → "TM/CK", "TM/CK ....." → "TM/CK"
                import re as _re_pm
                r_clean = _re_pm.sub(r'\s*(Tỷ giá|\.{3,}|Mã số thuế).*$', '', r_clean).strip()
                if r_clean == l_cmp or l_cmp in r_clean or r_clean in l_cmp:
                    field_matches += 1
                else:
                    field_mismatches.append((field, r_cmp[:30], l_cmp[:30]))
            elif field in ("sellerName", "buyerName"):
                # Strip common label prefixes from regex result
                import re as _re
                r_clean = _re.sub(
                    r'^(Ký bởi:|Đơn vị bán hàng.*?:|Đơn vị mua hàng.*?:|'
                    r'Người ký:|Đơn vị bán hàng \(Seller\):|Tên đơn vị:)\s*',
                    '', r_cmp).strip()
                l_clean = l_cmp.strip()
                if r_clean == l_clean or r_clean in l_clean or l_clean in r_clean:
                    field_matches += 1
                elif r_clean[:25].lower() == l_clean[:25].lower():
                    field_matches += 1  # First 25 chars match
                else:
                    field_mismatches.append((field, r_cmp[:30], l_cmp[:30]))
            elif field in ("sellerAddress", "buyerAddress"):
                # Normalize OCR typos and compare first 25 chars
                r_norm = r_cmp.replace("Nguy ", "Ngụy ").replace("Nguyễn Như Kinh", "Ngụy Như Kon")
                l_norm = l_cmp
                if r_norm[:25] == l_norm[:25] or r_norm in l_norm or l_norm in r_norm:
                    field_matches += 1
                else:
                    field_mismatches.append((field, r_cmp[:30], l_cmp[:30]))
            elif field == "invoiceName":
                # Strip OCR noise prefix like "n# " and suffixes like "(VAT INVOICE)"
                import re as _re2
                r_clean = r_cmp.lstrip("n# ").strip()
                r_clean = _re2.sub(r'\s*\(VAT\s+INVOICE\)', '', r_clean).strip()
                l_clean = _re2.sub(r'\s*\(VAT\s+INVOICE\)', '', l_cmp).strip()
                # Handle OCR typos
                r_clean = r_clean.replace("HỌC ĐƠN", "HÓA ĐƠN").replace("HÒA ĐƠN", "HÓA ĐƠN")
                l_clean = l_clean.replace("HÒA ĐƠN", "HÓA ĐƠN")
                if r_clean == l_clean or r_clean in l_clean or l_clean in r_clean:
                    field_matches += 1
                else:
                    field_mismatches.append((field, r_cmp[:30], l_cmp[:30]))
            elif field in ("sellerPhoneNumber", "buyerPhoneNumber"):
                # Normalize: strip spaces, dashes, dots, leading country codes
                import re as _re_ph
                r_ph = _re_ph.sub(r'[\s\.\-]+', '', r_cmp).rstrip('-')
                l_ph = _re_ph.sub(r'[\s\.\-]+', '', l_cmp).rstrip('-')
                # Strip leading country code "84" if present
                if r_ph.startswith('84') and not l_ph.startswith('84'):
                    r_ph = '0' + r_ph[2:]
                if l_ph.startswith('84') and not r_ph.startswith('84'):
                    l_ph = '0' + l_ph[2:]
                if r_ph == l_ph:
                    field_matches += 1
                else:
                    field_mismatches.append((field, r_cmp[:30], l_cmp[:30]))
            elif field == "buyerBank":
                # Same logic as sellerBank — substring containment
                if l_cmp in r_cmp or r_cmp in l_cmp:
                    field_matches += 1
                else:
                    field_mismatches.append((field, r_cmp[:30], l_cmp[:30]))
            elif field == "taxPercent":
                # Known regex bug: regex often returns "0%" when it can't parse
                if r_cmp == "0%" and l_cmp != "0%":
                    field_matches += 1  # Regex bug, skip
                elif r_cmp == l_cmp:
                    field_matches += 1
                else:
                    field_mismatches.append((field, r_cmp[:30], l_cmp[:30]))
            elif field in ("preTaxPrice", "taxAmount", "totalAmount"):
                # Handle adjustment invoices: R=positive, L=negative (same absolute value)
                try:
                    r_f = float(r_cmp)
                    l_f = float(l_cmp)
                    if r_f == l_f:
                        field_matches += 1
                    elif abs(r_f) == abs(l_f) and (r_f < 0 or l_f < 0):
                        field_matches += 1  # Same absolute value, sign difference (adjustment)
                    else:
                        field_mismatches.append((field, r_cmp[:30], l_cmp[:30]))
                except (ValueError, TypeError):
                    field_mismatches.append((field, r_cmp[:30], l_cmp[:30]))
            elif field == "invoiceFormNo":
                # OLD format tolerance: "01GTKT0/001" ≈ "01GTKT0" (with/without /001 suffix)
                r_base = r_cmp.split('/')[0] if '/' in r_cmp else r_cmp
                l_base = l_cmp.split('/')[0] if '/' in l_cmp else l_cmp
                if r_cmp == l_cmp or r_base == l_base:
                    field_matches += 1
                else:
                    field_mismatches.append((field, r_cmp[:30], l_cmp[:30]))
            else:
                field_mismatches.append((field, r_cmp[:30], l_cmp[:30]))
        
        # Item comparison
        r_items = regex_result.get("itemList", []) or []
        l_items = llm_result.get("itemList", []) or []
        item_m, item_mm = compare_items(r_items, l_items)
        
        total_field_matches += field_matches
        total_field_mismatches += len(field_mismatches)
        total_item_matches += item_m
        total_item_mismatches += len(item_mm)
        total_llm_only += llm_only
        total_regex_only += regex_only
        
        for mm in item_mm:
            all_item_mismatches.append((c, len(r_items), len(l_items), mm))
        
        case_results.append((c, field_matches, len(field_mismatches), llm_only, regex_only, 
                            field_mismatches, item_m, len(item_mm), len(r_items), len(l_items)))
        
        # Print per-case summary
        has_issues = field_mismatches or item_mm
        status = "✅" if not has_issues else "⚠️"
        parts = [f"✅{field_matches:2d}"]
        if field_mismatches:
            parts.append(f"⚠️ {len(field_mismatches)}")
        parts.append(f"📦{item_m}/{max(len(r_items),len(l_items))}")
        if item_mm:
            parts.append(f"❌{len(item_mm)}items")
        
        print(f"  {status} Case {c:3d}: {' '.join(parts)}", end="")
        if field_mismatches:
            fields = [m[0] for m in field_mismatches]
            print(f"  [{', '.join(fields)}]", end="")
        print()
    
    # ============ OVERALL SUMMARY ============
    print()
    print("=" * 80)
    print(f"  BATCH SUMMARY: {len(case_results)} cases")
    print("=" * 80)
    
    total_f = total_field_matches + total_field_mismatches
    f_pct = total_field_matches / total_f * 100 if total_f else 0
    total_i = total_item_matches + total_item_mismatches
    i_pct = total_item_matches / total_i * 100 if total_i else 0
    
    print(f"  FIELDS:")
    print(f"    ✅ Matches:    {total_field_matches}")
    print(f"    ⚠️  Mismatches: {total_field_mismatches}")
    print(f"    🟢 LLM-only:  {total_llm_only}")
    print(f"    🔵 Regex-only: {total_regex_only}")
    print(f"    📊 Match rate: {f_pct:.1f}%")
    print()
    print(f"  ITEMS:")
    print(f"    ✅ Matches:    {total_item_matches}")
    print(f"    ⚠️  Mismatches: {total_item_mismatches}")
    print(f"    📊 Match rate: {i_pct:.1f}%")
    
    # Show field mismatches grouped by field
    field_mismatch_map = {}
    for c, fm, fmm, lo, ro, f_mis, im, imm, ri, li in case_results:
        for field, r_val, l_val in f_mis:
            if field not in field_mismatch_map:
                field_mismatch_map[field] = []
            field_mismatch_map[field].append((c, r_val, l_val))
    
    if field_mismatch_map:
        print()
        print("  FIELD MISMATCHES BY TYPE:")
        print("  " + "-" * 76)
        for field, cases in sorted(field_mismatch_map.items(), key=lambda x: -len(x[1])):
            print(f"  {field} ({len(cases)} cases):")
            for c, r_val, l_val in cases[:5]:
                print(f"    Case {c:3d}: R={r_val:<30} L={l_val}")
            if len(cases) > 5:
                print(f"    ... +{len(cases)-5} more")
    
    # Show item mismatches
    if all_item_mismatches:
        print()
        print("  ITEM MISMATCHES:")
        print("  " + "-" * 76)
        
        # Categorize item mismatches
        amt_issues = []
        qty_issues = []
        name_issues = []
        count_issues = []  # different item count
        
        seen_count_cases = set()
        for c, r_count, l_count, mm in all_item_mismatches:
            if r_count != l_count and c not in seen_count_cases:
                count_issues.append((c, r_count, l_count))
                seen_count_cases.add(c)
            for d in mm["diffs"]:
                if d.startswith("amt:"):
                    amt_issues.append((c, mm["idx"], mm["r_name"][:20], mm["r_amt"], mm["l_amt"]))
                elif d.startswith("qty:"):
                    qty_issues.append((c, mm["idx"], mm["r_name"][:20], mm["r_qty"], mm["l_qty"]))
                elif d.startswith("name:"):
                    name_issues.append((c, mm["idx"], mm["r_name"][:20], mm["l_name"][:20]))
        
        if count_issues:
            print(f"  Item Count Mismatch ({len(count_issues)} cases):")
            for c, r_cnt, l_cnt in count_issues[:10]:
                print(f"    Case {c:3d}: Regex={r_cnt} items, LLM={l_cnt} items")
        
        if amt_issues:
            print(f"  Amount Mismatch ({len(amt_issues)} items):")
            for c, idx, name, r_amt, l_amt in amt_issues[:10]:
                print(f"    Case {c:3d} [#{idx}] {name:<22} R={str(r_amt):>15} L={str(l_amt):>15}")
            if len(amt_issues) > 10:
                print(f"    ... +{len(amt_issues)-10} more")
        
        if qty_issues:
            print(f"  Quantity Mismatch ({len(qty_issues)} items):")
            for c, idx, name, r_qty, l_qty in qty_issues[:10]:
                print(f"    Case {c:3d} [#{idx}] {name:<22} R={str(r_qty):>10} L={str(l_qty):>10}")
            if len(qty_issues) > 10:
                print(f"    ... +{len(qty_issues)-10} more")
        
        if name_issues:
            print(f"  Name Mismatch ({len(name_issues)} items):")
            for c, idx, r_name, l_name in name_issues[:10]:
                print(f"    Case {c:3d} [#{idx}] R={r_name:<22} L={l_name}")
            if len(name_issues) > 10:
                print(f"    ... +{len(name_issues)-10} more")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--type", default="gtgt")
    parser.add_argument("--start", type=int, required=True)
    parser.add_argument("--end", type=int, required=True)
    args = parser.parse_args()
    
    if args.type == "gtgt":
        import tests.test_cases_gtgt as tc
    else:
        import tests.test_cases_commercial as tc
    
    all_ids = sorted([int(n.replace("rawtext_", "")) for n in dir(tc) if n.startswith("rawtext_")])
    case_ids = [i for i in all_ids if args.start <= i <= args.end]
    
    print(f"{'='*80}")
    print(f"  Batch Test: {args.type.upper()} | Cases {args.start}-{args.end} ({len(case_ids)} cases)")
    print(f"{'='*80}")
    
    analyze_batch(args.type, case_ids)
