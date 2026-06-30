import asyncio
from dotenv import load_dotenv
load_dotenv()
from src.extractors.llm_extractor import extract_invoice_llm

raw_text = """
### COMMERCIAL INVOICE

#### Shipper
**HS Hyosung Quang Nam Co., Ltd**  

#### No & Date
**TCQKHKR-2605-01**

#### No & Date of LC
**5-Jun-26**

#### Remarks:
**T/T 30 DAYS AFTER BL DATE**  
**PO: 710061980**

#### Sailing on about
**7-Jun-26**

#### Unit-Price
**16. AMOUNT**
"""

result = extract_invoice_llm(raw_text, "")
print(result)
