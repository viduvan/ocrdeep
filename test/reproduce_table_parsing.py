
from typing import List
from src.parsers.invoice_table_parser import parse_markdown_table
from src.schemas.invoice_item import InvoiceItem

def test_sample_7_table():
    print("Testing Sample 7 Table Parsing...")
    lines = [
        "| STT (No.) | Tên hàng hóa, dịch vụ (Description) | Đơn vị tính (Unit) | Số lượng (Quantity) | Đơn giá (Unit price) | Thành tiền (Amount) |",
        "| (1)       | (2)                                  | (3)              | (4)               | (5)                 | (6) = (4) x (5)     |",
        "| 1         | Chất kết nối góc Epoxy Sikadur -732 1KG | kg              | 15                | 297.000            | 4.455.000          |"
    ]
    
    items = parse_markdown_table(lines)
    print(f"Items found: {len(items)}")
    for item in items:
        print(item)

def test_sample_12_table():
    print("\nTesting Sample 12 Table Parsing...")
    lines = [
        "|STT|Tên hàng hóa, dịch vụ|Đơn vị tính|Số lượng|Đơn giá|Thành tiền|Thuế suất|Tiền thuế|Thành tiền sau thuế|",
        "|1|2|3|4|5|6 = 4 x 5|7|8 = 6 x 7|9 = 6 + 8|",
        "|1|vữa rót sika Grout 214-11 25KG|KG|1.250|10.185,19|12.731.488|8%|1.018.512|13.750.000|",
        "|2|Phụ gia chống thấm SikaLatex TH-25L|LÍT|25|51.851,85|1.296.296|8%|103.704|1.400.000|",
        "|Cộng tiền hàng hóa, dịch vụ:||||||||14.027.784|1.122.216|15.150.000|"
        
    ]
    items = parse_markdown_table(lines)
    print(f"Items found: {len(items)}")
    for item in items:
        print(item)

if __name__ == "__main__":
    test_sample_7_table()
    test_sample_12_table()
