"""
Test cases for OCR Giấy Đăng Ký Kinh Doanh (ĐKKD) endpoint.

Test file: /home/vietpv/FIS/BE-ocr/back-end/Giay-dang-ky-kinh-doanh-FIS-lan-21_signed.pdf

Run all tests:
    python -m pytest tests/test_dkkd.py -v

Run specific groups:
    python -m pytest tests/test_dkkd.py -v -k "test_schema"
    python -m pytest tests/test_dkkd.py -v -k "test_regex"
    python -m pytest tests/test_dkkd.py -v -k "test_llm"
    python -m pytest tests/test_dkkd.py -v -k "test_api"
"""
import os
import json
import pytest
import requests
from pathlib import Path

# ── Config ─────────────────────────────────────────────────────────────────────

# Path to sample DKKD PDF (FIS company, 21st registration change)
SAMPLE_PDF = Path("/home/vietpv/FIS/BE-ocr/back-end/Giay-dang-ky-kinh-doanh-FIS-lan-21_signed.pdf")

# API base URL (adjust if running on different port)
API_BASE = os.getenv("OCR_API_BASE", "http://localhost:8000")
DKKD_ENDPOINT = f"{API_BASE}/ocr-dkkd"


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def sample_pdf_path():
    if not SAMPLE_PDF.exists():
        pytest.skip(f"Sample PDF not found: {SAMPLE_PDF}")
    return SAMPLE_PDF


@pytest.fixture(scope="module")
def ocr_raw_text(sample_pdf_path):
    """Run Vision OCR on sample PDF and return raw text (cached per module)."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))

    from src import file_handler, config
    from src.vllm_service import stream_ocr_response, OCRTimeoutError

    pdf_path = str(sample_pdf_path)
    page_count = file_handler.get_pdf_page_count(pdf_path)
    prompt = config.PROMPTS.get("plain", "Free OCR.")
    all_texts = []

    for page_idx in range(page_count):
        image_bytes = file_handler.extract_pdf_page_bytes(pdf_path, page_idx)
        chunks = []
        try:
            for chunk in stream_ocr_response(
                model_name=config.VLLM_MODEL,
                prompt=prompt,
                image_bytes=image_bytes,
                options=config.INFERENCE_PARAMS,
                timeout_seconds=config.OCR_TIMEOUT_SECONDS,
            ):
                if chunk:
                    chunks.append(chunk)
        except OCRTimeoutError:
            chunks.append("\n<!-- OCR_TIMEOUT -->\n")
        page_text = "".join(chunks).strip()
        all_texts.append(f"--- PAGE {page_idx + 1} ---\n{page_text}")

    return "\n\n".join(all_texts)


# ── Schema Tests ───────────────────────────────────────────────────────────────

class TestSchema:
    """Verify Pydantic schema classes are importable and well-formed."""

    def test_import_business_registration(self):
        from src.schemas.business_registration import BusinessRegistration
        biz = BusinessRegistration()
        assert biz.maSoDoanhNghiep is None
        assert biz.nguoiDaiDienPhapLuat == []
        assert biz.thanhVienGopVon == []

    def test_import_legal_representative(self):
        from src.schemas.business_registration import LegalRepresentative
        rep = LegalRepresentative(hoVaTen="NGUYỄN VĂN A", chucDanh="Tổng Giám đốc")
        assert rep.hoVaTen == "NGUYỄN VĂN A"

    def test_import_capital_contributor(self):
        from src.schemas.business_registration import CapitalContributor
        contrib = CapitalContributor(
            stt=1,
            tenThanhVien="NGUYỄN VĂN B",
            quocTich="Việt Nam",
            tyLe="25%",
        )
        assert contrib.stt == 1
        assert contrib.tyLe == "25%"

    def test_model_dump(self):
        from src.schemas.business_registration import BusinessRegistration, LegalRepresentative
        biz = BusinessRegistration(
            maSoDoanhNghiep="0101245017",
            tenDoanhNghiep="CÔNG TY CỔ PHẦN FPT",
            nguoiDaiDienPhapLuat=[
                LegalRepresentative(hoVaTen="TEST NAME", chucDanh="TGĐ")
            ]
        )
        dumped = biz.model_dump()
        assert dumped["maSoDoanhNghiep"] == "0101245017"
        assert len(dumped["nguoiDaiDienPhapLuat"]) == 1
        assert dumped["nguoiDaiDienPhapLuat"][0]["hoVaTen"] == "TEST NAME"


# ── Regex Parser Tests ─────────────────────────────────────────────────────────

class TestRegexParser:
    """Test regex fallback parser with synthetic and real OCR text."""

    SYNTHETIC_TEXT = """
CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM

GIẤY CHỨNG NHẬN ĐĂNG KÝ DOANH NGHIỆP
Công ty cổ phần

Đăng ký lần đầu ngày: 13/09/2002
Đăng ký thay đổi lần thứ: 21, ngày 10 tháng 06 năm 2024

Mã số doanh nghiệp: 0101245017

1. Tên doanh nghiệp:
Tên doanh nghiệp: CÔNG TY CỔ PHẦN FPT
Tên nước ngoài: FPT CORPORATION
Tên viết tắt: FPT

2. Địa chỉ trụ sở chính:
Địa chỉ trụ sở chính: Tòa nhà FPT, Phố Duy Tân, Phường Dịch Vọng Hậu, Quận Cầu Giấy, Thành phố Hà Nội, Việt Nam
Điện thoại: 024.37687898
Fax: 024.37687879
Email: fpt@fpt.com.vn
Website: www.fpt.com.vn

3. Vốn điều lệ: 18.961.210.840.000 đồng

Loại hình doanh nghiệp: Công ty cổ phần

Người đại diện theo pháp luật:
Họ và tên: NGUYỄN VĂN KHOA
Giới tính: Nam
Chức danh: Tổng Giám đốc
Sinh ngày: 01/01/1975
Quốc tịch: Việt Nam
Dân tộc: Kinh
CMND/CCCD số: 001075012345
Ngày cấp: 15/06/2020
Nơi cấp: Cục Cảnh sát QLHC về TTXH

4. Danh sách thành viên góp vốn
STT | Tên thành viên | Quốc tịch | Địa chỉ liên lạc | Phần vốn góp | Tỷ lệ (%) | Số giấy tờ pháp lý | Ghi chú
1 | NGUYỄN THÀNH NAM | Việt Nam | 123 Nguyễn Trãi, Hà Nội | 500.000.000 đồng | 5% | 001070012345 |
"""

    def test_parse_enterprise_code(self):
        from src.parsers.dkkd_parser import parse_dkkd
        biz = parse_dkkd(self.SYNTHETIC_TEXT)
        assert biz.maSoDoanhNghiep == "0101245017"

    def test_parse_enterprise_name(self):
        from src.parsers.dkkd_parser import parse_dkkd
        biz = parse_dkkd(self.SYNTHETIC_TEXT)
        assert biz.tenDoanhNghiep == "CÔNG TY CỔ PHẦN FPT"

    def test_parse_enterprise_type(self):
        from src.parsers.dkkd_parser import parse_dkkd
        biz = parse_dkkd(self.SYNTHETIC_TEXT)
        assert biz.loaiHinhDoanhNghiep is not None

    def test_parse_address(self):
        from src.parsers.dkkd_parser import parse_dkkd
        biz = parse_dkkd(self.SYNTHETIC_TEXT)
        assert biz.diaChi is not None
        assert "Hà Nội" in biz.diaChi or "FPT" in biz.diaChi

    def test_parse_capital(self):
        from src.parsers.dkkd_parser import parse_dkkd
        biz = parse_dkkd(self.SYNTHETIC_TEXT)
        assert biz.vonDieuLe is not None
        assert "18" in biz.vonDieuLe

    def test_parse_legal_representative(self):
        from src.parsers.dkkd_parser import parse_dkkd
        biz = parse_dkkd(self.SYNTHETIC_TEXT)
        assert len(biz.nguoiDaiDienPhapLuat) >= 1
        rep = biz.nguoiDaiDienPhapLuat[0]
        assert rep.hoVaTen == "NGUYỄN VĂN KHOA"
        assert rep.chucDanh == "Tổng Giám đốc"

    def test_parse_registration_dates(self):
        from src.parsers.dkkd_parser import parse_dkkd
        biz = parse_dkkd(self.SYNTHETIC_TEXT)
        assert biz.ngayDangKy == "13/09/2002"
        assert biz.lanDangKy == "21"

    def test_parse_returns_business_registration_type(self):
        from src.parsers.dkkd_parser import parse_dkkd
        from src.schemas.business_registration import BusinessRegistration
        biz = parse_dkkd(self.SYNTHETIC_TEXT)
        assert isinstance(biz, BusinessRegistration)


# ── LLM Extractor Tests ────────────────────────────────────────────────────────

class TestLLMExtractor:
    """Test LLM-based extractor (requires FPT_API_KEY env var and network)."""

    @pytest.mark.skipif(
        not os.getenv("FPT_API_KEY"),
        reason="FPT_API_KEY not set — skipping LLM tests"
    )
    def test_llm_extract_basic_fields(self, ocr_raw_text):
        from src.extractors.dkkd_extractor import extract_dkkd_llm
        result = extract_dkkd_llm(ocr_raw_text)
        assert result is not None, "LLM extraction returned None"
        assert result.get("maSoDoanhNghiep") is not None, "maSoDoanhNghiep missing"
        assert result.get("tenDoanhNghiep") is not None, "tenDoanhNghiep missing"

    @pytest.mark.skipif(
        not os.getenv("FPT_API_KEY"),
        reason="FPT_API_KEY not set — skipping LLM tests"
    )
    def test_llm_extract_legal_representative(self, ocr_raw_text):
        from src.extractors.dkkd_extractor import extract_dkkd_llm
        result = extract_dkkd_llm(ocr_raw_text)
        assert result is not None
        reps = result.get("nguoiDaiDienPhapLuat", [])
        assert len(reps) >= 1, "No legal representatives extracted"
        rep = reps[0]
        assert rep.get("hoVaTen") is not None, "Legal rep name missing"

    @pytest.mark.skipif(
        not os.getenv("FPT_API_KEY"),
        reason="FPT_API_KEY not set — skipping LLM tests"
    )
    def test_llm_extract_capital_contributors(self, ocr_raw_text):
        from src.extractors.dkkd_extractor import extract_dkkd_llm
        result = extract_dkkd_llm(ocr_raw_text)
        assert result is not None
        contributors = result.get("thanhVienGopVon", [])
        # FIS has shareholders — there should be at least 1
        assert len(contributors) >= 1, "No capital contributors extracted"
        contrib = contributors[0]
        assert contrib.get("tenThanhVien") is not None

    @pytest.mark.skipif(
        not os.getenv("FPT_API_KEY"),
        reason="FPT_API_KEY not set — skipping LLM tests"
    )
    def test_llm_extract_to_pydantic(self, ocr_raw_text):
        from src.extractors.dkkd_extractor import extract_dkkd_llm_to_pydantic
        from src.schemas.business_registration import BusinessRegistration
        biz = extract_dkkd_llm_to_pydantic(ocr_raw_text)
        assert biz is not None
        assert isinstance(biz, BusinessRegistration)


# ── API Endpoint Tests ─────────────────────────────────────────────────────────

class TestAPIEndpoint:
    """Test /ocr-dkkd endpoint (requires running ocr-deep server)."""

    @pytest.fixture(autouse=True)
    def check_server(self):
        try:
            resp = requests.get(f"{API_BASE}/health", timeout=3)
            if resp.status_code != 200:
                pytest.skip("ocr-deep server not running")
        except requests.exceptions.ConnectionError:
            pytest.skip(f"ocr-deep server not reachable at {API_BASE}")

    def test_endpoint_exists(self):
        """Verify the endpoint is registered (405 = exists but wrong method)."""
        resp = requests.get(DKKD_ENDPOINT, timeout=5)
        assert resp.status_code in (200, 405, 422), \
            f"Unexpected status: {resp.status_code}"

    def test_endpoint_rejects_unsupported_file_type(self, tmp_path):
        fake_png = tmp_path / "test.png"
        fake_png.write_bytes(b"fake image data")
        with open(fake_png, "rb") as f:
            resp = requests.post(
                DKKD_ENDPOINT,
                files={"file": ("test.png", f, "image/png")},
                timeout=10,
            )
        assert resp.status_code == 400

    def test_endpoint_full_flow(self, sample_pdf_path):
        """Full OCR flow with actual FIS DKKD PDF."""
        with open(sample_pdf_path, "rb") as f:
            resp = requests.post(
                DKKD_ENDPOINT,
                files={"file": (sample_pdf_path.name, f, "application/pdf")},
                timeout=300,  # OCR + LLM can be slow
            )

        assert resp.status_code == 200
        body = resp.json()

        # Check response structure
        assert "status" in body, "Missing 'status' field"
        assert body["status"] == 200, f"Response status not 200: {body.get('status')}"
        assert "data" in body, "Missing 'data' field"

        data = body["data"]
        assert isinstance(data, dict), "data should be a dict"

    def test_response_has_required_fields(self, sample_pdf_path):
        """Verify all fields required by OcrCorporateBussinessResponse are present."""
        with open(sample_pdf_path, "rb") as f:
            resp = requests.post(
                DKKD_ENDPOINT,
                files={"file": (sample_pdf_path.name, f, "application/pdf")},
                timeout=300,
            )

        assert resp.status_code == 200
        data = resp.json().get("data", {})

        # Required fields mapping to OcrCorporateBussinessResponse
        required_keys = [
            "maSoDoanhNghiep",
            "tenDoanhNghiep",
            "loaiHinhDoanhNghiep",
            "diaChi",
            "vonDieuLe",
            "nguoiDaiDienPhapLuat",
            "thanhVienGopVon",
        ]
        for key in required_keys:
            assert key in data, f"Missing required field: {key}"

    def test_response_format_compatible_with_be(self, sample_pdf_path):
        """
        Verify response format {status: 200, data: {...}} is compatible
        with BE Spring Boot OcrServiceImpl parser.
        """
        with open(sample_pdf_path, "rb") as f:
            resp = requests.post(
                DKKD_ENDPOINT,
                files={"file": (sample_pdf_path.name, f, "application/pdf")},
                timeout=300,
            )

        body = resp.json()

        # Simulate BE Java parsing logic:
        # if (root.get("status").asInt() == 200) { parse data }
        assert body.get("status") == 200
        data = body.get("data")
        assert data is not None
        assert isinstance(data, dict)

        # nguoiDaiDienPhapLuat should be a list
        assert isinstance(data.get("nguoiDaiDienPhapLuat"), list)

        # thanhVienGopVon should be a list
        assert isinstance(data.get("thanhVienGopVon"), list)


# ── Standalone debug runner ────────────────────────────────────────────────────

if __name__ == "__main__":
    """
    Quick debug runner — OCR and print extracted data without pytest.
    Usage: python tests/test_dkkd.py
    """
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))

    from src import file_handler, config
    from src.vllm_service import stream_ocr_response
    from src.extractors.dkkd_extractor import extract_dkkd_llm
    from src.parsers.dkkd_parser import parse_dkkd

    if not SAMPLE_PDF.exists():
        print(f"ERROR: Sample PDF not found: {SAMPLE_PDF}")
        sys.exit(1)

    print(f"Processing: {SAMPLE_PDF.name}")
    print(f"File size: {SAMPLE_PDF.stat().st_size / 1024:.1f} KB")

    pdf_path = str(SAMPLE_PDF)
    page_count = file_handler.get_pdf_page_count(pdf_path)
    print(f"Pages: {page_count}")

    # OCR all pages
    prompt = config.PROMPTS.get("plain", "Free OCR.")
    all_texts = []
    for page_idx in range(page_count):
        print(f"\n--- OCR page {page_idx + 1}/{page_count} ---")
        image_bytes = file_handler.extract_pdf_page_bytes(pdf_path, page_idx)
        chunks = []
        for chunk in stream_ocr_response(
            model_name=config.VLLM_MODEL,
            prompt=prompt,
            image_bytes=image_bytes,
            options=config.INFERENCE_PARAMS,
            timeout_seconds=config.OCR_TIMEOUT_SECONDS,
        ):
            if chunk:
                chunks.append(chunk)
                print(chunk, end="", flush=True)
        page_text = "".join(chunks).strip()
        all_texts.append(f"--- PAGE {page_idx + 1} ---\n{page_text}")

    raw_text = "\n\n".join(all_texts)
    print(f"\n\nTotal OCR chars: {len(raw_text)}")

    # Try LLM extraction
    print("\n--- LLM Extraction ---")
    if os.getenv("FPT_API_KEY"):
        result = extract_dkkd_llm(raw_text)
        if result:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print("LLM extraction failed, trying regex fallback...")
            biz = parse_dkkd(raw_text)
            print(json.dumps(biz.model_dump(), ensure_ascii=False, indent=2))
    else:
        print("FPT_API_KEY not set — using regex fallback")
        biz = parse_dkkd(raw_text)
        print(json.dumps(biz.model_dump(), ensure_ascii=False, indent=2))
