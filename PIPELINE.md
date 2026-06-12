# OCR Invoice Pipeline — LLM-first, Regex Fallback

## Tổng quan

Hệ thống OCR invoice sử dụng **2 lớp xử lý**:
1. **OCR Layer**: DeepSeek-OCR (vLLM) — chuyển ảnh/PDF thành text
2. **Extraction Layer**: FPT Cloud LLM (Qwen3-32B) — trích xuất structured JSON từ OCR text

Nếu LLM không khả dụng, hệ thống tự động fallback về Regex parser.

---

## Pipeline Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                        API Request                                  │
│                  POST /ocr-invoice (file)                           │
└─────────────────┬───────────────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 1: FILE HANDLING                                              │
│  ─────────────────────                                              │
│  • Save uploaded file to temp directory                             │
│  • Auto-convert DOCX → PDF (if needed)                             │
│  • Detect page count (PDF) or single image                         │
│  • Parse page selection (e.g., "1,3" or "1-3" or "all")           │
└─────────────────┬───────────────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 2: OCR — DeepSeek-OCR (vLLM Vision)                         │
│  ──────────────────────────────────────────                         │
│  • For each page:                                                   │
│    - Extract page as image bytes                                    │
│    - Stream OCR via vLLM OpenAI-compatible API                     │
│    - Apply TableGuard (markdown mode)                              │
│    - Hard timeout enforcement (60s/page)                           │
│  • Output: raw_text (full page OCR text)                           │
│  • Multi-page: separated by "--- PAGE N ---" markers              │
└─────────────────┬───────────────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 3: ZOOM-IN OCR (Conditional)                                 │
│  ──────────────────────────────────                                 │
│  • Trigger condition: missing critical header fields               │
│    (invoiceID, invoiceSerial, invoiceFormNo, invoiceDate,          │
│     invoiceName, sellerName, buyerName)                            │
│  • Header crop (top 30% of page) → OCR again                      │
│  • Right crop (right 50% of header) → OCR again (for overlapping  │
│    text layouts)                                                    │
│  • Output: zoom_text (header-focused OCR text)                     │
└─────────────────┬───────────────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 4: EXTRACTION — LLM-first, Regex Fallback                   │
│  ────────────────────────────────────────────────                   │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────┐     │
│  │  4a. TRY LLM EXTRACTION (Primary)                         │     │
│  │  ─────────────────────────────────                         │     │
│  │  • Call FPT Cloud API (Qwen3-32B)                         │     │
│  │  • Input: raw_text + zoom_text (combined)                 │     │
│  │  • System prompt: detailed extraction rules               │     │
│  │  • Output: JSON dict with all invoice fields              │     │
│  │  • Timeout: 60s (configurable via FPT_TIMEOUT)            │     │
│  │                                                            │     │
│  │  If SUCCESS → Go to Step 5 (Validation)                   │     │
│  │  If FAIL    → Log error + Go to 4b (Fallback)             │     │
│  └────────────────────────┬──────────────────────────────────┘     │
│                           │                                         │
│                    FAIL   │   SUCCESS                                │
│                    ┌──────┘──────┐                                   │
│                    ▼             ▼                                   │
│  ┌─────────────────────┐  ┌─────────────────────────────────┐     │
│  │  4b. REGEX FALLBACK │  │  → Step 5 (Validate LLM output)│     │
│  │  ──────────────────  │  └─────────────────────────────────┘     │
│  │  • parse_invoice_    │                                          │
│  │    block_based()     │                                          │
│  │  • parse_zoom_header │                                          │
│  │    (if zoom_text)    │                                          │
│  │  • normalize_invoice │                                          │
│  │    _output() as      │                                          │
│  │    secondary fallback│                                          │
│  └──────────┬───────────┘                                          │
│             │                                                       │
│             ▼                                                       │
│       → Step 6 (Build Response)                                    │
└─────────────────┬───────────────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 5: VALIDATION (LLM path only)                               │
│  ────────────────────────────────────                               │
│  InvoiceValidator post-processes LLM output:                       │
│  • Cross-check amounts (totalAmount = preTaxPrice + taxAmount)     │
│  • Item math (quantity × unitPrice ≈ amount)                       │
│  • Validate dates (range check)                                    │
│  • Validate tax codes (format check)                               │
│  • Verify values exist in raw_text (anti-hallucination)            │
│  • Clean template placeholders ([Invoice.No] → null)               │
│  • Compute per-field confidence (HIGH/MEDIUM/LOW)                  │
│  • Output: validated dict + flags + confidence summary             │
└─────────────────┬───────────────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 6: POST-PROCESSING                                          │
│  ─────────────────────────                                          │
│  • Date conversion: "YYYY-MM-DD" → Python date → "DD/MM/YYYY"    │
│  • Fallback totalAmount: parse "invoiceTotalInWord" → number      │
│  • Pydantic validation: dict → Invoice model                      │
│  • taxPercent coercion: float → string (10.0 → "10%")            │
└─────────────────┬───────────────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 7: API RESPONSE                                              │
│  ─────────────────────                                              │
│  {                                                                  │
│    "filename": "invoice.pdf",                                      │
│    "duration_sec": 5.2,                                            │
│    "ocr_mode": "plain",                                            │
│    "extraction_method": "llm" | "regex_fallback",                  │
│    "validation": { ... },       // confidence + flags              │
│    "raw_text": "...",                                              │
│    "data": { Invoice object }                                      │
│  }                                                                  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Fallback Scenarios & Logging

| Scenario | Behavior | Log Level | Log Message |
|---|---|---|---|
| FPT_API_KEY not set | Regex fallback | ERROR | `[LLM] API key not configured: ...` |
| FPT_API_KEY expired/invalid | Regex fallback | ERROR | `[LLM] Auth failed (key expired/invalid): ...` |
| FPT Cloud API down | Regex fallback | ERROR | `[LLM] Connection failed to {url}: ...` |
| FPT Cloud timeout | Regex fallback | ERROR | `[LLM] Timeout after {n}s: ...` |
| LLM returns invalid JSON | Regex fallback | WARNING | `[LLM] JSON parse failed: ...` |
| LLM returns null result | Regex fallback | WARNING | `[LLM] Extraction returned None` |
| Pydantic validation fails | Regex fallback | WARNING | `[LLM] Pydantic validation failed: ...` |
| LLM success | LLM extraction | INFO | `[LLM] Extraction OK` |

---

## Endpoints

| Endpoint | Extraction Method | Description |
|---|---|---|
| `POST /ocr-invoice` | LLM + Regex fallback | Single invoice file |
| `POST /ocr-invoices` | LLM + Regex fallback | Batch invoice files |
| `POST /ocr-bol` | Regex only | Bill of Lading |
| `POST /ocr-cccd` | Regex only | Citizen ID Card |
| `POST /ocr-cccd-realtime` | Regex only | Citizen ID (base64) |

---

## Configuration

Environment variables (via `.env` file or system env):

| Variable | Default | Description |
|---|---|---|
| `FPT_API_KEY` | _(empty)_ | FPT Cloud API key **(required for LLM)** |
| `FPT_API_BASE` | `https://mkp-api.fptcloud.com/v1` | FPT Cloud API base URL |
| `FPT_MODEL` | `Qwen3-32B` | LLM model name |
| `FPT_TIMEOUT` | `60` | LLM API timeout (seconds) |
| `VLLM_HOST` | `http://127.0.0.1:8000/v1` | vLLM OCR server URL |
| `VLLM_MODEL` | `deepseek-ai/DeepSeek-OCR` | OCR model name |
