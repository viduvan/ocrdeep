"""
Test script for improved invoice parser
"""
import pandas as pd
import json
from src.parsers.block_invoice_parser import parse_invoice_block_based

def test_parser():
    # Load test cases from Excel
    df = pd.read_excel('Case Invoice.xlsx')
    
    print("=" * 80)
    print("INVOICE PARSER TEST")
    print("=" * 80)
    
    test_indices = [2, 5, 10, 15, 20, 30]
    
    for idx in test_indices:
        if idx >= len(df):
            continue
            
        raw_text = df['DRAW_MARKDOWN'].iloc[idx]
        if pd.isna(raw_text):
            continue
            
        file_name = df['TÊN FILE'].iloc[idx]
        
        print(f"\n{'='*80}")
        print(f"Sample {idx}: {file_name}")
        print("=" * 80)
        
        try:
            invoice = parse_invoice_block_based(raw_text)
            
            # Convert to dict for display
            invoice_dict = invoice.model_dump(exclude_none=True)
            
            # Check key fields
            print("\n--- KEY FIELDS ---")
            print(f"invoiceID: {invoice.invoiceID}")
            print(f"invoiceSerial: {invoice.invoiceSerial}")
            print(f"invoiceFormNo: {invoice.invoiceFormNo}")
            print(f"invoiceDate: {invoice.invoiceDate}")
            print(f"invoiceName: {invoice.invoiceName}")
            print(f"paymentMethod: {invoice.paymentMethod}")
            print(f"currency: {invoice.currency}")
            
            print("\n--- SELLER ---")
            print(f"sellerName: {invoice.sellerName}")
            print(f"sellerTaxCode: {invoice.sellerTaxCode}")
            print(f"sellerEmail: {invoice.sellerEmail}")
            print(f"sellerBank: {invoice.sellerBank}")
            print(f"sellerBankAccountNumber: {invoice.sellerBankAccountNumber}")
            
            print("\n--- BUYER ---")
            print(f"buyerName: {invoice.buyerName}")
            print(f"buyerTaxCode: {invoice.buyerTaxCode}")
            print(f"buyerEmail: {invoice.buyerEmail}")
            print(f"buyerAddress: {invoice.buyerAddress}")
            
            print("\n--- AMOUNTS ---")
            print(f"preTaxPrice: {invoice.preTaxPrice}")
            print(f"taxPercent: {invoice.taxPercent}")
            print(f"taxAmount: {invoice.taxAmount}")
            print(f"totalAmount: {invoice.totalAmount}")
            print(f"invoiceTotalInWord: {invoice.invoiceTotalInWord}")
            
            print("\n--- ITEMS ---")
            for i, item in enumerate(invoice.itemList, 1):
                print(f"  Item {i}: {item.productName} | Qty: {item.quantity} | Unit: {item.unit} | Price: {item.unitPrice} | Amount: {item.amount}")
            
            print("\n--- FULL JSON ---")
            print(json.dumps(invoice_dict, ensure_ascii=False, indent=2, default=str))
            
        except Exception as e:
            print(f"ERROR: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    test_parser()
