from typing import Optional
from pydantic import BaseModel


class InvoiceItem(BaseModel):
    productCode: Optional[str] = None
    productName: Optional[str] = None
    unit: Optional[str] = None

    unitPrice: Optional[float] = None
    quantity: Optional[float] = None
    amount: Optional[float] = None

    discountPercent: Optional[str] = None
    discountAmount: Optional[float] = None
    payment: Optional[float] = None
