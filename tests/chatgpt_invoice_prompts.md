# ChatGPT Image Generation Prompts for OCR Testing Invoices

This file contains **20 complete ChatGPT/DALL-E 3 image generation prompts**. 
- **Prompts 1-10** generate Vietnamese GTGT (VAT) Invoices with specific serial numbers (`1C25TAA`, `1C25THO`, etc.), a bold red title "HÓA ĐƠN GIÁ TRỊ GIA TĂNG", and a company logo.
- **Prompts 11-20** generate Commercial Invoices with no `invoiceSerial` or `invoiceFormNo`, following international trade formats.

All prompts specify an A4 portrait layout, crisp text, and direct front-facing scanned document quality (no background clutter, hands, or perspective angles).

---

## Part A: 10 Vietnamese GTGT (VAT) Invoices

### VN-01: Software/IT Services (FPT eInvoice Style)
**Copy and paste the prompt below into ChatGPT:**
```text
A direct front-facing high-resolution scanned document, clean A4 portrait PDF format, white background, crisp vector-like text. No background objects, no hands, no perspective.
Top-left: A small corporate square logo.
Top-right:
"Ký hiệu: 1C25TAA"
"Số: 00008912"
Top-center: Large red bold title "HÓA ĐƠN GIÁ TRỊ GIA TĂNG" and subtitle "VAT INVOICE". Below it: "Ngày 15 tháng 06 năm 2025".

Seller info section:
"Đơn vị bán hàng: CÔNG TY CỔ PHẦN CÔNG NGHỆ VÀ GIẢI PHÁP FPT"
"Mã số thuế: 0101248141"
"Địa chỉ: Số 10 Phạm Văn Bạch, Phường Cầu Giấy, Hà Nội, Việt Nam"
"Điện thoại: 02435626000"

Buyer info section:
"Đơn vị mua hàng: NGÂN HÀNG TMCP ĐẦU TƯ VÀ PHÁT TRIỂN VIỆT NAM"
"Mã số thuế: 0100150619"
"Địa chỉ: Tháp BIDV, 35 Hàng Vôi, Quận Hoàn Kiếm, Hà Nội, Việt Nam"
"Hình thức thanh toán: Chuyển khoản"

An itemized table with thin borders:
Columns: "STT" | "Tên hàng hóa, dịch vụ" | "ĐVT" | "Số lượng" | "Đơn giá" | "Thành tiền"
Row 1: "1" | "Phí triển khai phần mềm Core Banking" | "Dịch vụ" | "1" | "850.000.000" | "850.000.000"
Row 2: "2" | "Phí bảo trì hệ thống Q3/2025" | "Dịch vụ" | "1" | "120.000.000" | "120.000.000"

Financial Summary below the table:
"Cộng tiền hàng: 970.000.000"
"Thuế suất GTGT: 10%"
"Tiền thuế GTGT: 97.000.000"
"Tổng cộng tiền thanh toán: 1.067.000.000"
"Số tiền viết bằng chữ: Một tỷ không trăm sáu mươi bảy triệu đồng"

Bottom-right: A green digital signature block: "Signature Valid - Ký bởi: CÔNG TY CỔ PHẦN CÔNG NGHỆ VÀ GIẢI PHÁP FPT"
```

---

### VN-02: Building Materials (MISA meInvoice Style)
**Copy and paste the prompt below into ChatGPT:**
```text
A direct front-facing scanned document, clean A4 portrait PDF format, white background, crisp vector-like text. No background objects, no hands, no perspective.
Top-left: A generic square company logo.
Top-right:
"Ký hiệu: 1C25TTD"
"Số: 00001578"
Top-center: Large red bold title "HÓA ĐƠN GIÁ TRỊ GIA TĂNG"
Below it: "Ngày 22 tháng 04 năm 2025"

Seller info section:
"Đơn vị bán hàng: CÔNG TY TNHH THƯƠNG MẠI VÀ XÂY DỰNG T&D"
"Mã số thuế: 0801285357"
"Địa chỉ: Đội 1, Nghi Khê, Xã Tân Kỳ, TP Hải Phòng, Việt Nam"
"Điện thoại: 0979372192" | "Email: dinhchung.ibst@gmail.com"
"Số tài khoản: 19134220914019 tại Techcombank - CN Thống nhất Hải Dương"

Buyer info section:
"Tên đơn vị mua hàng: CÔNG TY CỔ PHẦN VẬT LIỆU HOME"
"Mã số thuế: 0108921542"
"Địa chỉ: Tầng 7, số 18 Ngụy Như Kon Tum, Phường Thanh Xuân, Hà Nội, Việt Nam"
"Hình thức thanh toán: Tiền mặt/Chuyển khoản"

An itemized table with thin borders:
Columns: "STT" | "Tên hàng hóa, dịch vụ" | "ĐVT" | "Số lượng" | "Đơn giá" | "Thành tiền"
Row 1: "1" | "Sơn chống thấm Sika Raintite 20kg" | "thùng" | "45" | "1.250.000" | "56.250.000"
Row 2: "2" | "Keo dán gạch Weber Tai Flexible 25kg" | "bao" | "120" | "185.000" | "22.200.000"

Financial Summary below the table:
"Cộng tiền hàng: 78.450.000"

A smaller tax summary table below:
Columns: "Thuế suất" | "Tiền hàng" | "Tiền thuế"
Row 1: "8%" | "78.450.000" | "6.276.000"
Row 2: "Tổng cộng" | "78.450.000" | "6.276.000"

Grand totals:
"Tổng cộng tiền thanh toán: 84.726.000"
"Số tiền viết bằng chữ: Tám mươi bốn triệu bảy trăm hai mươi sáu nghìn đồng"

Footer text: "Phát hành bởi phần mềm MISA meInvoice - Công ty Cổ phần MISA (www.misa.vn)"
```

---

### VN-03: Pharmaceuticals (MISA meInvoice Style)
**Copy and paste the prompt below into ChatGPT:**
```text
A direct front-facing scanned document, clean A4 portrait PDF format, white background, crisp vector-like text. No background objects, no hands, no perspective.
Top-left: A generic square pharmaceutical logo.
Top-right:
"Ký hiệu: 1C25THO"
"Số: 00003241"
Top-center: Large red bold title "HÓA ĐƠN GIÁ TRỊ GIA TĂNG"
Below it: "Ngày 10 tháng 05 năm 2025"

Seller info section:
"Đơn vị bán hàng: CÔNG TY CỔ PHẦN DƯỢC PHẨM TRUNG ƯƠNG 1 - PHARBACO"
"Mã số thuế: 0100108656"
"Địa chỉ: 160 Tôn Thất Tùng, Phường Khương Thượng, Quận Đống Đa, Hà Nội, Việt Nam"

Buyer info section:
"Tên đơn vị mua hàng: BỆNH VIỆN ĐA KHOA TỈNH HẢI DƯƠNG"
"Mã số thuế: 0800100503"
"Địa chỉ: 225 Nguyễn Lương Bằng, TP Hải Dương, Hải Dương, Việt Nam"
"Hình thức thanh toán: CK"

An itemized table with thin borders:
Columns: "STT" | "Tên hàng hóa, dịch vụ" | "ĐVT" | "Số lượng" | "Đơn giá" | "Thành tiền"
Row 1: "1" | "Amoxicillin 500mg (hộp 10 vỉ x 10 viên)" | "hộp" | "500" | "42.000" | "21.000.000"
Row 2: "2" | "Paracetamol 500mg (hộp 10 vỉ x 10 viên)" | "hộp" | "1.000" | "18.500" | "18.500.000"
Row 3: "3" | "Vitamin C 500mg (lọ 100 viên)" | "lọ" | "200" | "35.000" | "7.000.000"

Financial Summary below the table:
"Cộng tiền hàng: 46.500.000"

A smaller tax summary table below:
Columns: "Thuế suất" | "Tiền hàng" | "Tiền thuế"
Row 1: "5%" | "46.500.000" | "2.325.000"
Row 2: "Tổng cộng" | "46.500.000" | "2.325.000"

Grand totals:
"Tổng cộng tiền thanh toán: 48.825.000"
"Số tiền viết bằng chữ: Bốn mươi tám triệu tám trăm hai mươi lăm nghìn đồng"
```

---

### VN-04: Medical Devices (Viettel S-Invoice Style)
**Copy and paste the prompt below into ChatGPT:**
```text
A direct front-facing scanned document, clean A4 portrait PDF format, white background, crisp vector-like text. No background objects, no hands, no perspective.
Top-left: A generic square medical company logo.
Top-right:
"Ký hiệu: 1C25MDT"
"Số: 00000089"
Top-center: Large red bold title "HÓA ĐƠN GIÁ TRỊ GIA TĂNG"
Below it: "Ngày 28 tháng 03 năm 2025"

Seller info section:
"Đơn vị bán hàng: CÔNG TY TNHH THIẾT BỊ Y TẾ PHƯƠNG ĐÔNG"
"Mã số thuế: 0314567890"
"Địa chỉ: 45 Bùi Thị Xuân, Quận 1, TP Hồ Chí Minh, Việt Nam"
"Điện thoại: 02838123456"

Buyer info section:
"Tên đơn vị mua hàng: SỞ Y TẾ THÀNH PHỐ ĐÀ NẴNG"
"Mã số thuế: 0401234567"
"Địa chỉ: 103 Quang Trung, Quận Hải Châu, Đà Nẵng, Việt Nam"
"Hình thức thanh toán: Chuyển khoản"

An itemized table with thin borders containing 9 columns:
Columns: "STT" | "Tên hàng hóa, dịch vụ" | "ĐVT" | "Số lượng" | "Đơn giá" | "Thành tiền" | "Thuế suất" | "Tiền thuế" | "Thành tiền sau thuế"
Row 1: "1" | "Máy đo huyết áp điện tử Omron HEM-7156" | "cái" | "80" | "1.890.000" | "151.200.000" | "5%" | "7.560.000" | "158.760.000"

Financial Summary below the table:
"Cộng tiền hàng: 151.200.000"
"Tổng cộng tiền thuế GTGT: 7.560.000"
"Tổng cộng tiền thanh toán: 158.760.000"
"Số tiền viết bằng chữ: Một trăm năm mươi tám triệu bảy trăm sáu mươi nghìn đồng"

Footer: "Mã của cơ quan thuế: M1-25-8HKPT-00000000089"
```

---

### VN-05: Hosting/Domain Services (MatBao eInvoice Style)
**Copy and paste the prompt below into ChatGPT:**
```text
A direct front-facing scanned document, clean A4 portrait PDF format, white background, crisp vector-like text. No background objects, no hands, no perspective.
Top-left: A generic cloud hosting service company logo.
Top-right:
"Ký hiệu: 1C24TMB"
"Số: 00018923"
Top-center: Large red bold title "HÓA ĐƠN GIÁ TRỊ GIA TĂNG"
Below it: "Ngày 05 tháng 02 năm 2025"

Seller info section:
"Đơn vị bán hàng: CHI NHÁNH CÔNG TY CỔ PHẦN MẮT BÃO"
"Mã số thuế: 0302712571-001"
"Địa chỉ: Tầng 8, Số 381 Đội Cấn, Phường Liễu Giai, Quận Ba Đình, Hà Nội, Việt Nam"
"Điện thoại: 024.35123456"
"Số tài khoản: 500038888 tại VP Bank - CN Láng Hạ"

Buyer info section:
"Người mua hàng: Nguyễn Văn Minh"
"Địa chỉ: Số 15 ngõ 82 Phố Chùa Láng, Phường Láng Thượng, Quận Đống Đa, Hà Nội, Việt Nam"
"Hình thức thanh toán: TM/CK"

An itemized table with thin borders:
Columns: "STT" | "Tên hàng hóa, dịch vụ" | "ĐVT" | "Số lượng" | "Đơn giá" | "Thành tiền"
Row 1: "1" | "Phí duy trì tên miền .vn (minhtech.vn)" | "Năm" | "3" | "350.000" | "1.050.000"
Row 2: "2" | "Phí hosting Linux SSD 5GB" | "Năm" | "2" | "890.000" | "1.780.000"
Row 3: "3" | "Phí SSL Certificate DV" | "Năm" | "1" | "450.000" | "450.000"

Financial Summary below the table:
"Cộng tiền hàng: 3.280.000"
"Thuế suất GTGT: 10%"
"Tiền thuế GTGT: 328.000"
"Tổng cộng tiền thanh toán: 3.608.000"
"Số tiền viết bằng chữ: Ba triệu sáu trăm lẻ tám nghìn đồng"
```

---

### VN-06: Food Products (Viettel S-Invoice Style)
**Copy and paste the prompt below into ChatGPT:**
```text
A direct front-facing scanned document, clean A4 portrait PDF format, white background, crisp vector-like text. No background objects, no hands, no perspective.
Top-left: A generic square agriculture company logo.
Top-right:
"Ký hiệu: 1C25TLT"
"Số: 00000425"
Top-center: Large red bold title "HÓA ĐƠN GIÁ TRỊ GIA TĂNG"
Below it: "Ngày 18 tháng 07 năm 2025"

Seller info section:
"Đơn vị bán hàng: CÔNG TY TNHH TÙNG LAM VP"
"Mã số thuế: 2500616746"
"Địa chỉ: Số 15, Đường Trần Phú, TP Việt Trì, Phú Thọ, Việt Nam"
"Điện thoại: 0979309565"
"Số tài khoản: 0361000334555 tại Ngân hàng TMCP Ngoại thương Việt Nam"

Buyer info section:
"Tên đơn vị mua hàng: CÔNG TY CỔ PHẦN VẬT LIỆU HOME"
"Mã số thuế: 0108921542"
"Địa chỉ: Tầng 7, số 18 Ngụy Như Kon Tum, Phường Thanh Xuân, Hà Nội, Việt Nam"
"Hình thức thanh toán: TM/CK"

An itemized table with thin borders containing 9 columns:
Columns: "STT" | "Tên hàng hóa, dịch vụ" | "ĐVT" | "Số lượng" | "Đơn giá" | "Thành tiền" | "Thuế suất" | "Tiền thuế" | "Thành tiền sau thuế"
Row 1: "1" | "Gạo Jasmine đặc sản 5kg" | "bao" | "2.000" | "125.000" | "250.000.000" | "5%" | "12.500.000" | "262.500.000"

Financial Summary below the table:
"Cộng tiền hàng: 250.000.000"
"Tổng cộng tiền thuế GTGT: 12.500.000"
"Tổng cộng tiền thanh toán: 262.500.000"
"Số tiền viết bằng chữ: Hai trăm sáu mươi hai triệu năm trăm nghìn đồng"

Footer: "Mã của cơ quan thuế: M1-25-7FGBT-00000000425"
```

---

### VN-07: Electricity (FPT eInvoice Style)
**Copy and paste the prompt below into ChatGPT:**
```text
A direct front-facing scanned document, clean A4 portrait PDF format, white background, crisp vector-like text. No background objects, no hands, no perspective.
Top-left: A generic lightning bolt power company logo.
Top-right:
"Ký hiệu: 1C25TAA"
"Số: 00125678"
Top-center: Large red bold title "HÓA ĐƠN GIÁ TRỊ GIA TĂNG"
Below it: "Ngày 01 tháng 08 năm 2025"

Seller info section:
"Đơn vị bán hàng: TỔNG CÔNG TY ĐIỆN LỰC MIỀN BẮC"
"Mã số thuế: 0100100417"
"Địa chỉ: Số 20 Trần Nguyên Hãn, Quận Hoàn Kiếm, Hà Nội, Việt Nam"

Buyer info section:
"Tên đơn vị mua hàng: CÔNG TY TNHH SẢN XUẤT THƯƠNG MẠI HƯNG THỊNH"
"Mã số thuế: 0106789012"
"Địa chỉ: Lô A5, KCN Quang Minh, Mê Linh, Hà Nội, Việt Nam"
"Hình thức thanh toán: Chuyển khoản"

An itemized table with thin borders:
Columns: "STT" | "Tên hàng hóa, dịch vụ" | "ĐVT" | "Số lượng" | "Đơn giá" | "Thành tiền"
Row 1: "1" | "Tiền điện T07/2025 (Giờ bình thường)" | "kWh" | "45.200" | "1.555" | "70.286.000"
Row 2: "2" | "Tiền điện T07/2025 (Giờ cao điểm)" | "kWh" | "12.800" | "2.871" | "36.748.800"
Row 3: "3" | "Tiền điện T07/2025 (Giờ thấp điểm)" | "kWh" | "18.500" | "970" | "17.945.000"

Financial Summary below the table:
"Cộng tiền hàng: 124.979.800"
"Thuế suất GTGT: 10%"
"Tiền thuế GTGT: 12.497.980"
"Tổng cộng tiền thanh toán: 137.477.780"
"Số tiền viết bằng chữ: Một trăm ba mươi bảy triệu bốn trăm bảy mươi bảy nghìn bảy trăm tám mươi đồng"
```

---

### VN-08: Office Furniture (M-INVOICE Style - Bilingual)
**Copy and paste the prompt below into ChatGPT:**
```text
A direct front-facing scanned document, clean A4 portrait PDF format, white background, crisp vector-like text. No perspective, no hands.
Bilingual Vietnamese/English labels.
Top-left: A generic square construction company logo.
Top-right:
"Ký hiệu (Serial): 1C25TAA"
"Số (No.): 00000054"
Top-center: Large red bold title "HÓA ĐƠN GIÁ TRỊ GIA TĂNG"
Below it in smaller text: "VAT INVOICE"
"Ngày 14 tháng 10 năm 2025"

Seller info section:
"Đơn vị bán hàng (Seller): CÔNG TY TNHH ĐẦU TƯ THƯƠNG MẠI VÀ TƯ VẤN XÂY DỰNG A&A"
"Mã số thuế (Tax Code): 0110255219"
"Địa chỉ (Address): Đường Lê Trọng Tấn, Phường Dương Nội, Hà Nội, Việt Nam"
"Điện thoại (Phone): 0363610739" | "Email: Ctytnhhaa@gmail.com"

Buyer info section:
"Tên đơn vị mua hàng (Buyer): CÔNG TY CỔ PHẦN VẬT LIỆU HOME"
"Mã số thuế (Tax Code): 0108921542"
"Địa chỉ (Address): Tầng 7, số 18 Ngụy Như Kon Tum, Phường Thanh Xuân, Hà Nội, Việt Nam"
"Hình thức thanh toán (Payment Method): TM/CK"

An itemized table with thin borders:
Columns: "STT (No.)" | "Tên hàng hóa, dịch vụ (Description)" | "ĐVT (Unit)" | "Số lượng (Qty)" | "Đơn giá (Unit Price)" | "Thành tiền (Amount)"
Row 1: "1" | "Bàn làm việc gỗ sồi 140x70cm" | "cái" | "25" | "4.850.000" | "121.250.000"
Row 2: "2" | "Ghế văn phòng lưới ergonomic" | "cái" | "25" | "3.200.000" | "80.000.000"

Financial Summary below the table:
"Cộng tiền hàng (Pre-tax price): 201.250.000"
"Thuế suất GTGT (VAT rate): 10%"
"Tiền thuế GTGT (VAT amount): 20.125.000"
"Tổng cộng tiền thanh toán (Total amount): 221.375.000"
"Số tiền viết bằng chữ (Total in words): Hai trăm hai mươi mốt triệu ba trăm bảy mươi lăm nghìn đồng"

Footer: "Tra cứu hóa đơn tại website: https://tracuuhoadon.minvoice.com.vn/"
```

---

### VN-09: Coal Transportation (Viettel S-Invoice Style)
**Copy and paste the prompt below into ChatGPT:**
```text
A direct front-facing scanned document, clean A4 portrait PDF format, white background, crisp vector-like text. No background objects, no hands, no perspective.
Top-left: A generic square coal logistics company logo.
Top-right:
"Ký hiệu: 1C25MDT"
"Số: 00000312"
Top-center: Large red bold title "HÓA ĐƠN GIÁ TRỊ GIA TĂNG"
Below it: "Ngày 20 tháng 09 năm 2025"

Seller info section:
"Đơn vị bán hàng: CÔNG TY CP VẬT TẢI ĐƯỜNG BỘ VINACOMIN"
"Mã số thuế: 5700100169"
"Địa chỉ: 85 Lê Thánh Tông, TP Hạ Long, Quảng Ninh, Việt Nam"
"Điện thoại: 02033838899"

Buyer info section:
"Tên đơn vị mua hàng: CÔNG TY CP XI MĂNG THĂNG LONG"
"Mã số thuế: 0500456789"
"Địa chỉ: KCN Bỉm Sơn, Thị xã Bỉm Sơn, Thanh Hóa, Việt Nam"
"Hình thức thanh toán: Chuyển khoản"

An itemized table with thin borders containing 9 columns:
Columns: "STT" | "Tên hàng hóa, dịch vụ" | "ĐVT" | "Số lượng" | "Đơn giá" | "Thành tiền" | "Thuế suất" | "Tiền thuế" | "Thành tiền sau thuế"
Row 1: "1" | "Cước vận chuyển than từ mỏ Hà Tu đến cảng Cái Lân (T9/2025)" | "chuyến" | "85" | "15.500.000" | "1.317.500.000" | "10%" | "131.750.000" | "1.449.250.000"

Financial Summary below the table:
"Cộng tiền hàng: 1.317.500.000"
"Tổng cộng tiền thuế GTGT: 131.750.000"
"Tổng cộng tiền thanh toán: 1.449.250.000"
"Số tiền viết bằng chữ: Một tỷ bốn trăm bốn mươi chín triệu hai trăm năm mươi nghìn đồng"
```

---

### VN-10: Steel Materials (MISA meInvoice Style)
**Copy and paste the prompt below into ChatGPT:**
```text
A direct front-facing scanned document, clean A4 portrait PDF format, white background, crisp vector-like text. No perspective, no hands.
Top-left: A generic square steel factory logo.
Top-right:
"Ký hiệu: 1C25THO"
"Số: 00000892"
Top-center: Large red bold title "HÓA ĐƠN GIÁ TRỊ GIA TĂNG"
Below it: "Ngày 12 tháng 11 năm 2025"

Seller info section:
"Đơn vị bán hàng: CÔNG TY TNHH THÉP KHÔNG GỈ ĐẠI VIỆT"
"Mã số thuế: 3602345678"
"Địa chỉ: KCN Nhơn Trạch 2, Đồng Nai, Việt Nam"
"Điện thoại: 02513560789"

Buyer info section:
"Tên đơn vị mua hàng: CÔNG TY CP CƠ KHÍ CHÍNH XÁC BÁCH KHOA"
"Mã số thuế: 0107890123"
"Địa chỉ: 27 Cổ Nhuế, Quận Bắc Từ Liêm, Hà Nội, Việt Nam"
"Hình thức thanh toán: CK"

An itemized table with thin borders:
Columns: "STT" | "Tên hàng hóa, dịch vụ" | "ĐVT" | "Số lượng" | "Đơn giá" | "Thành tiền"
Row 1: "1" | "Thép tấm inox SUS304 2mm (1220x2440mm)" | "tấm" | "300" | "2.800.000" | "840.000.000"
Row 2: "2" | "Ống inox SUS201 Ø48.6x1.5mm x 6m" | "cây" | "500" | "285.000" | "142.500.000"

Financial Summary below the table:
"Cộng tiền hàng: 982.500.000"

A smaller tax summary table below:
Columns: "Thuế suất" | "Tiền hàng" | "Tiền thuế"
Row 1: "10%" | "982.500.000" | "98.250.000"
Row 2: "Tổng cộng" | "982.500.000" | "98.250.000"

Grand totals:
"Tổng cộng tiền thanh toán: 1.080.750.000"
"Số tiền viết bằng chữ: Một tỷ không trăm tám mươi triệu bảy trăm năm mươi nghìn đồng"

Footer: "Phát hành bởi phần mềm MISA meInvoice"
```

---

## Part B: 10 Commercial Invoices

> [!NOTE]
> All Commercial invoices omit `invoiceSerial` and `invoiceFormNo`, adhering strictly to international standards.

### CM-01: Cashew Trading (Standard 2-Column - AUD)
**Copy and paste the prompt below into ChatGPT:**
```text
A direct front-facing scanned document of a professional commercial invoice, clean A4 portrait PDF format, white background, crisp black text. No perspective, no hands.
Top-center or Left: Large bold title "COMMERCIAL INVOICE"
Top Section (2 columns):
- Left column (Seller):
  "Minh Phát Trading Co., Ltd"
  "45 Nguyen Hue Boulevard, District 1, Ho Chi Minh City, Vietnam"
- Right column (Invoice details):
  "Invoice No: MPT-2025-0618"
  "Date: June 18, 2025"

Buyer Info Section:
"Bill to: Atlas Pacific Supplies Pty Ltd"
"Address: 120 Collins Street, Melbourne, Victoria 3000, Australia"

An itemized table with thin borders:
Columns: "No." | "Description of Goods" | "Unit" | "Quantity" | "Unit Price (AUD)" | "Total Amount (AUD)"
Row 1: "1" | "Cashew Nuts W320 Grade A" | "kg" | "150,000" | "4.20" | "630,000.00"
Row 2: "2" | "Cashew Nuts W450" | "kg" | "50,000" | "3.50" | "175,000.00"

Below table:
"Total Invoice Value: AUD 805,000.00"
"Delivery Terms: CIF Melbourne"
"Payment Terms: L/C at sight"

Footer:
"Bank Details:"
"Beneficiary: Minh Phát Trading Co., Ltd"
"Bank: Vietcombank, Ho Chi Minh Branch"
"Account No: 0071000888999"
```

---

### CM-02: Industrial Valves (CN to FR Trade - USD)
**Copy and paste the prompt below into ChatGPT:**
```text
A direct front-facing scanned document, clean A4 portrait PDF format, white background, crisp black text. No perspective, no hands.
Top-center: Large bold capital title "COMMERCIAL INVOICE"
Header Details:
"INVOICE NO.: INV250618"
"DATE: JUN 18TH, 2025"

Seller & Buyer Sections in bold all-caps headers:
"THE SELLER:"
"ANHUI PROSPER FLOW TECHNOLOGY CO., LTD."
"NO.951 TAISHAN ROAD, TONGLING, ANHUI, CHINA"
"TEL: 86-562-8898168"

"THE BUYER:"
"TLSH SAS"
"27 BOULEVARD CHARLES MORETTI - 13014 MARSEILLE, FRANCE"

An itemized table with thin borders:
Columns: "NO." | "DESCRIPTION OF GOODS" | "UNIT" | "QTY" | "UNIT PRICE (USD)" | "TOTAL AMOUNT (USD)"
Row 1: "1" | "Universal Coupling DN100" | "PCS" | "20" | "13.89" | "277.80"
Row 2: "2" | "Gate Valve DN80" | "PCS" | "15" | "39.17" | "587.55"
Row 3: "3" | "Air Valve DN25" | "PCS" | "200" | "2.92" | "584.00"

Below table:
"TOTAL AMOUNT: USD 1,449.35"
"DELIVERY TERMS: EXW"
"PAYMENT TERMS: T/T"
```

---

### CM-03: Frozen Seafood (International Shipping - AUD)
**Copy and paste the prompt below into ChatGPT:**
```text
A direct front-facing scanned document of an international shipping commercial invoice, clean A4 portrait PDF format, white background, crisp text. No perspective, no hands.
Top-center: Bold title "COMMERCIAL INVOICE"
Header Details:
"Invoice No: HLA-2025-0618"
"Date: 06/18/2025"

Shipper / Exporter Section:
"Hạ Long Aquaculture JSC"
"Lot A5, Cai Lan Industrial Zone, Quang Ninh, Vietnam"

Consignee / Buyer Section:
"Oceanic Fresh Foods Pty Ltd"
"Unit 7, 42 Wharf Road, Port Adelaide, SA 5015, Australia"

Shipping details block:
"Port of Loading: Hai Phong Port" | "Port of Discharge: Port Adelaide"
"Vessel: TBN" | "Delivery Terms: CFR Port Adelaide"

An itemized table with thin borders:
Columns: "No." | "Description of Goods (including HS Code)" | "Unit" | "Quantity" | "Unit Price (AUD)" | "Total Amount (AUD)"
Row 1: "1" | "Frozen Black Tiger Shrimp HOSO 16/20 (HS: 0306.17)" | "kg" | "10,000" | "18.50" | "185,000.00"
Row 2: "2" | "Frozen Vannamei Shrimp PD 31/40 (HS: 0306.36)" | "kg" | "6,000" | "12.00" | "72,000.00"

Below table:
"Total Invoice Amount: AUD 257,000.00"
"Payment Terms: T/T 30 days after B/L date"
```

---

### CM-04: Coffee Export (European Corporate - CHF)
**Copy and paste the prompt below into ChatGPT:**
```text
A direct front-facing scanned document of a European corporate trade invoice, clean A4 portrait PDF format, white background, clean sans-serif text. No perspective, no hands.
Top-left: A simple clean coffee-cup corporate logo.
Top-right: Bold title "INVOICE"
"Invoice Number: VCB-EXP-25128"
"Date: 18/06/2025"

Seller Details:
"Vinacafé Biên Hòa Export"
"2 Ngô Quyền, TP Biên Hòa, Đồng Nai, Vietnam"
"VAT Number: VN 0300401887"

Buyer Details:
"Bill to: Zürich Kaffee Import AG"
"Bahnhofstrasse 78, 8001 Zürich, Switzerland"
"VAT Number: CHE-123.456.789"

An itemized table with thin borders:
Columns: "Item" | "Description of Goods" | "Unit" | "Quantity" | "Unit Price (CHF)" | "Total (CHF)"
Row 1: "1" | "Arabica Green Coffee Beans Grade 1" | "MT" | "24" | "5,200.00" | "124,800.00"

Below table:
"Total Amount: CHF 124,800.00"
"Delivery Terms: CIF Zürich"
"Payment Terms: L/C 60 days"
"Country of Origin: Vietnam"

Bank Details:
"Beneficiary: Vinacafé Biên Hòa Export"
"Bank: Joint Stock Commercial Bank for Foreign Trade of Vietnam"
"IBAN: VN89 VCBH 0100 0004 0188 722"
"SWIFT Code: VFTB VNVX"
```

---

### CM-05: Tech Products eCommerce (Shippo-Style Layout - SGD)
**Copy and paste the prompt below into ChatGPT:**
```text
A direct front-facing scanned document of an eCommerce commercial invoice (Shippo-style layout), clean A4 portrait PDF format, white background, clean geometric layout. No perspective, no hands.
Top-left: A minimalist tech company logo.
Top-right: Bold title "Commercial Invoice"
"Invoice ID: #2025-0618"
"Date: 06/18/2025"

Shipper / Exporter:
"TechStore Vietnam JSC"
"88 Vo Van Tan, District 3, Ho Chi Minh City, Vietnam"
"Email: export@techstorevn.com"

Recipient / Ship To:
"SmartBuy Electronics Pte Ltd"
"30 Cecil Street, #19-08 Prudential Tower, Singapore 049712"

Shipping Metadata:
"Carrier: UPS" | "Tracking Number: 1Z798A900123456784"
"Contents Type: MERCHANDISE" | "Incoterms: DDP Singapore"

An itemized table with thin borders:
Columns: "No." | "Item Description" | "Unit" | "Qty" | "Unit Value (SGD)" | "Total Value (SGD)"
Row 1: "1" | "Wireless Earbuds TWS Pro" | "PCS" | "500" | "8.50" | "4,250.00"
Row 2: "2" | "USB-C Fast Charger 65W" | "PCS" | "300" | "5.20" | "1,560.00"
Row 3: "3" | "Phone Case Silicone (Mixed)" | "PCS" | "1,000" | "1.80" | "1,800.00"

Below table:
"Total Invoice Value: SGD 7,610.00"
"Payment Terms: T/T 100% before shipment"
```

---

### CM-06: Heavy Industrial Steel Export (USD)
**Copy and paste the prompt below into ChatGPT:**
```text
A direct front-facing scanned document of a heavy industrial commercial invoice, clean A4 portrait PDF format, white background, clean grid layout. No perspective, no hands.
Top-left: A minimalist industrial steel logo.
Top-right: Bold title "COMMERCIAL INVOICE"
"Invoice No: PMS-INV-92045"
"Date: July 12, 2025"

Seller Details:
"Phú Mỹ Steel Corporation"
"KCN Phú Mỹ 1, Tân Thành, Bà Rịa - Vũng Tàu, Vietnam"

Buyer Details:
"Al Rajhi Construction Materials LLC"
"King Fahd Road, P.O. Box 28, Riyadh 11411, Saudi Arabia"

Shipment Parameters:
"Port of Loading: Cai Mep Port, Vietnam" | "Delivery Term: FOB Cai Mep Port"
"Net Weight: 2,300 MT" | "Gross Weight: 2,345 MT"
"Country of Origin: Vietnam"

An itemized table with thin borders:
Columns: "No." | "Description of Goods & Specification" | "HS Code" | "Unit" | "Quantity" | "Unit Price (USD)" | "Total Amount (USD)"
Row 1: "1" | "Hot Rolled Steel Coil Q235B (3mm x 1250mm)" | "7208.37" | "MT" | "1,500" | "485.00" | "727,500.00"
Row 2: "2" | "Cold Rolled Steel SPCC (1mm x 1219x2438mm)" | "7209.16" | "MT" | "800" | "620.00" | "496,000.00"

Below table:
"Total Value: USD 1,223,500.00"
"Payment Terms: Irrevocable L/C at sight"
```

---

### CM-07: Ceramics & Tiles Export (EUR)
**Copy and paste the prompt below into ChatGPT:**
```text
A direct front-facing scanned document of a professional trade invoice, clean A4 portrait PDF format, white background, sharp text. No perspective, no hands.
Top-left: A geometric tile-like company logo.
Top-right: Bold title "COMMERCIAL INVOICE"
"Invoice No: TAC-2025-0345"
"Date: 06/05/2025"

Seller info:
"Thiên An Ceramics JSC"
"Km5 National Road 1A, Bien Hoa, Dong Nai, Vietnam"

Buyer info:
"EuroCasa Distributors GmbH"
"Friedrichstrasse 45, 10117 Berlin, Germany"
"VAT No: DE 812345678"

Trade Reference info:
"Proforma Invoice Ref: PI-TAC-2025-0290" | "Container Info: 2x40' HC"
"Delivery Terms: FOB Ho Chi Minh City"

An itemized table with thin borders:
Columns: "No." | "Description of Ceramic/Porcelain Tiles" | "Unit" | "Qty" | "Unit Price (EUR)" | "Total Value (EUR)"
Row 1: "1" | "Porcelain Floor Tiles 60x60cm White Marble" | "SQM" | "20,000" | "3.40" | "68,000.00"
Row 2: "2" | "Porcelain Wall Tiles 30x60cm Grey" | "SQM" | "10,000" | "2.80" | "28,000.00"
Row 3: "3" | "Ceramic Mosaic 30x30cm Mixed" | "SQM" | "5,000" | "4.50" | "22,500.00"

Below table:
"Total Amount Payable: EUR 118,500.00"
"Payment Terms: 30% T/T advance, 70% against B/L"
```

---

### CM-08: Bilingual Hardware Import (CN to VN - USD)
**Copy and paste the prompt below into ChatGPT:**
```text
A direct front-facing scanned document of a bilingual Chinese/English commercial invoice, clean A4 portrait PDF format, white background, clean grid layout. No perspective, no hands.
Top-center: Bold title "COMMERCIAL INVOICE / 商业发票"
"Invoice No. / 发票号: No20250618005"
"Date / 日期: 2025-06-18"

Shipper Info / 寄货人资料:
"Gunri Precision Hardware Co., Ltd. (宣城市冠瑞精密五金有限公司)"
"Changqiao Road, Xuancheng Economic Development Zone, Anhui, China"
"Tel: 86-18929233070"

Consignee Info / 收货人资料:
"DONG DUONG EQUIPMENT TRADING COMPANY LIMITED"
"124 Le Trong Tan Street, La Khe Ward, Ha Dong District, Ha Noi, Viet Nam"

An itemized table with thin borders:
Columns: "No." | "Description of Goods (货物名称)" | "Unit" | "Qty" | "Unit Price ($)" | "Amount ($)"
Row 1: "1" | "Locating Pin 8x35 (定位销)" | "PCS" | "2,000" | "0.13" | "260.00"
Row 2: "2" | "Guide Bushing GR 18x25 (导套)" | "PCS" | "300" | "1.00" | "300.00"
Row 3: "3" | "Shoulder Bolt 10x35 (肩螺栓)" | "PCS" | "800" | "0.14" | "112.00"

Below table:
"Total Amount: USD 672.00"
"Total in Words: SAY USD SIX HUNDRED SEVENTY TWO ONLY"
"Delivery Terms: EXW" | "Payment: T/T 100% before shipment"
"Country of Origin: China" | "Material: Steel"
```

---

### CM-09: Eyecare Equipment Import (FR to VN - EUR)
**Copy and paste the prompt below into ChatGPT:**
```text
A direct front-facing scanned document of a European corporate eyecare invoice, clean A4 portrait PDF format, white background, clean sans-serif layout. No perspective, no hands.
Top-left: Luneau Technology corporate logo.
Top-right: Bold title "Invoice"
"Invoice Number: 25004812"
"Date: 18.06.2025"

Seller details:
"Luneau Technology Operations"
"2 rue Roger Bonnet, 27340 Pont-de-l'Arche, France"
"VAT Number: FR 53 086 150 208"
"SIRET: 086 150 208 00048" | "Phone: +33 (0) 232 989 132"

Buyer details:
"Kim Hung Company Limited"
"86 Le Duan Street, Hoan Kiem District, 10000 Hanoi, Vietnam"

An itemized table with thin borders:
Columns: "Item" | "Description of Goods (including HS Code)" | "Unit" | "Qty" | "Unit Price (EUR)" | "Amount (EUR)"
Row 1: "1" | "Retinoscopy Racks Pair of L2 (HS: 9033009000)" | "PC" | "100" | "61.00" | "6,100.00"

Below table:
"Total Invoice Value: EUR 6,100.00"
"Delivery: Ex Works" | "Payment: Cash in advance"

Bank Details:
"IBAN: FR76 3000 4001 2200 0246 5236 831"
"SWIFT: BNPAFRPP"
```

---

### CM-10: Rubber Export (Full International Trade - USD)
**Copy and paste the prompt below into ChatGPT:**
```text
A direct front-facing scanned document of an international rubber trade commercial invoice, clean A4 portrait PDF format, white background, clean and professional layout. No perspective, no hands.
Top-left: A minimalist generic leaf-like materials company logo.
Top-right: Bold title "COMMERCIAL INVOICE"
"Invoice No: DP-INV-61025"
"Date: June 18, 2025"

Seller Info:
"Đại Phong Materials Co., Ltd"
"156 Le Thanh Ton, Hai Chau District, Da Nang, Vietnam"
"Tel: +84-236-3821456"

Buyer Info:
 greenfield Wholesale Inc
"789 Broadway, Suite 400, New York, NY 10003, USA"

Trade Metadata:
"Contract No: DP-GF-2025-018" | "Payment: Irrevocable L/C No. LC-2025-VCB-06789"
"Port of Loading: Da Nang Port, Vietnam" | "Port of Discharge: Port Newark, USA"
"Delivery Terms: CIF New York"

An itemized table with thin borders:
Columns: "No." | "Description of Goods (with HS Code)" | "Unit" | "Qty" | "Unit Price (USD)" | "Total Amount (USD)"
Row 1: "1" | "Natural Rubber SVR 10 (HS: 4001.22)" | "MT" | "200" | "1,580.00" | "316,000.00"
Row 2: "2" | "Natural Rubber SVR 20 (HS: 4001.22)" | "MT" | "100" | "1,450.00" | "145,000.00"

Below table:
"Total Invoice Amount: USD 461,000.00"
"Total in Words: SAY TOTAL USD FOUR HUNDRED SIXTY ONE THOUSAND ONLY"

Bank Info:
"Beneficiary Bank: Vietcombank - Da Nang Branch"
"Account No: 0071001234567" | "SWIFT Code: VFTB VNVX 007"
```
