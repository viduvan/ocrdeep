"""
Test parser với các sample từ plain_invoices.txt
Chia thành 2 batch để dễ debug:
- Batch 1: Sample 2-51 (50 samples đầu tiên)
- Batch 2: Sample 52-100 (49 samples cuối)

Các trường quan trọng không được thiếu:
- invoiceID, currency, invoiceDate, invoiceFormNo
- sellerName, sellerTaxCode
- buyerName, buyerTaxCode  
- totalAmount
"""
import re
import json
from src.parsers.block_invoice_parser import parse_invoice_block_based

# Các trường quan trọng không được thiếu
CRITICAL_FIELDS = [
    "invoiceID", "currency", "invoiceDate", "invoiceFormNo",
    "sellerName", "sellerTaxCode", 
    "buyerName", "buyerTaxCode",
    "totalAmount"
]

def load_samples_from_file(filename: str) -> list:
    """Load samples từ file plain_invoices.txt"""
    samples = []
    
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Split by sample separator
    pattern = r'={80}\r?\n=== SAMPLE (\d+) - ([^=]+) ===\r?\n={80}\r?\n'
    parts = re.split(pattern, content)
    
    # parts[0] là phần trước sample đầu tiên (có thể rỗng)
    # Sau đó: parts[1]=sample_num, parts[2]=sample_name, parts[3]=raw_text, ...
    
    i = 1
    while i + 2 < len(parts):
        sample_num = int(parts[i])
        sample_name = parts[i + 1].strip()
        raw_text = parts[i + 2].strip()
        
        # Remove leading/trailing quotes if present
        if raw_text.startswith('"') and raw_text.endswith('",'):
            raw_text = raw_text[1:-2]
        elif raw_text.startswith('"') and raw_text.endswith('"'):
            raw_text = raw_text[1:-1]
        elif raw_text.startswith(' "'):  # Some samples have leading space and quote
            raw_text = raw_text.strip()
            if raw_text.startswith('"'):
                raw_text = raw_text[1:]
            if raw_text.endswith('",') or raw_text.endswith('"'):
                raw_text = raw_text.rstrip(',').rstrip('"')
        
        samples.append({
            'num': sample_num,
            'name': sample_name,
            'raw_text': raw_text
        })
        
        i += 3
    
    return samples


def check_critical_fields(invoice_dict: dict) -> dict:
    """Kiểm tra các trường quan trọng"""
    missing = []
    present = []
    
    for field in CRITICAL_FIELDS:
        value = invoice_dict.get(field)
        if value is None or value == "" or value == []:
            missing.append(field)
        else:
            present.append(field)
    
    return {
        'missing': missing,
        'present': present,
        'score': len(present) / len(CRITICAL_FIELDS) * 100
    }


def test_batch(samples: list, batch_name: str):
    """Test một batch samples"""
    print("=" * 80)
    print(f"BATCH: {batch_name} ({len(samples)} samples)")
    print("=" * 80)
    
    results = {
        'success': 0,  # Score >= 80%
        'partial': 0,  # Score 50-79%
        'failed': 0,   # Score < 50%
        'error': 0,    # Exception
        'details': []
    }
    
    for sample in samples:
        try:
            invoice = parse_invoice_block_based(sample['raw_text'])
            invoice_dict = invoice.model_dump(exclude_none=True)
            
            check = check_critical_fields(invoice_dict)
            score = check['score']
            
            if score >= 80:
                status = "✅"
                results['success'] += 1
            elif score >= 50:
                status = "⚠️"
                results['partial'] += 1
            else:
                status = "❌"
                results['failed'] += 1
            
            # Short info
            seller = invoice_dict.get('sellerName', '')[:25] if invoice_dict.get('sellerName') else 'N/A'
            buyer = invoice_dict.get('buyerName', '')[:25] if invoice_dict.get('buyerName') else 'N/A'
            items = len(invoice_dict.get('itemList', []))
            missing_str = ', '.join(check['missing'][:3]) if check['missing'] else '-'
            
            print(f"{status} #{sample['num']:3} [{score:5.1f}%] Seller={seller:25} | Missing: {missing_str}")
            
            results['details'].append({
                'num': sample['num'],
                'name': sample['name'],
                'status': status,
                'score': score,
                'missing': check['missing'],
                'invoice': invoice_dict
            })
            
        except Exception as e:
            print(f"❌ #{sample['num']:3} ERROR: {str(e)[:60]}")
            results['error'] += 1
            results['details'].append({
                'num': sample['num'],
                'name': sample['name'],
                'status': '💥',
                'error': str(e)
            })
    
    # Summary
    total = len(samples)
    print("\n" + "-" * 80)
    print(f"SUMMARY: ✅ Success={results['success']} | ⚠️ Partial={results['partial']} | ❌ Failed={results['failed']} | 💥 Error={results['error']}")
    print(f"         Success Rate: {results['success']/total*100:.1f}% | Pass Rate (>50%): {(results['success']+results['partial'])/total*100:.1f}%")
    print("-" * 80)
    
    return results


def test_batch_1():
    """Test batch 1: Sample 2-51"""
    samples = load_samples_from_file('plain_invoices.txt')
    batch_1 = [s for s in samples if s['num'] <= 51]
    return test_batch(batch_1, "Batch 1 (Samples 2-51)")


def test_batch_2():
    """Test batch 2: Sample 52-100"""
    samples = load_samples_from_file('plain_invoices.txt')
    batch_2 = [s for s in samples if s['num'] > 51]
    return test_batch(batch_2, "Batch 2 (Samples 52-100)")


def test_single_sample(sample_num: int, verbose: bool = True):
    """Test một sample cụ thể với output chi tiết"""
    samples = load_samples_from_file('plain_invoices.txt')
    sample = next((s for s in samples if s['num'] == sample_num), None)
    
    if not sample:
        print(f"Sample {sample_num} not found!")
        return None
    
    print(f"\n{'='*80}")
    print(f"SAMPLE {sample_num}: {sample['name']}")
    print(f"{'='*80}")
    
    if verbose:
        print("\n--- RAW TEXT (first 1000 chars) ---")
        print(sample['raw_text'][:1000])
        print("\n...")
    
    try:
        invoice = parse_invoice_block_based(sample['raw_text'])
        invoice_dict = invoice.model_dump(exclude_none=True)
        
        print("\n--- PARSED RESULT ---")
        print(json.dumps(invoice_dict, indent=2, default=str, ensure_ascii=False))
        
        check = check_critical_fields(invoice_dict)
        print(f"\n--- CRITICAL FIELDS CHECK (Score: {check['score']:.1f}%) ---")
        print(f"Present: {check['present']}")
        print(f"Missing: {check['missing']}")
        
        return invoice_dict
        
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return None


def find_problem_samples():
    """Tìm các sample có vấn đề để debug"""
    samples = load_samples_from_file('plain_invoices.txt')
    
    problems = []
    for sample in samples:
        try:
            invoice = parse_invoice_block_based(sample['raw_text'])
            invoice_dict = invoice.model_dump(exclude_none=True)
            check = check_critical_fields(invoice_dict)
            
            if check['score'] < 70:
                problems.append({
                    'num': sample['num'],
                    'name': sample['name'],
                    'score': check['score'],
                    'missing': check['missing']
                })
        except Exception as e:
            problems.append({
                'num': sample['num'],
                'name': sample['name'],
                'score': 0,
                'error': str(e)
            })
    
    # Sort by score
    problems.sort(key=lambda x: x.get('score', 0))
    
    print("\n=== PROBLEM SAMPLES (Score < 70%) ===")
    for p in problems:
        if 'error' in p:
            print(f"#{p['num']:3} [{p['name'][:30]:30}] - ERROR: {p['error'][:40]}")
        else:
            print(f"#{p['num']:3} [{p['name'][:30]:30}] - Score: {p['score']:.1f}% - Missing: {p['missing']}")
    
    return problems


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg == "1" or arg == "batch1":
            test_batch_1()
        elif arg == "2" or arg == "batch2":
            test_batch_2()
        elif arg == "problems":
            find_problem_samples()
        elif arg.isdigit():
            test_single_sample(int(arg))
        else:
            print("Usage:")
            print("  python test_plain_invoices.py 1       # Test batch 1")
            print("  python test_plain_invoices.py 2       # Test batch 2")
            print("  python test_plain_invoices.py <num>   # Test single sample")
            print("  python test_plain_invoices.py problems # Find problem samples")
    else:
        # Default: test batch 1
        print("Testing Batch 1 (default)...")
        print("Use 'python test_plain_invoices.py 2' for batch 2")
        print("Use 'python test_plain_invoices.py <num>' for single sample")
        print()
        test_batch_1()
