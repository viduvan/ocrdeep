# 🚀 Hướng Dẫn Setup và Chạy OCR Project trên Ubuntu

## 📋 Yêu Cầu Hệ Thống

- **OS**: Ubuntu 20.04+ hoặc Linux tương đương
- **Python**: Python 3.8+ (đã cài sẵn trên hệ thống)
- **RAM**: Tối thiểu 8GB (khuyến nghị 16GB)
- **Dung lượng**: ~15GB trống (cho models và dependencies)
- **Kết nối**: Internet ổn định để tải models

---


## ⚙️ Bước 1: Setup Environment (Chạy 1 Lần Duy Nhất)

### 2.1. Di chuyển vào thư mục project

```bash
cd "~/ocr-deep"
```

### 2.2. Chạy script setup

```bash
./env_setup.sh
```

**Script này sẽ tự động:**
- ✅ Tạo Python virtual environment
- ✅ Cài đặt tất cả Python dependencies từ `requirements.txt`
- ✅ Tải Ollama (1.5GB)
- ✅ Tải DeepSeek-OCR model (6.7GB)

**⏱️ Thời gian:** 10-20 phút (tùy tốc độ mạng)

## 🏃 Bước 2: Chạy API Server

### 2.1. Khởi động server

```bash
./run_api_localhost.sh
```

### 2.2. Kiểm tra server đang chạy

Bạn sẽ thấy output như sau:

```
==============================
Pre-flight checks...
==============================
✓ Python found: /path/to/python/bin/python3
✓ Ollama found: /path/to/ollama/bin/ollama

==============================
Starting Ollama (background)...
==============================
- Ollama started with PID: 12345
- Waiting for Ollama to be ready...
✓ Ollama is ready and responding at http://127.0.0.1:11434

==============================
Starting FastAPI (foreground)...
==============================
- Server will be available at: http://0.0.0.0:8000
- API docs will be at: http://0.0.0.0:8000/docs
- Press Ctrl+C to stop both services
==============================
```

### 2.3. Truy cập API

- **API Server**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs (Swagger UI)
- **Alternative Docs**: http://localhost:8000/redoc

---


## 📝 Cấu Trúc Thư Mục

```
local_ai_ocr-master - Copy/
├── env_setup.sh              # Script setup môi trường (chạy 1 lần)
├── run_api_localhost.sh      # Script chạy API server
├── requirements.txt          # Python dependencies
├── src/
│   └── api_server.py        # FastAPI application
├── python/                   # Virtual environment (tự tạo)
├── ollama/                   # Ollama binary (tự tải)
└── models/                   # OCR models (tự tải)
```

---


## 🔄 Workflow 

### Lần đầu tiên:
```bash
# 1. Setup (chỉ 1 lần)
./env_setup.sh

# 2. Chạy server
./run_api_localhost.sh
```

### Các lần sau:
```bash
# Chỉ cần chạy server
./run_api_localhost.sh
```

## 🎯 Tóm Tắt Commands

```bash
# Setup (1 lần duy nhất)
./env_setup.sh

# Chạy server
./run_api_localhost.sh

# Dừng server
Ctrl+C

# Re-setup (nếu cần)
rm -rf python/ ollama/ models/
./env_setup.sh
```

---

**Chúc bạn sử dụng thành công! 🎉**

