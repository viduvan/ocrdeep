"""
Debug Sample 10 specifically and test more samples
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


# Test Sample 10
df = pd.read_excel('Case Invoice.xlsx')

print("=" * 80)
print("SAMPLE 10 DEBUG")
print("=" * 80)

raw_text = df['DRAW_MARKDOWN'].iloc[10]
if pd.notna(raw_text):
    lines = clean_lines(raw_text)
    print(f"\n--- All {len(lines)} Cleaned Lines ---")
    for i, line in enumerate(lines):
        print(f"{i:2}: {line[:100]}")
