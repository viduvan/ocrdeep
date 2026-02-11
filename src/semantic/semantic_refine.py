import json
import time
from src.vllm_service import get_vllm_client
from src import config


SEMANTIC_TIMEOUT = 10  # seconds


def semantic_refine(raw_text: str, invoice: dict) -> dict:
    invoice_dict = invoice
    missing_fields = [
        k for k, v in invoice_dict.items()
        if v in (None, "", []) and k != "itemList"
    ]

    # Không cần semantic
    if not missing_fields:
        return invoice_dict

    # Quá nhiều field thiếu → không semantic (tránh hallucination)
    if len(missing_fields) > len(invoice_dict) * 0.5:
        return invoice_dict

    prompt = f"""
ONLY fill the missing fields listed.
Return VALID JSON only.

Missing fields:
{missing_fields}

OCR text:
\"\"\"
{raw_text}
\"\"\"

Current JSON:
{json.dumps(invoice_dict, ensure_ascii=False)}
"""

    client = get_vllm_client()

    start = time.time()
    try:
        response = client.chat(
            model=config.VLLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            options={
                "temperature": 0,
                "num_predict": 512,
            },
        )

        if time.time() - start > SEMANTIC_TIMEOUT:
            return invoice_dict

        content = response["message"]["content"].strip()

        patch = json.loads(content)

        # merge patch
        for k, v in patch.items():
            if k in invoice_dict and invoice_dict[k] in (None, "", []):
                invoice_dict[k] = v

        return invoice_dict

    except Exception:
        return invoice_dict
