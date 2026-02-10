
import re
import json
import pandas as pd
from typing import List, Dict
from src.parsers.block_invoice_parser import parse_invoice_block_based

def load_samples(file_path: str) -> List[Dict]:
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Split by separator
    raw_samples = re.split(r'=== SAMPLE \d+ - [^=]+ ===', content)
    
    # Extract titles to get filenames/IDs
    titles = re.findall(r'=== SAMPLE (\d+) - ([^=]+) ===', content)
    
    # First part is usually empty if file starts with separator
    if not raw_samples[0].strip():
        raw_samples = raw_samples[1:]
    
    samples = []
    for i, raw_text in enumerate(raw_samples):
        if i < len(titles):
            sample_id, filename = titles[i]
            # Remove leading newlines
            text = raw_text.strip()
            if not text:
                continue
                
            samples.append({
                "id": sample_id,
                "filename": filename.strip(),
                "raw_text": text
            })
    return samples

def process_batch(samples: List[Dict], batch_name: str) -> pd.DataFrame:
    print(f"Processing {batch_name} ({len(samples)} samples)...")
    data_list = []
    
    for sample in samples:
        try:
            # Parse
            invoice = parse_invoice_block_based(sample["raw_text"])
            
            # Convert to dict
            data = invoice.model_dump()
            
            # Handle special fields
            row = {
                "Tên file": f"Sample {sample['id']} - {sample['filename']}",
                "draw": sample["raw_text"]
            }
            
            # Flatten invoice fields
            for key, value in data.items():
                if key == "itemList":
                    # Convert list to JSON string for Excel
                    row[key] = json.dumps(value, ensure_ascii=False) if value else ""
                else:
                    row[key] = value
            
            data_list.append(row)
        except Exception as e:
            print(f"Error parsing sample {sample['id']}: {e}")
            row = {
                "Tên file": f"Sample {sample['id']} - {sample['filename']}",
                "draw": sample["raw_text"],
                "error": str(e)
            }
            data_list.append(row)
            
    df = pd.DataFrame(data_list)
    
    # Calculate Statistics Row
    stats = {
        "Tên file": "PERCENTAGE FILLED",
        "draw": ""
    }
    
    total_rows = len(df)
    if total_rows > 0:
        for col in df.columns:
            if col in ["Tên file", "draw", "error"]:
                continue
            
            # Count non-empty/non-none values
            # Empty string, None, NaN treated as empty
            non_empty = df[col].apply(lambda x: x is not None and x != "" and str(x).lower() != "nan").sum()
            percent = (non_empty / total_rows) * 100
            stats[col] = f"{percent:.1f}%"
    
    # Prepend stats row (put at the top)
    df_stats = pd.DataFrame([stats])
    df = pd.concat([df_stats, df], ignore_index=True)
    
    return df

def main():
    input_file = "plain_invoices.txt"
    output_file = "invoice_exportV1.2.xlsx"
    
    print(f"Loading samples from {input_file}...")
    all_samples = load_samples(input_file)
    print(f"Found {len(all_samples)} samples total.")
    
    # Process all samples in one batch
    df1 = process_batch(all_samples, "All Samples")
    
    print(f"Exporting to {output_file}...")
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        df1.to_excel(writer, sheet_name='All Invoices', index=False)
        
    print("Done!")

if __name__ == "__main__":
    main()
