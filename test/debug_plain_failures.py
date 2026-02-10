
import pandas as pd
from src.parsers.block_invoice_parser import clean_lines, detect_blocks, parse_seller
from src.schemas.invoice import Invoice

def debug_sample(sample_id, index):
    print(f"\n{'='*50}")
    print(f"DEBUGGING SAMPLE {sample_id} (Index {index})")
    print(f"{'='*50}")
    
    try:
        df = pd.read_excel('Case Invoice.xlsx')
        raw_text = df.iloc[index]['DRAW_PLAIN']
        
        print("--- RAW TEXT START ---")
        print(raw_text[:500] + "..." if len(raw_text) > 500 else raw_text)
        print("--- RAW TEXT END ---")
        
        lines = clean_lines(raw_text)
        print(f"\n[Cleaned Lines]: {len(lines)}")
        blocks = detect_blocks(lines)
        
        print("\n--- BLOCKS BREAKDOWN ---")
        for name, blines in blocks.items():
            print(f"[{name.upper()}] ({len(blines)} lines):")
            for l in blines[:5]:
                print(f"  > {l}")
            if len(blines) > 5:
                print("  ... (more)")
                
        # Dry run seller parsing
        inv = Invoice()
        parse_seller(blocks['seller'], inv)
        print(f"\n[PARSED SELLER]: {inv.sellerName}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    # Sample 7 is index 5 (Excel row 7 -> header 1 + index 0 = row 2. Wait.
    # Script test said "Sample 7: 0110255219...".
    # Let's count indices based on test_all_samples mapping or just guess.
    # Inspecting excel usually safe.
    # Sample 2 is index 0. So Sample 7 is index 5.
    # Sample 12 is index 10.
    # Sample 26 is index 24.
    
    debug_sample("Sample 7", 5)
    debug_sample("Sample 12", 10)
    debug_sample("Sample 26", 24)
