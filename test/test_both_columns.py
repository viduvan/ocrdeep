"""
Test parser trên cả cột DRAW_MARKDOWN và DRAW_PLAIN
"""
import pandas as pd
import json
from src.parsers.block_invoice_parser import parse_invoice_block_based
from src.schemas.invoice import Invoice

def test_both_columns():
    df = pd.read_excel('Case Invoice.xlsx')
    
    print("=" * 100)
    print("FULL INVOICE PARSER TEST - BOTH COLUMNS (MARKDOWN & PLAIN)")
    print("=" * 100)
    
    test_indices = list(range(2, min(40, len(df))))
    
    results = {
        'markdown': {'success': 0, 'failed': 0, 'empty': 0},
        'plain': {'success': 0, 'failed': 0, 'empty': 0}
    }
    
    for idx in test_indices:
        print(f"\n--- Sample {idx}: {df['TÊN FILE'].iloc[idx]} ---")
        
        # Test MARKDOWN
        try:
            raw_md = df['DRAW_MARKDOWN'].iloc[idx]
            if pd.isna(raw_md):
                print(f"  [MD]    SKIP (Empty)")
                results['markdown']['empty'] += 1
            else:
                inv_md = parse_invoice_block_based(raw_md)
                score_md = sum([
                    bool(inv_md.sellerName or inv_md.sellerTaxCode),
                    bool(inv_md.buyerName or inv_md.buyerTaxCode),
                    len(inv_md.itemList) > 0
                ])
                status_md = "✅" if score_md >= 2 else "❌"
                print(f"  [MD]    {status_md} Items={len(inv_md.itemList)} | Seller={str(inv_md.sellerName)[:20]}...")
                if status_md == "✅": results['markdown']['success'] += 1
                else: results['markdown']['failed'] += 1
        except Exception as e:
            print(f"  [MD]    ❌ ERROR: {e}")
            results['markdown']['failed'] += 1
            
        # Test PLAIN
        try:
            raw_pl = df['DRAW_PLAIN'].iloc[idx]
            if pd.isna(raw_pl):
                print(f"  [PLAIN] SKIP (Empty)")
                results['plain']['empty'] += 1
            else:
                inv_pl = parse_invoice_block_based(raw_pl)
                score_pl = sum([
                    bool(inv_pl.sellerName or inv_pl.sellerTaxCode),
                    bool(inv_pl.buyerName or inv_pl.buyerTaxCode),
                    len(inv_pl.itemList) > 0
                ])
                status_pl = "✅" if score_pl >= 2 else "❌"
                print(f"  [PLAIN] {status_pl} Items={len(inv_pl.itemList)} | Seller={str(inv_pl.sellerName)[:20]}...")
                if status_pl == "✅": results['plain']['success'] += 1
                else: results['plain']['failed'] += 1
        except Exception as e:
            print(f"  [PLAIN] ❌ ERROR: {e}")
            results['plain']['failed'] += 1

    print("\n" + "=" * 100)
    print(f"SUMMARY MARKDOWN: ✅ {results['markdown']['success']} | ❌ {results['markdown']['failed']} | ⚪ {results['markdown']['empty']}")
    print(f"SUMMARY PLAIN:    ✅ {results['plain']['success']} | ❌ {results['plain']['failed']} | ⚪ {results['plain']['empty']}")
    print("=" * 100)

if __name__ == "__main__":
    test_both_columns()
