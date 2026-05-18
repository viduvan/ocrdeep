#!/usr/bin/env python3
"""
Tạo hóa đơn GTGT điện tử Việt Nam chuẩn format mẫu 1702108687-C25MDT69.pdf
Output: generated_invoices/vn_real_variant_N.pdf
"""
import os
from fpdf import FPDF

FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD    = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "generated_invoices")
os.makedirs(OUT_DIR, exist_ok=True)

# ─── Data ────────────────────────────────────────────────────────────────────
INVOICES = [
    dict(
        ky_hieu="1C25MDT", so="112",
        ngay="12 tháng 01 năm 2025",
        seller="CÔNG TY TNHH SẢN XUẤT VẬT LIỆU XÂY DỰNG MINH LONG",
        seller_mst="0312456789",
        seller_addr="Số 45, Đường Nguyễn Văn Linh, P. Bình Thuận, Q. 7, TP. Hồ Chí Minh",
        seller_phone="0909123456",
        seller_bank_no="0721000456789", seller_bank="Ngân Hàng TMCP Ngoại Thương Việt Nam - CN Bình Dương",
        buyer_name="Nguyễn Văn Hùng",
        buyer_co="CÔNG TY CỔ PHẦN ĐẦU TƯ XÂY DỰNG HÒA BÌNH",
        buyer_mst="0303456781",
        buyer_addr="Tầng 5, Tòa nhà Hòa Bình, 56 Nguyễn Đình Chiểu, Q.3, TP.HCM",
        buyer_bank_no="", buyer_bank="",
        payment="TM/CK", note="",
        items=[
            dict(stt=1, name="Gạch ốp lát Granite 60x60cm - MSP: GL6060", dvt="m2",
                 sl=500, don_gia=185000, ts=10),
            dict(stt=2, name="Keo dán gạch Mapei Keraflex 25kg", dvt="bao",
                 sl=120, don_gia=145000, ts=10),
        ],
        ma_co_quan_thue="M1-25-8ABCD-00000000201",
        ma_bi_mat="ABCD1234EFGH5678",
    ),
    dict(
        ky_hieu="1C25HDT", so="234",
        ngay="25 tháng 02 năm 2025",
        seller="CÔNG TY TNHH DƯỢC PHẨM VÀ THIẾT BỊ Y TẾ PHƯƠNG NAM",
        seller_mst="0313567890",
        seller_addr="Lô B5, KCN Tân Bình, Phường Tây Thạnh, Quận Tân Phú, TP. Hồ Chí Minh",
        seller_phone="0283 8456789",
        seller_bank_no="1234567890", seller_bank="Ngân Hàng TMCP Công Thương Việt Nam - CN Tân Phú",
        buyer_name="",
        buyer_co="BỆNH VIỆN ĐA KHOA TỈNH BÌNH DƯƠNG",
        buyer_mst="3700234567",
        buyer_addr="Đường Bình Dương, Phường Hiệp Thành, TP. Thủ Dầu Một, Tỉnh Bình Dương",
        buyer_bank_no="", buyer_bank="",
        payment="CK", note="Theo HĐ số 12/2025/HĐ-BVBD",
        items=[
            dict(stt=1, name="Bông băng y tế vô trùng 100g - Hãng Việt Đức", dvt="hộp",
                 sl=200, don_gia=45000, ts=5),
            dict(stt=2, name="Găng tay cao su y tế size M (100 cái/hộp)", dvt="hộp",
                 sl=150, don_gia=68000, ts=5),
        ],
        ma_co_quan_thue="M1-25-9WXYZ-00000000345",
        ma_bi_mat="WXYZ9876ABCD5432",
    ),
    dict(
        ky_hieu="2C25KDT", so="089",
        ngay="10 tháng 03 năm 2025",
        seller="CÔNG TY CỔ PHẦN CÔNG NGHỆ THÔNG TIN VÀ TRUYỀN THÔNG VIỆT",
        seller_mst="0105678901",
        seller_addr="Tầng 12, Tòa nhà CMC, 11 Duy Tân, Phường Dịch Vọng Hậu, Q. Cầu Giấy, Hà Nội",
        seller_phone="024 6680 5678",
        seller_bank_no="0101000987654", seller_bank="Ngân Hàng TMCP Đầu Tư và Phát Triển Việt Nam - CN Hà Nội",
        buyer_name="Trần Thị Mai",
        buyer_co="CÔNG TY TNHH GIẢI PHÁP PHẦN MỀM SMART TECH",
        buyer_mst="0109345678",
        buyer_addr="Số 72, Ngõ 168 Nguyễn Khánh Toàn, Phường Quan Hoa, Q. Cầu Giấy, Hà Nội",
        buyer_bank_no="1023456789", buyer_bank="Ngân Hàng TMCP Kỹ Thương Việt Nam - CN Cầu Giấy",
        payment="CK", note="",
        items=[
            dict(stt=1, name="Bản quyền phần mềm Microsoft Office 365 Business (1 năm)", dvt="license",
                 sl=20, don_gia=2850000, ts=10),
            dict(stt=2, name="Dịch vụ triển khai và cài đặt hệ thống", dvt="gói",
                 sl=1,  don_gia=15000000, ts=10),
        ],
        ma_co_quan_thue="M1-25-3PQRS-00000000456",
        ma_bi_mat="PQRS1357TUVW2468",
    ),
    dict(
        ky_hieu="1C25CDT", so="567",
        ngay="18 tháng 04 năm 2025",
        seller="CÔNG TY TNHH THƯƠNG MẠI VÀ DỊCH VỤ VẬN TẢI ĐÔNG NAM",
        seller_mst="0204567890",
        seller_addr="Số 89, Đường Trần Phú, Phường Mỹ Bình, TP. Long Xuyên, Tỉnh An Giang",
        seller_phone="0296 3852456",
        seller_bank_no="2100200456789", seller_bank="Ngân Hàng NN&PTNT Việt Nam - Chi Nhánh An Giang",
        buyer_name="",
        buyer_co="CÔNG TY CỔ PHẦN XUẤT NHẬP KHẨU NÔNG SẢN AN GIANG",
        buyer_mst="0200789012",
        buyer_addr="Khu Công nghiệp Bình Long, Huyện Châu Phú, Tỉnh An Giang",
        buyer_bank_no="", buyer_bank="",
        payment="TM/CK", note="",
        items=[
            dict(stt=1, name="Cước vận chuyển hàng hóa tuyến An Giang - TP.HCM (xe 10 tấn)", dvt="chuyến",
                 sl=15, don_gia=4500000, ts=10),
            dict(stt=2, name="Phí bốc xếp và đóng gói hàng hóa", dvt="tấn",
                 sl=120, don_gia=85000, ts=10),
        ],
        ma_co_quan_thue="M1-25-4LMNO-00000000678",
        ma_bi_mat="LMNO2468PQRS1357",
    ),
    dict(
        ky_hieu="1C25BDT", so="901",
        ngay="05 tháng 06 năm 2025",
        seller="CÔNG TY CỔ PHẦN THỰC PHẨM VÀ ĐỒ UỐNG GOLD STAR",
        seller_mst="3600890123",
        seller_addr="Lô D8, Khu Công nghiệp Mỹ Xuân A2, Huyện Tân Thành, Tỉnh Bà Rịa - Vũng Tàu",
        seller_phone="0254 3892345",
        seller_bank_no="3502000345678", seller_bank="Ngân Hàng TMCP Ngoại Thương Việt Nam - CN Vũng Tàu",
        buyer_name="Lê Minh Tuấn",
        buyer_co="HỆ THỐNG SIÊU THỊ CO.OPMART HÀ NỘI",
        buyer_mst="0100235678",
        buyer_addr="Số 1, Đường Trần Duy Hưng, Phường Trung Hòa, Q. Cầu Giấy, Hà Nội",
        buyer_bank_no="", buyer_bank="",
        payment="CK", note="Theo PO số GS-2025-0601",
        items=[
            dict(stt=1, name="Nước trái cây đóng hộp Gold Star 330ml (thùng 24 lon)", dvt="thùng",
                 sl=500, don_gia=195000, ts=10),
            dict(stt=2, name="Nước tăng lực Gold Energy 250ml (thùng 24 lon)", dvt="thùng",
                 sl=300, don_gia=168000, ts=10),
        ],
        ma_co_quan_thue="M1-25-6RSTU-00000000789",
        ma_bi_mat="RSTU3579VWXY1234",
    ),
]


# ─── PDF Generator ───────────────────────────────────────────────────────────
class VNInvoicePDF(FPDF):
    def __init__(self, inv):
        super().__init__(orientation="L", format="A4")  # landscape for wide table
        self.inv = inv
        self.add_font("R", "", FONT_REGULAR)
        self.add_font("B", "", FONT_BOLD)
        self.set_margins(12, 10, 12)
        self.set_auto_page_break(True, margin=15)

    def _r(self, size=9): self.set_font("R", size=size)
    def _b(self, size=9): self.set_font("B", size=size)

    def build(self):
        self.add_page()
        inv = self.inv
        pw = self.w - self.l_margin - self.r_margin  # usable page width

        # ══════════════════════════════════════════════════════
        # HEADER: Tiêu đề căn giữa + Ký hiệu/Số bên phải (label + value cùng dòng)
        # Mẫu thật:  [  HÓA ĐƠN GIÁ TRỊ GIA TĂNG  ]  Ký hiệu: 1C25MDT
        #            [  Bản thể hiện hóa đơn ĐT     ]  Số:      112
        #            [  Ngày ...                     ]
        # ══════════════════════════════════════════════════════
        title_w = pw * 0.65   # 65% cho tiêu đề (thu hẹp để Ký hiệu/Số sát hơn)
        lbl_w   = 12          # width nhãn "Ký hiệu:" / "Số:" (thu hẹp để sát giá trị hơn)
        val_w   = pw - title_w - lbl_w  # phần còn lại cho giá trị

        # Dòng 1: Tiêu đề lớn | "Ký hiệu:" | "1C25MDT"
        self._b(17)
        self.cell(title_w, 9, "HÓA ĐƠN GIÁ TRỊ GIA TĂNG", align="C")
        self._r(8)
        self.cell(lbl_w, 9, "Ký hiệu:", align="L")
        self._b(9)
        self.cell(val_w, 9, inv["ky_hieu"], align="L", new_x="LMARGIN", new_y="NEXT")

        # Dòng 2: Bản thể hiện | "Số:" | "112"
        self._r(8)
        self.cell(title_w, 5, "Bản thể hiện của hóa đơn điện tử", align="C")
        self._r(8)
        self.cell(lbl_w, 5, "Số:", align="L")
        self._b(10)
        self.cell(val_w, 5, inv["so"], align="L", new_x="LMARGIN", new_y="NEXT")

        # Dòng 3: Ngày
        self._r(8)
        self.cell(title_w, 5, f"Ngày {inv['ngay']}", align="C")
        self.cell(lbl_w + val_w, 5, "", new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

        # ── Thông tin người bán ──
        lw = 50   # label width
        rh = 5    # row height

        def row(label, value, bold_val=True):
            self._b(8)
            self.cell(lw, rh, label)
            self._b(8) if bold_val else self._r(8)
            self.cell(0, rh, value, new_x="LMARGIN", new_y="NEXT")

        def row2(l1, v1, l2, v2, w1=lw, wv1=55, wl2=22):
            self._b(8); self.cell(w1, rh, l1)
            self._r(8); self.cell(wv1, rh, v1)
            self._b(8); self.cell(wl2, rh, l2)
            self._r(8); self.cell(0, rh, v2, new_x="LMARGIN", new_y="NEXT")

        row("Đơn vị bán hàng:", inv["seller"])
        row("Mã số thuế:", inv["seller_mst"])
        row("Địa chỉ:", inv["seller_addr"], bold_val=False)
        row2("Điện thoại:", inv["seller_phone"], "Số tài khoản:", inv["seller_bank_no"])
        row2("Ngân hàng:", inv["seller_bank"], "", "", wv1=pw - lw, wl2=0)
        self.ln(1)

        # ── Thông tin người mua ──
        row("Họ tên người mua:", inv.get("buyer_name", ""), bold_val=False)
        row("Tên đơn vị:", inv["buyer_co"])
        row("Mã số thuế:", inv["buyer_mst"])
        row("Địa chỉ:", inv["buyer_addr"], bold_val=False)
        row2("Số tài khoản:", inv.get("buyer_bank_no",""), "Ngân hàng:", inv.get("buyer_bank",""))
        row2("Hình thức thanh toán:", inv["payment"], "Ghi chú:", inv.get("note",""), w1=lw+5, wv1=25, wl2=18)
        self.ln(2)

        # ── Bảng hàng hóa ──
        # Columns: STT | Tên hàng | ĐVT | SL | Đơn giá | Thành tiền | Thuế suất | Tiền thuế | TT sau thuế
        cw = [9, 85, 14, 16, 28, 30, 14, 26, 30]
        hdr = ["STT", "Tên hàng hóa, dịch vụ", "ĐVT", "Số\nlượng",
               "Đơn giá", "Thành tiền", "Thuế\nsuất", "Tiền thuế", "Thành tiền\nsau thuế"]
        nums = ["1", "2", "3", "4", "5", "6=4x5", "7", "8=6x7", "9=6+8"]

        self.set_fill_color(220, 220, 220)
        self._b(7)
        for i, h in enumerate(hdr):
            self.cell(cw[i], 10, h, border=1, fill=True, align="C")
        self.ln()
        self._r(7)
        for i, n in enumerate(nums):
            self.cell(cw[i], 5, n, border=1, align="C")
        self.ln()

        total_hang = total_thue = 0
        tax_by_rate = {}

        for it in inv["items"]:
            tt = int(it["sl"] * it["don_gia"])
            thue = int(tt * it["ts"] / 100)
            sau = tt + thue
            total_hang += tt; total_thue += thue
            r = it["ts"]
            if r not in tax_by_rate: tax_by_rate[r] = {"base": 0, "thue": 0}
            tax_by_rate[r]["base"] += tt; tax_by_rate[r]["thue"] += thue

            def fmt(n): return f"{n:,.0f}".replace(",",".")
            self._r(7)
            vals = [str(it["stt"]), it["name"], it["dvt"],
                    fmt(it["sl"]), fmt(it["don_gia"]), fmt(tt),
                    f"{it['ts']}%", fmt(thue), fmt(sau)]
            for i, v in enumerate(vals):
                align = "L" if i == 1 else "C"
                self.cell(cw[i], 6, v, border=1, align=align)
            self.ln()

        # Cộng row (dòng tổng trong bảng)
        tong_sau = total_hang + total_thue
        def fmt(n): return f"{n:,.0f}".replace(",",".")
        self._b(7)
        span = cw[0]+cw[1]+cw[2]+cw[3]
        self.cell(span, 6, "Cộng tiền hàng hóa, dịch vụ:", border=1, align="R")
        self._r(7)
        self.cell(cw[4], 6, "", border=1)
        self.cell(cw[5], 6, fmt(total_hang), border=1, align="C")
        self.cell(cw[6], 6, "", border=1)
        self.cell(cw[7], 6, fmt(total_thue), border=1, align="C")
        self.cell(cw[8], 6, fmt(tong_sau), border=1, align="C")
        self.ln()  # xuống dòng sau bảng

        # "Số tiền bằng chữ" bên trái | "Tổng cộng tiền thanh toán" bên phải — cùng dòng
        self._r(8)
        self.cell(pw * 0.5, 6, "Số tiền viết bằng chữ: (viết bằng chữ tương ứng)", align="L")
        self._b(8)
        self.cell(pw * 0.5, 6,
                  f"Tổng cộng tiền thanh toán: {fmt(tong_sau)} đồng",
                  align="R", new_x="LMARGIN", new_y="NEXT")
        self.ln(3)

        # Chữ ký
        half = pw / 2
        self._b(9)
        self.cell(half, 5, "Người mua hàng", align="C")
        self.cell(half, 5, "Người bán hàng", align="C", new_x="LMARGIN", new_y="NEXT")
        self._r(7)
        self.cell(half, 4, "(Ký, ghi rõ họ tên)", align="C")
        self.cell(half, 4, "(Ký, ghi rõ họ tên)", align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(8)

        # Footer
        self.set_draw_color(150, 150, 150)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(1)
        self._r(6.5)
        self.cell(0, 4, f"Mã của cơ quan thuế: {inv['ma_co_quan_thue']}", align="C",
                  new_x="LMARGIN", new_y="NEXT")
        self.cell(0, 4,
                  "Đơn vị cung cấp dịch vụ HĐĐT: Tập đoàn Công nghiệp - Viễn thông Quân đội (Viettel), MST: 0100109106",
                  align="C", new_x="LMARGIN", new_y="NEXT")
        self.cell(0, 4,
                  f"Tra cứu: https://vinvoice.viettel.vn/utilities/invoice-search  |  Mã bí mật: {inv['ma_bi_mat']}",
                  align="C", new_x="LMARGIN", new_y="NEXT")


def main():
    print("Tạo hóa đơn GTGT điện tử chuẩn format mẫu...")
    for i, inv in enumerate(INVOICES, 1):
        pdf = VNInvoicePDF(inv)
        pdf.build()
        path = os.path.join(OUT_DIR, f"vn_real_variant_{i}.pdf")
        pdf.output(path)
        print(f"  ✅ {path}")
    print(f"\n🎉 Xong! {len(INVOICES)} hóa đơn lưu tại: {OUT_DIR}")

if __name__ == "__main__":
    main()
