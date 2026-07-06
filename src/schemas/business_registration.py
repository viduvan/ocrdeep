# src/schemas/business_registration.py
"""Schema for Vietnamese Business Registration Certificate (Giấy đăng ký kinh doanh - ĐKKD)"""

from typing import List, Optional
from pydantic import BaseModel


class AddressDetail(BaseModel):
    """Chi tiết địa chỉ tách cấu trúc (province/district/ward level)"""
    country: Optional[str] = None       # Quốc gia
    province: Optional[str] = None      # Tỉnh/Thành phố
    provinceCode: Optional[str] = None  # Mã tỉnh
    district: Optional[str] = None      # Quận/Huyện
    ward: Optional[str] = None          # Phường/Xã
    street: Optional[str] = None        # Số nhà, đường


class LegalRepresentative(BaseModel):
    """
    Người đại diện theo pháp luật.
    Có thể là mảng (nhiều người đại diện cùng lúc).
    """
    hoVaTen: Optional[str] = None       # Họ và tên
    gioiTinh: Optional[str] = None      # Giới tính (Nam/Nữ)
    chucDanh: Optional[str] = None      # Chức danh (Chủ tịch HĐQT, Tổng giám đốc...)
    ngaySinh: Optional[str] = None      # Ngày sinh (dd/MM/yyyy)
    quocTich: Optional[str] = None      # Quốc tịch
    danToc: Optional[str] = None        # Dân tộc
    loaiGiayTo: Optional[str] = None    # Loại giấy tờ (CMND/CCCD/Hộ chiếu)
    soGiayTo: Optional[str] = None      # Số giấy tờ định danh
    ngayCap: Optional[str] = None       # Ngày cấp giấy tờ
    noiCap: Optional[str] = None        # Nơi cấp
    noiDkHktt: Optional[str] = None     # Nơi đăng ký hộ khẩu thường trú
    diaChiTt: Optional[str] = None      # Địa chỉ thường trú (text đầy đủ)
    chiTietDiaChiTt: Optional[AddressDetail] = None  # Chi tiết địa chỉ thường trú


class CapitalContributor(BaseModel):
    """
    Thành viên góp vốn — mapping từ bảng '4. Danh sách thành viên góp vốn'
    trên giấy ĐKKD (8 cột theo mẫu thực tế):
      STT | Tên thành viên | Quốc tịch | Địa chỉ liên lạc | Phần vốn góp | Tỷ lệ (%) | Số GTPL | Ghi chú
    """
    stt: Optional[int] = None                # STT (số thứ tự)
    tenThanhVien: Optional[str] = None       # Tên thành viên (cá nhân hoặc tổ chức)
    quocTich: Optional[str] = None           # Quốc tịch
    diaChiLienLac: Optional[str] = None      # Địa chỉ liên lạc (cá nhân) / địa chỉ trụ sở chính (tổ chức)
    phanVonGop: Optional[str] = None         # Phần vốn góp (VNĐ và giá trị tương đương ngoại tệ nếu có)
    tyLe: Optional[str] = None               # Tỷ lệ góp vốn (%)
    soGiayToPhapLy: Optional[str] = None     # Số GTPL cá nhân / Mã số DN / Số GTPL tổ chức
    ghiChu: Optional[str] = None             # Ghi chú


class BusinessRegistration(BaseModel):
    """
    Schema cho Giấy chứng nhận đăng ký doanh nghiệp (ĐKKD).

    Field names dùng tiếng Việt để tương thích trực tiếp với
    OcrCorporateBussinessResponse trên BE Spring Boot (FIS/BE-ocr).
    """

    # ===== Thông tin doanh nghiệp =====
    maSoDoanhNghiep: Optional[str] = None          # Mã số DN / Mã số thuế
    tenDoanhNghiep: Optional[str] = None            # Tên doanh nghiệp (tiếng Việt)
    tenDoanhNghiepEn: Optional[str] = None          # Tên doanh nghiệp (tiếng Anh / tên giao dịch)
    tenDoanhNghiepVietTat: Optional[str] = None     # Tên viết tắt
    loaiHinhDoanhNghiep: Optional[str] = None       # Loại hình doanh nghiệp (Công ty CP, TNHH...)
    diaChi: Optional[str] = None                    # Địa chỉ trụ sở chính (text đầy đủ)
    dienThoai: Optional[str] = None                 # Số điện thoại
    email: Optional[str] = None                     # Email
    fax: Optional[str] = None                       # Fax
    website: Optional[str] = None                   # Website

    # ===== Thông tin đăng ký =====
    ngayDangKy: Optional[str] = None               # Ngày đăng ký lần đầu (dd/MM/yyyy)
    lanDangKy: Optional[str] = None                # Lần đăng ký thay đổi (số thứ tự)
    ngayThayDoi: Optional[str] = None              # Ngày thay đổi gần nhất
    noiCapDkkd: Optional[str] = None               # Nơi cấp ĐKKD (Phòng ĐKDD TP/tỉnh...)

    # ===== Thông tin vốn =====
    vonDieuLe: Optional[str] = None                # Vốn điều lệ (giữ nguyên dạng text vì định dạng phức tạp)
    menhGiaCoPhan: Optional[str] = None            # Mệnh giá cổ phần (nếu có)
    tongSoCoPhan: Optional[str] = None             # Tổng số cổ phần (nếu có)

    # ===== Người đại diện pháp luật =====
    nguoiDaiDienPhapLuat: List[LegalRepresentative] = []

    # ===== Chi tiết địa chỉ trụ sở chính =====
    chiTietDiaChi: Optional[AddressDetail] = None

    # ===== Thành viên góp vốn =====
    thanhVienGopVon: List[CapitalContributor] = []
