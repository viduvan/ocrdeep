with open("src/utils/table_guard.py", "r") as f:
    content = f.read()

target = """        # === LINE REPETITION DETECTION ===
        normalized = line.strip().replace("*", "").replace("_", "")
        if normalized and len(normalized) > 5:
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
                self.line_repeat_count = 0"""

replacement = """        # === LINE REPETITION DETECTION ===
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
                return True"""

new_content = content.replace(target, replacement)
if new_content != content:
    with open("src/utils/table_guard.py", "w") as f:
        f.write(new_content)
    print("Patched successfully.")
else:
    print("Patch failed. Target not found.")
