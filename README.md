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


