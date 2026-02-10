# src/config.py
import sys

APP_VERSION = "v1"




OLLAMA_HOST = "http://127.0.0.1:11434"
OLLAMA_MODEL = "deepseek-ocr:3b"

# DeepSeek-OCR expects 1024x1024 inputs
TARGET_IMAGE_SIZE = (1024, 1024)

# Configuration from Ollama Modelfile
INFERENCE_PARAMS = {
    "temperature": 0.1,
    "num_ctx": 4096,
}

PROMPTS = {
    "markdown": "<|grounding|>Convert the document to markdown.",
    "plain":  "Free OCR.",
    "header_only": "Free OCR.",
}



DEFAULT_OCR_MODE = "plain" 

# Hard timeout for OCR streaming (seconds)
# Prevents infinite loops in DeepSeek model
OCR_TIMEOUT_SECONDS = 60

# Separate timeout for Zoom OCR (header crop is smaller, should be faster)
ZOOM_OCR_TIMEOUT_SECONDS = 30

# Per-page timeout for multi-page PDF OCR (each page gets this much time)
MULTIPAGE_OCR_TIMEOUT_SECONDS = 45
