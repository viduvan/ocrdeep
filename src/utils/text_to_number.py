
import re

def text_to_number_vn(text: str) -> float:
    """
    Convert Vietnamese text numbers to float.
    Handles standard format: "Chín nghìn đồng", "Một triệu hai trăm nghìn".
    """
    if not text:
        return 0.0

    text = text.lower().strip()
    # Remove currency words and punctuation
    text = re.sub(r"[^\w\s]", "", text)
    text = text.replace("đồng", "").replace("chẵn", "").replace("vnđ", "").replace("vnd", "").strip()
    
    words = text.split()
    
    digits = {
        "không": 0, "một": 1, "mốt": 1, "hai": 2, "ba": 3, "bốn": 4, "tư": 4, 
        "năm": 5, "lăm": 5, "sáu": 6, "bảy": 7, "tám": 8, "chín": 9, "mười": 10
    }
    
    # Multipliers
    M_TY = 1_000_000_000
    M_TRIEU = 1_000_000
    M_NGHIN = 1_000
    M_TRAM = 100
    M_CHUC = 10     # mươi/chục

    total_value = 0
    current_period = 0 # Accumulates values < 1000 (unit, ten, hundred)
    
    # Logic: 
    # Iterate words. 
    # If digit: add to current_period (handling tens if needed, but simplified: assume sequential)
    # If multiplier (tram, chuc): multiply current_period
    # If period multiplier (nghin, trieu, ty): multiply current_period and add to total, reset current.
    
    # Refined Loop for Stack-like processing
    
    temp_val = 0 # Holds the current small number (e.g. 9 or 23)
    
    for word in words:
        if word in digits:
            v = digits[word]
            if temp_val == 10: # mười hai -> 12
                temp_val += v
            elif temp_val > 0 and temp_val <= 9: # hai ba -> 23 (slang/short) or hai mươi ba?
                 # Assume standard: "hai" then "mươi" then "ba". 
                 # If "hai ba", treat as 23? uncommon. 
                 # Let's just Add for now.
                 temp_val = temp_val * 10 + v
            else:
                temp_val = v
                
        elif word == "mươi" or word == "chục":
            if temp_val == 0: temp_val = 1 # "mươi" alone (rare) -> 10? usually "mười".
            temp_val *= 10
            
        elif word == "lẻ" or word == "linh":
            pass # skip
            
        elif word == "trăm":
            if temp_val == 0: temp_val = 1
            temp_val *= 100
            current_period += temp_val
            temp_val = 0
            
        elif word == "nghìn" or word == "ngàn":
            current_period += temp_val
            total_value += current_period * 1000
            current_period = 0
            temp_val = 0
            
        elif word == "triệu":
            current_period += temp_val
            total_value += current_period * 1_000_000
            current_period = 0
            temp_val = 0
            
        elif word == "tỷ" or word == "tỉ":
            current_period += temp_val
            total_value += current_period * 1_000_000_000
            current_period = 0
            temp_val = 0

    # End of loop: Add remaining parts
    current_period += temp_val
    total_value += current_period
    
    return float(total_value)
