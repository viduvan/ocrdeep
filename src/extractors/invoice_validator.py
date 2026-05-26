"""
Post-extraction validator for invoice data.
Uses rule-based logic to validate and fix critical fields,
cross-check amounts, and compute confidence scores.

Usage:
    from src.extractors.invoice_validator import InvoiceValidator
    validator = InvoiceValidator()
    validated = validator.validate(invoice_dict, raw_text)
"""
import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class InvoiceValidator:
    """Validate and fix LLM extraction output for critical fields."""
    
    def validate(self, invoice: dict, raw_text: str, zoom_text: str = "") -> dict:
        """
        Post-process LLM output:
        1. Verify critical fields against raw text
        2. Fix common LLM mistakes (amounts, dates)
        3. Calculate per-field confidence scores
        4. Flag suspicious values
        """
        flags = {}
        combined_text = raw_text + "\n" + (zoom_text or "")
        
        self._validate_amounts(invoice, flags)
        self._validate_dates(invoice, flags)
        self._validate_tax_codes(invoice, flags)
        self._verify_against_raw_text(invoice, combined_text, flags)
        self._clean_template_placeholders(invoice)
        
        invoice["_flags"] = flags
        invoice["_confidence"] = self._compute_confidence(invoice, combined_text)
        
        return invoice
    
    def _validate_amounts(self, invoice: dict, flags: dict):
        """
        Cross-check amount consistency:
        - totalAmount ≈ sum(item.amount)
        - quantity × unitPrice ≈ amount per item
        - preTaxPrice + taxAmount ≈ totalAmount
        """
        items = invoice.get("itemList", []) or []
        
        # Item-level math validation
        for i, item in enumerate(items):
            qty = item.get("quantity")
            price = item.get("unitPrice")
            amount = item.get("amount")
            
            if (
                qty is not None
                and price is not None
                and amount is not None
                and qty > 0
                and price > 0
                and amount > 0
            ):
                expected = round(qty * price, 2)
                if abs(expected - amount) > 0.5:
                    flags[f"item_{i}_math"] = (
                        f"MISMATCH: {qty}×{price}={expected} ≠ {amount}"
                    )
        
        # Total vs item sum validation
        total = invoice.get("totalAmount")
        item_sum = sum(
            item.get("amount", 0) or 0 for item in items
        )
        
        if total and item_sum > 0:
            # For GTGT invoices, items may be pre-tax amounts while total is post-tax
            # Also check against preTaxPrice
            pre_tax = invoice.get("preTaxPrice")
            if pre_tax and pre_tax > 0:
                diff_pretax = abs(pre_tax - item_sum) / max(pre_tax, item_sum)
                diff_total = abs(total - item_sum) / max(total, item_sum)
                # Match if items ≈ preTaxPrice OR items ≈ total
                if diff_pretax > 0.02 and diff_total > 0.02:
                    flags["total_vs_items"] = (
                        f"total={total}, preTax={pre_tax}, sum(items)={item_sum}"
                    )
            else:
                diff_pct = abs(total - item_sum) / max(total, item_sum)
                if diff_pct > 0.02:  # >2% difference
                    flags["total_vs_items"] = (
                        f"total={total}, sum(items)={item_sum}, diff={diff_pct:.1%}"
                    )
        
        # Pre-tax + tax ≈ total
        pre_tax = invoice.get("preTaxPrice")
        tax_amount = invoice.get("taxAmount")
        if pre_tax is not None and total:
            tax_amount = invoice.get("taxAmount") or 0
            expected_total = round(pre_tax + tax_amount, 2)
            if abs(expected_total - total) > 1.0:
                flags["pretax_plus_tax"] = (
                    f"preTax({pre_tax})+tax({tax_amount})="
                    f"{expected_total} ≠ total({total})"
                )
    
    def _validate_dates(self, invoice: dict, flags: dict):
        """Reject obviously invalid dates."""
        date_val = invoice.get("invoiceDate")
        if date_val and isinstance(date_val, str):
            # Try ISO format YYYY-MM-DD
            m = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})", str(date_val))
            if m:
                y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
                if not (1900 <= y <= 2100 and 1 <= mo <= 12 and 1 <= d <= 31):
                    flags["invalid_date"] = f"Out of range: {date_val}"
                    invoice["invoiceDate"] = None
    
    def _validate_tax_codes(self, invoice: dict, flags: dict):
        """
        Validate tax code formats:
        - VN: 10 digits or 10-3/4 digits (e.g., 0106046798 or 0106046798-001)
        - Other: just flag if suspiciously short/long
        """
        for field in ["sellerTaxCode", "buyerTaxCode"]:
            val = invoice.get(field)
            if val:
                clean = str(val).replace(" ", "").replace("-", "")
                if len(clean) < 5:
                    flags[f"{field}_short"] = f"Suspiciously short: {val}"
    
    def _verify_against_raw_text(
        self, invoice: dict, raw_text: str, flags: dict
    ):
        """
        Check if critical extracted values actually exist in the source text.
        Flags potential hallucinations.
        """
        critical_fields = [
            "invoiceID",
            "sellerName",
            "buyerName",
            "sellerTaxCode",
            "buyerTaxCode",
        ]
        
        for field in critical_fields:
            val = invoice.get(field)
            if val and str(val) not in raw_text:
                # Check case-insensitive match
                if str(val).lower() not in raw_text.lower():
                    flags[f"{field}_not_in_source"] = (
                        f"Value '{val}' not found in raw text"
                    )
    
    def _clean_template_placeholders(self, invoice: dict):
        """
        Remove template placeholder values like [Sender.Company],
        [Invoice.No], etc.
        """
        placeholder_pattern = re.compile(r'^\[[\w.]+\]$')
        
        for key, val in invoice.items():
            if (
                isinstance(val, str)
                and placeholder_pattern.match(val)
            ):
                invoice[key] = None
        
        # Also clean items
        for item in invoice.get("itemList", []) or []:
            for key, val in item.items():
                if (
                    isinstance(val, str)
                    and placeholder_pattern.match(val)
                ):
                    item[key] = None
    
    def _compute_confidence(self, invoice: dict, raw_text: str) -> dict:
        """
        Per-field confidence scoring:
        - HIGH: Value found verbatim in raw text
        - MEDIUM: Partial match (some words found)
        - LOW: Value not found (possible hallucination or transformation)
        """
        confidence = {}
        skip_fields = {"itemList", "_flags", "_confidence"}
        
        # Normalize raw text: remove VN thousand separators for number matching
        raw_text_normalized = raw_text
        
        for field, value in invoice.items():
            if value is None or field in skip_fields:
                continue
            
            val_str = str(value)
            
            # Direct match
            if val_str in raw_text:
                confidence[field] = "HIGH"
                continue
            
            # For numeric values, try matching with VN formatting (dots as thousands)
            try:
                num_val = float(val_str)
                # Format as VN number: 4463014 → check for "4.463.014" or "4,463,014"
                int_val = int(num_val) if num_val == int(num_val) else None
                if int_val is not None:
                    vn_formatted = f"{int_val:,}".replace(",", ".")
                    if vn_formatted in raw_text or str(int_val) in raw_text:
                        confidence[field] = "HIGH"
                        continue
                # Also try the float string without trailing .0
                if val_str.endswith(".0"):
                    if val_str[:-2] in raw_text:
                        confidence[field] = "HIGH"
                        continue
            except (ValueError, TypeError):
                pass
            
            if len(val_str) > 3:
                # Check if significant parts are in the text
                words = [w for w in val_str.split() if len(w) > 2]
                if words:
                    found = sum(
                        1 for w in words if w in raw_text
                    )
                    ratio = found / len(words)
                    if ratio >= 0.5:
                        confidence[field] = "MEDIUM"
                    else:
                        confidence[field] = "LOW"
                else:
                    confidence[field] = "MEDIUM"
            else:
                # Short values - check exact match
                confidence[field] = (
                    "HIGH" if val_str in raw_text else "LOW"
                )
        
        return confidence
    
    def get_summary(self, invoice: dict) -> dict:
        """
        Get a summary of validation results.
        Returns counts of flags and confidence levels.
        """
        flags = invoice.get("_flags", {})
        confidence = invoice.get("_confidence", {})
        
        return {
            "total_flags": len(flags),
            "flags": list(flags.keys()),
            "confidence_high": sum(
                1 for v in confidence.values() if v == "HIGH"
            ),
            "confidence_medium": sum(
                1 for v in confidence.values() if v == "MEDIUM"
            ),
            "confidence_low": sum(
                1 for v in confidence.values() if v == "LOW"
            ),
            "low_confidence_fields": [
                k for k, v in confidence.items() if v == "LOW"
            ],
        }
