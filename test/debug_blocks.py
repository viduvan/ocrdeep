"""
Debug block detection for different invoice formats
"""
import pandas as pd
import re
from typing import List, Dict

def clean_lines(raw_text: str) -> List[str]:
    lines = []
    text = raw_text.replace('\\n', '\n')
    text = re.sub(r'<\|ref\|>.*?<\|/ref\|><\|det\|>.*?<\|/det\|>', '', text)
    text = re.sub(r'<\|[^>]+\|>', '', text)
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = re.sub(r'^#+\s*', '', text, flags=re.MULTILINE)
    
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if re.fullmatch(r"\|[-\s|]+\|", line):
            continue
        if line in ['"', "'"]:
            continue
        lines.append(line)
    return lines


def detect_blocks(lines: List[str]) -> Dict[str, List[str]]:
    blocks = {
        "seller": [],
        "header": [],
        "buyer": [],
        "table": [],
        "total": [],
        "signature": [],
    }

    current = "seller"
    seen_header = False
    seen_table = False
    seller_locked = False
    
    for i, line in enumerate(lines):
        l = line.lower().strip()

        # TABLE
        if "<table>" in l:
            current = "table"
            seen_table = True
        # TOTAL
        elif seen_table and any(k in l for k in [
            "tổng cộng", "tổng tiền", "số tiền viết bằng chữ", "cộng tiền hàng"
        ]):
            current = "total"
        # SIGNATURE
        elif seen_table and any(k in l for k in [
            "signature valid", "ký bởi", "signed", "(ký, ghi rõ họ tên)"
        ]):
            current = "signature"
        # HEADER
        elif any(k in l for k in [
            "hóa đơn giá trị gia tăng", "vat invoice", "kí hiệu", "ký hiệu",
            "mẫu số", "invoice no", "serial no",
        ]):
            current = "header"
            seen_header = True
        # BUYER
        elif seen_header and any(k in l for k in [
            "người mua", "buyer", "họ tên người mua", "customer", "khách hàng"
        ]):
            current = "buyer"
            seller_locked = True

        if current == "seller" and seller_locked:
            continue
            
        blocks[current].append(line)
        print(f"  [{current:8}] Line {i:2}: {line[:60]}...")

    return blocks


# Test each sample
df = pd.read_excel('Case Invoice.xlsx')

for idx in [2, 15]:
    raw_text = df['DRAW_MARKDOWN'].iloc[idx]
    if pd.isna(raw_text):
        continue
    
    file_name = df['TÊN FILE'].iloc[idx]
    
    print("\n" + "=" * 80)
    print(f"SAMPLE {idx}: {file_name}")
    print("=" * 80)
    
    lines = clean_lines(raw_text)
    print(f"\n--- Cleaned Lines ({len(lines)} total) ---")
    for i, line in enumerate(lines[:25]):
        print(f"{i:2}: {line[:80]}")
    
    print(f"\n--- Block Detection ---")
    blocks = detect_blocks(lines)
    
    print(f"\n--- Block Summary ---")
    for block_name, block_lines in blocks.items():
        if block_lines:
            print(f"{block_name}: {len(block_lines)} lines")
