# src/ollama_service.py
# Ollama Vision OCR service (API-only)

import time
from ollama import Client
from typing import Generator, Dict, Any

from src import config
from src.utils.table_guard import TableGuard


# Ollama Client Singleton (API-safe)


_ollama_client: Client | None = None


def get_ollama_client() -> Client:
    """
    Lazily create and reuse a single Ollama client.
    Safe for FastAPI (no UI, no threads).
    """
    global _ollama_client

    if _ollama_client is None:
        _ollama_client = Client(
            host=getattr(config, "OLLAMA_HOST", "http://127.0.0.1:11434")
        )

    return _ollama_client


class OCRTimeoutError(Exception):
    """Raised when OCR streaming exceeds the timeout limit."""
    pass


# Vision OCR Streaming (API)

def stream_ocr_response(
    *,
    model_name: str,
    prompt: str,
    image_bytes: bytes,
    options: Dict[str, Any] | None = None,
    timeout_seconds: int | None = None,
) -> Generator[str, None, None]:
    """
    Stream OCR text from Ollama Vision model.

    - API-only (no PySide, no UI thread)
    - Supports image OCR via Ollama Vision models
    - Hard-stops infinite table loops via TableGuard
    - Hard timeout enforcement to prevent infinite loops
    
    Args:
        model_name: Ollama model name
        prompt: OCR prompt
        image_bytes: Image data as bytes
        options: Ollama inference options
        timeout_seconds: Max seconds to wait (default from config.OCR_TIMEOUT_SECONDS)
    
    Yields:
        Text chunks from OCR stream
        
    Raises:
        OCRTimeoutError: If streaming exceeds timeout
    """

    if not image_bytes:
        raise ValueError("image_bytes is empty or None")

    # Get timeout from config if not specified
    if timeout_seconds is None:
        timeout_seconds = getattr(config, "OCR_TIMEOUT_SECONDS", 60)

    client = get_ollama_client()

    stream = client.chat(
        model=model_name,
        messages=[
            {
                "role": "user",
                "content": prompt,
                "images": [image_bytes],
            }
        ],
        stream=True,
    )

    # Hard timeout enforcement
    start_time = time.time()
    chunk_count = 0

    for chunk in stream:
        # Check timeout on every chunk
        elapsed = time.time() - start_time
        if elapsed > timeout_seconds:
            yield f"\n<!-- OCR_TIMEOUT: Exceeded {timeout_seconds}s limit after {chunk_count} chunks -->\n"
            raise OCRTimeoutError(
                f"OCR streaming timed out after {elapsed:.1f}s (limit: {timeout_seconds}s)"
            )

        if not chunk:
            continue

        msg = chunk.get("message")
        if not msg:
            continue

        content = msg.get("content")
        if not content:
            continue

        chunk_count += 1
        yield content
