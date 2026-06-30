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
        self.line_buffer = ""
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
        self.line_buffer = ""

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
        self.line_buffer += text
        force_close = False
        
        # If there's a newline, we process the completed lines
        if "\n" in self.line_buffer:
            lines = self.line_buffer.split("\n")
            self.line_buffer = lines[-1]  # Keep incomplete line
            completed_lines = lines[:-1]
            
            for line in completed_lines:
                force_close = self._process_line(line)
                if force_close:
                    break
                    
        if force_close:
            self.reset()
            return "", True
            
        return text, False

    def _process_line(self, line: str) -> bool:
        # === LOOP PATTERN DETECTION ===
        if self._is_loop_pattern(line):
            self.loop_pattern_count += 1
            if self.loop_pattern_count >= 2:
                return True
        
        # === SIGNATURE SECTION LIMIT ===
        if self.in_signature:
            self.chars_after_signature += len(line)
            if self.chars_after_signature >= self.signature_char_limit:
                return True
        
        if self._is_signature_keyword(line):
            self.in_signature = True
        
        # === LINE REPETITION DETECTION ===
        normalized = "".join(c for c in line.strip() if c.isalnum())
        if normalized and len(normalized) > 5:
            # 1. Single line repetition check (with fuzzy similarity fallback)
            if normalized == self.last_line:
                self.line_repeat_count += 1
                if self.line_repeat_count >= self.max_line_repetition:
                    return True
            elif self._calculate_similarity(normalized, self.last_line) > self.similarity_threshold:
                self.line_repeat_count += 1
                if self.line_repeat_count >= self.max_line_repetition:
                    return True
            else:
                self.last_line = normalized
                self.line_repeat_count = 0
            
            # 2. Multi-line pattern loop check (e.g. A B A B A B)
            self.recent_lines.append(normalized)
            if len(self.recent_lines) > 20:
                self.recent_lines.pop(0)
                
            if len(self.recent_lines) >= 6 and self.recent_lines[-2:] == self.recent_lines[-4:-2] == self.recent_lines[-6:-4]:
                return True
            if len(self.recent_lines) >= 9 and self.recent_lines[-3:] == self.recent_lines[-6:-3] == self.recent_lines[-9:-6]:
                return True
            if len(self.recent_lines) >= 12 and self.recent_lines[-4:] == self.recent_lines[-8:-4] == self.recent_lines[-12:-8]:
                return True
                
        # === TABLE-SPECIFIC CHECKS ===
        line_strip = line.strip()
        
        # HTML Table detection
        if "<table" in line_strip:
            self.in_table = True
            
        if self.in_table and "<tr" in line_strip:
            self.row_count += 1
            if self._is_empty_row(line_strip):
                self.empty_row_streak += 1
            else:
                self.empty_row_streak = 0
                
            stt = self._extract_stt(line_strip)
            if stt is not None:
                if self.last_stt is not None and stt <= self.last_stt:
                    return True
                self.last_stt = stt
                
        # Markdown Table detection
        pipe_count = line_strip.count("|")
        if pipe_count >= 3:
            # Exclude separator lines like |---|---|
            if not set(line_strip).issubset({"|", "-", " ", ":", "+"}):
                self.row_count += 1
                
                # Check if empty row
                cells = line_strip.split("|")[1:-1]
                is_empty = all(not any(c.isalpha() for c in cell) for cell in cells)
                if is_empty:
                    self.empty_row_streak += 1
                else:
                    self.empty_row_streak = 0
                    
        # Hard stop conditions
        if (
            self.row_count >= self.max_rows
            or self.empty_row_streak >= self.max_consecutive_empty_rows
        ):
            return True
            
        return False
