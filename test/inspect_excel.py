
import pandas as pd
try:
    df = pd.read_excel('Case Invoice.xlsx')
    print(f"Total Rows: {len(df)}")
    print(f"Columns: {list(df.columns)}")
    print("-" * 50)
    for col in df.columns:
        non_null = df[col].count()
        print(f"Column '{col}': {non_null} non-null values")
        if df[col].dtype == object and len(df) > 0:
             print(f"  Sample: {str(df[col].iloc[0])[:100]}")
except Exception as e:
    print(f"Error reading excel: {e}")
