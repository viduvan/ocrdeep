# src/utils/text_extractors.py
import re
from typing import Optional


def extract_phone(line: str) -> Optional[str]:
    """
    Extract ONLY phone number after 'Điện thoại' or 'Tel'
    Ignore Fax
    """
    if not line:
        return None

    m = re.search(
        r"(Điện thoại|Tel|TEL)\s*[:\-]?\s*([\d\.\s\(\)\-]{8,})",
        line,
        re.IGNORECASE,
    )

    if not m:
        return None

    phone_raw = m.group(2)

    # cắt nếu phía sau có Fax
    phone_raw = re.split(r"Fax|FAX", phone_raw)[0]

    phone = re.sub(r"[^\d]", "", phone_raw)

    return phone if len(phone) >= 8 else None
