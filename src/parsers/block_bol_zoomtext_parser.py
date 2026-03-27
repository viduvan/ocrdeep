# src/parsers/block_bol_zoomtext_parser.py
"""
Zoom text parser for Bill of Lading (B/L) documents.
Parses the header crop (45%) OCR text to extract/refine:
- B/L Number, Carrier name
- Shipper info (name, address, tel)
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
        "exporter/shipper",
        "shipper (name and address",
        "ship from",
        "shipper",
    ]
    CONSIGNEE_TRIGGERS = [
        "consignee (complete name",
        "consignee (name",
        "consignee:",
        "consignee/importer",
        "consignee (if to order",
        "consignee (not negotiable",
        "consignee (non-negotiable",
        "consignee",
    ]
    NOTIFY_TRIGGERS = [
        "notify party",
        "notify address",
        "notify:",
        "also notify",
    ]
    DELIVERY_TRIGGERS = [
        "for delivery",
        "please apply to",
        "for cargo delivery",
    ]

    for line in lines:
        low = line.lower().strip()

        # Skip ZOOM TEXT markers
        if 'zoom text' in low and low.strip('-').strip().replace('zoom text', '').strip() == '':
            continue

        if any(k in low for k in SHIPPER_TRIGGERS) and "load" not in low and "seal" not in low and "pack" not in low and "declared" not in low:
            current = "shipper"
        elif any(k in low for k in CONSIGNEE_TRIGGERS) and "reference" not in low:
            current = "consignee"
        elif any(k in low for k in NOTIFY_TRIGGERS):
            current = "notify"
        elif any(k in low for k in DELIVERY_TRIGGERS):
            current = "delivery"
        elif any(k in low for k in ["bill of lading", "b/l no", "b/l-no", "b/l nr", "received in apparent"]):
            current = "header"
        elif any(k in low for k in ["pre-carriage", "pre-carrier", "ocean vessel", "port of", "vessel and voyage", "vessel/voyage", "vessel(s)"]):
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

        # Tel / Fax (both go to shipperTel)
        tel_m = re.search(r'TEL[.:\s]*([+\d\-\s]+)', clean, re.I)
        fax_m = re.search(r'FAX[.:\s]*([+\d\-\s]+)', clean, re.I)
        if tel_m:
            if not bol.shipperTel:
                bol.shipperTel = tel_m.group(1).strip()
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
    for i, line in enumerate(lines):
        clean = line.strip()
        low = clean.lower()

        # B/L No - multiple patterns
        bl_patterns = [
            r'B/L\s*No\.?\s*[:\s]*([A-Z0-9]{5,})',
            r'B/L\s*Number\s*[:\s]*([A-Z0-9]{5,})',
            r'B/L[\s-]*NR\.?\s*[:\s]*([A-Z0-9]{5,})',
            r'BL\s*(?:No|Number)\.?\s*[:\s]*([A-Z0-9]{5,})',
            r'Bill[/\s]*Lading\s*Number\s*[:\s]*([A-Z0-9]{5,})',
            r'BILL\s+OF\s+LADING\s+NO\.?\s*[:\s]*([A-Z0-9]{5,})',
        ]
        for pat in bl_patterns:
            bl_m = re.search(pat, clean, re.I)
            if bl_m and not bol.blNumber:
                bol.blNumber = bl_m.group(1).strip()
                break

        # B/L No on label line, value on next line
        if not bol.blNumber and re.match(r'^\**\s*B/L\s*(?:No|NR|Number)\.?\s*[:\s]*\**\s*$', clean, re.I):
            if i + 1 < len(lines):
                nxt = lines[i + 1].strip().lstrip('*').strip()
                bl_m2 = re.match(r'^([A-Z0-9]{5,})$', nxt)
                if bl_m2:
                    bol.blNumber = bl_m2.group(1).strip()

        # Carrier from "Carrier:" label
        if not bol.carrier:
            cm = re.search(r'Carrier[:\s]+(.+)', clean, re.I)
            if cm:
                val = cm.group(1).strip()
                if len(val) > 3 and "not" not in val.lower()[:10]:
                    bol.carrier = val

        # Vessel / Voyage
        m = re.search(r'(?:CA|MV|MT|MS|SS)\s+[A-Z]+\s+\d{3,}[A-Z]*', clean)
        if m and not bol.vesselVoyage:
            bol.vesselVoyage = m.group(0).strip()

        # Vessel from label:value (same line)
        if not bol.vesselVoyage:
            vm = re.search(r'(?:Vessel|Ocean\s+Vessel)[/\s]*(?:Voy(?:age)?\.\s*(?:No\.?)?)?[\s:]+(.+)', clean, re.I)
            if vm:
                val = vm.group(1).strip()
                if len(val) > 3 and not any(k in val.lower() for k in ["port", "loading", "discharge"]):
                    bol.vesselVoyage = val

        # Vessel label only → value on next line
        if not bol.vesselVoyage and re.match(r'^\**\s*(?:Ocean\s+)?(?:Vessel|Voy)[/\s]*(?:Voy(?:age)?\.?\s*(?:No\.?)?)?\s*[:\s]*\**\s*$', clean, re.I):
            if i + 1 < len(lines):
                nxt = lines[i + 1].strip()
                if len(nxt) > 3 and not any(k in nxt.lower() for k in ["port", "loading", "discharge", "shipper", "consignee"]):
                    bol.vesselVoyage = nxt

        # Voyage No. on separate lines
        if not bol.vesselVoyage:
            vm2 = re.search(r'Voyage[\s-]*N[or]\.?\s*[:\s]+(.+)', clean, re.I)
            if vm2 and vm2.group(1).strip():
                bol.vesselVoyage = vm2.group(1).strip()

        # ===== PORTS AND PLACES (same-line and next-line) =====
        def _get_next_line_val(idx, all_lines, exclude_kws=None):
            """Get value from next line if current line is a label-only line."""
            if idx + 1 < len(all_lines):
                nxt = all_lines[idx + 1].strip()
                if nxt and len(nxt) > 2 and not nxt.startswith("|"):
                    if exclude_kws and any(k in nxt.lower() for k in exclude_kws):
                        return None
                    return nxt
            return None

        port_exclude = ["port of", "place of", "ocean vessel", "shipper", "consignee", "pre-carriage"]

        # Port of Loading
        if "port of loading" in low:
            if "|" in clean:
                cells = [c.strip() for c in clean.split("|") if c.strip()]
                for ci, cell in enumerate(cells):
                    if "port of loading" in cell.lower() and ci + 1 < len(cells):
                        if not bol.portOfLoading:
                            bol.portOfLoading = cells[ci + 1].strip()
            else:
                m2 = re.search(r'Port\s+of\s+Loading[.:\s]+(.+)', clean, re.I)
                if m2 and not bol.portOfLoading:
                    bol.portOfLoading = m2.group(1).strip()
                elif not bol.portOfLoading:
                    # Value on next line
                    nxt_val = _get_next_line_val(i, lines, port_exclude)
                    if nxt_val:
                        bol.portOfLoading = nxt_val

        # Port of Discharge
        if "port of discharge" in low:
            if "|" in clean:
                cells = [c.strip() for c in clean.split("|") if c.strip()]
                for ci, cell in enumerate(cells):
                    if "port of discharge" in cell.lower() and ci + 1 < len(cells):
                        if not bol.portOfDischarge:
                            bol.portOfDischarge = cells[ci + 1].strip()
            else:
                m2 = re.search(r'Port\s+of\s+Discharge[.:\s]+(.+)', clean, re.I)
                if m2 and not bol.portOfDischarge:
                    bol.portOfDischarge = m2.group(1).strip()
                elif not bol.portOfDischarge:
                    nxt_val = _get_next_line_val(i, lines, port_exclude)
                    if nxt_val:
                        bol.portOfDischarge = nxt_val

        # Place of Delivery
        if "place of delivery" in low:
            m2 = re.search(r'Place\s+of\s+Delivery[.:\s]+(.+)', clean, re.I)
            if m2 and not bol.placeOfDelivery:
                bol.placeOfDelivery = m2.group(1).strip()
            elif not bol.placeOfDelivery:
                nxt_val = _get_next_line_val(i, lines, port_exclude)
                if nxt_val:
                    bol.placeOfDelivery = nxt_val

        # Place of Receipt
        if "place of receipt" in low:
            m2 = re.search(r'Place\s+of\s+Receipt[.:\s]+(.+)', clean, re.I)
            if m2 and not bol.placeOfReceipt:
                bol.placeOfReceipt = m2.group(1).strip()
            elif not bol.placeOfReceipt:
                nxt_val = _get_next_line_val(i, lines, port_exclude)
                if nxt_val:
                    bol.placeOfReceipt = nxt_val


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
