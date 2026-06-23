# src/api_server.py
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from pathlib import Path
import uuid
import time
import re
import os
import asyncio
import logging

from src import file_handler, config
from src.vllm_service import stream_ocr_response, OCRTimeoutError
from src.utils.table_guard import TableGuard
from src.utils.date_utils import parse_vn_date
from src.schemas.invoice import Invoice
from src.schemas.invoice_item import InvoiceItem
from src.parsers.invoice_parser import normalize_invoice_output
from src.parsers.block_invoice_parser import parse_invoice_block_based, parse_header
from src.parsers.block_invoice_zoomtext_parser import parse_zoom_header, parse_zoom_right_header
from src.extractors.llm_extractor import extract_invoice_llm
from src.extractors.invoice_validator import InvoiceValidator

logger = logging.getLogger(__name__)


def _try_right_crop_zoom(invoice: Invoice, filepath: str, page_idx: int,
                          model_name: str) -> str:
    """
    Second zoom pass: crop right side of header to extract invoiceID
    when it overlaps with large title text on the left.
    Returns the right-crop OCR text (or empty string).
    """
    # Skip if invoiceID is already set (any value)
    if invoice.invoiceID:
        print(f"Right-crop skipped: invoiceID already set to '{invoice.invoiceID}'")
        return ""
    print(f"Right-crop triggered: invoiceID is null")
    
    right_bytes = file_handler.get_header_right_crop_bytes(filepath, page_idx)
    if not right_bytes:
        return ""
    
    try:
        zoom_prompt = config.PROMPTS.get("header_only", "Extract header info.")
        right_chunks = []
        for chunk in stream_ocr_response(
            model_name=model_name,
            prompt=zoom_prompt,
            image_bytes=right_bytes,
            options=config.INFERENCE_PARAMS,
            timeout_seconds=config.ZOOM_OCR_TIMEOUT_SECONDS,
        ):
            if chunk:
                right_chunks.append(chunk)
        
        right_text = "".join(right_chunks).strip()
        if right_text:
            print(f"Right-crop Zoom Text: {right_text[:100]}...")
            right_lines = right_text.splitlines()
            parse_zoom_right_header(right_lines, invoice)
        return right_text
    except Exception as e:
        print(f"Right-crop Zoom OCR failed: {e}")
        return ""



# ── LLM-first, Regex-fallback invoice processing ─────────────────────────────

def _process_invoice_page(
    raw_text: str,
    zoom_text: str = "",
    page_label: str = "single",
) -> tuple:
    """
    Process a single invoice page: LLM-first, regex-fallback.
    
    Args:
        raw_text: Full OCR text for this page
        zoom_text: Header zoom OCR text (if available)
        page_label: Label for logging (e.g., "single", "page_1", "batch_file_3")
    
    Returns:
        (Invoice, metadata_dict) where metadata contains:
        - extraction_method: "llm" or "regex_fallback"
        - validation: flags + confidence from InvoiceValidator (LLM only)
    """
    metadata = {"extraction_method": "llm", "validation": {}}
    
    # ── Step 1: Try LLM extraction ──
    llm_result = extract_invoice_llm(raw_text, zoom_text)
    
    if llm_result is not None:
        # LLM succeeded — validate and post-process
        logger.info(f"[LLM] Extraction OK — {page_label}")
        
        # Validate LLM output
        validator = InvoiceValidator()
        llm_result = validator.validate(llm_result, raw_text, zoom_text)
        summary = validator.get_summary(llm_result)
        metadata["validation"] = summary
        
        # Date conversion
        if isinstance(llm_result.get("invoiceDate"), str):
            llm_result["invoiceDate"] = parse_vn_date(llm_result["invoiceDate"])
        
        # Fallback totalAmount from words
        if not llm_result.get("totalAmount") and llm_result.get("invoiceTotalInWord"):
            from src.utils.text_to_number import text_to_number_vn
            try:
                val = text_to_number_vn(llm_result["invoiceTotalInWord"])
                if val > 0:
                    llm_result["totalAmount"] = val
                    logger.info(f"[LLM] Recovered totalAmount from words: {val}")
            except Exception:
                pass
        
        # Clean internal validator fields before Pydantic
        llm_result.pop("_flags", None)
        llm_result.pop("_confidence", None)
        
        try:
            invoice = Invoice(**llm_result)
            return invoice, metadata
        except Exception as e:
            logger.warning(f"[LLM] Pydantic validation failed, falling back to regex — {page_label}: {e}")
    else:
        logger.warning(f"[LLM] Extraction returned None — falling back to regex — {page_label}")
    
    # ── Step 2: Fallback to Regex Parser ──
    metadata["extraction_method"] = "regex_fallback"
    logger.info(f"[FALLBACK] Using regex parser — {page_label}")
    
    invoice = parse_invoice_block_based(raw_text)
    
    # Secondary fallback if block parser is empty
    if not invoice.itemList and not invoice.sellerName and not invoice.buyerName:
        invoice_data = normalize_invoice_output(raw_text)
        invoice = Invoice(**invoice_data)
    
    # Apply zoom text via regex zoom parser
    if zoom_text and zoom_text.strip():
        zoom_lines = zoom_text.splitlines()
        parse_zoom_header(zoom_lines, invoice)
    
    # Date fix
    invoice_dict = invoice.model_dump()
    if isinstance(invoice_dict.get("invoiceDate"), str):
        invoice_dict["invoiceDate"] = parse_vn_date(invoice_dict["invoiceDate"])
    
    # Fallback totalAmount from words
    if not invoice_dict.get("totalAmount") and invoice_dict.get("invoiceTotalInWord"):
        from src.utils.text_to_number import text_to_number_vn
        try:
            val = text_to_number_vn(invoice_dict["invoiceTotalInWord"])
            if val > 0:
                invoice_dict["totalAmount"] = val
                logger.info(f"[FALLBACK] Recovered totalAmount from words: {val}")
        except Exception:
            pass
    
    invoice = Invoice(**invoice_dict)
    return invoice, metadata



# FASTAPI APP

app = FastAPI(
    title="Local Vision OCR API",
    description="FastAPI wrapper for local Vision OCR",
    version="1.0.0",
)



# OCR CORE (VISION OCR)

def run_vision_ocr(
    file_path: str,
    *,
    model_name: str,
    ocr_mode: str,
    pages: str = None,  # Optional: "1,3" or "1-3" or "all" or None (=all)
    timeout_seconds: int = None,  # Per-file timeout override (None = use config defaults)
) -> Dict[str, Any]:

    prompt = config.PROMPTS.get(ocr_mode, config.PROMPTS["plain"])
    
    # Auto-convert Word files to PDF
    if file_handler.is_word(file_path):
        file_path = file_handler.convert_docx_to_pdf(file_path)
    
    # Determine total pages in PDF
    if file_handler.is_pdf(file_path):
        total_page_count = file_handler.get_pdf_page_count(file_path)
        if total_page_count == 0:
            return {"raw_text": "", "duration_sec": 0, "ocr_mode": ocr_mode, "error": "Failed to read PDF"}
    else:
        total_page_count = 1  # Images are single-page
    
    # Parse page selection
    if pages is None or pages.lower() == "all" or pages.strip() == "":
        # Process all pages
        page_indices = list(range(total_page_count))
    else:
        # Parse page selection string (1-indexed input, convert to 0-indexed)
        page_indices = []
        for part in pages.split(","):
            part = part.strip()
            if "-" in part:
                # Range: "1-3" means pages 1,2,3
                try:
                    start, end = part.split("-")
                    start = max(1, int(start.strip()))
                    end = min(total_page_count, int(end.strip()))
                    page_indices.extend(range(start - 1, end))  # 0-indexed
                except ValueError:
                    pass
            else:
                # Single page: "2" means page 2
                try:
                    p = int(part)
                    if 1 <= p <= total_page_count:
                        page_indices.append(p - 1)  # 0-indexed
                except ValueError:
                    pass
        # Remove duplicates and sort
        page_indices = sorted(set(page_indices))
    
    if not page_indices:
        page_indices = list(range(total_page_count))  # Fallback to all
    
    page_count = len(page_indices)

    all_raw_texts = []
    total_duration = 0
    timed_out = False
    triggered = False

    for page_idx in page_indices:
        # Get image bytes for this page
        if file_handler.is_pdf(file_path):
            image_bytes = file_handler.extract_pdf_page_bytes(file_path, page_idx)
        else:
            image_bytes = file_handler.get_image_bytes(file_path)

        table_guard = None
        if ocr_mode == "markdown":
            table_guard = TableGuard(max_rows=150, max_consecutive_empty_rows=4)

        chunks: List[str] = []
        start_time = time.time()
        
        # Use per-page timeout: prefer passed parameter, fallback to config
        if timeout_seconds is not None:
            page_timeout = timeout_seconds
        elif page_count > 1:
            page_timeout = config.MULTIPAGE_OCR_TIMEOUT_SECONDS
        else:
            page_timeout = config.OCR_TIMEOUT_SECONDS

        try:
            for chunk in stream_ocr_response(
                model_name=model_name,
                prompt=prompt,
                image_bytes=image_bytes,
                options=config.INFERENCE_PARAMS,
                timeout_seconds=page_timeout,
            ):
                if not chunk:
                    continue

                if table_guard:
                    chunk, force_close = table_guard.process(chunk)
                    if force_close:
                        triggered = True
                        chunks.append(chunk)
                        break

                chunks.append(chunk)
        except OCRTimeoutError as e:
            # Hard timeout hit - return partial result
            timed_out = True
            chunks.append(f"\n<!-- OCR_TIMEOUT: {e} -->\n")

        page_text = "".join(chunks).strip()
        total_duration += time.time() - start_time
        
        # Add page marker if multi-page
        if page_count > 1:
            all_raw_texts.append(f"--- PAGE {page_idx + 1} ---\n{page_text}")
        else:
            all_raw_texts.append(page_text)

    return {
        "raw_text": "\n\n".join(all_raw_texts).strip(),
        "duration_sec": round(total_duration, 3),
        "ocr_mode": ocr_mode,
        "page_count": page_count,
        "page_indices": page_indices,  # 0-indexed list of pages that were processed
        "timed_out": timed_out,
        "table_guard": {
            "triggered": triggered,
            "row_count": table_guard.row_count if table_guard else 0,
            "empty_row_streak": table_guard.empty_row_streak if table_guard else 0,
        },
    }


# API ENDPOINT - Single File (Full Logic)

@app.post(
    "/ocr-invoice",
    summary="Vision OCR single invoice file",
)
async def detect_single_invoice_ocr(
    file: UploadFile = File(...),
    model_name: str = Form(config.VLLM_MODEL),
    ocr_mode: str = Form(config.DEFAULT_OCR_MODE),
    semantic: bool = Form(True),
    pages: str = Form(None),
    per_file_timeout: int = Form(config.OCR_TIMEOUT_SECONDS),
):
    """
    OCR a single invoice file (PNG, JPG, JPEG, PDF, DOC, DOCX).
    Returns parsed invoice data.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded")
    
    if not file.filename.lower().endswith(file_handler.SUPPORTED_EXTENSIONS):
        raise HTTPException(status_code=400, detail="Unsupported file type. Use PNG, JPG, JPEG, PDF, DOC, or DOCX.")
    
    session_id = str(uuid.uuid4())
    temp_dir = Path("temp_ocr") / session_id
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    # Save temp file
    temp_file = temp_dir / file.filename
    with open(temp_file, "wb") as f:
        f.write(await file.read())
    
    file_start_time = time.time()

    try:
        # Call OCR with per-file timeout - returns partial results on timeout
        ocr_result = run_vision_ocr(
            str(temp_file),
            model_name=model_name,
            ocr_mode=ocr_mode,
            pages=pages,
            timeout_seconds=per_file_timeout,
        )

        raw_text = ocr_result["raw_text"]
        page_count = ocr_result.get("page_count", 1)

        # ---- MULTI-PAGE PDF HANDLING ----
        if page_count > 1:
            import re
            page_texts = re.split(r'--- PAGE \d+ ---\n?', raw_text)
            page_texts = [p.strip() for p in page_texts if p.strip()]
            
            actual_page_indices = ocr_result.get("page_indices", list(range(len(page_texts))))
            
            invoices = []
            all_metadata = []
            for arr_idx, page_text in enumerate(page_texts):
                actual_page_idx = actual_page_indices[arr_idx] if arr_idx < len(actual_page_indices) else arr_idx
                
                # Zoom-in OCR for this page (get text only, pass to LLM)
                page_zoom_text = ""
                header_bytes = file_handler.get_header_crop_bytes_page(str(temp_file), actual_page_idx)
                if header_bytes:
                    zoom_prompt = config.PROMPTS.get("header_only", "Extract header info.")
                    zoom_chunks = []
                    try:
                        for chunk in stream_ocr_response(
                            model_name=model_name,
                            prompt=zoom_prompt,
                            image_bytes=header_bytes,
                            options=config.INFERENCE_PARAMS,
                            timeout_seconds=config.ZOOM_OCR_TIMEOUT_SECONDS,
                        ):
                            if chunk:
                                zoom_chunks.append(chunk)
                        page_zoom_text = "".join(zoom_chunks).strip()
                    except Exception as e:
                        logger.warning(f"Page {actual_page_idx + 1} Zoom-in OCR failed: {e}")
                
                # Process page through LLM-first pipeline
                invoice, page_meta = _process_invoice_page(
                    page_text, page_zoom_text,
                    page_label=f"page_{actual_page_idx + 1}",
                )
                invoices.append(invoice)
                all_metadata.append(page_meta)
            
            result_data = {
                "filename": file.filename,
                "duration_sec": ocr_result["duration_sec"],
                "ocr_mode": ocr_mode,
                "page_count": page_count,
                "raw_text": raw_text,
                "extraction_metadata": all_metadata,
                "data": invoices,
            }
            if ocr_result.get("timed_out"):
                result_data["warning"] = f"OCR timeout - partial results (limit: {per_file_timeout}s)"
            return result_data

        # ---- SINGLE PAGE HANDLING ----
        # Zoom-in OCR: get header crop text
        zoom_text = ""
        selected_page_indices = ocr_result.get("page_indices", [0])
        zoom_page_idx = selected_page_indices[0] if selected_page_indices else 0
        header_bytes = file_handler.get_header_crop_bytes_page(str(temp_file), zoom_page_idx)
        if header_bytes:
            zoom_prompt = config.PROMPTS.get("header_only", "Extract header info.")
            zoom_chunks = []
            try:
                for chunk in stream_ocr_response(
                    model_name=model_name,
                    prompt=zoom_prompt,
                    image_bytes=header_bytes,
                    options=config.INFERENCE_PARAMS,
                    timeout_seconds=config.ZOOM_OCR_TIMEOUT_SECONDS,
                ):
                    if chunk: zoom_chunks.append(chunk)
                zoom_text = "".join(zoom_chunks).strip()
                if zoom_text:
                    logger.info(f"Zoom-in Text (first 100): {zoom_text[:100]}...")
            except Exception as e:
                logger.warning(f"Zoom-in OCR failed: {e}")

        # Process through LLM-first pipeline
        invoice, extraction_meta = _process_invoice_page(
            raw_text, zoom_text,
            page_label=f"single/{file.filename}",
        )

        # Build result
        result_data = {
            "filename": file.filename,
            "duration_sec": ocr_result["duration_sec"],
            "ocr_mode": ocr_mode,
            "extraction_method": extraction_meta["extraction_method"],
            "validation": extraction_meta.get("validation", {}),
            "raw_text": raw_text,
            "data": invoice,
        }
        if ocr_result.get("timed_out"):
            result_data["warning"] = f"OCR timeout - partial results (limit: {per_file_timeout}s)"
        return result_data
        
    except Exception as e:
        elapsed = time.time() - file_start_time
        return {
            "filename": file.filename,
            "error": str(e),
            "duration_sec": round(elapsed, 2),
            "data": None
        }




# API ENDPOINT - Multiple Files

@app.post(
    "/ocr-invoices",
    summary="Vision OCR multiple invoice files (batch)",
)
async def detect_invoice_ocr(
    files: List[UploadFile] = File(...),  # Changed to support multiple files
    model_name: str = Form(config.VLLM_MODEL),
    ocr_mode: str = Form(config.DEFAULT_OCR_MODE),  # chọn model OCR từ config.py
    semantic: bool = Form(True), # bật/tắt tinh chỉnh ngữ nghĩa
    pages: str = Form(None),  # Optional: "1,3" or "1-3" or "all" or None (=all)
    per_file_timeout: int = Form(config.OCR_TIMEOUT_SECONDS),  # Per-file timeout in seconds
):
    # Validate at least one file uploaded
    if not files or len(files) == 0:
        raise HTTPException(status_code=400, detail="No files uploaded")
    
    # Session ID for all files in this request
    session_id = str(uuid.uuid4())
    temp_dir = Path("temp_ocr") / session_id
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    # Results array for all files
    all_results = []
    total_start_time = time.time()
    
    for file in files:
        if not file.filename:
            continue
            
        if not file.filename.lower().endswith(file_handler.SUPPORTED_EXTENSIONS):
            # Skip unsupported files but continue with others
            all_results.append({
                "filename": file.filename,
                "error": "Unsupported file type",
                "data": None
            })
            continue
        
        # ---- Save temp file ----
        temp_file = temp_dir / file.filename
        with open(temp_file, "wb") as f:
            f.write(await file.read())
        
        file_start_time = time.time()

        try:
            # Call OCR with per-file timeout - returns partial results on timeout
            ocr_result = run_vision_ocr(
                str(temp_file),
                model_name=model_name,
                ocr_mode=ocr_mode,
                pages=pages,
                timeout_seconds=per_file_timeout,
            )

            raw_text = ocr_result["raw_text"]
            page_count = ocr_result.get("page_count", 1)

            # ---- MULTI-PAGE PDF HANDLING ----
            if page_count > 1:
                import re
                page_texts = re.split(r'--- PAGE \d+ ---\n?', raw_text)
                page_texts = [p.strip() for p in page_texts if p.strip()]
                
                actual_page_indices = ocr_result.get("page_indices", list(range(len(page_texts))))
                
                invoices = []
                all_page_meta = []
                for arr_idx, page_text in enumerate(page_texts):
                    actual_page_idx = actual_page_indices[arr_idx] if arr_idx < len(actual_page_indices) else arr_idx
                    
                    # Zoom-in OCR for this page
                    page_zoom_text = ""
                    header_bytes = file_handler.get_header_crop_bytes_page(str(temp_file), actual_page_idx)
                    if header_bytes:
                        zoom_prompt = config.PROMPTS.get("header_only", "Extract header info.")
                        zoom_chunks = []
                        try:
                            for chunk in stream_ocr_response(
                                model_name=model_name,
                                prompt=zoom_prompt,
                                image_bytes=header_bytes,
                                options=config.INFERENCE_PARAMS,
                                timeout_seconds=config.ZOOM_OCR_TIMEOUT_SECONDS,
                            ):
                                if chunk:
                                    zoom_chunks.append(chunk)
                            page_zoom_text = "".join(zoom_chunks).strip()
                        except Exception as e:
                            logger.warning(f"Batch {file.filename} page {actual_page_idx + 1} Zoom failed: {e}")
                    
                    # Process page through LLM-first pipeline
                    invoice, page_meta = _process_invoice_page(
                        page_text, page_zoom_text,
                        page_label=f"batch/{file.filename}/page_{actual_page_idx + 1}",
                    )
                    invoices.append(invoice)
                    all_page_meta.append(page_meta)
                
                result_data = {
                    "filename": file.filename,
                    "duration_sec": ocr_result["duration_sec"],
                    "ocr_mode": ocr_mode,
                    "page_count": page_count,
                    "raw_text": raw_text,
                    "extraction_metadata": all_page_meta,
                    "data": invoices,
                }
                if ocr_result.get("timed_out"):
                    result_data["warning"] = f"OCR timeout - partial results (limit: {per_file_timeout}s)"
                all_results.append(result_data)
                continue

            # ---- SINGLE PAGE HANDLING ----
            # Zoom-in OCR: get header crop text
            zoom_text = ""
            selected_page_indices = ocr_result.get("page_indices", [0])
            zoom_page_idx = selected_page_indices[0] if selected_page_indices else 0
            header_bytes = file_handler.get_header_crop_bytes_page(str(temp_file), zoom_page_idx)
            if header_bytes:
                zoom_prompt = config.PROMPTS.get("header_only", "Extract header info.")
                zoom_chunks = []
                try:
                    for chunk in stream_ocr_response(
                        model_name=model_name,
                        prompt=zoom_prompt,
                        image_bytes=header_bytes,
                        options=config.INFERENCE_PARAMS,
                        timeout_seconds=config.ZOOM_OCR_TIMEOUT_SECONDS,
                    ):
                        if chunk: zoom_chunks.append(chunk)
                    zoom_text = "".join(zoom_chunks).strip()
                    if zoom_text:
                        logger.info(f"Batch {file.filename} Zoom-in Text (first 100): {zoom_text[:100]}...")
                except Exception as e:
                    logger.warning(f"Batch {file.filename} Zoom-in OCR failed: {e}")

            # Process through LLM-first pipeline
            invoice, extraction_meta = _process_invoice_page(
                raw_text, zoom_text,
                page_label=f"batch/{file.filename}",
            )

            # Build result
            result_data = {
                "filename": file.filename,
                "duration_sec": ocr_result["duration_sec"],
                "ocr_mode": ocr_mode,
                "extraction_method": extraction_meta["extraction_method"],
                "validation": extraction_meta.get("validation", {}),
                "raw_text": raw_text,
                "data": invoice,
            }
            if ocr_result.get("timed_out"):
                result_data["warning"] = f"OCR timeout - partial results (limit: {per_file_timeout}s)"
            all_results.append(result_data)
            
        except Exception as e:
            elapsed = time.time() - file_start_time
            all_results.append({
                "filename": file.filename,
                "error": str(e),
                "duration_sec": round(elapsed, 2),
                "data": None
            })
    
    # Return all results after processing all files
    total_duration = time.time() - total_start_time
    return {
        "total_files": len(files),
        "total_duration_sec": round(total_duration, 2),
        "results": all_results
    }



# ============================================
# CCCD OCR ENDPOINT (Căn Cước Công Dân)
# ============================================

@app.post(
    "/ocr-cccd",
    summary="OCR Vietnamese Citizen ID Card (CCCD)",
)
async def ocr_citizen_id(
    files: List[UploadFile] = File(...),  # 1-2 images: front and optionally back
    model_name: str = Form(config.VLLM_MODEL),
    ocr_mode: str = Form("plain"),
    per_file_timeout: int = Form(config.OCR_TIMEOUT_SECONDS),
):
    """
    OCR Vietnamese Citizen ID Card (Căn Cước Công Dân).
    
    - Upload 1 image (front only) or 2 images (front + back)
    - Returns raw OCR text for each image
    """
    from src.schemas.citizen_id import CitizenID
    
    if not files or len(files) == 0:
        raise HTTPException(status_code=400, detail="No files uploaded")
    
    if len(files) > 2:
        raise HTTPException(status_code=400, detail="Maximum 2 files allowed (front + back)")
    
    session_id = str(uuid.uuid4())
    temp_dir = Path("temp_ocr") / session_id
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    all_raw_texts = []
    total_start_time = time.time()
    
    for idx, file in enumerate(files):
        if not file.filename:
            continue
            
        if not file.filename.lower().endswith((".png", ".jpg", ".jpeg")):
            all_raw_texts.append({
                "side": "front" if idx == 0 else "back",
                "filename": file.filename,
                "error": "Unsupported file type. Use PNG or JPG.",
                "raw_text": None
            })
            continue
        
        temp_file = temp_dir / file.filename
        with open(temp_file, "wb") as f:
            f.write(await file.read())
        
        file_start_time = time.time()
        
        try:
            # Use CCCD-specific prompt if available
            cccd_prompt = config.PROMPTS.get("cccd", config.PROMPTS.get("plain", "Extract all text from this ID card image."))
            
            # Get image bytes
            image_bytes = file_handler.get_image_bytes(str(temp_file))
            
            chunks = []
            for chunk in stream_ocr_response(
                model_name=model_name,
                prompt=cccd_prompt,
                image_bytes=image_bytes,
                options=config.INFERENCE_PARAMS,
                timeout_seconds=per_file_timeout,
            ):
                if chunk:
                    chunks.append(chunk)
            
            raw_text = "".join(chunks).strip()
            elapsed = time.time() - file_start_time
            
            all_raw_texts.append({
                "side": "front" if idx == 0 else "back",
                "filename": file.filename,
                "duration_sec": round(elapsed, 2),
                "raw_text": raw_text
            })
            
        except OCRTimeoutError as e:
            elapsed = time.time() - file_start_time
            all_raw_texts.append({
                "side": "front" if idx == 0 else "back",
                "filename": file.filename,
                "error": f"OCR timeout after {round(elapsed, 1)}s",
                "duration_sec": round(elapsed, 2),
                "raw_text": "".join(chunks) if chunks else None
            })
            
        except Exception as e:
            elapsed = time.time() - file_start_time
            all_raw_texts.append({
                "side": "front" if idx == 0 else "back",
                "filename": file.filename,
                "error": str(e),
                "duration_sec": round(elapsed, 2),
                "raw_text": None
            })
    
    total_duration = time.time() - total_start_time
    
    # Phase 2: Parse CCCD data from raw text
    from src.parsers.cccd_parser import parse_cccd
    
    front_text = None
    back_text = None
    
    for result in all_raw_texts:
        if result.get("raw_text"):
            if result.get("side") == "front":
                front_text = result["raw_text"]
            elif result.get("side") == "back":
                back_text = result["raw_text"]
    
    # Parse if we have at least front side
    cccd_data = None
    if front_text:
        try:
            cccd = parse_cccd(front_text, back_text)
            cccd_data = cccd.model_dump()
        except Exception as e:
            cccd_data = {"parse_error": str(e)}
    
    return {
        "total_files": len(files),
        "total_duration_sec": round(total_duration, 2),
        "session_id": session_id,
        "results": all_raw_texts,
        "data": cccd_data,
    }



# ============================================
# CCCD REALTIME OCR ENDPOINT (Base64 Images)
# ============================================

class CCCDRealtimeRequest(BaseModel):
    """Request model for realtime CCCD OCR with base64 images"""
    front_image: str  # Base64 encoded image (required)
    back_image: Optional[str] = None  # Base64 encoded image (optional)
    model_name: Optional[str] = None
    timeout_seconds: Optional[int] = None

@app.post(
    "/ocr-cccd-realtime",
    summary="OCR Vietnamese Citizen ID Card (CCCD) - Realtime with Base64 images",
)
async def ocr_cccd_realtime(request: CCCDRealtimeRequest):
    """
    OCR Vietnamese Citizen ID Card using base64 encoded images.
    
    - Accepts JSON body with base64 encoded front/back images
    - Faster than file upload for web clients
    - Front image is required, back image is optional
    
    Request body:
    ```json
    {
      "front_image": "base64_encoded_string...",
      "back_image": "base64_encoded_string..." (optional),
      "model_name": "gemma3:4b" (optional),
      "timeout_seconds": 60 (optional)
    }
    ```
    """
    import base64
    from src.parsers.cccd_parser import parse_cccd
    
    model_name = request.model_name or config.VLLM_MODEL
    timeout = request.timeout_seconds or config.OCR_TIMEOUT_SECONDS
    
    if not request.front_image:
        raise HTTPException(status_code=400, detail="front_image is required")
    
    results = []
    total_start_time = time.time()
    
    # Process front image
    front_text = None
    back_text = None
    
    for side, b64_image in [("front", request.front_image), ("back", request.back_image)]:
        if not b64_image:
            continue
            
        try:
            # Decode base64 image
            # Handle data URL format: "data:image/jpeg;base64,/9j/..."
            if "," in b64_image:
                b64_image = b64_image.split(",", 1)[1]
            
            image_bytes = base64.b64decode(b64_image)
            
            file_start_time = time.time()
            
            # Get prompt
            cccd_prompt = config.PROMPTS.get("cccd", config.PROMPTS.get("plain", "Extract all text from this ID card image."))
            
            # OCR
            chunks = []
            for chunk in stream_ocr_response(
                model_name=model_name,
                prompt=cccd_prompt,
                image_bytes=image_bytes,
                options=config.INFERENCE_PARAMS,
                timeout_seconds=timeout,
            ):
                if chunk:
                    chunks.append(chunk)
            
            raw_text = "".join(chunks).strip()
            elapsed = time.time() - file_start_time
            
            if side == "front":
                front_text = raw_text
            else:
                back_text = raw_text
            
            results.append({
                "side": side,
                "duration_sec": round(elapsed, 2),
                "raw_text": raw_text
            })
            
        except base64.binascii.Error as e:
            results.append({
                "side": side,
                "error": f"Invalid base64 encoding: {str(e)}",
                "raw_text": None
            })
            
        except OCRTimeoutError as e:
            elapsed = time.time() - file_start_time
            partial_text = "".join(chunks) if chunks else None
            if side == "front":
                front_text = partial_text
            else:
                back_text = partial_text
            results.append({
                "side": side,
                "error": f"OCR timeout after {round(elapsed, 1)}s",
                "duration_sec": round(elapsed, 2),
                "raw_text": partial_text
            })
            
        except Exception as e:
            results.append({
                "side": side,
                "error": str(e),
                "raw_text": None
            })
    
    total_duration = time.time() - total_start_time
    
    # Parse CCCD
    cccd_data = None
    if front_text:
        try:
            cccd = parse_cccd(front_text, back_text)
            cccd_data = cccd.model_dump()
        except Exception as e:
            cccd_data = {"parse_error": str(e)}
    
    return {
        "total_duration_sec": round(total_duration, 2),
        "results": results,
        "data": cccd_data,
    }




# ============================================
# BILL OF LADING OCR ENDPOINT
# ============================================

@app.post(
    "/ocr-bol",
    summary="OCR Bill of Lading (B/L) document",
)
async def detect_bill_of_lading_ocr(
    file: UploadFile = File(...),
    model_name: str = Form(config.VLLM_MODEL),
    ocr_mode: str = Form(config.DEFAULT_OCR_MODE),
    pages: str = Form(None),
    per_file_timeout: int = Form(config.OCR_TIMEOUT_SECONDS),
):
    """
    OCR a single Bill of Lading (B/L) document (PNG, JPG, JPEG, PDF, DOC, DOCX).
    Returns parsed B/L data with shipper, consignee, cargo details.
    Uses 45% header crop for zoom-in OCR pass.
    """
    from src.schemas.bill_of_lading import BillOfLading
    from src.parsers.block_bol_parser import parse_bol_block_based
    from src.parsers.block_bol_zoomtext_parser import parse_zoom_bol

    if not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded")

    if not file.filename.lower().endswith(file_handler.SUPPORTED_EXTENSIONS):
        raise HTTPException(status_code=400, detail="Unsupported file type. Use PNG, JPG, JPEG, PDF, DOC, or DOCX.")

    session_id = str(uuid.uuid4())
    temp_dir = Path("temp_ocr") / session_id
    temp_dir.mkdir(parents=True, exist_ok=True)

    # Save temp file
    temp_file = temp_dir / file.filename
    with open(temp_file, "wb") as f:
        f.write(await file.read())

    file_start_time = time.time()

    try:
        # OCR the full document
        ocr_result = run_vision_ocr(
            str(temp_file),
            model_name=model_name,
            ocr_mode=ocr_mode,
            pages=pages,
            timeout_seconds=per_file_timeout,
        )

        raw_text = ocr_result["raw_text"]

        # Parse B/L from raw text
        bol = parse_bol_block_based(raw_text)

        # ---- ZOOM-IN PASS (45% crop) ----
        # Always run zoom-in for B/L since header fields are critical
        missing_fields = []
        if not bol.blNumber:
            missing_fields.append("blNumber")
        if not bol.shipperName:
            missing_fields.append("shipperName")
        if not bol.consigneeName:
            missing_fields.append("consigneeName")
        if not bol.carrier:
            missing_fields.append("carrier")

        if missing_fields:
            print(f"B/L Missing fields {missing_fields} - Triggering 45% Zoom-in Pass...")
            selected_page_indices = ocr_result.get("page_indices", [0])
            zoom_page_idx = selected_page_indices[0] if selected_page_indices else 0

            # Use 45% crop for B/L documents
            bol_crop_bytes = file_handler.get_bol_crop_bytes_page(str(temp_file), zoom_page_idx)
            if bol_crop_bytes:
                zoom_prompt = config.PROMPTS.get("header_only", "Free OCR.")
                zoom_chunks = []
                try:
                    for chunk in stream_ocr_response(
                        model_name=model_name,
                        prompt=zoom_prompt,
                        image_bytes=bol_crop_bytes,
                        options=config.INFERENCE_PARAMS,
                        timeout_seconds=config.ZOOM_OCR_TIMEOUT_SECONDS,
                    ):
                        if chunk:
                            zoom_chunks.append(chunk)

                    zoom_text = "".join(zoom_chunks).strip()
                    print(f"B/L Zoom-in Text: {zoom_text[:100]}...")

                    # Parse zoom text
                    zoom_lines = zoom_text.splitlines()
                    parse_zoom_bol(zoom_lines, bol)

                    # Append zoom text for debugging
                    if zoom_text:
                        raw_text += f"\n\n--- ZOOM TEXT ---\n{zoom_text}"

                except Exception as e:
                    print(f"B/L Zoom-in OCR failed: {e}")
                    raw_text += f"\n\n--- ZOOM ERROR ---\n{e}"

        # Build result
        result_data = {
            "filename": file.filename,
            "duration_sec": ocr_result["duration_sec"],
            "ocr_mode": ocr_mode,
            "raw_text": raw_text,
            "data": bol,
        }
        if ocr_result.get("timed_out"):
            result_data["warning"] = f"OCR timeout - partial results (limit: {per_file_timeout}s)"
        return result_data

    except Exception as e:
        elapsed = time.time() - file_start_time
        return {
            "filename": file.filename,
            "error": str(e),
            "duration_sec": round(elapsed, 2),
            "data": None
        }



# FILE ACCESS (DEBUG)
@app.get("/files/{session_id}/{filename}")
async def get_temp_file(session_id: str, filename: str):
    path = Path("temp_ocr") / session_id / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(str(path))



# STARTUP

@app.on_event("startup")
def on_startup():
    Path("temp_ocr").mkdir(exist_ok=True)



# OPENAPI

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(
        title="Local Vision OCR API",
        version="1.0.0",
        description="FastAPI wrapper for local Vision OCR engine",
        routes=app.routes,
    )
    app.openapi_schema = schema
    return schema


app.openapi = custom_openapi


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.api_server:app", host="0.0.0.0", port=8000, reload=False)
