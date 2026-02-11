# src/vllm_service.py
# vLLM Vision OCR service (API-only)

import time
import base64
from openai import OpenAI
from typing import Generator, Dict, Any

from src import config
from src.utils.table_guard import TableGuard


# vLLM Client Singleton (API-safe)

_vllm_client: OpenAI | None = None


def get_vllm_client() -> OpenAI:
    """
    Lazily create and reuse a single vLLM client.
    Safe for FastAPI (no UI, no threads).
    Uses OpenAI-compatible API.
    """
    global _vllm_client

    if _vllm_client is None:
        _vllm_client = OpenAI(
            base_url=getattr(config, "VLLM_HOST", "http://127.0.0.1:8000/v1"),
            api_key="EMPTY",  # vLLM doesn't require API key
        )

    return _vllm_client


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
    Stream OCR text from vLLM Vision model.

    - API-only (no PySide, no UI thread)
    - Supports image OCR via vLLM Vision models
    - Hard-stops infinite table loops via TableGuard
    - Hard timeout enforcement to prevent infinite loops
    
    Args:
        model_name: vLLM model name (HuggingFace format)
        prompt: OCR prompt
        image_bytes: Image data as bytes
        options: Inference options (temperature, max_tokens, etc.)
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

    # Convert image bytes to base64 for OpenAI API
    image_base64 = base64.b64encode(image_bytes).decode('utf-8')
    
    client = get_vllm_client()

    # Prepare inference options
    inference_options = {
        "temperature": 0.1,
        "max_tokens": 4096,
    }
    if options:
        inference_options.update(options)

    # Create chat completion with streaming
    try:
        stream = client.chat.completions.create(
            model=model_name,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt,
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_base64}"
                            },
                        },
                    ],
                }
            ],
            stream=True,
            **inference_options,
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

            if not chunk.choices:
                continue

            delta = chunk.choices[0].delta
            if not delta or not delta.content:
                continue

            chunk_count += 1
            yield delta.content

    except Exception as e:
        if isinstance(e, OCRTimeoutError):
            raise
        raise RuntimeError(f"vLLM inference error: {str(e)}") from e
