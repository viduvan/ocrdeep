# src/utils/date_utils.py
from datetime import date
import re

def parse_vn_date(text: str) -> date | None:
    """
    Parse Vietnamese date formats:
    - dd/mm/yyyy (or mm/dd/yyyy fallback)
    - Ngày 04 tháng 08 năm 2025
    """
    if not text:
        return None
    
    text = text.strip()

    # Pattern 1: Slash/Dot/Hyphen separated (dd/mm/yyyy)
    m = re.search(r"(\d{1,2})[/\.\-](\d{1,2})[/\.\-](\d{4})", text)
    if m:
        p1, p2, y = map(int, m.groups())
        
        # Priority 1: D/M/Y (Standard VN)
        try:
            return date(y, p2, p1)
        except ValueError:
            pass # Month likely > 12 or invalid day
            
        # Priority 2: M/D/Y (US Format)
        try:
            return date(y, p1, p2) # p1=Month, p2=Day
        except ValueError:
            pass # Invalid date
            
    # Pattern 2: Explicit "Ngày ... tháng ... năm ..."
    m = re.search(
        r"Ngày\s*(\d{1,2})\s*tháng\s*(\d{1,2})\s*năm\s*(\d{4})",
        text,
        re.I,
    )
    if m:
        d, mth, y = map(int, m.groups())
        try:
            return date(y, mth, d)
        except ValueError:
            pass

    return None
