"""
Generate 5 variants for each of 2 invoice formats:
  - AGB_14166_Invoice_International (Case 03 format)
  - AGB_12487_Invoice_Domestic (GTGT format)
Keeps exact structure/format, only changes business data.
"""

# ─── Data pools ───
INTL_VARIANTS = [
    {
        "seller": "Minh Phát Trading Co., Ltd",
        "seller_addr": "45 Nguyen Hue Boulevard, District 1, Ho Chi Minh City, Vietnam",
        "buyer": "Atlas Pacific Supplies",
        "buyer_addr": "120 Collins Street, Melbourne, Victoria, Australia",
        "inv_no": "83412",
        "inv_date": "3/15/2025",
        "product": "Cashew Nuts",
        "qty": "150320",
        "unit_price": "USD 0.25",
        "unit": "kg",
        "price": "USD 37,580",
        "subtotal": "USD 37,580",
        "tax_rate": "10%",
        "tax": "USD 3,758",
        "total": "USD 41,338",
        "currency": "USD",
        "delivery": "FOB",
    },
    {
        "seller": "Hoàng Long Logistics JSC",
        "seller_addr": "12 Tran Phu Street, Ba Dinh District, Hanoi, Vietnam",
        "buyer": "Nordic Fresh Imports AB",
        "buyer_addr": "Storgatan 22, 411 38 Gothenburg, Sweden",
        "inv_no": "VN-20250401",
        "inv_date": "4/1/2025",
        "product": "Frozen Pangasius Fillets",
        "qty": "82500",
        "unit_price": "EUR 1.85",
        "unit": "kg",
        "price": "EUR 152,625",
        "subtotal": "EUR 152,625",
        "tax_rate": "5%",
        "tax": "EUR 7,631",
        "total": "EUR 160,256",
        "currency": "EUR",
        "delivery": "CIF",
    },
    {
        "seller": "Sài Gòn Export Corp",
        "seller_addr": "88 Vo Van Tan, District 3, Ho Chi Minh City, Vietnam",
        "buyer": "Kobe Trading House Ltd",
        "buyer_addr": "2-4-7 Kitano-cho, Chuo-ku, Kobe 650-0002, Japan",
        "inv_no": "SGE-2025-0078",
        "inv_date": "5/10/2025",
        "product": "Robusta Coffee Beans",
        "qty": "45000",
        "unit_price": "JPY 320",
        "unit": "kg",
        "price": "JPY 14,400,000",
        "subtotal": "JPY 14,400,000",
        "tax_rate": "8%",
        "tax": "JPY 1,152,000",
        "total": "JPY 15,552,000",
        "currency": "JPY",
        "delivery": "CFR",
    },
    {
        "seller": "Đại Phong Materials Co., Ltd",
        "seller_addr": "156 Le Thanh Ton, Hai Chau District, Da Nang, Vietnam",
        "buyer": "Greenfield Wholesale Inc",
        "buyer_addr": "789 Broadway, Suite 400, New York, NY 10003, USA",
        "inv_no": "DP-INV-55021",
        "inv_date": "2/28/2025",
        "product": "Natural Rubber SVR 10",
        "qty": "126000",
        "unit_price": "USD 1.58",
        "unit": "kg",
        "price": "USD 199,080",
        "subtotal": "USD 199,080",
        "tax_rate": "0%",
        "tax": "USD 0",
        "total": "USD 199,080",
        "currency": "USD",
        "delivery": "CIF",
    },
    {
        "seller": "Thiên An Ceramics JSC",
        "seller_addr": "Km5 National Road 1A, Bien Hoa, Dong Nai, Vietnam",
        "buyer": "EuroCasa Distributors GmbH",
        "buyer_addr": "Friedrichstrasse 45, 10117 Berlin, Germany",
        "inv_no": "TAC-2025-0193",
        "inv_date": "6/5/2025",
        "product": "Porcelain Floor Tiles 60x60cm",
        "qty": "32000",
        "unit_price": "EUR 3.40",
        "unit": "sqm",
        "price": "EUR 108,800",
        "subtotal": "EUR 108,800",
        "tax_rate": "10%",
        "tax": "EUR 10,880",
        "total": "EUR 119,680",
        "currency": "EUR",
        "delivery": "FOB",
    },
]

DOMESTIC_VARIANTS = [
    {
        "seller": "Công Ty TNHH Thương Mại Bình Minh",
        "seller_addr": "25 Lý Thường Kiệt, Quận Hoàn Kiếm, Hà Nội, Việt Nam",
        "serial": "002",
        "inv_no": "10245",
        "inv_date": "5/12/2025",
        "buyer": "Công Ty CP Phát Triển Số Việt",
        "buyer_addr": "78 Nguyễn Trãi, Quận Thanh Xuân, Hà Nội, Việt Nam",
        "product": "Máy in laser HP LaserJet Pro",
        "unit": "cái",
        "qty": "15",
        "unit_price": "VND 8,500,000",
        "amount": "VND 127,500,000",
        "tax_rate": "10%",
        "tax": "VND 12,750,000",
        "total": "VND 140,250,000",
    },
    {
        "seller": "Công Ty CP Vật Liệu Xây Dựng Đông Á",
        "seller_addr": "112 Trần Đại Nghĩa, Quận Hai Bà Trưng, Hà Nội, Việt Nam",
        "serial": "003",
        "inv_no": "87623",
        "inv_date": "4/8/2025",
        "buyer": "Công Ty TNHH Xây Dựng Hòa Phát",
        "buyer_addr": "56 Phạm Văn Đồng, Quận Bắc Từ Liêm, Hà Nội, Việt Nam",
        "product": "Xi măng Portland PC40",
        "unit": "tấn",
        "qty": "200",
        "unit_price": "VND 1,850,000",
        "amount": "VND 370,000,000",
        "tax_rate": "8%",
        "tax": "VND 29,600,000",
        "total": "VND 399,600,000",
    },
    {
        "seller": "Công Ty TNHH Điện Tử Sao Việt",
        "seller_addr": "34 Lê Văn Lương, Quận Cầu Giấy, Hà Nội, Việt Nam",
        "serial": "001",
        "inv_no": "45890",
        "inv_date": "3/20/2025",
        "buyer": "Công Ty CP Giải Pháp Công Nghệ FTS",
        "buyer_addr": "99 Hoàng Quốc Việt, Quận Cầu Giấy, Hà Nội, Việt Nam",
        "product": "Bộ lưu điện UPS APC 3000VA",
        "unit": "bộ",
        "qty": "8",
        "unit_price": "VND 25,600,000",
        "amount": "VND 204,800,000",
        "tax_rate": "10%",
        "tax": "VND 20,480,000",
        "total": "VND 225,280,000",
    },
    {
        "seller": "Công Ty CP Thực Phẩm Hương Quê",
        "seller_addr": "67 Ngô Quyền, Quận Hai Bà Trưng, Hà Nội, Việt Nam",
        "serial": "004",
        "inv_no": "33401",
        "inv_date": "6/1/2025",
        "buyer": "Siêu Thị Mega Market Việt Nam",
        "buyer_addr": "162 Lê Duẩn, Quận 1, TP Hồ Chí Minh, Việt Nam",
        "product": "Gạo Jasmine đặc sản 5kg",
        "unit": "bao",
        "qty": "5000",
        "unit_price": "VND 125,000",
        "amount": "VND 625,000,000",
        "tax_rate": "5%",
        "tax": "VND 31,250,000",
        "total": "VND 656,250,000",
    },
    {
        "seller": "Công Ty TNHH Nội Thất Phú Quý",
        "seller_addr": "210 Giải Phóng, Quận Đống Đa, Hà Nội, Việt Nam",
        "serial": "005",
        "inv_no": "72018",
        "inv_date": "1/15/2025",
        "buyer": "Khách Sạn Mường Thanh Grand Hà Nội",
        "buyer_addr": "4 Lý Thái Tổ, Quận Hoàn Kiếm, Hà Nội, Việt Nam",
        "product": "Bàn ghế hội nghị gỗ sồi",
        "unit": "bộ",
        "qty": "30",
        "unit_price": "VND 12,800,000",
        "amount": "VND 384,000,000",
        "tax_rate": "10%",
        "tax": "VND 38,400,000",
        "total": "VND 422,400,000",
    },
]


def gen_intl_rawtext(v):
    return (
        f'{v["seller"]}\n'
        f'{v["seller_addr"]}\n'
        f'Tel:\n\n'
        f'Beneficiary: {v["seller"]}\n'
        f'Bank:\nBank account: SWIFT Code:\n\n'
        f'INVOICE\n\n'
        f'Bill to: {v["buyer"]}\n'
        f'Address: {v["buyer_addr"]}\n'
        f'Phone: \nFax: \n'
        f'Invoice #: {v["inv_no"]}\n'
        f'Invoice Date: {v["inv_date"]}\n\n'
        f'Customer: {v["buyer"]}\n'
        f'Address: {v["buyer_addr"]}\n\n'
        f'Invoice For PO#: Delivery term: {v["delivery"]}\n\n'
        f'| Item # | Description | Quantity | Unit Price | Unit | Price |\n'
        f'|--------|-------------|----------|-----------|------|-------|\n'
        f'| 1      | {v["product"]}    | {v["qty"]}   | {v["unit_price"]}   | {v["unit"]}  | {v["price"]} |\n\n'
        f'Signature\n\n'
        f'Invoice Subtotal\nTax Rate\nSales Tax\n\n'
        f'{v["subtotal"]}\n{v["tax_rate"]}\n{v["tax"]}\n\n'
        f'| Other | TOTAL |\n|-------|-------|\n| {v["total"]} |       |\n\n'
        f'Other\nTOTAL\n\n'
        f'--- ZOOM TEXT ---\n'
        f'{v["seller"]}  \n'
        f'{v["seller_addr"].split(",")[0]},  \n'
        f'{",".join(v["seller_addr"].split(",")[1:])}  \n'
        f'Tel:  \n\n'
        f'Beneficiary: {v["seller"]}  \n'
        f'Bank:  \nBank account:  \n\nSWIFT Code:  \n\n'
        f'INVOICE  \n\n'
        f'Bill to: {v["buyer"]}  \n'
        f'Phone:  \nInvoice #: {v["inv_no"]}  \n'
        f'Address: {v["buyer_addr"].split(",")[0]},  \n'
        f'Fax:  \nInvoice Date: {v["inv_date"]}  \n'
    )


def gen_intl_zoomtext(v):
    parts = v["buyer_addr"].split(",")
    return (
        f'{v["seller"]}  \n'
        f'{v["seller_addr"].split(",")[0]},  \n'
        f'{",".join(v["seller_addr"].split(",")[1:]).strip()}  \n'
        f'Tel:  \n\n'
        f'Beneficiary: {v["seller"]}  \n'
        f'Bank:  \nBank account:  \n\nSWIFT Code:  \n\n'
        f'---\n\n'
        f'**INVOICE**  \n\n'
        f'**Bill to:** {v["buyer"]}  \n'
        f'**Phone:**  \n'
        f'**Invoice #:** {v["inv_no"]}  \n'
        f'**Address:** {parts[0].strip()},  \n'
        f'**Fax:**  \n'
        f'**Invoice Date:** {v["inv_date"]}  \n'
        f'**{",".join(parts[1:]).strip()}**  \n\n'
        f'**Customer:** {v["buyer"]}  \n'
        f'**Address:** {parts[0].strip()},  \n'
        f'**{",".join(parts[1:]).strip()}**'
    )


def gen_domestic_rawtext(v):
    return (
        f'{v["seller"]}\n'
        f'Địa chỉ: {v["seller_addr"]} Ký hiệu: {v["serial"]}\n'
        f'Số: {v["inv_no"]}\n\n'
        f'HÓA ĐƠN GTGT\n\n'
        f'Ngày: {v["inv_date"]}\n\n\n'
        f'Mã cửa hàng:\nSố đơn hàng:\n'
        f'Tên người mua hàng: {v["buyer"]}\n'
        f'Tên đơn vị:\nMã số thuế:\n'
        f'Địa chỉ: {v["buyer_addr"]}\n'
        f'Số CCCD:\n'
        f'STT    Tên hàng hóa, dịch Đơn vị Số lượng          Đơn giá    Thành tiền      Thuế    Thuế      Tổng tiền sau\n'
        f'              vụ           tính                                               suất    GTGT         thuế\n'
        f'            {v["product"]}        {v["unit"]}   {v["qty"]}       {v["unit_price"]}   {v["amount"]}      {v["tax_rate"]}       {v["tax"]}      {v["total"]}\n\n\n'
        f'       Cộng                                                                                      {v["total"]}\n'
        f'       Bằng chữ\n\n\n'
        f'              Tổng hợp                        Số tiền             Thuế GTGT            Thành tiền đã có thuế\n'
        f'                                                                                             GTGT\n'
        f'Tổng tiền không chịu thuế\n'
        f'Tổng tiền chịu thuế suất 0%\n'
        f'Tổng tiền chịu thuế suất 5%\n'
        f'Tổng tiền chịu thuế suất 8%\n'
        f'Tổng tiền chịu thuế suất {v["tax_rate"]}             {v["amount"]}              {v["tax"]}                {v["total"]}\n\n\n'
        f'                   Người mua hàng                                          Người bán hàng\n'
    )


def gen_domestic_zoomtext(v):
    return (
        f'{v["seller"]}  \n'
        f'Địa chỉ: {v["seller_addr"]}  \n'
        f'Ký hiệu: {v["serial"]}  \n'
        f'Số: {v["inv_no"]}  \n\n'
        f'HÓA ĐƠN GTGT  \n\n'
        f'Ngày: {v["inv_date"]}  \n\n'
        f'Tên người mua hàng: {v["buyer"]}  \n'
        f'Địa chỉ: {v["buyer_addr"]}  \n'
    )


def generate_code():
    lines = []
    # International variants (cases 72-76)
    for i, v in enumerate(INTL_VARIANTS):
        case_num = 72 + i
        lines.append(f"\n# ── Case {case_num}: AGB_14166_variant_{i+1}.pdf ──")
        lines.append(f"def rawtext_{case_num:02d}():")
        lines.append(f"    return {repr(gen_intl_rawtext(v))}")
        lines.append(f"")
        lines.append(f"def zoomtext_{case_num:02d}():")
        lines.append(f"    return {repr(gen_intl_zoomtext(v))}")
        lines.append(f"")

    # Domestic variants (cases 77-81)
    for i, v in enumerate(DOMESTIC_VARIANTS):
        case_num = 77 + i
        lines.append(f"\n# ── Case {case_num}: AGB_12487_variant_{i+1}.pdf ──")
        lines.append(f"def rawtext_{case_num:02d}():")
        lines.append(f"    return {repr(gen_domestic_rawtext(v))}")
        lines.append(f"")
        lines.append(f"def zoomtext_{case_num:02d}():")
        lines.append(f"    return {repr(gen_domestic_zoomtext(v))}")
        lines.append(f"")

    # Registry entries
    lines.append("\n# ── Registry entries to add to CASES list ──")
    for i in range(5):
        cn = 72 + i
        lines.append(f"    ({cn}, 'AGB_14166_variant_{i+1}.pdf', rawtext_{cn:02d}, zoomtext_{cn:02d}),")
    for i in range(5):
        cn = 77 + i
        lines.append(f"    ({cn}, 'AGB_12487_variant_{i+1}.pdf', rawtext_{cn:02d}, zoomtext_{cn:02d}),")

    return "\n".join(lines)


if __name__ == "__main__":
    code = generate_code()
    print(code)

    # Write to output file
    out_path = "/home/vietpv/Desktop/ocr-deep/tests/generated_invoice_variants.py"
    with open(out_path, "w") as f:
        f.write('"""\nAuto-generated invoice variants.\n'
                '5 variants of AGB_14166 (International) format\n'
                '5 variants of AGB_12487 (Domestic/GTGT) format\n"""\n\n')
        f.write(code)
    print(f"\n✅ Written to {out_path}")
