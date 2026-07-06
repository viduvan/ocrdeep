# src/parsers/dkkd_parser.py
"""
Regex-based fallback parser for Vietnamese Business Registration Certificate (Giấy ĐKKD).
Used when LLM extraction fails or returns None.

Pattern: follows cccd_parser.py structure.
"""

import re
from typing import List, Optional

from src.schemas.business_registration import (
    BusinessRegistration,
    LegalRepresentative,
    CapitalContributor,
)


# ── Helper utilities ───────────────────────────────────────────────────────────

def _extract_field(text: str, *patterns: str) -> Optional[str]:
    """
    Try multiple label patterns and return the value on the same line (or next line).
    Returns cleaned string or None.
    """
    for pattern in patterns:
        # Same-line extraction: "Label: value"
        m = re.search(
            rf'(?:{pattern})\s*:?\s*(.+?)(?:\r?\n|$)',
            text,
            re.IGNORECASE,
        )
        if m:
            val = m.group(1).strip()
            # Strip leading label repetition: "Tên doanh nghiệp: CÔNG TY..." → "CÔNG TY..."
            # Sometimes OCR duplicates the label on the value line
            for pat in patterns:
                val = re.sub(rf'^{pat}\s*:?\s*', '', val, flags=re.IGNORECASE).strip()
            # Strip trailing noise (dots, colons, semicolons)
            val = re.sub(r'[.;]+$', '', val).strip()
            if val:
                return val
    return None


def _normalize_date(date_str: Optional[str]) -> Optional[str]:
    """
    Normalize various Vietnamese date formats to dd/MM/yyyy.
    E.g., "ngày 15 tháng 3 năm 2024" → "15/03/2024"
    """
    if not date_str:
        return None

    date_str = date_str.strip()

    # Already in dd/MM/yyyy format
    m = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{4})$', date_str)
    if m:
        d, mo, y = m.group(1), m.group(2), m.group(3)
        return f"{int(d):02d}/{int(mo):02d}/{y}"

    # "ngày X tháng Y năm Z" format
    m = re.search(r'ngày\s*(\d{1,2})\s*tháng\s*(\d{1,2})\s*năm\s*(\d{4})', date_str, re.IGNORECASE)
    if m:
        d, mo, y = m.group(1), m.group(2), m.group(3)
        return f"{int(d):02d}/{int(mo):02d}/{y}"

    # dd-MM-yyyy
    m = re.match(r'^(\d{1,2})-(\d{1,2})-(\d{4})$', date_str)
    if m:
        d, mo, y = m.group(1), m.group(2), m.group(3)
        return f"{int(d):02d}/{int(mo):02d}/{y}"

    return date_str  # Return as-is if unrecognized


# ── Main enterprise info parser ────────────────────────────────────────────────

def _parse_enterprise_info(text: str, biz: BusinessRegistration) -> None:
    """Extract top-level enterprise fields from OCR text."""

    # Mã số doanh nghiệp / Mã số thuế
    biz.maSoDoanhNghiep = _extract_field(
        text,
        r'Mã số doanh nghiệp',
        r'Mã số thuế',
        r'MST',
    )

    # Tên doanh nghiệp
    biz.tenDoanhNghiep = _extract_field(
        text,
        r'Tên doanh nghiệp',
        r'Tên công ty',
    )

    # Tên tiếng Anh / giao dịch
    biz.tenDoanhNghiepEn = _extract_field(
        text,
        r'Tên(?:\s+doanh\s+nghiệp)?\s+(?:bằng\s+)?tiếng\s+(?:nước\s+ngoài|Anh)',
        r'Tên giao dịch',
        r'Tên nước ngoài',
    )

    # Tên viết tắt
    biz.tenDoanhNghiepVietTat = _extract_field(
        text,
        r'Tên viết tắt',
    )

    # Loại hình doanh nghiệp
    biz.loaiHinhDoanhNghiep = _extract_field(
        text,
        r'Loại hình doanh nghiệp',
        r'Loại hình',
    )

    # Địa chỉ trụ sở chính
    biz.diaChi = _extract_field(
        text,
        r'Địa chỉ trụ sở chính',
        r'Địa chỉ',
    )

    # Điện thoại
    biz.dienThoai = _extract_field(
        text,
        r'Điện thoại',
        r'Tel',
        r'Phone',
        r'ĐT',
    )

    # Email
    biz.email = _extract_field(text, r'E-?mail')

    # Fax
    biz.fax = _extract_field(text, r'Fax')

    # Website
    biz.website = _extract_field(text, r'Website', r'Web')

    # Vốn điều lệ
    biz.vonDieuLe = _extract_field(text, r'Vốn điều lệ')

    # Mệnh giá cổ phần
    biz.menhGiaCoPhan = _extract_field(text, r'Mệnh giá cổ phần')

    # Tổng số cổ phần
    biz.tongSoCoPhan = _extract_field(text, r'Tổng số cổ phần')

    # Ngày đăng ký lần đầu
    ngay_dau = _extract_field(
        text,
        r'Đăng ký lần đầu ngày',
        r'Ngày cấp lần đầu',
        r'Đăng ký lần đầu',
    )
    biz.ngayDangKy = _normalize_date(ngay_dau)

    # Lần đăng ký thay đổi
    m = re.search(
        r'(?:Đăng ký thay đổi lần thứ|Lần thứ)[:\s]*(\d+)',
        text, re.IGNORECASE
    )
    if m:
        biz.lanDangKy = m.group(1).strip()

    # Ngày thay đổi — extract date from the registration header line
    # Pattern: "ngày ... tháng ... năm ..." near "Đăng ký thay đổi lần thứ"
    m = re.search(
        r'(?:Đăng ký thay đổi.*?|Thay đổi lần.*?)'
        r'ngày\s*(\d{1,2})\s*tháng\s*(\d{1,2})\s*năm\s*(\d{4})',
        text, re.IGNORECASE | re.DOTALL
    )
    if m:
        d, mo, y = m.group(1), m.group(2), m.group(3)
        biz.ngayThayDoi = f"{int(d):02d}/{int(mo):02d}/{y}"
    else:
        raw = _extract_field(text, r'Ngày thay đổi', r'Ngày đăng ký thay đổi')
        biz.ngayThayDoi = _normalize_date(raw)

    # Nơi cấp ĐKKD
    biz.noiCapDkkd = _extract_field(
        text,
        r'Phòng Đăng ký kinh doanh',
        r'Nơi cấp',
        r'Sở Kế hoạch',
    )


# ── Legal representative parser ────────────────────────────────────────────────

def _parse_legal_representatives(text: str) -> List[LegalRepresentative]:
    """
    Extract legal representative blocks.
    Handles multiple representatives separated by known section markers.
    """
    reps = []

    # Split text at each representative header
    # Pattern: "Người đại diện theo pháp luật" or numbered like "2. Người đại diện..."
    split_pattern = re.compile(
        r'(?:^|\n)\s*\d*\.?\s*Người đại diện(?:\s+theo)?\s+pháp\s+luật',
        re.IGNORECASE,
    )
    parts = split_pattern.split(text)

    # Skip the first part (text before any representative section)
    rep_parts = parts[1:] if len(parts) > 1 else []

    # If no split found, try to extract from the whole text
    if not rep_parts:
        if re.search(r'Người đại diện(?:\s+theo)?\s+pháp\s+luật', text, re.IGNORECASE):
            rep_parts = [text]

    for part in rep_parts:
        rep = LegalRepresentative()

        rep.hoVaTen = _extract_field(part, r'Họ và tên', r'Họ tên')
        rep.gioiTinh = _extract_field(part, r'Giới tính')
        rep.chucDanh = _extract_field(part, r'Chức danh', r'Chức vụ')

        raw_birth = _extract_field(part, r'Sinh ngày', r'Ngày sinh')
        rep.ngaySinh = _normalize_date(raw_birth)

        rep.quocTich = _extract_field(part, r'Quốc tịch')
        rep.danToc = _extract_field(part, r'Dân tộc')
        rep.loaiGiayTo = _extract_field(
            part,
            r'Loại giấy tờ pháp lý',
            r'Loại giấy tờ',
            r'Giấy tờ pháp lý',
        )
        rep.soGiayTo = _extract_field(
            part,
            r'Số CCCD',
            r'Số CMND',
            r'Số Hộ chiếu',
            r'CMND/CCCD số',
            r'Số giấy tờ',
        )

        raw_issue = _extract_field(part, r'Ngày cấp')
        rep.ngayCap = _normalize_date(raw_issue)

        rep.noiCap = _extract_field(part, r'Nơi cấp')
        rep.noiDkHktt = _extract_field(
            part,
            r'Nơi đăng ký hộ khẩu thường trú',
            r'ĐKHKTT',
            r'Hộ khẩu thường trú',
        )
        rep.diaChiTt = _extract_field(
            part,
            r'Địa chỉ thường trú',
            r'Chỗ ở hiện tại',
            r'Nơi ở hiện nay',
        )

        # Only add if we got at least the name
        if rep.hoVaTen:
            reps.append(rep)

    return reps


# ── Capital contributors table parser ─────────────────────────────────────────

def _parse_capital_contributors(text: str) -> List[CapitalContributor]:
    """
    Extract capital contributors from the table section.
    Table header: STT | Tên thành viên | Quốc tịch | Địa chỉ | Phần vốn góp | Tỷ lệ | Số GTPL | Ghi chú

    The table may appear as:
    - Pipe-delimited text from markdown OCR
    - Space-aligned plain text
    - Line-by-line key-value pairs
    """
    contributors = []

    # Find the capital contributors section
    section_match = re.search(
        r'(?:Danh sách thành viên góp vốn|danh sách thành viên góp vốn)(.*?)(?:\n\s*\n\s*\n|\Z)',
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if not section_match:
        return contributors

    table_text = section_match.group(1)

    # Strategy 1: Pipe-delimited table rows (from markdown OCR mode)
    pipe_rows = re.findall(r'\|(.+?)\|(.+?)\|(.+?)\|(.+?)\|(.+?)\|(.+?)\|(.+?)\|', table_text)
    if pipe_rows:
        for row in pipe_rows:
            cells = [c.strip() for c in row]
            if len(cells) < 7:
                continue
            # Skip header rows
            if re.search(r'STT|Tên thành viên|Quốc tịch', cells[0], re.IGNORECASE):
                continue
            # Skip empty rows
            if not any(cells):
                continue

            try:
                stt_val = int(cells[0]) if cells[0].isdigit() else None
            except (ValueError, IndexError):
                stt_val = None

            contrib = CapitalContributor(
                stt=stt_val,
                tenThanhVien=cells[1] or None,
                quocTich=cells[2] or None,
                diaChiLienLac=cells[3] or None,
                phanVonGop=cells[4] or None,
                tyLe=cells[5] or None,
                soGiayToPhapLy=cells[6] or None,
                ghiChu=cells[7].strip() if len(cells) > 7 and cells[7].strip() else None,
            )
            if contrib.tenThanhVien:
                contributors.append(contrib)
        if contributors:
            return contributors

    # Strategy 2: Look for numbered rows (plain text)
    # Pattern: "1. Nguyễn Văn A ..." or "1 Nguyễn Văn A ..."
    row_pattern = re.compile(
        r'^(\d+)[.\s]+(.+?)$',
        re.MULTILINE,
    )
    rows = row_pattern.findall(table_text)
    for stt_str, content in rows:
        contrib = CapitalContributor()
        try:
            contrib.stt = int(stt_str)
        except ValueError:
            pass

        # Try to extract sub-fields from the content line
        contrib.tenThanhVien = content.strip() if content.strip() else None

        # Look for percentage nearby
        m = re.search(r'(\d+[\.,]?\d*)\s*%', content)
        if m:
            contrib.tyLe = m.group(0).strip()

        if contrib.tenThanhVien:
            contributors.append(contrib)

    return contributors


# ── Main public API ────────────────────────────────────────────────────────────

def parse_dkkd(raw_text: str) -> BusinessRegistration:
    """
    Parse business registration certificate from OCR text using regex patterns.
    Used as fallback when LLM extraction fails.

    Args:
        raw_text: Full OCR text (all pages combined, may contain --- PAGE N --- markers)

    Returns:
        BusinessRegistration object with extracted fields (some may be None if not found)
    """
    biz = BusinessRegistration()

    # Parse enterprise info from the full text
    _parse_enterprise_info(raw_text, biz)

    # Parse legal representatives
    biz.nguoiDaiDienPhapLuat = _parse_legal_representatives(raw_text)

    # Parse capital contributors table (usually on page 2)
    biz.thanhVienGopVon = _parse_capital_contributors(raw_text)

    return biz
