"""
Test cases 179-183 through LLM extractor.
Usage: python tests/test_llm_cases.py
"""
import sys
import os
import json
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load .env if exists
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, val = line.split('=', 1)
                os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))

from src.extractors.llm_extractor import extract_invoice_llm
from tests.test_cases_gtgt import (
    rawtext_179, zoomtext_179,
    rawtext_180, zoomtext_180,
    rawtext_181, zoomtext_181,
    rawtext_182, zoomtext_182,
    rawtext_183, zoomtext_183,
    rawtext_184, zoomtext_184,
)

CASES = [
    (179, 'Hóa đơn VN (1).png', rawtext_179, zoomtext_179),
    (180, 'Hóa đơn VN (2).png', rawtext_180, zoomtext_180),
    (181, 'Hóa đơn VN (3).png', rawtext_181, zoomtext_181),
    (182, 'hóa đơn VN (4).png', rawtext_182, zoomtext_182),
    (183, 'Hóa đơn Việt Nam 5.png', rawtext_183, zoomtext_183),
    (184, 'VND.pdf', rawtext_184, zoomtext_184),
]


def main():
    import sys
    target_case = int(sys.argv[1]) if len(sys.argv) > 1 else None
    for case_id, filename, rawtext_fn, zoomtext_fn in CASES:
        if target_case is not None and case_id != target_case:
            continue
        raw = rawtext_fn()
        zoom = zoomtext_fn()
        
        print(f"\n{'='*80}")
        print(f"[{case_id}] {filename} — Calling LLM...")
        print(f"{'='*80}")
        
        start = time.time()
        result = extract_invoice_llm(raw, zoom)
        elapsed = time.time() - start
        
        if result is None:
            print(f"  ❌ LLM returned None (elapsed: {elapsed:.1f}s)")
            continue
        
        print(f"  ✅ LLM OK (elapsed: {elapsed:.1f}s)")
        
        # Pretty print the result (excluding itemList for brevity first)
        items = result.pop('itemList', [])
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
        # Print items separately
        if items:
            print(f"\n  📦 itemList: {len(items)} items")
            for i, item in enumerate(items, 1):
                name = item.get('productName', '?')
                unit = item.get('unit', '')
                qty = item.get('quantity', '')
                price = item.get('unitPrice', '')
                amt = item.get('amount', '')
                print(f"    [{i}] {name} | unit={unit} | qty={qty} | price={price} | amt={amt}")
        
        # Restore for completeness
        result['itemList'] = items
        print()


if __name__ == '__main__':
    main()
