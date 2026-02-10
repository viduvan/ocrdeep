# src/schemas/citizen_id.py
"""Schema for Vietnamese Citizen ID Card (CCCD - Căn Cước Công Dân)"""

from typing import Optional
from pydantic import BaseModel, field_serializer
from datetime import date


class CitizenID(BaseModel):
    """
    Vietnamese Citizen ID Card schema.
    Supports both front and back sides of the card.
    """
    
    # ===== Front Side (Mặt trước) =====
    idNumber: Optional[str] = None  # Số CCCD (12 digits)
    fullName: Optional[str] = None  # Họ và tên
    dateOfBirth: Optional[date] = None  # Ngày sinh
    gender: Optional[str] = None  # Giới tính (Nam/Nữ)
    nationality: Optional[str] = None  # Quốc tịch
    placeOfOrigin: Optional[str] = None  # Quê quán
    placeOfResidence: Optional[str] = None  # Nơi thường trú
    
    # ===== Back Side (Mặt sau) =====
    dateOfExpiry: Optional[date] = None  # Có giá trị đến
    personalIdFeatures: Optional[str] = None  # Đặc điểm nhận dạng
    dateOfIssue: Optional[date] = None  # Ngày cấp
    
    # ===== Metadata =====
    cardType: Optional[str] = None  # Loại thẻ: "cccd_chip", "cmnd", etc.
    issuingAuthority: Optional[str] = None  # Cơ quan cấp
    
    # Date serializers
    @field_serializer('dateOfBirth', 'dateOfExpiry', 'dateOfIssue')
    def serialize_date(self, dt: date | str | None, _info):
        if not dt:
            return None
        if isinstance(dt, date):
            return dt.strftime('%d/%m/%Y')
        if isinstance(dt, str):
            try:
                from datetime import datetime
                parsed = datetime.strptime(dt, "%Y-%m-%d")
                return parsed.strftime('%d/%m/%Y')
            except ValueError:
                return dt
        return str(dt)
