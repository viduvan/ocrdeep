"""
Test parser với nhiều samples hơn để verify toàn bộ
"""
import pandas as pd
import json
from src.parsers.block_invoice_parser import parse_invoice_block_based

def test_all_samples():
    df = pd.read_excel('Case Invoice.xlsx')
    
    print("=" * 80)
    print("FULL INVOICE PARSER TEST - ALL SAMPLES")
    print("=" * 80)
    
    # Test nhiều samples khác nhau
    test_indices = list(range(2, min(40, len(df))))  # Test từ sample 2 đến 39
    
    results = {
        'success': 0,
        'partial': 0,
        'failed': 0,
        'details': []
    }
    
    for idx in test_indices:
        raw_text = df['DRAW_MARKDOWN'].iloc[idx]
        if pd.isna(raw_text):
            continue
            
        file_name = df['TÊN FILE'].iloc[idx]
        
        try:
            invoice = parse_invoice_block_based(raw_text)
            invoice_dict = invoice.model_dump(exclude_none=True)
            
            # Calculate score
            has_seller = bool(invoice.sellerName or invoice.sellerTaxCode)
            has_buyer = bool(invoice.buyerName or invoice.buyerTaxCode or invoice.buyerAddress)
            has_items = len(invoice.itemList) > 0
            has_key_fields = bool(invoice.invoiceID or invoice.invoiceDate or invoice.invoiceName)
            
            score = sum([has_seller, has_buyer, has_items])
            
            status = "✅" if score >= 2 else "⚠️" if score >= 1 else "❌"
            
            if score >= 2:
                results['success'] += 1
            elif score >= 1:
                results['partial'] += 1
            else:
                results['failed'] += 1
            
            # Short summary
            seller_info = invoice.sellerName[:30] if invoice.sellerName else (invoice.sellerTaxCode or "None")
            buyer_info = invoice.buyerName[:30] if invoice.buyerName else (invoice.buyerTaxCode or "None")
            item_count = len(invoice.itemList)
            
            print(f"{status} Sample {idx:2}: Seller={seller_info[:25]:25} | Buyer={buyer_info[:25]:25} | Items={item_count}")
            
            results['details'].append({
                'idx': idx,
                'status': status,
                'seller': has_seller,
                'buyer': has_buyer,
                'items': has_items
            })
            
        except Exception as e:
            print(f"❌ Sample {idx:2}: ERROR - {str(e)[:50]}")
            results['failed'] += 1
    
    print("\n" + "=" * 80)
    print(f"SUMMARY: ✅ Success={results['success']} | ⚠️ Partial={results['partial']} | ❌ Failed={results['failed']}")
    print("=" * 80)


if __name__ == "__main__":
    test_all_samples()
