from typing import List, Optional
from pydantic import BaseModel, field_serializer, field_validator
from datetime import date

from src.schemas.invoice_item import InvoiceItem


class Invoice(BaseModel):
    # ===== Invoice info =====
    invoiceID: Optional[str] = None
    invoiceName: Optional[str] = None
    currency: Optional[str] = None

    invoiceDate: Optional[date] = None
    
    @field_serializer('invoiceDate')
    def serialize_date(self, dt: date | str | None, _info):
        if not dt:
            return None
        if isinstance(dt, date):
            return dt.strftime('%d/%m/%Y')
        # If it's a string, try to parse ISO or return as-is
        if isinstance(dt, str):
            # Attempt to convert YYYY-MM-DD back to dd/MM/YYYY if possible
            try:
                from datetime import datetime
                # Handle ISO format commonly seen
                parsed = datetime.strptime(dt, "%Y-%m-%d")
                return parsed.strftime('%d/%m/%Y')
            except ValueError:
                return dt # Return original string if parsing fails
        return str(dt)

    invoiceFormNo: Optional[str] = None
    invoiceSerial: Optional[str] = None
    paymentMethod: Optional[str] = None

    # ===== Seller =====
    sellerName: Optional[str] = None
    sellerTaxCode: Optional[str] = None
    sellerEmail: Optional[str] = None
    sellerAddress: Optional[str] = None
    sellerPhoneNumber: Optional[str] = None
    sellerBank: Optional[str] = None
    sellerBankAccountNumber: Optional[str] = None

    # ===== Buyer =====
    buyerName: Optional[str] = None
    buyerTaxCode: Optional[str] = None
    buyerEmail: Optional[str] = None
    buyerAddress: Optional[str] = None
    buyerPhoneNumber: Optional[str] = None
    buyerBank: Optional[str] = None
    buyerBankAccountNumber: Optional[str] = None

    # ===== Amount =====
    preTaxPrice: Optional[float] = None
    discountTotal: Optional[float] = None
    taxPercent: Optional[str] = None

    @field_validator('taxPercent', mode='before')
    @classmethod
    def coerce_tax_percent(cls, v):
        """Convert float/int taxPercent to string (e.g. 10.0 -> '10%')"""
        if v is None:
            return v
        if isinstance(v, (int, float)):
            # 10.0 -> "10%", 10.5 -> "10.5%"
            if isinstance(v, float) and v == int(v):
                return str(int(v)) + '%'
            return str(v) + '%'
        return v
    taxAmount: Optional[float] = None
    totalAmount: Optional[float] = None
    invoiceTotalInWord: Optional[str] = None

    # ===== Items =====
    itemList: List[InvoiceItem] = []
