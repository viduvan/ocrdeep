import re

class TableGuard:
    """
    Guards against OCR infinite loops:
    1. Table loops (HTML table with empty/repeating rows)
    2. Text repetition loops (same line repeating many times)
    3. Signature section limit (stop shortly after signature area)
    4. Fuzzy repetition detection for OCR noise
    """
    def __init__(
        self,
        max_rows=10,
        max_consecutive_empty_rows=2,
        max_line_repetition=5,          # Max times same line can repeat
        signature_char_limit=500,        # Max chars after signature keywords
        similarity_threshold=0.7,        # Min similarity for fuzzy repeat detection
    ):
        self.max_rows = max_rows
        self.max_consecutive_empty_rows = max_consecutive_empty_rows
        self.max_line_repetition = max_line_repetition
        self.signature_char_limit = signature_char_limit
        self.similarity_threshold = similarity_threshold
        self.reset()

    def reset(self):
        self.in_table = False
        self.row_count = 0
        self.empty_row_streak = 0
        self.last_stt = None
        # Line repetition tracking
        self.last_line = ""
        self.line_repeat_count = 0
        # Signature section tracking
        self.in_signature = False
        self.chars_after_signature = 0
        # Fuzzy repetition tracking
        self.recent_lines = []  # Store last N lines for pattern detection
        # Loop pattern counter (separate from line repeat)
        self.loop_pattern_count = 0

    def _is_empty_row(self, text: str) -> bool:
        # All <td> are empty or whitespace
        tds = re.findall(r"<td>(.*?)</td>", text, flags=re.S)
        if not tds:
            return False
        return all(td.strip() == "" for td in tds)

    def _extract_stt(self, text: str):
        m = re.search(r"<td>\s*(\d+)\s*</td>", text)
        return int(m.group(1)) if m else None

    def _is_signature_keyword(self, text: str) -> bool:
        """Check if text contains signature/footer keywords"""
        keywords = [
            "signature valid",
            "được ký bởi",
            "ký bởi",
            "trang: 1/1",
            "trang 1/1",
            "ngày ký:",
            "tra cứu hóa đơn",
            "khởi tạo từ phần mềm",
            # Added for internal transfer slip loops
            "người lập",
            "thủ kho",
            "người vận chuyển",
            "(ký, ghi rõ họ tên)",
            "ký, ghi rõ họ tên",
        ]
        text_lower = text.lower()
        return any(kw in text_lower for kw in keywords)

    def _is_loop_pattern(self, text: str) -> bool:
        """Check if text matches known loop patterns (table headers repeating)"""
        loop_patterns = [
            # Common loop pattern: table headers repeating after signature
            r"thời gian.*đơn giá.*thành tiền",
            r"đơn giá.*thành tiền",
            # Time stamp loops
            r"thời gian:\s*\d{1,2}/\d{1,2}/\d{4}",
            # Repeating digit artifacts (e.g., 5.8.8.8.8.8...)
            r"(\d\.){10,}",  # 10+ repetitions of "digit." pattern
            # Footer text loops (signature blocks repeating)
            r"trang chủ hóa đơn",
            r"thời gian sử dụng",
            r"tracuuhoadon",
            r"minvoice\.com",
        ]
        text_lower = text.lower().replace("*", "").strip()
        for pattern in loop_patterns:
            if re.search(pattern, text_lower, re.I):
                return True
        return False

    def _calculate_similarity(self, s1: str, s2: str) -> float:
        """Calculate simple character-based similarity ratio"""
        if not s1 or not s2:
            return 0.0
        # Simple approach: count common characters
        s1_set = set(s1.lower())
        s2_set = set(s2.lower())
        common = len(s1_set & s2_set)
        total = len(s1_set | s2_set)
        return common / total if total > 0 else 0.0

    def process(self, text: str):
        force_close = False
        
        # === LOOP PATTERN DETECTION ===
        # Check for known loop patterns immediately
        # Use dedicated counter that doesn't get reset by normal lines
        if self._is_loop_pattern(text):
            self.loop_pattern_count += 1
            # Stop after just 2 matches of footer patterns (they shouldn't repeat at all)
            if self.loop_pattern_count >= 2:
                return "", True
        
        # === SIGNATURE SECTION LIMIT ===
        # If already in signature section, count chars
        if self.in_signature:
            self.chars_after_signature += len(text)
            if self.chars_after_signature >= self.signature_char_limit:
                return text, True  # Stop after signature limit
        
        # Check if entering signature section
        if self._is_signature_keyword(text):
            self.in_signature = True
        
        # === LINE REPETITION DETECTION (Exact + Fuzzy) ===
        # Normalize text for comparison (strip whitespace and markdown)
        normalized = text.strip().replace("*", "").replace("_", "")
        if normalized and len(normalized) > 5:  # Ignore very short lines
            # Exact match
            if normalized == self.last_line:
                self.line_repeat_count += 1
                if self.line_repeat_count >= self.max_line_repetition:
                    return "", True  # Stop and don't include this repeated line
            # Fuzzy match (for OCR noise)
            elif self._calculate_similarity(normalized, self.last_line) > self.similarity_threshold:
                self.line_repeat_count += 1
                if self.line_repeat_count >= self.max_line_repetition:
                    return "", True
            else:
                self.last_line = normalized
                self.line_repeat_count = 0

        # === TABLE-SPECIFIC CHECKS (existing logic) ===
        if "<table" in text:
            self.in_table = True

        if self.in_table:
            if "<tr" in text:
                self.row_count += 1

                # Rule 1: Empty rows
                if self._is_empty_row(text):
                    self.empty_row_streak += 1
                else:
                    self.empty_row_streak = 0

                # Rule 2: STT not increasing
                stt = self._extract_stt(text)
                if stt is not None:
                    if self.last_stt is not None and stt <= self.last_stt:
                        force_close = True
                    self.last_stt = stt

            # HARD STOP CONDITIONS for table
            if (
                self.row_count >= self.max_rows
                or self.empty_row_streak >= self.max_consecutive_empty_rows
            ):
                force_close = True

        if force_close:
            self.reset()

        return text, force_close
