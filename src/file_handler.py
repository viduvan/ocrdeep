# src/file_handler.py
# Handles loading and preprocessing of images and PDF files for OCR.

import io
import fitz # PyMuPDF
from PIL import Image # Pillow
import pillow_heif # Handle HEIC images
from src import config

# Register HEIC opener
pillow_heif.register_heif_opener()

# Disable Pillow's safety limit for very large images (e.g. scanned documents)
Image.MAX_IMAGE_PIXELS = None


# Ollama already handled the image padding
# See: https://github.com/ollama/ollama/blob/main/model/models/deepseekocr/imageprocessor.go
def preprocess_image(img: Image.Image) -> bytes:
    # Apply standard preprocessing and return PNG bytes.
    # We DO NOT resize or pad here because Ollama needs the original
    # high-resolution image to perform its own multi-view cropping.

    # Ensure RGB format (matches Ollama/vLLM implementation)
    if img.mode != 'RGB':
        img = img.convert('RGB')

    # Export as PNG bytes (lossless format preserves text quality)
    img_buffer = io.BytesIO()
    img.save(img_buffer, format='PNG')
    return img_buffer.getvalue()

def get_image_bytes(filepath):
    # Read an image file, preprocess it, and return PNG bytes.
    try:
        with Image.open(filepath) as img:
            return preprocess_image(img)
    except Exception as e:
        print(f"PIL failed to load {filepath} or process it: {e}")
        # Fallback: return raw file bytes if preprocessing fails
        with open(filepath, "rb") as f:
            return f.read()

def get_pdf_page_count(filepath):
    # Return the number of pages in a PDF without loading images.
    try:
        doc = fitz.open(filepath)
        count = len(doc)
        doc.close()
        return count
    except Exception as e:
        print(f"Failed to get PDF page count for {filepath}: {e}")
        return 0

def extract_pdf_page_bytes(filepath, page_index, target_dpi=300):
    # Render a PDF page as an image, preprocess it, and return PNG bytes.
    doc = fitz.open(filepath)
    page = doc.load_page(page_index)

    # Cap maximum dimension to prevent malloc errors
    # Increased to 4096 and using higher num_ctx/temperature to avoid loops
    MAX_DIM = 4096
    rect = page.rect
    width, height = rect.width, rect.height

    # Calculate zoom based on DPI
    # 144 / 72.0 (Default PDF DPI) = 2.0x zoom.
    zoom = target_dpi / 72.0

    # If 144 DPI results in a huge image (>3000px), scale down to fit MAX_DIM.
    if (width * zoom > MAX_DIM) or (height * zoom > MAX_DIM):
        zoom = MAX_DIM / max(width, height)
    zoom = max(zoom, 0.5)  # Minimum 50% zoom to ensure readability

    # fitz.Matrix applies uniform scaling in both dimensions
    matrix = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=matrix, alpha=False)

    # Convert PyMuPDF pixmap to PIL Image, then preprocess
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    img_bytes = preprocess_image(img)

    doc.close()
    return img_bytes


def get_header_crop_bytes(filepath: str, ratio: float = 0.33) -> bytes:
    """
    Crops the top `ratio` part of the image/PDF (the header).
    Returns PNG bytes of the cropped region.
    Useful for 'Zoom-in' OCR pass.
    """
    try:
        if filepath.lower().endswith(".pdf"):
            # Render page 0 at high DPI
            doc = fitz.open(filepath)
            page = doc.load_page(0)
            rect = page.rect
            
            # Define crop box (top portion) relative to page origin
            # Use rect.x0, rect.y0 to handle PDFs with non-zero origins
            clip_height = rect.height * ratio
            clip = fitz.Rect(rect.x0, rect.y0, rect.x1, rect.y0 + clip_height)
            
            # Zoom logic consistent with extract_pdf_page_bytes
            # "No Zoom" = Native PDF resolution (72 DPI)
            target_dpi = 72
            zoom = target_dpi / 72.0
            
            matrix = fitz.Matrix(zoom, zoom)
            
            pix = page.get_pixmap(matrix=matrix, clip=clip, alpha=False)
            doc.close()
            return pix.tobytes("png")
        else:
            # Image handling
            with Image.open(filepath) as img:
                w, h = img.size
                crop_h = int(h * ratio)
                cropped_img = img.crop((0, 0, w, crop_h))
                
                # Convert to bytes
                buf = io.BytesIO()
                cropped_img.save(buf, format="PNG")
                return buf.getvalue()
    except Exception as e:
        print(f"Error extracting header crop: {e}")
        return None


def get_header_crop_bytes_page(filepath: str, page_index: int, ratio: float = 0.35) -> bytes:
    """
    Crops the top `ratio` part of a SPECIFIC PAGE of a PDF.
    Returns PNG bytes of the cropped region.
    For multi-page PDF zoom-in OCR pass.
    """
    try:
        if not filepath.lower().endswith(".pdf"):
            # For images, just delegate to the regular function
            return get_header_crop_bytes(filepath, ratio)
        
        doc = fitz.open(filepath)
        if page_index >= len(doc):
            doc.close()
            print(f"Page index {page_index} out of range for PDF with {len(doc)} pages")
            return None
        
        page = doc.load_page(page_index)
        rect = page.rect
        
        # Define crop box (top portion) relative to page origin
        clip_height = rect.height * ratio
        clip = fitz.Rect(rect.x0, rect.y0, rect.x1, rect.y0 + clip_height)
        
        # Use native PDF resolution
        target_dpi = 72
        zoom = target_dpi / 72.0
        
        matrix = fitz.Matrix(zoom, zoom)
        
        pix = page.get_pixmap(matrix=matrix, clip=clip, alpha=False)
        doc.close()
        return pix.tobytes("png")
    except Exception as e:
        print(f"Error extracting header crop for page {page_index}: {e}")
        return None