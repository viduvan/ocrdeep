# src/parsers/cccd_parser.py
"""Parser for Vietnamese Citizen ID Card (CCCD - Căn Cước Công Dân)"""

import re
from typing import Optional
from src.schemas.citizen_id import CitizenID
from src.utils.date_utils import parse_vn_date
from src.semantic.cccd_semantic import apply_all_corrections


def parse_cccd(front_text: str, back_text: Optional[str] = None) -> CitizenID:
    """
    Parse CCCD from OCR text.
    
    Args:
        front_text: OCR text from front side of the card
        back_text: OCR text from back side (optional)
    
    Returns:
        CitizenID object with extracted fields
    """
    cccd = CitizenID()
    
    # Apply semantic corrections to fix common OCR errors
    if front_text:
        front_text = apply_all_corrections(front_text)
    if back_text:
        back_text = apply_all_corrections(back_text)
    
    # ===== FRONT SIDE PARSING =====
    if front_text:
        lines = front_text.splitlines()
        full_text = front_text
        
        # --- ID Number ---
        # Pattern: "Số / No.: 033204006521" or "Số: 033204006521"
        m = re.search(r"(?:Số|No\.?)\s*[:/]?\s*(\d{12})", full_text, re.I)
        if m:
            cccd.idNumber = m.group(1)
        
        # --- Full Name ---
        # Pattern: "Họ và tên / Full name:" followed by name on next line or same line
        for i, line in enumerate(lines):
            if "họ và tên" in line.lower() or "full name" in line.lower():
                # Check if name is on same line after ":"
                m = re.search(r"(?:Họ và tên|Full name)[^:]*:\s*(.+)", line, re.I)
                if m and len(m.group(1).strip()) > 2:
                    cccd.fullName = m.group(1).strip()
                # Check next line
                elif i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    # Name should be uppercase Vietnamese, no keywords
                    if next_line and not any(kw in next_line.lower() for kw in ["ngày", "giới", "quốc", "quê", "nơi", "date", "sex"]):
                        cccd.fullName = next_line
                break
        
        # --- Date of Birth ---
        # Pattern: "Ngày sinh / Date of birth: 01/01/2004"
        m = re.search(r"(?:Ngày sinh|Date of birth)[^:]*:\s*(\d{1,2}/\d{1,2}/\d{4})", full_text, re.I)
        if m:
            cccd.dateOfBirth = parse_vn_date(m.group(1))
        
        # --- Gender ---
        # Pattern: "Giới tính / Sex: Nam"
        m = re.search(r"(?:Giới tính|Sex)[^:]*:\s*(Nam|Nữ|Male|Female)", full_text, re.I)
        if m:
            gender = m.group(1).strip()
            if gender.lower() in ["nam", "male"]:
                cccd.gender = "Nam"
            elif gender.lower() in ["nữ", "female"]:
                cccd.gender = "Nữ"
        
        # --- Nationality ---
        # Pattern: "Quốc tịch / Nationality: Việt Nam"
        m = re.search(r"(?:Quốc tịch|Nationality)[^:]*:\s*(.+?)(?:\n|$)", full_text, re.I)
        if m:
            cccd.nationality = m.group(1).strip()
        
        # --- Place of Origin ---
        # Pattern: "Quê quán / Place of origin:" followed by address
        for i, line in enumerate(lines):
            if "quê quán" in line.lower() or "place of origin" in line.lower():
                # Check if address is on same line
                m = re.search(r"(?:Quê quán|Place of origin)[^:]*:\s*(.+)", line, re.I)
                if m and len(m.group(1).strip()) > 3:
                    cccd.placeOfOrigin = m.group(1).strip()
                # Check next line
                elif i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if next_line and not any(kw in next_line.lower() for kw in ["nơi thường trú", "place of residence"]):
                        cccd.placeOfOrigin = next_line
                break
        
        # --- Place of Residence ---
        # Pattern: "Nơi thường trú / Place of residence:" followed by address
        for i, line in enumerate(lines):
            if "nơi thường trú" in line.lower() or "place of residence" in line.lower():
                m = re.search(r"(?:Nơi thường trú|Place of residence)[^:]*:\s*(.+)", line, re.I)
                if m and len(m.group(1).strip()) > 3:
                    cccd.placeOfResidence = m.group(1).strip()
                elif i + 1 < len(lines):
                    # Collect multi-line address
                    address_parts = []
                    for j in range(i + 1, min(i + 3, len(lines))):
                        next_line = lines[j].strip()
                        if next_line and not any(kw in next_line.lower() for kw in ["có giá trị", "date of expiry"]):
                            address_parts.append(next_line)
                        else:
                            break
                    if address_parts:
                        cccd.placeOfResidence = ", ".join(address_parts)
                break
        
        # --- Date of Expiry ---
        # Pattern: "Có giá trị đến: 01/01/2029" or "Date of expiry: 01/01/2029"
        m = re.search(r"(?:Có giá trị đến|Date of expiry)[^:]*:\s*(\d{1,2}/\d{1,2}/\d{4})", full_text, re.I)
        if m:
            cccd.dateOfExpiry = parse_vn_date(m.group(1))
    
    # ===== BACK SIDE PARSING =====
    if back_text:
        full_text = back_text
        lines = back_text.splitlines()
        
        # --- Personal Identification Features ---
        # Pattern: "Đặc điểm nhân dạng / Personal identification:" followed by description
        for i, line in enumerate(lines):
            if "đặc điểm" in line.lower() or "personal identification" in line.lower():
                m = re.search(r"(?:Đặc điểm nhân dạng|Personal identification)[^:]*:\s*(.+)", line, re.I)
                if m and len(m.group(1).strip()) > 3:
                    cccd.personalIdFeatures = m.group(1).strip()
                elif i + 1 < len(lines):
                    # Collect next 1-2 lines as features description
                    feature_parts = []
                    for j in range(i + 1, min(i + 3, len(lines))):
                        next_line = lines[j].strip()
                        if next_line and not any(kw in next_line.lower() for kw in ["ngày", "date", "cục", "director"]):
                            feature_parts.append(next_line)
                        else:
                            break
                    if feature_parts:
                        cccd.personalIdFeatures = " ".join(feature_parts)
                break
        
        # --- Date of Issue ---
        # Pattern: "Ngày, tháng, năm / Date, month, year: 27/06/2021"
        m = re.search(r"(?:Ngày,?\s*tháng,?\s*năm|Date,?\s*month,?\s*year)[^:]*:\s*(\d{1,2}/\d{1,2}/\d{4})", full_text, re.I)
        if m:
            cccd.dateOfIssue = parse_vn_date(m.group(1))
        
        # --- Issuing Authority ---
        # Pattern: "CỤC TRƯỞNG CỤC CẢNH SÁT..."
        if "CỤC TRƯỞNG" in full_text.upper() or "CỤC CẢNH SÁT" in full_text.upper():
            # Extract the authority name
            m = re.search(r"(CỤC TRƯỞNG CỤC CẢNH SÁT[^\n]+(?:\n[^\n]+)?)", full_text, re.I)
            if m:
                authority = m.group(1).replace("\n", " ").strip()
                # Clean up
                authority = re.sub(r"\s+", " ", authority)
                cccd.issuingAuthority = authority
        
        # --- Card Type Detection ---
        # Check for CCCD chip by looking at MRZ code pattern
        if "IDVNM" in full_text:
            cccd.cardType = "cccd_chip"
        elif "CMND" in full_text.upper():
            cccd.cardType = "cmnd"
        else:
            cccd.cardType = "cccd"
    
    return cccd
