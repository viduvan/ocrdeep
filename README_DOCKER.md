# 🐳 Docker Deployment Guide (NVIDIA A30 Optimized)

## 🏗 Architecture: Split Images (Offline Ready)
This project uses a **Split Images** architecture designed for production stability and speed:

1.  **`ocr-vllm-model:latest`**:
    *   Contains **vLLM Engine** AND **DeepSeek-OCR Model** (Pre-downloaded).
    *   **Size**: ~15GB+.
    *   **Benefit**: Zero runtime download. Starts immediately. Runs offline.
2.  **`ocr-api:latest`**:
    *   Contains **FastAPI** source code.
    *   **Size**: Lightweight.

---

## 💻 Hardware Requirements
*   **GPU**: NVIDIA GPU with **≥16GB VRAM** (Optimized for **NVIDIA A30 24GB**).
*   **Driver**: NVIDIA Driver ≥ 535.
*   **Docker**: Docker Engine + **NVIDIA Container Toolkit**.

---

## 🚀 Deployment Steps

### 1. Setup Environment
Ensure NVIDIA Container Toolkit is installed:
```bash
sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker
```

### 2. Build Images
Run the helper script to build both images (this will take time to download the model):
```bash
chmod +x build_images.sh
./build_images.sh
```

### 3. Start Services
Start the stack in background mode:
```bash
docker-compose up -d
```

### 4. Verify Status
Check if services are healthy:
```bash
docker-compose ps
```

View logs to confirm model loaded (should take ~1-2 minutes):
```bash
docker-compose logs -f vllm
```
*Wait for: `Application startup complete.`*

---

## ⚙️ Configuration (A30 Optimized)

The `docker-compose.yml` is pre-configured for **NVIDIA A30 (24GB)**:

| Setting | Value | Description |
| :--- | :--- | :--- |
| `gpu-memory-utilization` | **0.95** | Uses 95% of 24GB VRAM (~22.8GB) for model & KV cache. |
| `max-model-len` | **8192** | Extended context window for long documents. |
| `HF_HUB_OFFLINE` | **1** | Forces offline mode to prevent network hangs. |

---

## 📂 Project Structure
*   **`Dockerfile.vllm-model`**: Builds the vLLM image and downloads model to `/opt/models`.
*   **`Dockerfile`**: Builds the API server.
*   **`docker-compose.yml`**: Orchestrates the services.
*   **`build_images.sh`**: Script to build everything correctly.

---

## ❓ Troubleshooting

### Error: `Exit Code 137` (OOM)
*   **Cause**: Out of VRAM/RAM.
*   **Fix**: Lower `gpu-memory-utilization` in `docker-compose.yml` (e.g., to 0.9 or 0.8).

### Error: `Medical check failed` or API Unhealthy
*   **Fix**: fast API might start before vLLM is ready. It has auto-restart, so just wait a moment or run:
    ```bash
    docker-compose restart api
    ```

### Error: `Network unreachable` during build
*   **Fix**: Ensure server has internet access during the build phase (to download model from HuggingFace). Runtime does NOT need internet.
