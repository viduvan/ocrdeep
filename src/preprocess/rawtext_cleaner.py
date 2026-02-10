import re

def clean_rawtext(raw_text: str) -> str:
    """
    Remove OCR noise: <|ref|>, <|det|>, bbox, duplicated spaces
    Keep HTML <table> intact
    """

    # remove ref / det tags
    raw_text = re.sub(r"<\|ref\|>.*?<\|/ref\|>", "", raw_text, flags=re.S)
    raw_text = re.sub(r"<\|det\|>.*?<\|/det\|>", "", raw_text, flags=re.S)

    # normalize newlines
    raw_text = raw_text.replace("\r", "\n")
    raw_text = re.sub(r"\n{2,}", "\n", raw_text)

    return raw_text.strip()
