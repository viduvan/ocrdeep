import pandas as pd

df = pd.read_excel('Case Invoice.xlsx')

# Lưu các mẫu rawtext vào file txt để xem
with open('sample_invoices.txt', 'w', encoding='utf-8') as f:
    for i in [2, 5, 10, 15, 20, 30]:
        val = df['DRAW_MARKDOWN'].iloc[i] if i < len(df) and pd.notna(df['DRAW_MARKDOWN'].iloc[i]) else None
        if val:
            f.write(f"\n{'='*80}\n")
            f.write(f"=== SAMPLE {i} - {df['TÊN FILE'].iloc[i]} ===\n")
            f.write(f"{'='*80}\n")
            f.write(val)
            f.write("\n\n")

print("Done! Check sample_invoices.txt")
