"""
Test Case 79 through LLM extractor (commercial invoice).
Usage: python scratch/test_llm_case79.py
"""
import sys, os, json, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load .env
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, val = line.split('=', 1)
                os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))

from src.extractors.llm_extractor import extract_invoice_llm
from tests.test_cases_commercial import rawtext_79, zoomtext_79

raw = rawtext_79()
zoom = zoomtext_79()

print(f"{'='*80}")
print(f"[79] HS Hyosung Quang Nam 2 — Calling LLM...")
print(f"{'='*80}")

start = time.time()
result = extract_invoice_llm(raw, zoom)
elapsed = time.time() - start

if result is None:
    print(f"  ❌ LLM returned None (elapsed: {elapsed:.1f}s)")
else:
    print(f"  ✅ LLM OK (elapsed: {elapsed:.1f}s)")
    
    items = result.pop('itemList', [])
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    if items:
        print(f"\n  📦 itemList: {len(items)} items")
        for i, item in enumerate(items, 1):
            name = item.get('productName', '?')
            unit = item.get('unit', '')
            qty = item.get('quantity', '')
            price = item.get('unitPrice', '')
            amt = item.get('amount', '')
            print(f"    [{i}] {name} | unit={unit} | qty={qty} | price={price} | amt={amt}")
    
    result['itemList'] = items
