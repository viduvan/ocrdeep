import re
from typing import List
from src.schemas.invoice_item import InvoiceItem

def parse_table_from_text(lines: list[str]) -> List[InvoiceItem]:
    items = []

    for line in lines:
        # Bắt dòng bắt đầu bằng STT
        if not re.match(r"^\d+\s+", line):
            continue

        # Tách số ở cuối
        numbers = re.findall(r"\d[\d\.,]*", line)
        if len(numbers) < 3:
            continue

        try:
            quantity = int(numbers[-3].replace(".", "").replace(",", ""))
            unit_price = float(numbers[-2].replace(".", "").replace(",", ""))
            amount = float(numbers[-1].replace(".", "").replace(",", ""))
        except Exception:
            continue

        # Remove numeric tail to get product name
        name_part = line
        for n in numbers[-3:]:
            name_part = name_part.replace(n, "")
        product_name = name_part.strip()

        items.append(InvoiceItem(
            productName=product_name,
            quantity=quantity,
            unitPrice=unit_price,
            amount=amount,
        ))

    return items
