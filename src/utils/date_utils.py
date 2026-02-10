# src/utils/date_utils.py
from datetime import date
import re

def parse_vn_date(text: str) -> date | None:
    """
    Parse Vietnamese date formats:
    - dd/mm/yyyy
    - Ngày 04 tháng 08 năm 2025
    """
    if not text:
        return None

    # dd/mm/yyyy
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", text)
    if m:
        d, mth, y = map(int, m.groups())
        return date(y, mth, d)

    # Ngày 04 tháng 08 năm 2025
    m = re.search(
        r"Ngày\s*(\d{1,2})\s*tháng\s*(\d{1,2})\s*năm\s*(\d{4})",
        text,
        re.I,
    )
    if m:
        d, mth, y = map(int, m.groups())
        return date(y, mth, d)

    return None
