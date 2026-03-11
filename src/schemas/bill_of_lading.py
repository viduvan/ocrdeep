# src/schemas/bill_of_lading.py
from typing import Optional
from pydantic import BaseModel


class BillOfLading(BaseModel):
    """Schema for Bill of Lading (B/L) documents."""

    # ===== B/L Identification =====
    blNumber: Optional[str] = None
    issueDate: Optional[str] = None
    issuePlace: Optional[str] = None

    # ===== Shipper =====
    shipperName: Optional[str] = None
    shipperAddress: Optional[str] = None
    shipperTel: Optional[str] = None
    shipperFax: Optional[str] = None

    # ===== Consignee =====
    consigneeName: Optional[str] = None
    consigneeAddress: Optional[str] = None
    consigneeTaxId: Optional[str] = None

    # ===== Notify Party =====
    notifyParty: Optional[str] = None

    # ===== Carrier / Vessel =====
    carrier: Optional[str] = None
    vesselVoyage: Optional[str] = None
    portOfLoading: Optional[str] = None
    portOfDischarge: Optional[str] = None
    placeOfReceipt: Optional[str] = None
    placeOfDelivery: Optional[str] = None

    # ===== Cargo Details =====
    description: Optional[str] = None
    grossWeight: Optional[str] = None
    measurement: Optional[str] = None
    containerNo: Optional[str] = None
    sealNo: Optional[str] = None
    packages: Optional[str] = None
    hsCode: Optional[str] = None

    # ===== Freight & Terms =====
    freightTerms: Optional[str] = None
    deliveryAgent: Optional[str] = None
    numberOfOriginals: Optional[str] = None
