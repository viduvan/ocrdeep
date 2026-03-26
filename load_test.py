#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║              OCR API - LOAD / STRESS TEST TOOL                  ║
║         Kiểm tra sức chịu đựng API OCR trên GPU A30            ║
╚══════════════════════════════════════════════════════════════════╝

Sử dụng:
  # Test cơ bản: 5 request đồng thời
  python load_test.py

  # Test 10 request đồng thời với file ảnh cụ thể
  python load_test.py --concurrent 10 --image path/to/invoice.png

  # Test tăng dần từ 1 đến 200 request (tìm giới hạn thực sự)
  python load_test.py --ramp-up --max-concurrent 200

  # Tìm giới hạn với ngưỡng response time tối đa 30 giây
  python load_test.py --ramp-up --max-concurrent 200 --max-response-time 30

  # Test với endpoint khác
  python load_test.py --endpoint /ocr-bol --concurrent 5

  # Test dài hạn (stress test 60 giây)
  python load_test.py --duration 60 --concurrent 10
"""

import argparse
import asyncio
import io
import os
import sys
import time
import statistics
from dataclasses import dataclass, field
from typing import List, Optional

try:
    import aiohttp
except ImportError:
    print("❌ Cần cài đặt aiohttp: pip install aiohttp")
    sys.exit(1)

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("❌ Cần cài đặt Pillow: pip install Pillow")
    sys.exit(1)


# ─── Configuration ────────────────────────────────────────────────
BASE_URL = "http://172.16.2.187:8888"
DEFAULT_ENDPOINT = "/ocr-invoice"
DEFAULT_CONCURRENT = 5
DEFAULT_TIMEOUT = 120  # seconds per request


# ─── Data Classes ─────────────────────────────────────────────────

@dataclass
class RequestResult:
    """Kết quả của một request."""
    request_id: int
    status_code: int
    duration_sec: float
    success: bool
    error: str = ""
    ocr_duration_sec: float = 0.0  # Thời gian OCR từ response


@dataclass
class TestReport:
    """Báo cáo tổng hợp của một lần test."""
    concurrency: int
    total_requests: int
    results: List[RequestResult] = field(default_factory=list)
    wall_time_sec: float = 0.0

    @property
    def successful(self) -> int:
        return sum(1 for r in self.results if r.success)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if not r.success)

    @property
    def durations(self) -> List[float]:
        return [r.duration_sec for r in self.results if r.success]

    @property
    def avg_duration(self) -> float:
        d = self.durations
        return statistics.mean(d) if d else 0

    @property
    def median_duration(self) -> float:
        d = self.durations
        return statistics.median(d) if d else 0

    @property
    def min_duration(self) -> float:
        d = self.durations
        return min(d) if d else 0

    @property
    def max_duration(self) -> float:
        d = self.durations
        return max(d) if d else 0

    @property
    def p95_duration(self) -> float:
        d = sorted(self.durations)
        if not d:
            return 0
        idx = int(len(d) * 0.95)
        return d[min(idx, len(d) - 1)]

    @property
    def throughput(self) -> float:
        """Requests per second (dựa trên wall time)."""
        return self.successful / self.wall_time_sec if self.wall_time_sec > 0 else 0


# ─── Test Image Generator ────────────────────────────────────────

def generate_test_invoice_image() -> bytes:
    """Tạo ảnh hóa đơn giả lập để test (không cần file thật)."""
    img = Image.new("RGB", (800, 1100), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    # Try to use a decent font, fallback to default
    try:
        font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
        font_medium = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
    except (IOError, OSError):
        font_large = ImageFont.load_default()
        font_medium = font_large
        font_small = font_large

    # Header
    draw.text((200, 30), "HOA DON GIA TRI GIA TANG", fill=(0, 0, 0), font=font_large)
    draw.text((250, 60), "(VAT INVOICE)", fill=(100, 100, 100), font=font_medium)

    # Invoice info
    y = 100
    lines = [
        "Mau so (Form):      01GTKT0/001",
        "Ky hieu (Serial):   AA/24E",
        "So (No.):           0001234",
        "",
        "Ngay 15 thang 03 nam 2026",
        "",
        "Don vi ban hang (Seller):",
        "  Cong ty TNHH ABC Technology",
        "  MST: 0123456789",
        "  Dia chi: 123 Nguyen Hue, Q.1, TP.HCM",
        "",
        "Don vi mua hang (Buyer):",
        "  Cong ty CP XYZ Solutions",
        "  MST: 9876543210",
        "  Dia chi: 456 Le Loi, Q.3, TP.HCM",
        "",
        "─" * 60,
        "STT | Ten hang hoa        | DVT  | SL | Don gia    | Thanh tien",
        "─" * 60,
        " 1  | Dich vu phan mem     | Goi  | 1  | 50,000,000 | 50,000,000",
        " 2  | Bao tri he thong     | Thang| 12 |  5,000,000 | 60,000,000",
        " 3  | Hosting server       | Nam  | 1  | 10,000,000 | 10,000,000",
        "─" * 60,
        "",
        "Cong tien hang:           120,000,000 VND",
        "Thue GTGT (10%):           12,000,000 VND",
        "Tong cong:                132,000,000 VND",
        "",
        "So tien bang chu: Mot tram ba muoi hai trieu dong.",
    ]

    for line in lines:
        draw.text((40, y), line, fill=(0, 0, 0), font=font_small)
        y += 20

    # Convert to bytes
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


def load_test_image(image_path: Optional[str]) -> bytes:
    """Load ảnh test từ file hoặc tạo ảnh giả lập."""
    if image_path and os.path.exists(image_path):
        with open(image_path, "rb") as f:
            return f.read()
    else:
        if image_path:
            print(f"⚠️  File '{image_path}' không tồn tại, sử dụng ảnh giả lập.")
        return generate_test_invoice_image()


# ─── Core Test Functions ──────────────────────────────────────────

async def send_single_request(
    session: aiohttp.ClientSession,
    request_id: int,
    url: str,
    image_bytes: bytes,
    filename: str = "test_invoice.png",
    timeout_sec: int = DEFAULT_TIMEOUT,
    semantic: bool = False,
) -> RequestResult:
    """Gửi 1 request OCR và trả về kết quả."""
    start = time.time()
    try:
        form = aiohttp.FormData()
        form.add_field(
            "file",
            image_bytes,
            filename=filename,
            content_type="image/png",
        )
        form.add_field("semantic", str(semantic).lower())

        timeout = aiohttp.ClientTimeout(total=timeout_sec)
        async with session.post(url, data=form, timeout=timeout) as resp:
            duration = time.time() - start
            body = await resp.json()

            ocr_dur = 0.0
            if isinstance(body, dict):
                ocr_dur = body.get("duration_sec", 0.0)

            success = resp.status == 200 and body.get("data") is not None
            error = ""
            if not success:
                error = body.get("error", body.get("detail", f"HTTP {resp.status}"))
                if isinstance(error, list):
                    error = str(error[0]) if error else "Unknown"

            return RequestResult(
                request_id=request_id,
                status_code=resp.status,
                duration_sec=round(duration, 3),
                success=success,
                error=str(error)[:200] if error else "",
                ocr_duration_sec=ocr_dur,
            )

    except asyncio.TimeoutError:
        return RequestResult(
            request_id=request_id,
            status_code=0,
            duration_sec=round(time.time() - start, 3),
            success=False,
            error=f"Timeout after {timeout_sec}s",
        )
    except aiohttp.ClientError as e:
        return RequestResult(
            request_id=request_id,
            status_code=0,
            duration_sec=round(time.time() - start, 3),
            success=False,
            error=f"Connection error: {e}",
        )
    except Exception as e:
        return RequestResult(
            request_id=request_id,
            status_code=0,
            duration_sec=round(time.time() - start, 3),
            success=False,
            error=f"Unexpected: {e}",
        )


async def run_concurrent_test(
    concurrency: int,
    image_bytes: bytes,
    endpoint: str = DEFAULT_ENDPOINT,
    timeout_sec: int = DEFAULT_TIMEOUT,
    semantic: bool = False,
) -> TestReport:
    """Gửi N request đồng thời và thu thập kết quả."""
    url = f"{BASE_URL}{endpoint}"
    report = TestReport(concurrency=concurrency, total_requests=concurrency)

    print(f"\n🚀 Gửi {concurrency} request đồng thời đến {endpoint}...")

    connector = aiohttp.TCPConnector(limit=concurrency + 5, force_close=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        wall_start = time.time()
        tasks = [
            send_single_request(session, i + 1, url, image_bytes, timeout_sec=timeout_sec, semantic=semantic)
            for i in range(concurrency)
        ]
        report.results = await asyncio.gather(*tasks)
        report.wall_time_sec = round(time.time() - wall_start, 3)

    return report


async def run_duration_test(
    concurrency: int,
    duration_sec: int,
    image_bytes: bytes,
    endpoint: str = DEFAULT_ENDPOINT,
    timeout_sec: int = DEFAULT_TIMEOUT,
    semantic: bool = False,
) -> TestReport:
    """Gửi request liên tục trong khoảng thời gian nhất định."""
    url = f"{BASE_URL}{endpoint}"
    report = TestReport(concurrency=concurrency, total_requests=0)

    print(f"\n🔥 Stress test: {concurrency} worker(s) liên tục trong {duration_sec}s...")

    connector = aiohttp.TCPConnector(limit=concurrency + 5, force_close=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        wall_start = time.time()
        request_counter = 0
        active_tasks = set()

        async def worker(worker_id: int):
            nonlocal request_counter
            while time.time() - wall_start < duration_sec:
                request_counter += 1
                req_id = request_counter
                result = await send_single_request(
                    session, req_id, url, image_bytes,
                    timeout_sec=timeout_sec, semantic=semantic,
                )
                report.results.append(result)

                # Print progress
                elapsed = time.time() - wall_start
                status = "✅" if result.success else "❌"
                print(
                    f"  {status} Worker {worker_id} | Req #{req_id:>4d} | "
                    f"{result.duration_sec:>6.1f}s | "
                    f"Elapsed: {elapsed:>5.1f}s / {duration_sec}s"
                )

        tasks = [asyncio.create_task(worker(i + 1)) for i in range(concurrency)]
        await asyncio.gather(*tasks)

        report.wall_time_sec = round(time.time() - wall_start, 3)
        report.total_requests = len(report.results)

    return report


async def run_ramp_up_test(
    max_concurrent: int,
    image_bytes: bytes,
    endpoint: str = DEFAULT_ENDPOINT,
    timeout_sec: int = DEFAULT_TIMEOUT,
    semantic: bool = False,
    max_response_time: float = 0,
) -> List[TestReport]:
    """Test tăng dần số request đồng thời để tìm giới hạn."""
    reports = []

    # Build ramp levels: denser at low end, sparser at high end
    levels = set()
    # Low end: 1-10 step 1
    for i in range(1, min(11, max_concurrent + 1)):
        levels.add(i)
    # Mid: 10-50 step 5
    for i in range(10, min(51, max_concurrent + 1), 5):
        levels.add(i)
    # High: 50-200 step 10
    for i in range(50, min(201, max_concurrent + 1), 10):
        levels.add(i)
    # Very high: 200+ step 25
    for i in range(200, max_concurrent + 1, 25):
        levels.add(i)
    levels.add(max_concurrent)
    levels = sorted(levels)

    print(f"\n📈 Ramp-up test: tăng dần từ 1 → {max_concurrent} request đồng thời")
    if max_response_time > 0:
        print(f"   Ngưỡng response time tối đa (P95): {max_response_time}s")
    print(f"   Các mức test: {levels}")

    for level in levels:
        report = await run_concurrent_test(
            level, image_bytes, endpoint, timeout_sec, semantic=semantic
        )
        reports.append(report)
        print_report(report)

        # Dừng nếu có quá nhiều lỗi
        if report.total_requests > 0 and report.failed / report.total_requests > 0.5:
            print(f"\n⛔ Dừng ramp-up: Tỉ lệ lỗi > 50% tại mức {level} concurrent")
            break

        # Dừng nếu P95 response time vượt ngưỡng cho phép
        if max_response_time > 0 and report.p95_duration > max_response_time:
            print(f"\n⛔ Dừng ramp-up: P95 response time ({report.p95_duration:.1f}s) "
                  f"> ngưỡng {max_response_time}s tại mức {level} concurrent")
            break

        # Dừng nếu có request timeout (= hạ tầng quá tải thực sự)
        if any(r.error.startswith("Timeout") for r in report.results):
            print(f"\n⛔ Dừng ramp-up: Có request bị timeout tại mức {level} concurrent")
            break

        # Nghỉ giữa các mức để GPU hồi phục
        if level < levels[-1]:
            wait_time = 3 if level < 20 else 5
            print(f"   ⏳ Đợi {wait_time}s cho GPU hồi phục...")
            await asyncio.sleep(wait_time)

    return reports


# ─── Report Printing ──────────────────────────────────────────────

def print_report(report: TestReport):
    """In báo cáo kết quả test."""
    print()
    print("═" * 66)
    print(f"   KẾT QUẢ TEST - {report.concurrency} REQUEST ĐỒNG THỜI")
    print("═" * 66)
    print(f"  Tổng request:        {report.total_requests}")
    print(f"  Thành công:          {report.successful}")
    print(f"  Thất bại:            {report.failed}")
    print(f"  Thời gian thực tế:   {report.wall_time_sec:.1f}s")
    print(f"  Throughput:          {report.throughput:.2f} req/s")

    if report.durations:
        print(f"  ─────────────────────────────────")
        print(f"  Response time (thành công):")
        print(f"    Min:               {report.min_duration:.1f}s")
        print(f"    Max:               {report.max_duration:.1f}s")
        print(f"    Trung bình:        {report.avg_duration:.1f}s")
        print(f"    Median (P50):      {report.median_duration:.1f}s")
        print(f"    P95:               {report.p95_duration:.1f}s")

    if report.failed > 0:
        print(f"  ─────────────────────────────────")
        print(f"  Lỗi chi tiết:")
        errors = [r for r in report.results if not r.success]
        for r in errors[:10]:  # Show max 10
            print(f"    Req #{r.request_id}: {r.error}")
        if len(errors) > 10:
            print(f"    ... và {len(errors) - 10} lỗi khác")

    print("═" * 66)


def print_ramp_summary(reports: List[TestReport]):
    """In bảng tổng hợp ramp-up test."""
    print()
    print("╔" + "═" * 78 + "╗")
    print("║" + "  📈 TỔNG HỢP RAMP-UP TEST".ljust(78) + "║")
    print("╠" + "═" * 78 + "╣")
    print("║ {:>5s} │ {:>4s}/{:>4s} │ {:>7s} │ {:>7s} │ {:>7s} │ {:>7s} │ {:>8s} ║".format(
        "Conc", "OK", "Fail", "Avg(s)", "P50(s)", "P95(s)", "Wall(s)", "Thru/s"
    ))
    print("╠" + "═" * 78 + "╣")
    for r in reports:
        print("║ {:>5d} │ {:>4d}/{:>4d} │ {:>7.1f} │ {:>7.1f} │ {:>7.1f} │ {:>7.1f} │ {:>8.2f} ║".format(
            r.concurrency,
            r.successful, r.failed,
            r.avg_duration,
            r.median_duration,
            r.p95_duration,
            r.wall_time_sec,
            r.throughput,
        ))
    print("╚" + "═" * 78 + "╝")

    # Recommendation
    best = max(reports, key=lambda r: r.throughput)
    print(f"\n  💡 Throughput cao nhất: {best.throughput:.2f} req/s tại mức {best.concurrency} concurrent")

    # Single-request baseline
    baseline = reports[0].avg_duration if reports else 1.0
    print(f"  📏 Baseline (1 request): {baseline:.1f}s")

    # Find limits based on response time thresholds
    print(f"\n  ─── GIỚI HẠN THEO NGƯỠNG RESPONSE TIME ───")
    thresholds = [5, 10, 15, 20, 30, 45, 60, 90, 120]
    for t in thresholds:
        # Find the highest concurrency where P95 <= threshold
        matching = [r for r in reports if r.p95_duration <= t and r.successful > 0]
        if matching:
            best_at_t = max(matching, key=lambda r: r.concurrency)
            print(f"  P95 <= {t:>3d}s  →  tối đa {best_at_t.concurrency:>4d} concurrent")

    # Find error/timeout point
    print(f"\n  ─── PHÂN TÍCH GIỚI HẠN ───")
    for i, r in enumerate(reports):
        if r.failed > 0:
            print(f"  ⚠️  Bắt đầu có lỗi tại mức {r.concurrency} concurrent ({r.failed} lỗi)")
            if i > 0:
                prev = reports[i - 1]
                print(f"  ✅ Giới hạn an toàn (0% lỗi): {prev.concurrency} concurrent")
            break
    else:
        last = reports[-1]
        print(f"  ✅ Không có lỗi! Chịu được tối thiểu {last.concurrency} concurrent")

    # Throughput degradation analysis
    if len(reports) >= 3:
        throughputs = [(r.concurrency, r.throughput) for r in reports if r.successful > 0]
        peak_thru = max(throughputs, key=lambda x: x[1])
        # Find where throughput drops > 20% from peak
        for conc, thru in throughputs:
            if conc > peak_thru[0] and thru < peak_thru[1] * 0.8:
                print(f"  📉 Throughput giảm >20% tại mức {conc} concurrent "
                      f"({thru:.2f} vs peak {peak_thru[1]:.2f} req/s)")
                break


# ─── Main ─────────────────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser(
        description="🔧 OCR API Load Test Tool - Kiểm tra sức chịu đựng API OCR",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ví dụ sử dụng:
  python load_test.py                              # Test cơ bản 5 request
  python load_test.py --concurrent 10              # 10 request đồng thời
  python load_test.py --image invoice.png -c 8     # Dùng file ảnh thật
  python load_test.py --ramp-up --max-concurrent 20  # Tìm giới hạn
  python load_test.py --duration 60 -c 5           # Stress test 60 giây
  python load_test.py --endpoint /ocr-bol -c 3     # Test endpoint B/L
  python load_test.py --url http://10.0.0.1:8888   # Đổi URL server
        """
    )

    parser.add_argument(
        "-c", "--concurrent",
        type=int, default=DEFAULT_CONCURRENT,
        help=f"Số request đồng thời (default: {DEFAULT_CONCURRENT})"
    )
    parser.add_argument(
        "--image",
        type=str, default=None,
        help="Đường dẫn file ảnh/PDF để test (mặc định: tạo ảnh giả lập)"
    )
    parser.add_argument(
        "--endpoint",
        type=str, default=DEFAULT_ENDPOINT,
        choices=["/ocr-invoice", "/ocr-bol", "/ocr-cccd"],
        help=f"Endpoint API để test (default: {DEFAULT_ENDPOINT})"
    )
    parser.add_argument(
        "--ramp-up",
        action="store_true",
        help="Test tăng dần số request để tìm giới hạn"
    )
    parser.add_argument(
        "--max-concurrent",
        type=int, default=200,
        help="Số request tối đa cho ramp-up test (default: 200)"
    )
    parser.add_argument(
        "--max-response-time",
        type=float, default=0,
        help="Ngưỡng P95 response time tối đa (giây). Ramp-up dừng khi vượt ngưỡng. 0 = không giới hạn (default: 0)"
    )
    parser.add_argument(
        "--duration",
        type=int, default=0,
        help="Thời gian stress test (giây). 0 = chỉ test 1 batch (default: 0)"
    )
    parser.add_argument(
        "--timeout",
        type=int, default=DEFAULT_TIMEOUT,
        help=f"Timeout mỗi request (giây) (default: {DEFAULT_TIMEOUT})"
    )
    parser.add_argument(
        "--semantic",
        action="store_true",
        help="Bật semantic refine (tốn GPU hơn, default: tắt)"
    )
    parser.add_argument(
        "--url",
        type=str, default=None,
        help="Override URL gốc (ví dụ: http://10.0.0.1:8888)"
    )

    args = parser.parse_args()

    # Override base URL nếu được chỉ định
    global BASE_URL
    if args.url:
        BASE_URL = args.url.rstrip("/")

    # Banner
    print()
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║           🔧 OCR API LOAD TEST TOOL                        ║")
    print("║           GPU: NVIDIA A30 24GB VRAM                         ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print(f"  Server:    {BASE_URL}")
    print(f"  Endpoint:  {args.endpoint}")
    print(f"  Timeout:   {args.timeout}s per request")
    print(f"  Semantic:  {'ON' if args.semantic else 'OFF'}")

    # Load/generate test image
    image_bytes = load_test_image(args.image)
    img_size_kb = len(image_bytes) / 1024
    print(f"  Test file: {args.image or 'Generated invoice image'} ({img_size_kb:.0f} KB)")

    # Quick health check
    print(f"\n🏥 Kiểm tra kết nối đến {BASE_URL}...")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{BASE_URL}/docs", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    print(f"  ✅ Server sẵn sàng!")
                else:
                    print(f"  ⚠️  Server trả về HTTP {resp.status}")
    except Exception as e:
        print(f"  ❌ Không thể kết nối: {e}")
        print(f"  Vui lòng kiểm tra server đang chạy tại {BASE_URL}")
        return

    # Run appropriate test mode
    if args.ramp_up:
        reports = await run_ramp_up_test(
            args.max_concurrent, image_bytes,
            endpoint=args.endpoint,
            timeout_sec=args.timeout,
            semantic=args.semantic,
            max_response_time=args.max_response_time,
        )
        print_ramp_summary(reports)

    elif args.duration > 0:
        report = await run_duration_test(
            args.concurrent, args.duration, image_bytes,
            endpoint=args.endpoint,
            timeout_sec=args.timeout,
            semantic=args.semantic,
        )
        print_report(report)

    else:
        report = await run_concurrent_test(
            args.concurrent, image_bytes,
            endpoint=args.endpoint,
            timeout_sec=args.timeout,
            semantic=args.semantic,
        )
        print_report(report)

    print("\n🏁 Test hoàn tất!\n")


if __name__ == "__main__":
    asyncio.run(main())
