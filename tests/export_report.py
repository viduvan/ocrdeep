#!/usr/bin/env python3
"""
Export GTGT Invoice Extraction Report to Excel.
Compares LLM vs Regex results for all test cases.
"""
import sys, os, re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

from tests.test_llm_extraction import run_regex_parser, run_llm_extractor, ALL_FIELDS, normalize_date
import tests.test_cases_gtgt as tc

# ─── Config ──────────────────────────────────────────────────────────────────
ITEM_FIELDS = ["productName", "quantity", "unitPrice", "amount"]

# Styles
HEADER_FILL = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
HEADER_FONT = Font(bold=True, color="FFFFFF", size=10)
MATCH_FILL = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
MISMATCH_FILL = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
LLM_ONLY_FILL = PatternFill(start_color="E2EFDA", end_color="E2EFDA", fill_type="solid")
REGEX_ONLY_FILL = PatternFill(start_color="BDD7EE", end_color="BDD7EE", fill_type="solid")
THIN_BORDER = Border(
    left=Side(style='thin'), right=Side(style='thin'),
    top=Side(style='thin'), bottom=Side(style='thin')
)


def get_case_ids():
    """Find all available test case numbers."""
    case_nums = set()
    for attr in dir(tc):
        m = re.match(r'rawtext_(\d+)', attr)
        if m:
            case_nums.add(int(m.group(1)))
    return sorted(case_nums)


def get_test_data(case_ids):
    """Load test cases and extract both regex and LLM results."""
    results = []
    for i, c in enumerate(case_ids):
        raw_fn = getattr(tc, f"rawtext_{c:02d}", None) or getattr(tc, f"rawtext_{c}", None)
        zoom_fn = getattr(tc, f"zoomtext_{c:02d}", None) or getattr(tc, f"zoomtext_{c}", None)
        if not raw_fn:
            continue

        raw = raw_fn()
        zoom = zoom_fn() if zoom_fn else ""

        print(f"  [{i+1}/{len(case_ids)}] Case {c}...", end='\r')

        regex_result = run_regex_parser(raw, zoom)
        try:
            llm_result = run_llm_extractor(raw, zoom)
            if not llm_result:
                llm_result = {}
        except Exception as e:
            print(f"  Case {c}: LLM error - {e}")
            llm_result = {}

        # Normalize dates
        if llm_result.get("invoiceDate"):
            llm_result["invoiceDate"] = normalize_date(llm_result["invoiceDate"])

        results.append({'case': c, 'regex': regex_result, 'llm': llm_result})

    print(f"\n  ✅ Processed {len(results)} cases.")
    return results


def compare_field(field, r_val, l_val):
    """Compare a single field. Returns (status, r_str, l_str)."""
    if r_val is None and l_val is None:
        return ('skip', '', '')
    if r_val is not None and l_val is None:
        return ('regex_only', str(r_val), '')
    if r_val is None and l_val is not None:
        return ('llm_only', '', str(l_val))

    r_str = str(r_val).strip()
    l_str = str(l_val).strip()

    # Numeric
    try:
        if float(r_str) == float(l_str):
            return ('match', r_str, l_str)
        if abs(float(r_str)) == abs(float(l_str)):
            return ('match', r_str, l_str)
    except:
        pass

    if r_str == l_str:
        return ('match', r_str, l_str)

    return ('mismatch', r_str, l_str)


def create_excel(results, output_path):
    """Create comprehensive Excel report."""
    wb = Workbook()

    # ── Sheet 1: Summary ──────────────────────────────────────────────────────
    ws = wb.active
    ws.title = "Summary"
    ws.sheet_properties.tabColor = "1F4E79"

    ws.merge_cells('A1:F1')
    ws['A1'] = "BÁO CÁO ĐÁNH GIÁ LLM EXTRACTOR - HÓA ĐƠN GTGT"
    ws['A1'].font = Font(bold=True, size=14, color="1F4E79")
    ws['A2'] = f"Tổng số cases: {len(results)} | Model: Qwen3-32B (FPT Cloud)"
    ws['A2'].font = Font(size=11)

    # Per-field stats
    field_stats = {f: {'match': 0, 'mismatch': 0, 'regex_only': 0, 'llm_only': 0} for f in ALL_FIELDS}
    total_m, total_mm = 0, 0
    total_item_m, total_item_mm = 0, 0

    for r in results:
        for field in ALL_FIELDS:
            status, _, _ = compare_field(field, r['regex'].get(field), r['llm'].get(field))
            if status == 'match':
                total_m += 1; field_stats[field]['match'] += 1
            elif status == 'mismatch':
                total_mm += 1; field_stats[field]['mismatch'] += 1
            elif status == 'regex_only':
                field_stats[field]['regex_only'] += 1
            elif status == 'llm_only':
                field_stats[field]['llm_only'] += 1

    # Summary table
    row = 4
    for c, h in enumerate(['Metric', 'Value'], 1):
        cell = ws.cell(row=row, column=c, value=h)
        cell.font = HEADER_FONT; cell.fill = HEADER_FILL; cell.border = THIN_BORDER

    tc_compared = total_m + total_mm
    stats_data = [
        ('Total Cases', len(results)),
        ('Field Matches', total_m),
        ('Field Mismatches', total_mm),
        ('Field Match Rate', f"{total_m/tc_compared*100:.1f}%" if tc_compared else "N/A"),
    ]
    for i, (lab, val) in enumerate(stats_data):
        ws.cell(row=row+1+i, column=1, value=lab).border = THIN_BORDER
        ws.cell(row=row+1+i, column=2, value=val).border = THIN_BORDER

    # Per-field table
    row = 11
    ws.cell(row=row, column=1, value="CHI TIẾT THEO TRƯỜNG").font = Font(bold=True, size=12, color="1F4E79")
    row += 1
    for c, h in enumerate(['Field', 'Match', 'Mismatch', 'Match Rate', 'LLM-only', 'Regex-only'], 1):
        cell = ws.cell(row=row, column=c, value=h)
        cell.font = HEADER_FONT; cell.fill = HEADER_FILL; cell.border = THIN_BORDER

    for i, field in enumerate(ALL_FIELDS):
        r = row + 1 + i
        s = field_stats[field]
        compared = s['match'] + s['mismatch']
        rate = f"{s['match']/compared*100:.1f}%" if compared else "N/A"
        ws.cell(row=r, column=1, value=field).border = THIN_BORDER
        ws.cell(row=r, column=2, value=s['match']).border = THIN_BORDER
        cell_mm = ws.cell(row=r, column=3, value=s['mismatch'])
        cell_mm.border = THIN_BORDER
        if s['mismatch'] > 0:
            cell_mm.fill = MISMATCH_FILL
        ws.cell(row=r, column=4, value=rate).border = THIN_BORDER
        ws.cell(row=r, column=5, value=s['llm_only']).border = THIN_BORDER
        ws.cell(row=r, column=6, value=s['regex_only']).border = THIN_BORDER

    for col_w in [('A', 28), ('B', 10), ('C', 10), ('D', 12), ('E', 10), ('F', 10)]:
        ws.column_dimensions[col_w[0]].width = col_w[1]

    # ── Sheet 2: Field Detail ─────────────────────────────────────────────────
    ws2 = wb.create_sheet("Field Detail")
    ws2.sheet_properties.tabColor = "2E75B6"

    # Headers: Case | field1_Regex | field1_LLM | field1_Match | ...
    headers = ['Case']
    for field in ALL_FIELDS:
        headers.extend([f"{field}_Regex", f"{field}_LLM", f"{field}_Match"])

    for c, h in enumerate(headers, 1):
        cell = ws2.cell(row=1, column=c, value=h)
        cell.font = Font(bold=True, color="FFFFFF", size=8)
        cell.fill = HEADER_FILL
        cell.border = THIN_BORDER
        cell.alignment = Alignment(wrap_text=True, horizontal='center')

    for row_idx, r in enumerate(results, 2):
        ws2.cell(row=row_idx, column=1, value=r['case']).border = THIN_BORDER
        col = 2
        for field in ALL_FIELDS:
            status, r_str, l_str = compare_field(field, r['regex'].get(field), r['llm'].get(field))

            cell_r = ws2.cell(row=row_idx, column=col, value=r_str[:60] if r_str else '')
            cell_l = ws2.cell(row=row_idx, column=col+1, value=l_str[:60] if l_str else '')
            cell_s = ws2.cell(row=row_idx, column=col+2, value='✅' if status == 'match' else ('❌' if status == 'mismatch' else ''))

            for c in [cell_r, cell_l, cell_s]:
                c.border = THIN_BORDER
                c.font = Font(size=8)

            if status == 'mismatch':
                cell_r.fill = MISMATCH_FILL
                cell_l.fill = MISMATCH_FILL
                cell_s.fill = MISMATCH_FILL
            elif status == 'match':
                cell_s.fill = MATCH_FILL

            col += 3

    ws2.freeze_panes = 'B2'
    ws2.column_dimensions['A'].width = 6

    # ── Sheet 3: Items Detail ─────────────────────────────────────────────────
    ws3 = wb.create_sheet("Items Detail")
    ws3.sheet_properties.tabColor = "548235"

    item_headers = ['Case', 'Item#',
                    'Name_Regex', 'Name_LLM', 'Name_Match',
                    'Qty_Regex', 'Qty_LLM', 'Qty_Match',
                    'UnitPrice_Regex', 'UnitPrice_LLM', 'UnitPrice_Match',
                    'Amount_Regex', 'Amount_LLM', 'Amount_Match']
    for c, h in enumerate(item_headers, 1):
        cell = ws3.cell(row=1, column=c, value=h)
        cell.font = Font(bold=True, color="FFFFFF", size=9)
        cell.fill = HEADER_FILL
        cell.border = THIN_BORDER

    item_row = 2
    for r in results:
        r_items = r['regex'].get('itemList', []) or []
        l_items = r['llm'].get('itemList', []) or []
        max_items = max(len(r_items), len(l_items))
        if max_items == 0:
            continue

        for i in range(max_items):
            ri = r_items[i] if i < len(r_items) else {}
            li = l_items[i] if i < len(l_items) else {}

            ws3.cell(row=item_row, column=1, value=r['case']).border = THIN_BORDER
            ws3.cell(row=item_row, column=2, value=i+1).border = THIN_BORDER

            col = 3
            for item_f in ITEM_FIELDS:
                rv = ri.get(item_f)
                lv = li.get(item_f)
                r_str = str(rv)[:40] if rv is not None else ''
                l_str = str(lv)[:40] if lv is not None else ''

                match = False
                if rv is None and lv is None:
                    match = True
                elif rv is not None and lv is not None:
                    try:
                        if abs(float(rv) - float(lv)) < 1:
                            match = True
                    except:
                        if str(rv).strip()[:20].lower() == str(lv).strip()[:20].lower():
                            match = True

                cell_r = ws3.cell(row=item_row, column=col, value=r_str)
                cell_l = ws3.cell(row=item_row, column=col+1, value=l_str)
                cell_m = ws3.cell(row=item_row, column=col+2, value='✅' if match else '❌')

                for c_cell in [cell_r, cell_l, cell_m]:
                    c_cell.border = THIN_BORDER
                    c_cell.font = Font(size=8)

                if not match and (rv is not None or lv is not None):
                    cell_r.fill = MISMATCH_FILL
                    cell_l.fill = MISMATCH_FILL
                    cell_m.fill = MISMATCH_FILL
                elif match and (rv is not None or lv is not None):
                    cell_m.fill = MATCH_FILL

                col += 3
            item_row += 1

    ws3.freeze_panes = 'C2'
    ws3.column_dimensions['A'].width = 6
    ws3.column_dimensions['B'].width = 6
    for cl in ['C', 'D', 'F', 'G', 'I', 'J', 'L', 'M']:
        ws3.column_dimensions[cl].width = 18
    for cl in ['E', 'H', 'K', 'N']:
        ws3.column_dimensions[cl].width = 6

    # Save
    wb.save(output_path)
    print(f"\n✅ Report saved: {output_path}")
    print(f"   Sheets: Summary, Field Detail ({len(results)} rows), Items Detail")


if __name__ == "__main__":
    output = os.path.join(os.path.dirname(__file__), '..', 'gtgt_llm_report.xlsx')
    print("Generating GTGT LLM Extraction Report...")
    print("=" * 60)
    case_ids = get_case_ids()
    print(f"  Found {len(case_ids)} test cases")
    results = get_test_data(case_ids)
    create_excel(results, output)
