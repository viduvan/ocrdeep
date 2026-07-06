"""
LLM-based extractor for Vietnamese Business Registration Certificate (Giấy ĐKKD).
Uses FPT Cloud Qwen3-32B to extract structured data from OCR text.

Usage:
    from src.extractors.dkkd_extractor import extract_dkkd_llm
    result = extract_dkkd_llm(raw_text)
"""
import json
import re
import time
import logging
from typing import Optional

import openai
from openai import OpenAI

from src import config

logger = logging.getLogger(__name__)


# ── System Prompt ─────────────────────────────────────────────────────────────
DKKD_SYSTEM_PROMPT = """You are an expert Vietnamese business registration certificate (Giấy đăng ký kinh doanh - ĐKKD) data extractor.
Your task is to extract structured data from OCR text of Vietnamese business registration certificates.

DOCUMENT STRUCTURE:
- The document typically has 2 pages:
  * Page 1 (--- PAGE 1 ---): General enterprise info + legal representatives
  * Page 2 (--- PAGE 2 ---): Capital contributors table (Danh sách thành viên góp vốn)
- Extract data from ALL pages.

CRITICAL RULES:
1. Extract EXACT text as it appears. Do NOT translate, calculate, or modify values.
2. For dates: keep as-is in Vietnamese format (e.g., "15/03/2024" or "ngày 15 tháng 3 năm 2024" → return "15/03/2024").
3. For monetary values (vonDieuLe, phanVonGop): keep as-is including currency unit (e.g., "18.961.210.840.000 đồng" or "18,961,210,840,000 VND").
4. For "Tỷ lệ (%)" in capital table: return as string (e.g., "25%" or "25.5%").
5. If a field is genuinely not found, return null — NEVER guess or hallucinate.
6. For "Người đại diện theo pháp luật": there may be MULTIPLE legal representatives — extract ALL of them as an array.
7. For "Danh sách thành viên góp vốn": this is a TABLE — extract each row as one object in the array.

FIELD EXTRACTION GUIDE:

Doanh nghiệp (Enterprise info):
- maSoDoanhNghiep: Look for "Mã số doanh nghiệp:", "Mã số thuế:", "MST:" — typically 10 digits
- tenDoanhNghiep: Look for "Tên doanh nghiệp:", "Tên công ty:" — uppercase Vietnamese company name
- tenDoanhNghiepEn: Look for "Tên giao dịch:", "Tên nước ngoài:", "Tên tiếng Anh:" — English name
- tenDoanhNghiepVietTat: Look for "Tên viết tắt:"
- loaiHinhDoanhNghiep: Look for "Loại hình doanh nghiệp:", "Loại hình:" — e.g., "Công ty cổ phần", "Công ty TNHH hai thành viên trở lên"
- diaChi: Look for "Địa chỉ trụ sở chính:", "Địa chỉ:" — full address text
- dienThoai: Look for "Điện thoại:", "Tel:", "Phone:"
- email: Look for "Email:", "E-mail:"
- fax: Look for "Fax:"
- website: Look for "Website:", "Web:"
- vonDieuLe: Look for "Vốn điều lệ:" — keep full text including đồng/VND
- menhGiaCoPhan: Look for "Mệnh giá cổ phần:" — for joint-stock companies
- tongSoCoPhan: Look for "Tổng số cổ phần:" — for joint-stock companies

Đăng ký (Registration info):
- ngayDangKy: Look for "Đăng ký lần đầu ngày:", "Ngày cấp lần đầu:" — first registration date
- lanDangKy: Look for "Đăng ký thay đổi lần thứ:", "Lần thứ:" — change registration number (e.g., "21")
- ngayThayDoi: Look for "Ngày:", "Ngày thay đổi:" — date of this change registration
- noiCapDkkd: Look for "Phòng Đăng ký kinh doanh", "Sở Kế hoạch và Đầu tư" — issuing authority

Người đại diện pháp luật (Legal representatives — may be multiple):
For each representative, extract:
- hoVaTen: "Họ và tên:" — full name in uppercase
- gioiTinh: "Giới tính:" — "Nam" or "Nữ"
- chucDanh: "Chức danh:" — position title
- ngaySinh: "Sinh ngày:", "Ngày sinh:" — date of birth
- quocTich: "Quốc tịch:" — nationality (usually "Việt Nam")
- danToc: "Dân tộc:" — ethnicity (usually "Kinh")
- loaiGiayTo: "Loại giấy tờ pháp lý:", "Giấy CMND/CCCD/Hộ chiếu" — document type
- soGiayTo: "Số CMND:", "Số CCCD:", "Số Hộ chiếu:", "CMND/CCCD số:" — ID number
- ngayCap: "Ngày cấp:" — ID issue date
- noiCap: "Nơi cấp:" — ID issuing authority
- noiDkHktt: "Nơi đăng ký hộ khẩu thường trú:", "ĐKHKTT:" — permanent residence registration
- diaChiTt: "Địa chỉ thường trú:", "Chỗ ở hiện tại:", "Nơi ở:" — permanent address

Thành viên góp vốn (Capital contributors table — 8 columns):
Table header: STT | Tên thành viên | Quốc tịch | Địa chỉ liên lạc | Phần vốn góp | Tỷ lệ (%) | Số giấy tờ pháp lý | Ghi chú
For each row:
- stt: row number (integer)
- tenThanhVien: member name (person or organization)
- quocTich: nationality
- diaChiLienLac: contact address (personal) or registered office (organization)
- phanVonGop: capital contribution amount (VNĐ)
- tyLe: percentage (e.g., "25%")
- soGiayToPhapLy: ID number (personal) / enterprise code (organization) / legal document number
- ghiChu: notes (usually null)

Return a JSON object with these exact fields (use null for missing values):
{
  "maSoDoanhNghiep": "string or null",
  "tenDoanhNghiep": "string or null",
  "tenDoanhNghiepEn": "string or null",
  "tenDoanhNghiepVietTat": "string or null",
  "loaiHinhDoanhNghiep": "string or null",
  "diaChi": "string or null",
  "dienThoai": "string or null",
  "email": "string or null",
  "fax": "string or null",
  "website": "string or null",
  "ngayDangKy": "string or null - first registration date dd/MM/yyyy",
  "lanDangKy": "string or null - change number e.g. '21'",
  "ngayThayDoi": "string or null - date of this change dd/MM/yyyy",
  "noiCapDkkd": "string or null",
  "vonDieuLe": "string or null - keep full text",
  "menhGiaCoPhan": "string or null",
  "tongSoCoPhan": "string or null",
  "nguoiDaiDienPhapLuat": [
    {
      "hoVaTen": "string or null",
      "gioiTinh": "string or null",
      "chucDanh": "string or null",
      "ngaySinh": "string or null",
      "quocTich": "string or null",
      "danToc": "string or null",
      "loaiGiayTo": "string or null",
      "soGiayTo": "string or null",
      "ngayCap": "string or null",
      "noiCap": "string or null",
      "noiDkHktt": "string or null",
      "diaChiTt": "string or null"
    }
  ],
  "chiTietDiaChi": null,
  "thanhVienGopVon": [
    {
      "stt": integer or null,
      "tenThanhVien": "string or null",
      "quocTich": "string or null",
      "diaChiLienLac": "string or null",
      "phanVonGop": "string or null",
      "tyLe": "string or null",
      "soGiayToPhapLy": "string or null",
      "ghiChu": "string or null"
    }
  ]
}

/no_think
IMPORTANT: Return ONLY the JSON object. No markdown, no code fences, no explanation."""


def _get_fpt_client() -> OpenAI:
    """Create OpenAI-compatible client for FPT Cloud."""
    api_key = config.FPT_API_KEY
    if not api_key:
        raise ValueError(
            "FPT_API_KEY not set. Export it or add to .env file: FPT_API_KEY='your-key'"
        )
    return OpenAI(
        base_url=config.FPT_API_BASE,
        api_key=api_key,
        timeout=config.FPT_TIMEOUT,
    )


def _clean_json_response(text: str) -> str:
    """Strip markdown fences and thinking tags from LLM response."""
    # Remove <think>...</think> blocks (Qwen3 thinking mode)
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    text = text.strip()

    # Remove markdown code fences
    if text.startswith("```"):
        text = re.sub(r'^```(?:json)?\s*\n?', '', text)
        text = re.sub(r'\n?```\s*$', '', text)

    return text.strip()


def _parse_llm_json(raw_response: str) -> Optional[dict]:
    """Parse LLM response into dict, handling common issues."""
    cleaned = _clean_json_response(raw_response)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.warning(f"[DKKD-LLM] JSON parse failed: {e}")
        logger.debug(f"Raw response (first 500 chars): {cleaned[:500]}")

        # Try to extract JSON object from the response
        match = re.search(r'\{[\s\S]*\}', cleaned)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        return None


def extract_dkkd_llm(
    raw_text: str,
    model: str = None,
    temperature: float = 0.0,
    max_tokens: int = 4096,
) -> Optional[dict]:
    """
    Extract business registration fields from OCR text using FPT Cloud LLM.

    Args:
        raw_text: OCR text from DeepSeek-OCR (all pages combined, with --- PAGE N --- markers)
        model: Override model name (default: FPT_MODEL from config)
        temperature: LLM temperature (0.0 = deterministic)
        max_tokens: Max output tokens

    Returns:
        dict with BusinessRegistration fields, or None if extraction failed.
        Returns None on ANY error — caller should fallback to regex parser.
    """
    model = model or config.FPT_MODEL
    text_len = len(raw_text)

    user_content = (
        "Extract business registration data from this Vietnamese ĐKKD OCR text:\n\n"
        f"{raw_text}"
    )

    start_time = time.time()

    try:
        client = _get_fpt_client()

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": DKKD_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=1,
            stream=False,
        )

        latency = time.time() - start_time

        raw_response = response.choices[0].message.content
        if not raw_response:
            logger.error(
                f"[DKKD-LLM] Empty response from {model} "
                f"(latency={latency:.1f}s, input={text_len} chars)"
            )
            return None

        result = _parse_llm_json(raw_response)
        if result is None:
            logger.warning(
                f"[DKKD-LLM] JSON parse failed — model={model}, "
                f"latency={latency:.1f}s, response_preview={raw_response[:200]}"
            )
            return None

        logger.info(
            f"[DKKD-LLM] Extraction OK — model={model}, latency={latency:.1f}s, "
            f"maSoDN={result.get('maSoDoanhNghiep')}, "
            f"tenDN={result.get('tenDoanhNghiep')}, "
            f"nguoiDDPL={len(result.get('nguoiDaiDienPhapLuat', []))}, "
            f"thanhVienGV={len(result.get('thanhVienGopVon', []))}"
        )
        return result

    except ValueError as e:
        logger.error(f"[DKKD-LLM] API key not configured: {e}")
        return None
    except openai.AuthenticationError as e:
        logger.error(f"[DKKD-LLM] Auth failed (key expired/invalid) — base_url={config.FPT_API_BASE}: {e}")
        return None
    except openai.APIConnectionError as e:
        logger.error(f"[DKKD-LLM] Connection failed to {config.FPT_API_BASE}: {e}")
        return None
    except openai.APITimeoutError as e:
        latency = time.time() - start_time
        logger.error(f"[DKKD-LLM] Timeout after {latency:.1f}s (limit={config.FPT_TIMEOUT}s) — model={model}: {e}")
        return None
    except openai.RateLimitError as e:
        logger.error(f"[DKKD-LLM] Rate limit exceeded — model={model}: {e}")
        return None
    except Exception as e:
        latency = time.time() - start_time
        logger.error(
            f"[DKKD-LLM] Unexpected error — {type(e).__name__}: {e} "
            f"(model={model}, latency={latency:.1f}s)"
        )
        return None


def extract_dkkd_llm_to_pydantic(raw_text: str, **kwargs):
    """
    Extract business registration data and return as Pydantic BusinessRegistration model.
    Falls back to None if extraction or validation fails.
    """
    from src.schemas.business_registration import BusinessRegistration

    result = extract_dkkd_llm(raw_text, **kwargs)
    if result is None:
        return None

    try:
        return BusinessRegistration(**result)
    except Exception as e:
        logger.warning(f"[DKKD-LLM] Pydantic validation failed: {e}")
        return None
