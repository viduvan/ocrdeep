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

from src import file_handler, config
from src.vllm_service import stream_ocr_response, OCRTimeoutError
from src.utils.table_guard import TableGuard
from src.utils.date_utils import parse_vn_date
from src.schemas.invoice import Invoice
from src.schemas.invoice_item import InvoiceItem
from src.parsers.invoice_parser import normalize_invoice_output
from src.semantic.semantic_refine import semantic_refine
from src.parsers.block_invoice_parser import parse_invoice_block_based, parse_header





# FASTAPI APP

app = FastAPI(
    title="Local Vision OCR API",
    description="FastAPI wrapper for local Vision OCR (same engine as UI)",
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
    
    # Determine total pages in PDF
    if file_path.lower().endswith(".pdf"):
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
        if file_path.lower().endswith(".pdf"):
            image_bytes = file_handler.extract_pdf_page_bytes(file_path, page_idx)
        else:
            image_bytes = file_handler.get_image_bytes(file_path)

        table_guard = None
        if ocr_mode == "markdown":
            table_guard = TableGuard(max_rows=10, max_consecutive_empty_rows=2)

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
    OCR a single invoice file (PNG, JPG, JPEG, PDF).
    Returns parsed invoice data.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded")
    
    if not file.filename.lower().endswith((".png", ".jpg", ".jpeg", ".pdf")):
        raise HTTPException(status_code=400, detail="Unsupported file type. Use PNG, JPG, JPEG, or PDF.")
    
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
            for arr_idx, page_text in enumerate(page_texts):
                actual_page_idx = actual_page_indices[arr_idx] if arr_idx < len(actual_page_indices) else arr_idx
                
                invoice = parse_invoice_block_based(page_text)
                
                if not invoice.itemList and not invoice.sellerName and not invoice.buyerName:
                    invoice_data = normalize_invoice_output(page_text)
                    invoice = Invoice(**invoice_data)
                
                # Per-page zoom-in
                missing_fields = []
                if not invoice.invoiceID or len(str(invoice.invoiceID)) < 3:
                    missing_fields.append("invoiceID")
                if not invoice.invoiceSerial:
                    missing_fields.append("invoiceSerial")
                form_no = (invoice.invoiceFormNo or "").lower()
                if not invoice.invoiceFormNo or "điều" in form_no or "mẫu" in form_no:
                    missing_fields.append("invoiceFormNo")
                
                if missing_fields:
                    print(f"Page {actual_page_idx + 1}: Missing {missing_fields} - Triggering Zoom-in...")
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
                            
                            zoom_text = "".join(zoom_chunks).strip()
                            from src.parsers.block_invoice_zoomtext_parser import parse_zoom_header
                            zoom_lines = zoom_text.splitlines()
                            parse_zoom_header(zoom_lines, invoice)
                            
                        except Exception as e:
                            print(f"Page {actual_page_idx + 1} Zoom-in OCR failed: {e}")
                
                # Convert to dict and refine
                from pydantic import BaseModel
                if isinstance(invoice, BaseModel):
                    invoice_dict = invoice.model_dump()
                else:
                    invoice_dict = invoice
                
                if semantic:
                    invoice_dict = semantic_refine(
                        raw_text=page_text,
                        invoice=invoice_dict,
                    )
                
                if isinstance(invoice_dict.get("invoiceDate"), str):
                    parsed = parse_vn_date(invoice_dict["invoiceDate"])
                    invoice_dict["invoiceDate"] = parsed
                
                if not invoice_dict.get("totalAmount") and invoice_dict.get("invoiceTotalInWord"):
                    from src.utils.text_to_number import text_to_number_vn
                    try:
                        val = text_to_number_vn(invoice_dict["invoiceTotalInWord"])
                        if val > 0:
                            invoice_dict["totalAmount"] = val
                    except:
                        pass
                
                invoices.append(Invoice(**invoice_dict))
            
            result_data = {
                "filename": file.filename,
                "duration_sec": ocr_result["duration_sec"],
                "ocr_mode": ocr_mode,
                "page_count": page_count,
                "raw_text": raw_text,
                "data": invoices,
            }
            if ocr_result.get("timed_out"):
                result_data["warning"] = f"OCR timeout - partial results (limit: {per_file_timeout}s)"
            return result_data

        # ---- SINGLE PAGE HANDLING ----
        invoice = parse_invoice_block_based(raw_text)

        if not invoice.itemList and not invoice.sellerName and not invoice.buyerName:
            invoice_data = normalize_invoice_output(raw_text)
            invoice = Invoice(**invoice_data)

        # Header zoom-in
        missing_fields = []
        if not invoice.invoiceID or len(str(invoice.invoiceID)) < 3: 
            missing_fields.append("invoiceID (missing/short)")
        if not invoice.invoiceSerial: 
            missing_fields.append("invoiceSerial")
        
        form_no = (invoice.invoiceFormNo or "").lower()
        if not invoice.invoiceFormNo or "điều" in form_no or "mẫu" in form_no: 
            missing_fields.append("invoiceFormNo (missing/suspicious)")
        
        if not invoice.invoiceDate: 
            missing_fields.append("invoiceDate")
            
        name_upper = (invoice.invoiceName or "").upper()
        valid_titles = ["HÓA ĐƠN", "PHIẾU", "RECEIPT", "INVOICE"]
        if not invoice.invoiceName or \
           not any(t in name_upper for t in valid_titles) or \
           invoice.invoiceName.strip().startswith("(") or \
           "BẢN THỂ HIỆN" in name_upper or "BẢN SAO" in name_upper:
             missing_fields.append("invoiceName (missing/suspicious)")

        if missing_fields:
            print(f"Missing header fields {missing_fields} - Triggering Zoom-in Pass...")
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
                    print(f"Zoom-in Text: {zoom_text[:100]}...")

                    from src.parsers.block_invoice_zoomtext_parser import parse_zoom_header
                    zoom_lines = zoom_text.splitlines()
                    
                    print(f"DEBUG: Before Zoom Parse ID: {invoice.invoiceID}")
                    parse_zoom_header(zoom_lines, invoice)
                    print(f"DEBUG: After Zoom Parse ID: {invoice.invoiceID}")
                    
                    if zoom_text:
                        raw_text += f"\n\n--- ZOOM TEXT ---\n{zoom_text}"
                        
                        if not invoice.sellerName:
                            import re
                            m = re.search(r"(?:Đơn vị bán hàng|Seller)[^:]*:\s*(.+)", zoom_text, re.I)
                            if m:
                                invoice.sellerName = m.group(1).strip()
                        if not invoice.sellerTaxCode:
                            import re
                            m = re.search(r"(?:Mã số thuế|Tax code)[^:]*:\s*(\d{10,14})", zoom_text, re.I)
                            if m:
                                invoice.sellerTaxCode = m.group(1)

                except Exception as e:
                    print(f"Zoom-in OCR failed: {e}")
                    raw_text += f"\n\n--- ZOOM ERROR ---\n{e}"

        # Semantic refine
        if semantic:
            from pydantic import BaseModel

            if isinstance(invoice, BaseModel):
                invoice_dict = invoice.model_dump()
            else:
                invoice_dict = invoice

            invoice_dict = semantic_refine(
                raw_text=raw_text,
                invoice=invoice_dict,
            )
            
            if isinstance(invoice_dict.get("invoiceDate"), str):
                parsed = parse_vn_date(invoice_dict["invoiceDate"])
                invoice_dict["invoiceDate"] = parsed

            if not invoice_dict.get("totalAmount") and invoice_dict.get("invoiceTotalInWord"):
                from src.utils.text_to_number import text_to_number_vn
                try:
                    val = text_to_number_vn(invoice_dict["invoiceTotalInWord"])
                    if val > 0:
                        invoice_dict["totalAmount"] = val
                        print(f"Recovered totalAmount from words: {val}")
                except Exception as e:
                    print(f"Failed to convert words to number: {e}")

            invoice = Invoice(**invoice_dict)

        # Build result
        result_data = {
            "filename": file.filename,
            "duration_sec": ocr_result["duration_sec"],
            "ocr_mode": ocr_mode,
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


# ================================
# API ENDPOINT - Multiple Files
# ================================

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
            
        if not file.filename.lower().endswith((".png", ".jpg", ".jpeg", ".pdf")):
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
            # If multiple pages, split by page markers and parse each as separate invoice
            if page_count > 1:
                import re
                # Split by "--- PAGE N ---" markers
                page_texts = re.split(r'--- PAGE \d+ ---\n?', raw_text)
                page_texts = [p.strip() for p in page_texts if p.strip()]  # Remove empty
                
                # Get actual page indices (0-indexed) from OCR result
                actual_page_indices = ocr_result.get("page_indices", list(range(len(page_texts))))
                
                invoices = []
                for arr_idx, page_text in enumerate(page_texts):
                    # Get the ACTUAL PDF page index (0-indexed) for this page
                    actual_page_idx = actual_page_indices[arr_idx] if arr_idx < len(actual_page_indices) else arr_idx
                    
                    # Parse each page as a separate invoice
                    invoice = parse_invoice_block_based(page_text)
                    
                    # Fallback if block parser empty
                    if not invoice.itemList and not invoice.sellerName and not invoice.buyerName:
                        invoice_data = normalize_invoice_output(page_text)
                        invoice = Invoice(**invoice_data)
                    
                    # ---- PER-PAGE ZOOM-IN STRATEGY ----
                    # Check if critical header fields are missing
                    missing_fields = []
                    if not invoice.invoiceID or len(str(invoice.invoiceID)) < 3:
                        missing_fields.append("invoiceID")
                    if not invoice.invoiceSerial:
                        missing_fields.append("invoiceSerial")
                    form_no = (invoice.invoiceFormNo or "").lower()
                    if not invoice.invoiceFormNo or "điều" in form_no or "mẫu" in form_no:
                        missing_fields.append("invoiceFormNo")
                    
                    if missing_fields:
                        # Use 1-indexed for display, but actual_page_idx is 0-indexed for function call
                        print(f"Page {actual_page_idx + 1}: Missing {missing_fields} - Triggering Zoom-in...")
                        # Get header crop for the ACTUAL PDF page
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
                                
                                zoom_text = "".join(zoom_chunks).strip()
                                print(f"Page {actual_page_idx + 1} Zoom Text: {zoom_text[:80]}...")
                                
                                # Parse zoom text to fill missing fields
                                from src.parsers.block_invoice_zoomtext_parser import parse_zoom_header
                                zoom_lines = zoom_text.splitlines()
                                parse_zoom_header(zoom_lines, invoice)
                                
                            except Exception as e:
                                print(f"Page {actual_page_idx + 1} Zoom-in OCR failed: {e}")
                    
                    # Convert to dict for semantic refine
                    from pydantic import BaseModel
                    if isinstance(invoice, BaseModel):
                        invoice_dict = invoice.model_dump()
                    else:
                        invoice_dict = invoice
                    
                    # Semantic refine
                    if semantic:
                        invoice_dict = semantic_refine(
                            raw_text=page_text,
                            invoice=invoice_dict,
                        )
                    
                    # Fix date
                    if isinstance(invoice_dict.get("invoiceDate"), str):
                        parsed = parse_vn_date(invoice_dict["invoiceDate"])
                        invoice_dict["invoiceDate"] = parsed
                    
                    # Fallback total from words
                    if not invoice_dict.get("totalAmount") and invoice_dict.get("invoiceTotalInWord"):
                        from src.utils.text_to_number import text_to_number_vn
                        try:
                            val = text_to_number_vn(invoice_dict["invoiceTotalInWord"])
                            if val > 0:
                                invoice_dict["totalAmount"] = val
                        except:
                            pass
                    
                    invoices.append(Invoice(**invoice_dict))
                
                return {
                    "duration_sec": ocr_result["duration_sec"],
                    "ocr_mode": ocr_mode,
                    "page_count": page_count,
                    "raw_text": raw_text,
                    "data": invoices,  # Array of invoices
                }

            # ---- SINGLE PAGE HANDLING (Original Logic) ----
            # invoice = normalize_invoice_output(raw_text)
            # PARSE INVOICE (BLOCK-BASED FIRST)
            invoice = parse_invoice_block_based(raw_text)

            # Fallback nếu block parser quá rỗng (an toàn)
            if not invoice.itemList and not invoice.sellerName and not invoice.buyerName:
                invoice_data = normalize_invoice_output(raw_text)
                invoice = Invoice(**invoice_data)

            # ---- HEADER ZOOM-IN STRATEGY ----
            # Optimize: Only run zoom if we are missing critical fields.
            # User request: "If first pass has ID, Serial, and FormNo, skip crop".
            # So we trigger if ANY of these are missing.
            missing_fields = []
            if not invoice.invoiceID or len(str(invoice.invoiceID)) < 3: 
                missing_fields.append("invoiceID (missing/short)")
            if not invoice.invoiceSerial: missing_fields.append("invoiceSerial")
            
            form_no = (invoice.invoiceFormNo or "").lower()
            if not invoice.invoiceFormNo or "điều" in form_no or "mẫu" in form_no: 
                missing_fields.append("invoiceFormNo (missing/suspicious)")
            
            # Also trigger if Date is missing or Name is suspicious
            if not invoice.invoiceDate: 
                missing_fields.append("invoiceDate")
                
            name_upper = (invoice.invoiceName or "").upper()
            # Trigger if name is missing, doesn't contain standard keywords, or starts with "(" (footer text)
            valid_titles = ["HÓA ĐƠN", "PHIẾU", "RECEIPT", "INVOICE"]
            if not invoice.invoiceName or \
               not any(t in name_upper for t in valid_titles) or \
               invoice.invoiceName.strip().startswith("(") or \
               "BẢN THỂ HIỆN" in name_upper or "BẢN SAO" in name_upper:
                 missing_fields.append("invoiceName (missing/suspicious)")

            if missing_fields:
                print(f"Missing header fields {missing_fields} - Triggering Zoom-in Pass...")
                # Use correct page index for zoom (might be a selected page from multi-page PDF)
                selected_page_indices = ocr_result.get("page_indices", [0])
                zoom_page_idx = selected_page_indices[0] if selected_page_indices else 0
                header_bytes = file_handler.get_header_crop_bytes_page(str(temp_file), zoom_page_idx)
                if header_bytes:
                    # Pass 2: OCR on header crop
                    # Use a specific prompt for header fields
                    zoom_prompt = config.PROMPTS.get("header_only", "Extract header info.")
                    zoom_chunks = []
                    try:
                        for chunk in stream_ocr_response(
                            model_name=model_name,
                            prompt=zoom_prompt,
                            image_bytes=header_bytes,
                            options=config.INFERENCE_PARAMS,
                            timeout_seconds=config.ZOOM_OCR_TIMEOUT_SECONDS,  # Shorter timeout for zoom
                        ):
                            if chunk: zoom_chunks.append(chunk)
                        
                        zoom_text = "".join(zoom_chunks).strip()
                        print(f"Zoom-in Text: {zoom_text[:100]}...") # Debug log
                        

                        # Parse header fields from zoom text using DEDICATED ZOOM PARSER
                        from src.parsers.block_invoice_zoomtext_parser import parse_zoom_header
                        
                        save_text = zoom_text
                        zoom_lines = zoom_text.splitlines()
                        
                        print(f"DEBUG: Before Zoom Parse ID: {invoice.invoiceID}")
                        parse_zoom_header(zoom_lines, invoice)
                        print(f"DEBUG: After Zoom Parse ID: {invoice.invoiceID}")
                        
                        # DEBUG: Append zoom text to raw_text so user can inspect it
                        if zoom_text:
                            raw_text += f"\n\n--- ZOOM TEXT ---\n{zoom_text}"
                            
                            # === SELLER FALLBACK FROM ZOOM TEXT ===
                            # For internal transfer slips, seller info is in ZOOM TEXT
                            if not invoice.sellerName:
                                import re
                                m = re.search(r"(?:Đơn vị bán hàng|Seller)[^:]*:\s*(.+)", zoom_text, re.I)
                                if m:
                                    invoice.sellerName = m.group(1).strip()
                            if not invoice.sellerTaxCode:
                                import re
                                m = re.search(r"(?:Mã số thuế|Tax code)[^:]*:\s*(\d{10,14})", zoom_text, re.I)
                                if m:
                                    invoice.sellerTaxCode = m.group(1)

                    except Exception as e:
                        print(f"Zoom-in OCR failed: {e}")
                        raw_text += f"\n\n--- ZOOM ERROR ---\n{e}"

            #SEMANTIC REFINE (CHỈ FIELD NULL)
            if semantic:
                from pydantic import BaseModel

                if isinstance(invoice, BaseModel):
                    invoice_dict = invoice.model_dump()
                else:
                    invoice_dict = invoice

                invoice_dict = semantic_refine(
                    raw_text=raw_text,
                    invoice=invoice_dict,
                )
                # fix date fields BEFORE Invoice validation
                if isinstance(invoice_dict.get("invoiceDate"), str):
                    parsed = parse_vn_date(invoice_dict["invoiceDate"])
                    invoice_dict["invoiceDate"] = parsed

                # Fallback: Convert TotalInWord to Number if totalAmount is missing
                if not invoice_dict.get("totalAmount") and invoice_dict.get("invoiceTotalInWord"):
                    from src.utils.text_to_number import text_to_number_vn
                    try:
                        val = text_to_number_vn(invoice_dict["invoiceTotalInWord"])
                        if val > 0:
                            invoice_dict["totalAmount"] = val
                            print(f"Recovered totalAmount from words: {val}")
                    except Exception as e:
                        print(f"Failed to convert words to number: {e}")

                invoice = Invoice(**invoice_dict)



            # Build result - include timed_out flag if OCR hit timeout (but still has partial data)
            result_data = {
                "filename": file.filename,
                "duration_sec": ocr_result["duration_sec"],
                "ocr_mode": ocr_mode,
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
