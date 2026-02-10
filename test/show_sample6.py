"""
Show Sample 6 details
"""
import pandas as pd
import re

df = pd.read_excel('Case Invoice.xlsx')

# Sample 6
raw = df['DRAW_MARKDOWN'].iloc[6]
file_name = df['TÊN FILE'].iloc[6]

print("=" * 80)
print(f"SAMPLE 6: {file_name}")
print("=" * 80)

# Clean
text = raw.replace('\\n', '\n')
text = re.sub(r'<\|ref\|>.*?<\|/ref\|><\|det\|>.*?<\|/det\|>', '', text)
text = re.sub(r'<\|[^>]+\|>', '', text)
text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
text = re.sub(r'^#+\s*', '', text, flags=re.MULTILINE)

lines = [l.strip() for l in text.splitlines() if l.strip() and l.strip() not in ['"', "'"]]

print(f"\n--- All {len(lines)} Cleaned Lines ---")
for i, l in enumerate(lines):
    print(f"{i:2}: {l[:100]}")
