# src/parsers/block_bol_parser.py
"""
Block-based parser for Bill of Lading (B/L) documents.
Extracts shipper, consignee, notify party, vessel/port info, cargo details,
and freight terms from plain OCR text.
"""

import re
from typing import List, Dict
from src.schemas.bill_of_lading import BillOfLading, BolItem


def clean_lines(raw_text: str) -> List[str]:
    """Clean and split raw text into lines, removing OCR noise."""
    text = raw_text.replace('\\n', '\n')
    # Remove OCR metadata tags
    text = re.sub(r'<\|ref\|>.*?<\|/ref\|><\|det\|>.*?<\|/det\|>', '', text)
    text = re.sub(r'<\|[^>]+\|>', '', text)
    # Remove markdown bold markers
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    # Remove markdown headers
    text = re.sub(r'^#+\s*', '', text, flags=re.MULTILINE)

    lines = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        # Skip table separators
        if re.fullmatch(r"\|[-\s|]+\|", line):
            continue
        lines.append(line)
    return lines


def detect_blocks(lines: List[str]) -> Dict[str, List[str]]:
    """
    Detect B/L document sections:
    shipper, consignee, notify_party, shipping, cargo, freight, signature
    """
    blocks = {
        "shipper": [],
        "consignee": [],
        "notify_party": [],
        "shipping": [],
        "cargo": [],
        "freight": [],
        "header": [],
        "signature": [],
    }

    # Filter out ZOOM TEXT section
    filtered_lines = []
    for line in lines:
        if '--- ZOOM TEXT ---' in line or '---ZOOM TEXT---' in line:
            break
        filtered_lines.append(line)
    lines = filtered_lines

    current = "header"

    for line in lines:
        low = line.lower().strip()

        # ===== SHIPPER =====
        if any(k in low for k in [
            "shipper (complete name",
            "shipper (name",
            "shipper:",
            "shipper/exporter",
        ]) or low == "shipper" or low.startswith("shipper "):
            current = "shipper"

        # ===== CONSIGNEE =====
        elif any(k in low for k in [
            "consignee (complete name",
            "consignee (name",
            "consignee:",
            "consignee/importer",
            "consignee (if to order",
        ]) or low == "consignee" or low.startswith("consignee "):
            current = "consignee"

        # ===== NOTIFY PARTY =====
        elif any(k in low for k in [
            "notify party",
            "notify:",
        ]):
            current = "notify_party"

        # ===== SHIPPING DETAILS (vessel, port, etc) =====
        elif any(k in low for k in [
            "pre-carriage by",
            "pre-contract by",
            "ocean vessel",
            "port of loading",
            "port of discharge",
            "place of receipt",
            "place of delivery",
            "final destination",
            "type of movement",
        ]):
            current = "shipping"

        # ===== CARGO (goods description, weight, measurement) =====
        elif any(k in low for k in [
            "marks & number",
            "marks and number",
            "container no",
            "description of goods",
            "description of packages",
            "quantity and",
            "gross weight",
            "measurement",
            "commodity",
            "shipped on board",
            "trade term",
            "l/c number",
            "l/c no",
        ]):
            current = "cargo"

        # ===== FREIGHT =====
        elif any(k in low for k in [
            "freight & charges",
            "freight and charges",
            "freight collect",
            "freight prepaid",
            "revenue tons",
            "exchange. rate",
            "exchange rate",
            "total prepaid",
            "laden on board",
            "s/o no",
            "total number of containers",
            "say one",
            "say two",
            "say three",
        ]):
            current = "freight"

        # ===== SIGNATURE =====
        elif any(k in low for k in [
            "as agent for the carrier",
            "for the carrier",
            "signed by",
            "authorized signature",
        ]):
            current = "signature"

        # ===== B/L HEADER (carrier name, B/L number) =====
        elif any(k in low for k in [
            "bill of lading",
            "b/l no",
            "b/l number",
            "bl no",
        ]):
            current = "header"

        blocks[current].append(line)

    return blocks


def parse_shipper(block: List[str], bol: BillOfLading):
    """Extract shipper info from shipper block."""
    address_lines = []
    for line in block:
        low = line.lower().strip()
        clean = line.strip()

        # Skip the section label itself
        if any(k in low for k in ["shipper (complete", "shipper (name", "shipper:"]) or low == "shipper":
            # Check if there's a value after the label
            if ":" in clean:
                val = clean.split(":", 1)[-1].strip()
                if val and not bol.shipperName:
                    bol.shipperName = val
            continue

        # Tel/Fax (both go to shipperTel)
        tel_m = re.search(r'TEL[.:\s]*([+\d\-\s]+)', clean, re.I)
        fax_m = re.search(r'FAX[.:\s]*([+\d\-\s]+)', clean, re.I)
        if tel_m:
            if not bol.shipperTel:
                bol.shipperTel = tel_m.group(1).strip()
        if tel_m or fax_m:
            continue

        # Skip pipe tables
        if clean.startswith("|"):
            continue

        # First non-label line without tel/fax = shipper name
        if not bol.shipperName and len(clean) > 2:
            bol.shipperName = clean
        elif bol.shipperName:
            address_lines.append(clean)

    if address_lines and not bol.shipperAddress:
        bol.shipperAddress = ", ".join(address_lines)


def parse_consignee(block: List[str], bol: BillOfLading):
    """Extract consignee info from consignee block."""
    address_lines = []
    for line in block:
        low = line.lower().strip()
        clean = line.strip()

        # Skip section label
        if any(k in low for k in ["consignee (complete", "consignee (name", "consignee:", "consignee (if to order"]) or low == "consignee":
            if ":" in clean:
                val = clean.split(":", 1)[-1].strip()
                if val and not bol.consigneeName:
                    bol.consigneeName = val
            continue

        # Tax ID
        tax_m = re.search(r'TAX\s*(?:ID|CODE)[:\s]*([0-9\-]+)', clean, re.I)
        if tax_m:
            if not bol.consigneeTaxId:
                bol.consigneeTaxId = tax_m.group(1).strip()
            continue

        # Skip pipe tables
        if clean.startswith("|"):
            continue

        # First non-label line = consignee name
        if not bol.consigneeName and len(clean) > 2:
            bol.consigneeName = clean
        elif bol.consigneeName:
            address_lines.append(clean)

    if address_lines and not bol.consigneeAddress:
        bol.consigneeAddress = ", ".join(address_lines)


def parse_notify_party(block: List[str], bol: BillOfLading):
    """Extract notify party from notify party block."""
    for line in block:
        low = line.lower().strip()
        clean = line.strip()

        # Skip label
        if "notify party" in low and ":" not in clean:
            continue
        if "notify party" in low and ":" in clean:
            val = clean.split(":", 1)[-1].strip()
            if val:
                bol.notifyParty = val
            continue

        # Skip pipe tables and empty
        if clean.startswith("|") or len(clean) < 2:
            continue

        if not bol.notifyParty:
            bol.notifyParty = clean
        else:
            bol.notifyParty = bol.notifyParty + ", " + clean


def parse_shipping(block: List[str], bol: BillOfLading):
    """Extract vessel, port, and routing info from shipping block.
    
    B/L pipe-tables typically have headers on one row and values on the next:
    | Ocean Vessel / Voy. No. | Port of Loading. | ...  |
    | CA NAGOYA 2451W          | NANSHA PORT, CHINA | |
    """
    # Two-pass approach for pipe tables
    # First collect all pipe-table rows
    pipe_rows = []
    non_pipe_lines = []
    for line in block:
        clean = line.strip()
        if clean.startswith("|"):
            cells = [c.strip() for c in clean.split("|")]
            # Remove empty first/last cells from split
            if cells and cells[0] == '':
                cells = cells[1:]
            if cells and cells[-1] == '':
                cells = cells[:-1]
            pipe_rows.append(cells)
        else:
            non_pipe_lines.append(clean)

    # Process pipe-table rows: header row → value row pairs
    FIELD_MAP = {
        "ocean vessel": "vesselVoyage",
        "voy": "vesselVoyage",
        "port of loading": "portOfLoading",
        "port of discharge": "portOfDischarge",
        "place of receipt": "placeOfReceipt",
        "place of delivery": "placeOfDelivery",
        "final destination": "finalDestination",
        "type of movement": "typeOfMovement",
    }

    i = 0
    while i < len(pipe_rows):
        header_cells = pipe_rows[i]
        # Check if this row contains header labels
        header_mapping = {}  # col_index -> field_name
        for col_idx, cell in enumerate(header_cells):
            cl = cell.lower().rstrip('.').strip()
            for keyword, field_name in FIELD_MAP.items():
                if keyword in cl:
                    header_mapping[col_idx] = field_name
                    break

        if header_mapping and i + 1 < len(pipe_rows):
            # Next row has the values
            value_cells = pipe_rows[i + 1]
            for col_idx, field_name in header_mapping.items():
                if col_idx < len(value_cells):
                    val = value_cells[col_idx].strip()
                    if val and len(val) > 1:
                        if field_name == "vesselVoyage" and not bol.vesselVoyage:
                            bol.vesselVoyage = val
                        elif field_name == "portOfLoading" and not bol.portOfLoading:
                            bol.portOfLoading = val
                        elif field_name == "portOfDischarge" and not bol.portOfDischarge:
                            bol.portOfDischarge = val
                        elif field_name == "placeOfReceipt" and not bol.placeOfReceipt:
                            bol.placeOfReceipt = val
                        elif field_name == "placeOfDelivery" and not bol.placeOfDelivery:
                            bol.placeOfDelivery = val
                        elif field_name == "typeOfMovement" and not bol.typeOfMovement:
                            bol.typeOfMovement = val.upper()
            i += 2  # Skip both header and value rows
            continue

        i += 1

    # Non-pipe-table lines: try label:value patterns
    for clean in non_pipe_lines:
        # Ocean Vessel
        m = re.search(r'(?:Ocean\s+Vessel|Vessel)[/\s]*(?:Voy\.?\s*No\.?)?[:\s]+(.+)', clean, re.I)
        if m and not bol.vesselVoyage:
            bol.vesselVoyage = m.group(1).strip()
            continue

        # Port of Loading
        m = re.search(r'Port\s+of\s+Loading[.:\s]+(.+)', clean, re.I)
        if m and not bol.portOfLoading:
            bol.portOfLoading = m.group(1).strip()
            continue

        # Port of Discharge
        m = re.search(r'Port\s+of\s+Discharge[.:\s]+(.+)', clean, re.I)
        if m and not bol.portOfDischarge:
            bol.portOfDischarge = m.group(1).strip()
            continue

        # Place of Receipt
        m = re.search(r'Place\s+of\s+Receipt[.:\s]+(.+)', clean, re.I)
        if m and not bol.placeOfReceipt:
            bol.placeOfReceipt = m.group(1).strip()
            continue

        # Place of Delivery
        m = re.search(r'Place\s+of\s+Delivery[.:\s]+(.+)', clean, re.I)
        if m and not bol.placeOfDelivery:
            bol.placeOfDelivery = m.group(1).strip()
            continue


def parse_cargo(block: List[str], bol: BillOfLading):
    """Extract cargo details: description, weight, measurement, container, HS code, trade terms."""
    description_parts = []
    hs_code = None
    for line in block:
        clean = line.strip()
        low = clean.lower()

        # Container No / Seal No
        container_m = re.search(r'([A-Z]{4}\d{7})', clean)
        if container_m and not bol.containerNo:
            bol.containerNo = container_m.group(1)

        # Seal No: often after container, separated by /
        seal_m = re.search(r'[A-Z]{4}\d{7}\s*/\s*\d+[\'"]?\s*(?:HQ|GP|HC)?\s*/\s*([A-Z]?\d{5,})', clean)
        if seal_m and not bol.sealNo:
            bol.sealNo = seal_m.group(1)

        # Gross Weight
        weight_m = re.search(r'(\d[\d,\.]+)\s*(?:KGS|KG|KGM)', clean, re.I)
        if weight_m and not bol.grossWeight:
            bol.grossWeight = weight_m.group(0).strip()

        # Net Weight
        nw_m = re.search(r'NET\s*WEIGHT[:\s]*(\d[\d,\.]+\s*(?:KGS|KG)?)', clean, re.I)
        if nw_m and not bol.netWeight:
            bol.netWeight = nw_m.group(1).strip()

        # Measurement
        meas_m = re.search(r'(\d[\d,\.]+)\s*(?:CBM|M[³3])', clean, re.I)
        if meas_m and not bol.measurement:
            bol.measurement = meas_m.group(0).strip()

        # HS Code (capture for BolItem)
        hs_m = re.search(r'HS[:\s]*(?:CODE)?[:\s]*(\d[\d\.]{3,})', clean, re.I)
        if hs_m and not hs_code:
            hs_code = hs_m.group(1).strip()

        # Packages count (10 PALLETS, 4 PACKAGES, 1 CASE, etc.)
        pkg_m = re.search(r'(\d+)\s*(?:PACKAGE|PALLET|CASE|CARTON|SETS|PCS)', clean, re.I)
        if pkg_m and not bol.packages:
            bol.packages = pkg_m.group(0).strip()

        # Type of Movement: CY-CY, CFS-CFS
        mov_m = re.search(r'\b(C[YF]S?-C[YF]S?)\b', clean, re.I)
        if mov_m and not bol.typeOfMovement:
            bol.typeOfMovement = mov_m.group(1).upper()

        # Trade Term: FOB, CIF, CFR, etc.
        trade_m = re.search(r'\bTRADE\s*TERM[:\s]*(FOB|CIF|CFR|CIP|FCA|EXW|DAP|DDP)\b', clean, re.I)
        if trade_m and not bol.tradeTerm:
            bol.tradeTerm = trade_m.group(1).upper()
        # Also detect standalone FOB/CIF at start of line
        if not bol.tradeTerm:
            trade_m2 = re.search(r'^(FOB|CIF|CFR)\s+[A-Z]', clean)
            if trade_m2:
                bol.tradeTerm = trade_m2.group(1).upper()

        # L/C Number
        lc_m = re.search(r'L/C\s*(?:NUMBER|NO\.?)?[:\s]*([A-Z0-9]+)', clean, re.I)
        if lc_m and not bol.lcNumber:
            bol.lcNumber = lc_m.group(1).strip()

        # Shipped on Board date
        sob_m = re.search(r'SHIPPED\s+ON\s+BOARD', clean, re.I)
        if sob_m and not bol.shippedOnBoardDate:
            # Try to find date in same line or nearby (YYYY/MM/DD or DDMMMYYYY)
            date_m = re.search(r'(\d{4}/\d{2}/\d{2}|\d{2}[A-Z]{3}\d{4})', clean)
            if date_m:
                bol.shippedOnBoardDate = date_m.group(1)

        # Shipping Marks
        marks_m = re.search(r'(?:SHIPPING\s*)?MARKS[:\s]+(.+)', clean, re.I)
        if marks_m and not bol.shippingMarks:
            val = marks_m.group(1).strip()
            if val and len(val) > 1:
                bol.shippingMarks = val

        # Description of goods
        if "shipper's load" in low or "shipper load" in low or "s.t.c." in low:
            continue
        if any(k in low for k in ["marks & number", "marks and number", "container no",
                                   "description of goods", "quantity and", "gross weight",
                                   "measurement", "kind of package"]):
            continue

        # Pipe table: extract HS code, weight, measurement, packages from cells
        if clean.startswith("|"):
            cells = [c.strip() for c in clean.split("|") if c.strip()]
            for cell in cells:
                hs_m2 = re.search(r'HS[:\s]*(?:CODE)?[:\s]*(\d[\d\.]{3,})', cell, re.I)
                if hs_m2 and not hs_code:
                    hs_code = hs_m2.group(1)
                wt_m2 = re.search(r'(\d[\d,\.]+)\s*(?:KGS|KG)', cell, re.I)
                if wt_m2 and not bol.grossWeight:
                    bol.grossWeight = wt_m2.group(0).strip()
                meas_m2 = re.search(r'(\d[\d,\.]+)\s*(?:CBM)', cell, re.I)
                if meas_m2 and not bol.measurement:
                    bol.measurement = meas_m2.group(0).strip()
                pkg_m2 = re.search(r'(\d+)\s*(?:PACKAGE|PALLET|CASE|CARTON)', cell, re.I)
                if pkg_m2 and not bol.packages:
                    bol.packages = pkg_m2.group(0).strip()
            continue

        # Collect goods description
        if len(clean) > 5 and not container_m and not weight_m and not meas_m and not hs_m:
            if not any(k in low for k in ["road,", "city,", "china", "vietnam", "viet nam",
                                           "made in", "6/f block", "phase 3"]):
                goods_kws = ["machine", "equipment", "tool", "device", "motor", "pump",
                             "valve", "pipe", "steel", "iron", "copper", "aluminum",
                             "chemical", "fabric", "textile", "garment", "furniture",
                             "electronic", "component", "part", "material", "product",
                             "sander", "saw", "milling", "cnc", "radial", "brush",
                             "yarn", "cotton", "weaving", "cone", "carton"]
                if any(gk in low for gk in goods_kws):
                    description_parts.append(clean)

    if description_parts and not bol.description:
        bol.description = "; ".join(description_parts)

    # Create BolItem if we have description or HS code
    if (description_parts or hs_code) and not bol.itemList:
        item = BolItem(
            description="; ".join(description_parts) if description_parts else None,
            hsCode=hs_code,
        )
        # Try to parse weight/quantity as float for the item
        if bol.grossWeight:
            try:
                item.grossWeight = float(re.sub(r'[^\d.]', '', bol.grossWeight.split('KG')[0].replace(',', '')))
            except (ValueError, IndexError):
                pass
        if bol.measurement:
            try:
                item.measurement = float(re.sub(r'[^\d.]', '', bol.measurement.split('CBM')[0].replace(',', '')))
            except (ValueError, IndexError):
                pass
        bol.itemList.append(item)


def parse_freight(block: List[str], bol: BillOfLading):
    """Extract freight terms, delivery agent, number of originals, dates."""
    for line in block:
        clean = line.strip()
        low = clean.lower()

        # Freight terms
        if "freight collect" in low and not bol.freightTerms:
            bol.freightTerms = "FREIGHT COLLECT"
        elif "freight prepaid" in low and not bol.freightTerms:
            bol.freightTerms = "FREIGHT PREPAID"

        # Number of originals: THREE (3)
        orig_m = re.search(r'(?:No\.?\s*of\s*Original|Original)\s*B.*?L\s*(.+)', clean, re.I)
        if orig_m and not bol.numberOfOriginals:
            val = re.sub(r'[\s|]+$', '', orig_m.group(1)).strip()
            bol.numberOfOriginals = val

        # Total containers in words: SAY ONE (1) CASE ONLY / SAY ONE (1X40'HQ) CONTAINER ONLY
        say_m = re.search(r'(SAY\s+.+(?:ONLY|CONTAINER))', clean, re.I)
        if say_m and not bol.totalContainers:
            bol.totalContainers = say_m.group(1).strip()

        # Laden on board / Shipped on board date
        laden_m = re.search(r'(?:LADEN\s+ON\s+BOARD|SHIPPED\s+ON\s+BOARD)', clean, re.I)
        if laden_m:
            date_m = re.search(r'(\d{2}[A-Z]{3}\d{4}|\d{4}/\d{2}/\d{2})', clean)
            if date_m:
                if not bol.shippedOnBoardDate:
                    bol.shippedOnBoardDate = date_m.group(1)
                if not bol.issueDate:
                    bol.issueDate = date_m.group(1)

        # Place and date of Issue
        issue_m = re.search(r'Place\s+and\s+date\s+of\s+Issue', clean, re.I)
        if issue_m:
            cells = [c.strip() for c in clean.split("|") if c.strip()]
            for cell in cells:
                if "place and date" in cell.lower():
                    continue
                date_m = re.search(r'(\d{2}[A-Z]{3}\d{4}|\d{4}/\d{2}/\d{2})', cell)
                if date_m and not bol.issueDate:
                    bol.issueDate = date_m.group(1)
                elif len(cell) > 3 and not date_m and not bol.issuePlace:
                    bol.issuePlace = cell

        # Standalone date pattern: 03JAN2025 or 2025/12/15
        if not bol.issueDate:
            date_m = re.search(r'(\d{2}[A-Z]{3}\d{4}|\d{4}/\d{2}/\d{2})', clean)
            if date_m:
                bol.issueDate = date_m.group(1)

        # Type of Movement: CY-CY, CFS-CFS (also check in freight block)
        mov_m = re.search(r'\b(C[YF]S?-C[YF]S?)\b', clean, re.I)
        if mov_m and not bol.typeOfMovement:
            bol.typeOfMovement = mov_m.group(1).upper()


def parse_header(block: List[str], bol: BillOfLading):
    """Extract B/L number, carrier name from header block."""
    for line in block:
        clean = line.strip()
        low = clean.lower()

        # B/L No: JWFEM24120648
        bl_m = re.search(r'B/L\s*No\.?\s*[:\s]*([A-Z0-9]+)', clean, re.I)
        if bl_m and not bol.blNumber:
            bol.blNumber = bl_m.group(1).strip()

        # BL No (without slash)
        if not bol.blNumber:
            bl_m2 = re.search(r'BL\s*(?:No|Number)\.?\s*[:\s]*([A-Z0-9]+)', clean, re.I)
            if bl_m2:
                bol.blNumber = bl_m2.group(1).strip()

        # Carrier name: "SHENZHEN JW INTERNATIONAL TRANSPORTATION CO., LTD"
        # Usually appears right before "BILL OF LADING"
        if "bill of lading" in low:
            # The carrier name is often the line before
            continue

        # Lines in header that look like company names (before BILL OF LADING)
        if not bol.carrier and len(clean) > 5:
            company_kws = ["transportation", "shipping", "logistics", "maritime",
                          "lines", "carrier", "navigation", "marine", "overseas"]
            if any(ck in low for ck in company_kws):
                bol.carrier = clean

        # Delivery agent: "For delivery Please apply to: V-MART LOGISTICS..."
        if "for delivery" in low or "please apply to" in low:
            if ":" in clean:
                val = clean.split(":", 1)[-1].strip()
                if val and not bol.deliveryAgent:
                    bol.deliveryAgent = val


def parse_bol_block_based(raw_text: str) -> BillOfLading:
    """
    Main B/L parser: split text into blocks, extract fields from each block.
    """
    bol = BillOfLading()

    lines = clean_lines(raw_text)
    if not lines:
        return bol

    blocks = detect_blocks(lines)

    # Parse each block
    parse_header(blocks["header"], bol)
    parse_shipper(blocks["shipper"], bol)
    parse_consignee(blocks["consignee"], bol)
    parse_notify_party(blocks["notify_party"], bol)
    parse_shipping(blocks["shipping"], bol)
    parse_cargo(blocks["cargo"], bol)
    parse_freight(blocks["freight"], bol)

    # === Cross-block fallback extraction ===
    # B/L Number: scan ALL lines if not found in header
    if not bol.blNumber:
        for line in lines:
            bl_m = re.search(r'B/L\s*No\.?\s*[:\s]*([A-Z0-9]+)', line, re.I)
            if bl_m:
                bol.blNumber = bl_m.group(1).strip()
                break

    # Carrier: scan for company name before "BILL OF LADING"
    if not bol.carrier:
        for i, line in enumerate(lines):
            if "bill of lading" in line.lower():
                # Check previous line for carrier name
                if i > 0:
                    prev = lines[i - 1].strip()
                    if len(prev) > 5 and not prev.startswith("|"):
                        bol.carrier = prev
                break

    # Delivery agent: scan all lines
    if not bol.deliveryAgent:
        in_delivery = False
        agent_parts = []
        for line in lines:
            low = line.lower().strip()
            if "for delivery" in low or "please apply to" in low:
                in_delivery = True
                if ":" in line:
                    val = line.strip().split(":", 1)[-1].strip()
                    if val:
                        agent_parts.append(val)
                continue
            if in_delivery:
                clean = line.strip()
                if len(clean) < 2 or any(k in low for k in [
                    "shipper", "consignee", "notify", "pre-carriage",
                    "ocean vessel", "port of", "marks", "container"
                ]):
                    break
                agent_parts.append(clean)
        if agent_parts:
            bol.deliveryAgent = ", ".join(agent_parts[:4])  # Limit to 4 lines

    # Vessel / Voyage: scan pipe tables and key-value lines
    if not bol.vesselVoyage:
        for line in lines:
            m = re.search(r'(?:CA|MV|MT|MS|SS)\s+[A-Z]+\s+\d{3,}[A-Z]*', line)
            if m:
                bol.vesselVoyage = m.group(0).strip()
                break

    # Port of Loading from pipe tables
    if not bol.portOfLoading:
        for line in lines:
            if "nansha" in line.lower() or "port" in line.lower():
                port_m = re.search(r'(NANSHA\s+PORT[^|]*|SHANGHAI\s+PORT[^|]*|SHENZHEN\s+PORT[^|]*)', line, re.I)
                if port_m:
                    bol.portOfLoading = port_m.group(1).strip().rstrip(",").strip()
                    break

    return bol
