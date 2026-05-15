#!/usr/bin/env python3
"""
Generate PDF invoices: 5 International (AGB_14166 format) + 5 Domestic GTGT (AGB_12487 format).
Output: generated_invoices/ directory.
"""
import os
from fpdf import FPDF

FONT_DIR = "/usr/share/fonts/truetype/dejavu"
FONT_REGULAR = os.path.join(FONT_DIR, "DejaVuSans.ttf")
FONT_BOLD = os.path.join(FONT_DIR, "DejaVuSans-Bold.ttf")

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "generated_invoices")
os.makedirs(OUT_DIR, exist_ok=True)

# ═══════════════════════════════════════════════════════════════
# DATA
# ═══════════════════════════════════════════════════════════════

INTL_DATA = [
    dict(seller="Minh Phát Trading Co., Ltd",
         seller_addr="45 Nguyen Hue Boulevard, District 1, Ho Chi Minh City, Vietnam",
         buyer="Atlas Pacific Supplies",
         buyer_addr="120 Collins Street, Melbourne, Victoria, Australia",
         inv_no="83412", inv_date="3/15/2025",
         product="Cashew Nuts", qty="150,320", unit_price="USD 0.25", unit="kg",
         price="USD 37,580", subtotal="USD 37,580", tax_rate="10%",
         tax="USD 3,758", total="USD 41,338", delivery="FOB"),
    dict(seller="Hoàng Long Logistics JSC",
         seller_addr="12 Tran Phu Street, Ba Dinh District, Hanoi, Vietnam",
         buyer="Nordic Fresh Imports AB",
         buyer_addr="Storgatan 22, 411 38 Gothenburg, Sweden",
         inv_no="VN-20250401", inv_date="4/1/2025",
         product="Frozen Pangasius Fillets", qty="82,500", unit_price="EUR 1.85", unit="kg",
         price="EUR 152,625", subtotal="EUR 152,625", tax_rate="5%",
         tax="EUR 7,631", total="EUR 160,256", delivery="CIF"),
    dict(seller="Sài Gòn Export Corp",
         seller_addr="88 Vo Van Tan, District 3, Ho Chi Minh City, Vietnam",
         buyer="Kobe Trading House Ltd",
         buyer_addr="2-4-7 Kitano-cho, Chuo-ku, Kobe 650-0002, Japan",
         inv_no="SGE-2025-0078", inv_date="5/10/2025",
         product="Robusta Coffee Beans", qty="45,000", unit_price="JPY 320", unit="kg",
         price="JPY 14,400,000", subtotal="JPY 14,400,000", tax_rate="8%",
         tax="JPY 1,152,000", total="JPY 15,552,000", delivery="CFR"),
    dict(seller="Đại Phong Materials Co., Ltd",
         seller_addr="156 Le Thanh Ton, Hai Chau District, Da Nang, Vietnam",
         buyer="Greenfield Wholesale Inc",
         buyer_addr="789 Broadway, Suite 400, New York, NY 10003, USA",
         inv_no="DP-INV-55021", inv_date="2/28/2025",
         product="Natural Rubber SVR 10", qty="126,000", unit_price="USD 1.58", unit="kg",
         price="USD 199,080", subtotal="USD 199,080", tax_rate="0%",
         tax="USD 0", total="USD 199,080", delivery="CIF"),
    dict(seller="Thiên An Ceramics JSC",
         seller_addr="Km5 National Road 1A, Bien Hoa, Dong Nai, Vietnam",
         buyer="EuroCasa Distributors GmbH",
         buyer_addr="Friedrichstrasse 45, 10117 Berlin, Germany",
         inv_no="TAC-2025-0193", inv_date="6/5/2025",
         product="Porcelain Floor Tiles 60x60cm", qty="32,000", unit_price="EUR 3.40", unit="sqm",
         price="EUR 108,800", subtotal="EUR 108,800", tax_rate="10%",
         tax="EUR 10,880", total="EUR 119,680", delivery="FOB"),
]

DOMESTIC_DATA = [
    dict(seller="Công Ty TNHH Thương Mại Bình Minh",
         seller_addr="25 Lý Thường Kiệt, Quận Hoàn Kiếm, Hà Nội, Việt Nam",
         seller_tax="0101567890",
         serial="002", inv_no="10245", inv_date="12/05/2025",
         buyer="Công Ty CP Phát Triển Số Việt",
         buyer_addr="78 Nguyễn Trãi, Quận Thanh Xuân, Hà Nội, Việt Nam",
         buyer_tax="0108234567",
         product="Máy in laser HP LaserJet Pro", unit="cái", qty="15",
         unit_price="8.500.000", amount="127.500.000",
         tax_rate="10%", tax="12.750.000", total="140.250.000"),
    dict(seller="Công Ty CP Vật Liệu Xây Dựng Đông Á",
         seller_addr="112 Trần Đại Nghĩa, Quận Hai Bà Trưng, Hà Nội, Việt Nam",
         seller_tax="0102345678",
         serial="003", inv_no="87623", inv_date="08/04/2025",
         buyer="Công Ty TNHH Xây Dựng Hòa Phát",
         buyer_addr="56 Phạm Văn Đồng, Quận Bắc Từ Liêm, Hà Nội, Việt Nam",
         buyer_tax="0109876543",
         product="Xi măng Portland PC40", unit="tấn", qty="200",
         unit_price="1.850.000", amount="370.000.000",
         tax_rate="8%", tax="29.600.000", total="399.600.000"),
    dict(seller="Công Ty TNHH Điện Tử Sao Việt",
         seller_addr="34 Lê Văn Lương, Quận Cầu Giấy, Hà Nội, Việt Nam",
         seller_tax="0103456789",
         serial="001", inv_no="45890", inv_date="20/03/2025",
         buyer="Công Ty CP Giải Pháp Công Nghệ FTS",
         buyer_addr="99 Hoàng Quốc Việt, Quận Cầu Giấy, Hà Nội, Việt Nam",
         buyer_tax="0107654321",
         product="Bộ lưu điện UPS APC 3000VA", unit="bộ", qty="8",
         unit_price="25.600.000", amount="204.800.000",
         tax_rate="10%", tax="20.480.000", total="225.280.000"),
    dict(seller="Công Ty CP Thực Phẩm Hương Quê",
         seller_addr="67 Ngô Quyền, Quận Hai Bà Trưng, Hà Nội, Việt Nam",
         seller_tax="0104567891",
         serial="004", inv_no="33401", inv_date="01/06/2025",
         buyer="Siêu Thị Mega Market Việt Nam",
         buyer_addr="162 Lê Duẩn, Quận 1, TP Hồ Chí Minh, Việt Nam",
         buyer_tax="0312987654",
         product="Gạo Jasmine đặc sản 5kg", unit="bao", qty="5.000",
         unit_price="125.000", amount="625.000.000",
         tax_rate="5%", tax="31.250.000", total="656.250.000"),
    dict(seller="Công Ty TNHH Nội Thất Phú Quý",
         seller_addr="210 Giải Phóng, Quận Đống Đa, Hà Nội, Việt Nam",
         seller_tax="0105678912",
         serial="005", inv_no="72018", inv_date="15/01/2025",
         buyer="Khách Sạn Mường Thanh Grand Hà Nội",
         buyer_addr="4 Lý Thái Tổ, Quận Hoàn Kiếm, Hà Nội, Việt Nam",
         buyer_tax="0106543210",
         product="Bàn ghế hội nghị gỗ sồi", unit="bộ", qty="30",
         unit_price="12.800.000", amount="384.000.000",
         tax_rate="10%", tax="38.400.000", total="422.400.000"),
]


# ═══════════════════════════════════════════════════════════════
# PDF GENERATORS
# ═══════════════════════════════════════════════════════════════

class InternationalInvoicePDF(FPDF):
    """Generates International Invoice matching AGB_14166 format."""

    def __init__(self, data):
        super().__init__()
        self.d = data
        self.add_font("DejaVu", "", FONT_REGULAR)
        self.add_font("DejaVu", "B", FONT_BOLD)
        self.set_auto_page_break(auto=True, margin=15)

    def build(self):
        self.add_page()
        d = self.d

        # ── Seller header (left) + Beneficiary (right) ──
        self.set_font("DejaVu", "B", 14)
        self.cell(0, 8, d["seller"], new_x="LMARGIN", new_y="NEXT")
        self.set_font("DejaVu", "", 9)
        self.cell(0, 5, d["seller_addr"], new_x="LMARGIN", new_y="NEXT")
        self.cell(0, 5, "Tel:", new_x="LMARGIN", new_y="NEXT")
        self.ln(3)

        self.set_font("DejaVu", "", 9)
        self.cell(0, 5, f"Beneficiary: {d['seller']}", new_x="LMARGIN", new_y="NEXT")
        self.cell(0, 5, "Bank:                                          SWIFT Code:", new_x="LMARGIN", new_y="NEXT")
        self.cell(0, 5, "Bank account:", new_x="LMARGIN", new_y="NEXT")
        self.ln(6)

        # ── INVOICE title ──
        self.set_font("DejaVu", "B", 22)
        self.cell(0, 12, "INVOICE", align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(5)

        # ── Bill to / Invoice info ──
        self.set_font("DejaVu", "", 9)
        y_start = self.get_y()
        # Left column
        self.cell(95, 5, f"Bill to: {d['buyer']}", new_x="LMARGIN", new_y="NEXT")
        self.cell(95, 5, f"Address: {d['buyer_addr']}", new_x="LMARGIN", new_y="NEXT")
        self.cell(95, 5, "Phone:", new_x="LMARGIN", new_y="NEXT")
        self.cell(95, 5, "Fax:", new_x="LMARGIN", new_y="NEXT")
        y_end = self.get_y()

        # Right column
        self.set_xy(120, y_start)
        self.set_font("DejaVu", "B", 9)
        self.cell(70, 5, f"Invoice #: {d['inv_no']}", new_x="LMARGIN", new_y="NEXT")
        self.set_xy(120, y_start + 5)
        self.cell(70, 5, f"Invoice Date: {d['inv_date']}", new_x="LMARGIN", new_y="NEXT")
        self.set_y(y_end)
        self.ln(3)

        # ── Customer ──
        self.set_font("DejaVu", "", 9)
        self.cell(0, 5, f"Customer: {d['buyer']}", new_x="LMARGIN", new_y="NEXT")
        self.cell(0, 5, f"Address: {d['buyer_addr']}", new_x="LMARGIN", new_y="NEXT")
        self.ln(3)
        self.cell(0, 5, f"Invoice For PO#:                    Delivery term: {d['delivery']}", new_x="LMARGIN", new_y="NEXT")
        self.ln(5)

        # ── Item table ──
        col_w = [15, 55, 25, 30, 20, 40]
        headers = ["Item #", "Description", "Quantity", "Unit Price", "Unit", "Price"]
        self.set_font("DejaVu", "B", 9)
        self.set_fill_color(220, 220, 220)
        for i, h in enumerate(headers):
            self.cell(col_w[i], 7, h, border=1, fill=True, align="C")
        self.ln()

        self.set_font("DejaVu", "", 9)
        row = ["1", d["product"], d["qty"], d["unit_price"], d["unit"], d["price"]]
        for i, v in enumerate(row):
            self.cell(col_w[i], 7, v, border=1, align="C")
        self.ln(15)

        # ── Signature area ──
        self.cell(95, 5, "Signature", new_x="LMARGIN", new_y="NEXT")
        self.ln(10)

        # ── Totals (right-aligned) ──
        x_label = 120
        x_val = 160
        self.set_font("DejaVu", "", 10)
        for label, val in [("Invoice Subtotal", d["subtotal"]),
                           ("Tax Rate", d["tax_rate"]),
                           ("Sales Tax", d["tax"])]:
            self.set_x(x_label)
            self.cell(40, 6, label, align="R")
            self.cell(35, 6, val, align="R", new_x="LMARGIN", new_y="NEXT")

        self.ln(5)
        self.set_font("DejaVu", "B", 10)
        self.set_x(x_label)
        self.cell(40, 6, "Other")
        self.ln()
        self.set_x(x_label)
        self.cell(40, 8, "TOTAL", align="R")
        self.set_font("DejaVu", "B", 12)
        self.cell(35, 8, d["total"], align="R")


class DomesticInvoicePDF(FPDF):
    """Generates Vietnamese GTGT Invoice matching AGB_12487 format."""

    def __init__(self, data):
        super().__init__()
        self.d = data
        self.add_font("DejaVu", "", FONT_REGULAR)
        self.add_font("DejaVu", "B", FONT_BOLD)
        self.set_auto_page_break(auto=True, margin=15)

    def build(self):
        self.add_page()
        d = self.d

        # ── Seller header ──
        self.set_font("DejaVu", "B", 12)
        self.cell(120, 7, d["seller"], new_x="RIGHT")
        self.set_font("DejaVu", "", 9)
        self.cell(0, 7, f"Ký hiệu: {d['serial']}", align="R", new_x="LMARGIN", new_y="NEXT")

        self.set_font("DejaVu", "", 9)
        self.cell(120, 5, f"Địa chỉ: {d['seller_addr']}", new_x="RIGHT")
        self.cell(0, 5, f"Số: {d['inv_no']}", align="R", new_x="LMARGIN", new_y="NEXT")
        self.cell(0, 5, f"Mã số thuế: {d['seller_tax']}", new_x="LMARGIN", new_y="NEXT")
        self.ln(6)

        # ── Title ──
        self.set_font("DejaVu", "B", 20)
        self.cell(0, 12, "HÓA ĐƠN GIÁ TRỊ GIA TĂNG", align="C", new_x="LMARGIN", new_y="NEXT")
        self.set_font("DejaVu", "", 10)
        self.cell(0, 7, f"Ngày: {d['inv_date']}", align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(5)

        # ── Buyer info ──
        self.set_font("DejaVu", "", 9)
        fields = [
            ("Mã cửa hàng:", ""),
            ("Tên người mua hàng:", d["buyer"]),
            ("Tên đơn vị:", ""),
            ("Mã số thuế:", d["buyer_tax"]),
            ("Địa chỉ:", d["buyer_addr"]),
            ("Số CCCD:", ""),
        ]
        for label, val in fields:
            self.set_font("DejaVu", "", 9)
            self.cell(45, 5, label)
            self.set_font("DejaVu", "B" if val else "", 9)
            self.cell(0, 5, val, new_x="LMARGIN", new_y="NEXT")
        self.ln(5)

        # ── Item table ──
        col_w = [10, 42, 15, 16, 25, 28, 12, 22, 25]
        headers = ["STT", "Tên hàng hóa", "ĐVT", "Số lượng", "Đơn giá", "Thành tiền", "Thuế\nsuất", "Thuế\nGTGT", "Tổng tiền\nsau thuế"]
        self.set_font("DejaVu", "B", 7)
        self.set_fill_color(230, 230, 230)
        for i, h in enumerate(headers):
            self.cell(col_w[i], 10, h, border=1, fill=True, align="C")
        self.ln()

        self.set_font("DejaVu", "", 7)
        row = ["1", d["product"], d["unit"], d["qty"], d["unit_price"], d["amount"], d["tax_rate"], d["tax"], d["total"]]
        for i, v in enumerate(row):
            self.cell(col_w[i], 8, v, border=1, align="C")
        self.ln(12)

        # ── Cộng ──
        self.set_font("DejaVu", "B", 9)
        self.cell(45, 6, "Cộng")
        self.set_x(170)
        self.cell(0, 6, d["total"], align="R", new_x="LMARGIN", new_y="NEXT")
        self.set_font("DejaVu", "", 9)
        self.cell(0, 6, "Bằng chữ:", new_x="LMARGIN", new_y="NEXT")
        self.ln(8)

        # ── Tax summary table ──
        self.set_font("DejaVu", "B", 8)
        self.set_fill_color(230, 230, 230)
        sum_w = [60, 40, 40, 50]
        sum_h = ["Tổng hợp", "Số tiền", "Thuế GTGT", "Thành tiền đã có thuế GTGT"]
        for i, h in enumerate(sum_h):
            self.cell(sum_w[i], 7, h, border=1, fill=True, align="C")
        self.ln()

        self.set_font("DejaVu", "", 8)
        tax_rows = [
            ("Tổng tiền không chịu thuế", "", "", ""),
            ("Tổng tiền chịu thuế suất 0%", "", "", ""),
            ("Tổng tiền chịu thuế suất 5%", "", "", ""),
            ("Tổng tiền chịu thuế suất 8%", "", "", ""),
            (f"Tổng tiền chịu thuế suất {d['tax_rate']}", d["amount"], d["tax"], d["total"]),
        ]
        for row in tax_rows:
            for i, v in enumerate(row):
                self.cell(sum_w[i], 6, v, border=1, align="C" if i > 0 else "L")
            self.ln()
        self.ln(15)

        # ── Signatures ──
        self.set_font("DejaVu", "B", 10)
        self.cell(95, 7, "Người mua hàng", align="C")
        self.cell(95, 7, "Người bán hàng", align="C")


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    print("Generating International Invoice PDFs (AGB_14166 format)...")
    for i, data in enumerate(INTL_DATA, 1):
        pdf = InternationalInvoicePDF(data)
        pdf.build()
        path = os.path.join(OUT_DIR, f"AGB_14166_variant_{i}.pdf")
        pdf.output(path)
        print(f"  ✅ {path}")

    print("\nGenerating Domestic GTGT Invoice PDFs (AGB_12487 format)...")
    for i, data in enumerate(DOMESTIC_DATA, 1):
        pdf = DomesticInvoicePDF(data)
        pdf.build()
        path = os.path.join(OUT_DIR, f"AGB_12487_variant_{i}.pdf")
        pdf.output(path)
        print(f"  ✅ {path}")

    print(f"\n🎉 Done! All 10 PDFs saved to: {OUT_DIR}")


if __name__ == "__main__":
    main()
