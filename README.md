# DeepSeek-OCR (vLLM + FastAPI + Docker)

Local Vision OCR API sử dụng:

- **DeepSeek-OCR** (Vision model)
- **vLLM** OpenAI-compatible server
- **FastAPI** backend
- **Docker Compose**
- **GPU** (NVIDIA)

**Hỗ trợ:**

- OCR hóa đơn (single / multi-page PDF)
- OCR CCCD (upload file hoặc realtime base64)
- Streaming inference
- Timeout protection
- Zoom-in header pass
- Semantic refinement

---

## Architecture

```
Client
   ↓
FastAPI (Port 8888)
   ↓
vLLM Server (Port 8000)
   ↓
DeepSeek-OCR Model (GPU)
```

**Docker services:**

| Service | Port | Description |
| :--- | :--- | :--- |
| `vllm` | 8000 | Model inference server |
| `api` | 8888 | FastAPI wrapper |

---

## �️ Requirements

- Ubuntu 20.04+
- Docker
- Docker Compose (v2 recommended)
- NVIDIA Driver
- NVIDIA Container Toolkit
- GPU (>= 16GB VRAM recommended)

---

##  Setup

### 1️Clone project

```bash
git clone <your-repo>
cd <project-folder>
```

### 2️ Build images

 **Recommended:**
```bash
docker compose build
```

**Clean rebuild:**
```bash
docker compose build --no-cache
```

### 3️Run services

```bash
docker compose up -d
```

Hoặc build + run luôn:
```bash
docker compose up -d --build
```

---

## Verify

**Check containers:**
```bash
docker ps
```

**Check vLLM model:**
```bash
curl http://localhost:8000/v1/models
```

**Check API health:**
```bash
curl http://localhost:8888/health
```

**Swagger UI:**
```
http://<server-ip>:8888/docs
```

---

##  Project Structure

| File | Description |
| :--- | :--- |
| `Dockerfile.vllm-model` | Build vLLM image + pre-download model vào `/opt/models` |
| `Dockerfile` | Build API image (Python 3.11 + FastAPI) |
| `docker-compose.yml` | Orchestrate cả 2 services |
| `build_images.sh` | Script build nhanh cả 2 images |
| `.dockerignore` | Loại bỏ file không cần thiết khi build |

---

## Configuration

Các thông số chính trong `docker-compose.yml`:

| Setting | Value | Description |
| :--- | :--- | :--- |
| `gpu-memory-utilization` | `0.9` | Sử dụng 90% VRAM cho model + KV cache |
| `max-model-len` | `8192` | Context window (tối đa token/request) |
| `dtype` | `auto` | Tự động chọn FP16/BF16 theo GPU |
| `VLLM_HOST` | `http://vllm:8000/v1` | API kết nối tới vLLM qua Docker network |
| `VLLM_MODEL` | `deepseek-ai/DeepSeek-OCR` | Model name cho API client |

---

##  Logs

**Xem log realtime:**
```bash
docker compose logs -f vllm
docker compose logs -f api
```

**Xem log gần nhất:**
```bash
docker compose logs --tail=50 vllm
```

**Dừng tất cả:**
```bash
docker compose down
```

---

##  Troubleshooting

| Lỗi | Nguyên nhân | Cách fix |
| :--- | :--- | :--- |
| `Exit Code 137` | Out of Memory (VRAM/RAM) | Giảm `gpu-memory-utilization` (0.8 → 0.7) |
| `API Unhealthy` | vLLM chưa sẵn sàng khi API start | `docker compose restart api` |
| `Network unreachable` khi build | Không có internet | Cần internet khi build lần đầu (tải model) |
| `CUDA error` | GPU driver không tương thích | Cài NVIDIA Container Toolkit |

---



