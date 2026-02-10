# src/semantic/cccd_semantic.py
"""Semantic corrections for Vietnamese Citizen ID Card (CCCD) OCR text"""

import re
from typing import Dict, List, Tuple


# Common OCR misreads for Vietnamese text in CCCD
# Format: (wrong, correct)
CCCD_CORRECTIONS: List[Tuple[str, str]] = [
    # ===== Administrative divisions (Địa danh) =====
    # Hưng Yên province districts
    ("Ấn Thị", "Ân Thi"),
    ("Ân Thị", "Ân Thi"),
    ("An Thi", "Ân Thi"),
    
    # Common district/province OCR errors
    ("Thị xã", "Thị xã"),  # Already correct but ensure consistency
    
    # ===== Finger labels (Ngón tay) =====
    ("Ngôn trò", "Ngón trỏ"),
    ("Ngón trò", "Ngón trỏ"),
    ("Ngôn tro", "Ngón trỏ"),
    ("Ngon tro", "Ngón trỏ"),
    ("Ngón tro", "Ngón trỏ"),
    ("ngôn trò", "ngón trỏ"),
    ("ngón trò", "ngón trỏ"),
    
    # ===== Common Vietnamese OCR errors =====
    # Diacritics confusion
    ("quôc tịch", "quốc tịch"),
    ("quôc tich", "quốc tịch"),
    ("Quôc tịch", "Quốc tịch"),
    
    # Common character confusion
    ("công dân", "công dân"),  # Already correct
    
    # ===== ID card specific terms =====
    ("căn cuớc", "căn cước"),
    ("can cuoc", "căn cước"),
    ("Căn Cuớc", "Căn Cước"),
    
    # Date labels
    ("Ngày, tháng, năm", "Ngày, tháng, năm"),  # Already correct
    
    # Personal identification
    ("nhân dạng", "nhân dạng"),  # Already correct
    ("nhan dang", "nhân dạng"),
    
    # Place of residence
    ("nơi thuờng trú", "nơi thường trú"),
    ("noi thuong tru", "nơi thường trú"),
    
    # Gender
    ("Nữ", "Nữ"),  # Already correct
    ("nữ", "nữ"),
]


def semantic_correct_cccd(text: str) -> str:
    """
    Apply semantic corrections to CCCD OCR text.
    
    Args:
        text: Raw OCR text
    
    Returns:
        Corrected text
    """
    if not text:
        return text
    
    corrected = text
    
    for wrong, correct in CCCD_CORRECTIONS:
        if wrong != correct:  # Only apply if actually different
            # Case-sensitive replacement
            corrected = corrected.replace(wrong, correct)
    
    return corrected


def correct_place_names(text: str) -> str:
    """
    Correct Vietnamese administrative place names.
    Uses fuzzy matching for common OCR errors.
    """
    # List of known Vietnamese district/province names that are often misread
    place_corrections = {
        # Hưng Yên districts
        "Ấn Thị": "Ân Thi",
        "Ân Thị": "Ân Thi", 
        "An Thi": "Ân Thi",
        "Ẩn Thi": "Ân Thi",
        
        # Other common misreads (add more as discovered)
        "Thành phó": "Thành phố",
        "Thành pho": "Thành phố",
    }
    
    corrected = text
    for wrong, correct in place_corrections.items():
        corrected = corrected.replace(wrong, correct)
    
    return corrected


def apply_all_corrections(text: str) -> str:
    """Apply all semantic corrections to CCCD text."""
    if not text:
        return text
    
    text = semantic_correct_cccd(text)
    text = correct_place_names(text)
    
    return text
