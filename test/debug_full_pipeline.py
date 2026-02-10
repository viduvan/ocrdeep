
import pandas as pd
from src.parsers.block_invoice_parser import parse_invoice_block_based

def debug_full_run():
    print("Loading data...")
    df = pd.read_excel('Case Invoice.xlsx')
    
    # Sample 7 is index 5
    print("\nXXX DEBUGGING SAMPLE 7 XXX")
    raw7 = df.iloc[5]['DRAW_PLAIN']
    inv7 = parse_invoice_block_based(raw7)
    print(f"Items: {len(inv7.itemList)}")
    for item in inv7.itemList:
        print(f" - {item}")

    # Sample 26 is index 24
    print("\nXXX DEBUGGING SAMPLE 26 XXX")
    raw26 = df.iloc[24]['DRAW_PLAIN']
    inv26 = parse_invoice_block_based(raw26)
    print(f"Items: {len(inv26.itemList)}")
    for item in inv26.itemList:
        print(f" - {item}")

if __name__ == "__main__":
    debug_full_run()
