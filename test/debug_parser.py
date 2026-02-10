"""
Debug script để xem dữ liệu sau khi clean
"""
import pandas as pd
import re
from typing import List

def clean_lines(raw_text: str) -> List[str]:
    lines = []
    
    # Xử lý escape sequences từ OCR output
    text = raw_text.replace('\\n', '\n')
    
    # Remove OCR metadata tags
    text = re.sub(r'<\|ref\|>.*?<\|/ref\|><\|det\|>.*?<\|/det\|>', '', text)
    text = re.sub(r'<\|[^>]+\|>', '', text)
    
    # Remove markdown bold markers
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    
    # Remove markdown headers
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


# Load test case
df = pd.read_excel('Case Invoice.xlsx')
raw_text = df['DRAW_MARKDOWN'].iloc[5]

print("=" * 80)
print("RAW TEXT (first 500 chars):")
print("=" * 80)
print(raw_text[:500])

print("\n" + "=" * 80)
print("CLEANED LINES:")
print("=" * 80)
lines = clean_lines(raw_text)
for i, line in enumerate(lines[:30]):
    print(f"{i}: {line[:100]}")

# Test detect_blocks logic
print("\n" + "=" * 80)
print("KEYWORD DETECTION:")
print("=" * 80)

keywords_to_check = [
    "hóa đơn giá trị gia tăng",
    "vat invoice",
    "ký hiệu",
    "kí hiệu", 
    "serial",
    "đơn vị bán",
    "mã số thuế",
    "người mua",
    "tổng cộng"
]

for line in lines:
    low = line.lower()
    for kw in keywords_to_check:
        if kw in low:
            print(f"Found '{kw}' in: {line[:80]}")
