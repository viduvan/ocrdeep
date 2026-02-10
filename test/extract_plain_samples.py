"""
Extract DRAW_PLAIN column from Case Invoice.xlsx to plain_invoices.txt
"""
import pandas as pd

def extract_plain_text():
    try:
        df = pd.read_excel('Case Invoice.xlsx')
        output_file = 'plain_invoices.txt'
        
        with open(output_file, 'w', encoding='utf-8') as f:
            for idx, row in df.iterrows():
                if pd.notna(row['DRAW_PLAIN']):
                    f.write("=" * 80 + "\n")
                    f.write(f"=== SAMPLE {idx} - {row['TÊN FILE']} ===\n")
                    f.write("=" * 80 + "\n")
                    f.write(str(row['DRAW_PLAIN']) + "\n\n")
                    
        print(f"Successfully extracted {len(df)} samples (Plain Text) to {output_file}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    extract_plain_text()
