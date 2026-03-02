#!/usr/bin/env python3
"""
Test script: chạy parse_invoice_block_based với raw_text mẫu
và in ra toàn bộ JSON output để kiểm tra các trường.
"""
import sys
import json
import os

sys.path.insert(0, os.path.dirname(__file__))

from src.parsers.block_invoice_parser import parse_invoice_block_based

# === Case 1 or New Test Case ===
raw_text = r"""
INSERT RAW TEXT HERE
"""

invoice = parse_invoice_block_based(raw_text)

# In ra JSON đầy đủ
result = invoice.dict() if hasattr(invoice, "dict") else invoice.__dict__
print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
