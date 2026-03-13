# src/schemas/bill_of_lading.py
from typing import List, Optional
from pydantic import BaseModel


class BolItem(BaseModel):
    """A single cargo/goods line item in a Bill of Lading or Packing List."""
    description: Optional[str] = None
    hsCode: Optional[str] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None           # PCS, SETS, PALLETS, CASES, CARTONS...
    grossWeight: Optional[float] = None  # KGS
    netWeight: Optional[float] = None    # KGS
    measurement: Optional[float] = None  # CBM
    size: Optional[str] = None           # Kích thước (1220*1070*570 mm)


class BillOfLading(BaseModel):
    """Schema for Bill of Lading (B/L) and Packing List documents."""

    # ===== B/L Identification =====
    blNumber: Optional[str] = None       # B/L No. (VD: JWFEM24120648)
    issueDate: Optional[str] = None      # Ngày phát hành
    issuePlace: Optional[str] = None     # Nơi phát hành

    # ===== Shipper / Seller =====
    shipperName: Optional[str] = None
    shipperAddress: Optional[str] = None
    shipperTel: Optional[str] = None

    # ===== Consignee / Buyer =====
    consigneeName: Optional[str] = None
    consigneeAddress: Optional[str] = None
    consigneeTaxId: Optional[str] = None

    # ===== Notify Party =====
    notifyParty: Optional[str] = None

    # ===== Carrier / Vessel =====
    carrier: Optional[str] = None                # Hãng vận chuyển
    vesselVoyage: Optional[str] = None            # Tên tàu / số chuyến
    portOfLoading: Optional[str] = None           # Cảng xếp hàng
    portOfDischarge: Optional[str] = None         # Cảng dỡ hàng
    placeOfReceipt: Optional[str] = None          # Nơi nhận hàng
    placeOfDelivery: Optional[str] = None         # Nơi giao hàng

    # ===== Container =====
    containerNo: Optional[str] = None             # Số container (VD: BEAU6340730)
    sealNo: Optional[str] = None                  # Số seal
    typeOfMovement: Optional[str] = None          # CY-CY, CFS-CFS

    # ===== Cargo Summary =====
    description: Optional[str] = None             # Mô tả hàng hóa tổng
    packages: Optional[str] = None                # Số kiện (VD: 10 PALLETS)
    grossWeight: Optional[str] = None             # Tổng trọng lượng (VD: 13,500.000KGS)
    netWeight: Optional[str] = None               # Tổng trọng lượng tịnh
    measurement: Optional[str] = None             # Tổng thể tích (VD: 32.2000CBM)
    shippingMarks: Optional[str] = None           # Nhãn hiệu vận chuyển

    # ===== Freight & Terms =====
    freightTerms: Optional[str] = None            # FREIGHT COLLECT / FREIGHT PREPAID
    tradeTerm: Optional[str] = None               # FOB, CIF, CFR...
    lcNumber: Optional[str] = None                # Số L/C (thư tín dụng)
    numberOfOriginals: Optional[str] = None       # Số bản gốc (VD: THREE (3))
    shippedOnBoardDate: Optional[str] = None      # Ngày xếp hàng lên tàu
    totalContainers: Optional[str] = None         # SAY ONE (1X40'HQ) CONTAINER ONLY

    # ===== Delivery Agent =====
    deliveryAgent: Optional[str] = None           # Đại lý giao hàng

    # ===== Item List =====
    itemList: List[BolItem] = []                  # Danh sách hàng hóa chi tiết
