# src/parsers/block_bol_zoomtext_parser.py
"""
Zoom text parser for Bill of Lading (B/L) documents.
Parses the header crop (45%) OCR text to extract/refine:
- B/L Number, Carrier name
- Shipper info (name, address, tel, fax)
- Consignee info (name, address, tax ID)
- Notify party
- Delivery agent
"""

import re
from typing import List
from src.schemas.bill_of_lading import BillOfLading


def _detect_zoom_blocks(lines: List[str]):
    """
    Split zoom text lines into shipper / consignee / notify / header blocks.
    """
    shipper_lines = []
    consignee_lines = []
    notify_lines = []
    header_lines = []
    delivery_lines = []

    current = "header"

    SHIPPER_TRIGGERS = [
        "shipper (complete name",
        "shipper (name",
        "shipper:",
        "shipper/exporter",
        "shipper",
    ]
    CONSIGNEE_TRIGGERS = [
        "consignee (complete name",
        "consignee (name",
        "consignee:",
        "consignee/importer",
        "consignee",
    ]
    NOTIFY_TRIGGERS = [
        "notify party",
        "notify:",
    ]
    DELIVERY_TRIGGERS = [
        "for delivery",
        "please apply to",
    ]

    for line in lines:
        low = line.lower().strip()

        # Skip ZOOM TEXT markers
        if 'zoom text' in low and low.strip('-').strip().replace('zoom text', '').strip() == '':
            continue

        if any(k in low for k in SHIPPER_TRIGGERS):
            current = "shipper"
        elif any(k in low for k in CONSIGNEE_TRIGGERS):
            current = "consignee"
        elif any(k in low for k in NOTIFY_TRIGGERS):
            current = "notify"
        elif any(k in low for k in DELIVERY_TRIGGERS):
            current = "delivery"
        elif any(k in low for k in ["bill of lading", "b/l no", "received in apparent"]):
            current = "header"
        elif any(k in low for k in ["pre-carriage", "ocean vessel", "port of"]):
            current = "header"  # shipping details go to header in zoom

        if current == "shipper":
            shipper_lines.append(line)
        elif current == "consignee":
            consignee_lines.append(line)
        elif current == "notify":
            notify_lines.append(line)
        elif current == "delivery":
            delivery_lines.append(line)
        else:
            header_lines.append(line)

    return shipper_lines, consignee_lines, notify_lines, header_lines, delivery_lines


def _parse_shipper(lines: List[str], bol: BillOfLading):
    """Parse shipper from zoom text lines."""
    address_lines = []
    for line in lines:
        clean = line.strip()
        low = clean.lower()

        # Skip section label
        if any(k in low for k in ["shipper (complete", "shipper (name"]):
            continue
        if low == "shipper" or low == "shipper:":
            continue

        # Tel / Fax
        tel_m = re.search(r'TEL[.:\s]*([+\d\-\s]+)', clean, re.I)
        fax_m = re.search(r'FAX[.:\s]*([+\d\-\s]+)', clean, re.I)
        if tel_m:
            if not bol.shipperTel:
                bol.shipperTel = tel_m.group(1).strip()
        if fax_m:
            if not bol.shipperFax:
                bol.shipperFax = fax_m.group(1).strip()
        if tel_m or fax_m:
            continue

        if clean.startswith("|"):
            continue

        if not bol.shipperName and len(clean) > 2:
            bol.shipperName = clean
        elif bol.shipperName:
            address_lines.append(clean)

    if address_lines and not bol.shipperAddress:
        bol.shipperAddress = ", ".join(address_lines)


def _parse_consignee(lines: List[str], bol: BillOfLading):
    """Parse consignee from zoom text lines."""
    address_lines = []
    for line in lines:
        clean = line.strip()
        low = clean.lower()

        # Skip section label
        if any(k in low for k in ["consignee (complete", "consignee (name"]):
            continue
        if low == "consignee" or low == "consignee:":
            continue

        # Tax ID
        tax_m = re.search(r'TAX\s*(?:ID|CODE)[:\s]*([0-9\-]+)', clean, re.I)
        if tax_m:
            if not bol.consigneeTaxId:
                bol.consigneeTaxId = tax_m.group(1).strip()
            continue

        if clean.startswith("|"):
            continue

        if not bol.consigneeName and len(clean) > 2:
            bol.consigneeName = clean
        elif bol.consigneeName:
            address_lines.append(clean)

    if address_lines and not bol.consigneeAddress:
        bol.consigneeAddress = ", ".join(address_lines)


def _parse_header(lines: List[str], bol: BillOfLading):
    """Parse B/L number, carrier, vessel info from zoom text header."""
    for line in lines:
        clean = line.strip()
        low = clean.lower()

        # B/L No
        bl_m = re.search(r'B/L\s*No\.?\s*[:\s]*([A-Z0-9]+)', clean, re.I)
        if bl_m and not bol.blNumber:
            bol.blNumber = bl_m.group(1).strip()

        # Carrier name: line containing transportation/shipping/logistics + CO
        if not bol.carrier and len(clean) > 10:
            carrier_kws = ["transportation", "shipping", "logistics", "maritime",
                          "lines", "carrier", "navigation", "marine"]
            if any(ck in low for ck in carrier_kws):
                bol.carrier = clean

        # Vessel / Voyage
        m = re.search(r'(?:CA|MV|MT|MS|SS)\s+[A-Z]+\s+\d{3,}[A-Z]*', clean)
        if m and not bol.vesselVoyage:
            bol.vesselVoyage = m.group(0).strip()

        # Port of Loading
        if "port of loading" in low:
            if "|" in clean:
                cells = [c.strip() for c in clean.split("|") if c.strip()]
                for i, cell in enumerate(cells):
                    if "port of loading" in cell.lower() and i + 1 < len(cells):
                        if not bol.portOfLoading:
                            bol.portOfLoading = cells[i + 1].strip()
            else:
                m2 = re.search(r'Port\s+of\s+Loading[.:\s]+(.+)', clean, re.I)
                if m2 and not bol.portOfLoading:
                    bol.portOfLoading = m2.group(1).strip()


def _parse_delivery(lines: List[str], bol: BillOfLading):
    """Parse delivery agent info from zoom text."""
    parts = []
    for line in lines:
        clean = line.strip()
        low = clean.lower()

        # Skip the label
        if "for delivery" in low or "please apply to" in low:
            if ":" in clean:
                val = clean.split(":", 1)[-1].strip()
                if val:
                    parts.append(val)
            continue

        if len(clean) > 2:
            parts.append(clean)

    if parts and not bol.deliveryAgent:
        bol.deliveryAgent = ", ".join(parts[:4])


def parse_zoom_bol(zoom_lines: List[str], bol: BillOfLading):
    """
    Main zoom text parser for B/L.
    Parse zoom text lines and fill/overwrite missing fields in the BillOfLading object.
    """
    if not zoom_lines:
        return

    shipper_lines, consignee_lines, notify_lines, header_lines, delivery_lines = _detect_zoom_blocks(zoom_lines)

    _parse_header(header_lines, bol)
    _parse_shipper(shipper_lines, bol)
    _parse_consignee(consignee_lines, bol)
    _parse_delivery(delivery_lines, bol)

    # Notify party
    for line in notify_lines:
        clean = line.strip()
        low = clean.lower()
        if "notify party" in low:
            if ":" in clean:
                val = clean.split(":", 1)[-1].strip()
                if val and not bol.notifyParty:
                    bol.notifyParty = val
            continue
        if clean.startswith("|") or len(clean) < 2:
            continue
        if not bol.notifyParty:
            bol.notifyParty = clean
        else:
            bol.notifyParty = bol.notifyParty + ", " + clean
