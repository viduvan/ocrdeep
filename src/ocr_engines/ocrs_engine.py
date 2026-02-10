# src/ocr_engines/ocrs_engine.py 
"""
OCRS CLI Wrapper - Engine 2 for header fallback.
Calls OCRS (Rust-based OCR) via subprocess.
"""

import subprocess
import json
from pathlib import Path
from typing import Optional, Dict, Any, List


class OcrsEngine:
    """Wrapper for OCRS CLI (Rust-based OCR)."""
    
    def __init__(
        self, 
        ocrs_path: str = "ocrs",
        detect_model_path: Optional[str] = None,
        rec_model_path: Optional[str] = None,
    ):
        """
        Initialize OCRS engine.
        
        Args:
            ocrs_path: Path to ocrs executable. Defaults to 'ocrs'.
            detect_model_path: Path to detection model (.rten).
            rec_model_path: Path to recognition model (.rten).
        """
        self.ocrs_path = ocrs_path
        self.detect_model_path = detect_model_path
        self.rec_model_path = rec_model_path
    
    def run_ocr(self, image_path: str, timeout: int = 30) -> Dict[str, Any]:
        """
        Run OCRS CLI and return JSON output.
        """
        image_path = str(Path(image_path).resolve())
        
        # Build command
        cmd = [self.ocrs_path, image_path, "--json"]
        
        if self.detect_model_path:
            cmd.extend(["--detect-model", str(self.detect_model_path)])
            
        if self.rec_model_path:
            cmd.extend(["--rec-model", str(self.rec_model_path)])
        
        try:
            # Run from the directory of the executable to ensure local assets/configs are found
            cwd = Path(self.ocrs_path).parent
            
            result = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding="utf-8",
            )
            
            if result.returncode != 0:
                raise RuntimeError(f"OCRS failed (code {result.returncode}): {result.stderr}")
            
            return json.loads(result.stdout)
            
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"OCRS timed out after {timeout}s")
        except json.JSONDecodeError as e:
            raise RuntimeError(f"OCRS returned invalid JSON: {e}")
    
    def get_raw_text(self, image_path: str) -> str:
        """
        Run OCRS and return plain text (lines joined).
        
        Args:
            image_path: Path to input image.
            
        Returns:
            OCR text as single string with newlines.
        """
        data = self.run_ocr(image_path)
        
        lines: List[str] = []
        for para in data.get("paragraphs", []):
            for line in para.get("lines", []):
                text = line.get("text", "").strip()
                if text:
                    lines.append(text)
        
        return "\n".join(lines)
    
    def get_lines_with_positions(self, image_path: str) -> List[Dict[str, Any]]:
        """
        Run OCRS and return lines with bounding box positions.
        
        Args:
            image_path: Path to input image.
            
        Returns:
            List of dicts with 'text' and 'vertices'.
        """
        data = self.run_ocr(image_path)
        
        result: List[Dict[str, Any]] = []
        for para in data.get("paragraphs", []):
            for line in para.get("lines", []):
                result.append({
                    "text": line.get("text", ""),
                    "vertices": line.get("vertices", []),
                    "words": line.get("words", []),
                })
        
        return result
    
    def is_available(self) -> bool:
        """Check if OCRS CLI is available."""
        try:
            result = subprocess.run(
                [self.ocrs_path, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except Exception:
            return False
