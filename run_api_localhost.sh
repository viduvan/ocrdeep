#!/bin/bash

# Exit on error
set -e

SCRIPTROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${SCRIPTROOT}/python/bin/python3"
OLLAMA_BIN="${SCRIPTROOT}/ollama/bin/ollama"

# Ollama config
export OLLAMA_HOST="http://127.0.0.1:11434"
export OLLAMA_MODELS="${SCRIPTROOT}/models"

# ============================================================
# CLEANUP FUNCTION
# ============================================================
cleanup() {
    echo ""
    echo "=============================="
    echo "Shutting down services..."
    echo "=============================="
    
    if [ -n "$OLLAMA_PID" ]; then
        echo "- Stopping Ollama (PID: $OLLAMA_PID)..."
        kill $OLLAMA_PID 2>/dev/null || true
        wait $OLLAMA_PID 2>/dev/null || true
        echo "- Ollama stopped."
    fi
    
    echo "Cleanup complete."
}

# Register cleanup function to run on exit
trap cleanup EXIT INT TERM

# ============================================================
# PRE-FLIGHT CHECKS
# ============================================================
echo "=============================="
echo "Pre-flight checks..."
echo "=============================="

if [ ! -f "$PYTHON_BIN" ]; then
    echo "[ERROR] Python not found at: $PYTHON_BIN"
    echo "Please run './env_setup.sh' first to set up the environment."
    exit 1
fi
echo "✓ Python found: $PYTHON_BIN"

if [ ! -f "$OLLAMA_BIN" ]; then
    echo "[ERROR] Ollama not found at: $OLLAMA_BIN"
    echo "Please run './env_setup.sh' first to set up the environment."
    exit 1
fi
echo "✓ Ollama found: $OLLAMA_BIN"

if [ ! -f "${SCRIPTROOT}/src/api_server.py" ]; then
    echo "[WARNING] API server file not found at: ${SCRIPTROOT}/src/api_server.py"
    echo "The FastAPI server might fail to start."
fi

echo ""

# ============================================================
# START OLLAMA
# ============================================================
echo "=============================="
echo "Starting Ollama (background)..."
echo "=============================="

"$OLLAMA_BIN" serve > /dev/null 2>&1 &
OLLAMA_PID=$!
echo "- Ollama started with PID: $OLLAMA_PID"

# Wait for Ollama to be ready
echo "- Waiting for Ollama to be ready..."
sleep 3

# Check if Ollama is actually running
if ! kill -0 $OLLAMA_PID 2>/dev/null; then
    echo "[ERROR] Ollama failed to start!"
    echo "Please check if port 11434 is already in use or check Ollama logs."
    exit 1
fi

# Verify Ollama is responding
if command -v curl &> /dev/null; then
    if curl -s "$OLLAMA_HOST/api/tags" > /dev/null 2>&1; then
        echo "✓ Ollama is ready and responding at $OLLAMA_HOST"
    else
        echo "[WARNING] Ollama is running but not responding yet. Giving it more time..."
        sleep 2
    fi
else
    echo "✓ Ollama appears to be running (curl not available for health check)"
fi

echo ""

# ============================================================
# START FASTAPI
# ============================================================
echo "=============================="
echo "Starting FastAPI (foreground)..."
echo "=============================="
echo "- Server will be available at: http://0.0.0.0:8000"
echo "- API docs will be at: http://0.0.0.0:8000/docs"
echo "- Press Ctrl+C to stop both services"
echo "=============================="
echo ""

# Disable exit on error for uvicorn (we want cleanup to run)
set +e
"$PYTHON_BIN" -m uvicorn src.api_server:app --host 0.0.0.0 --port 8000
FASTAPI_EXIT_CODE=$?
set -e

# Check FastAPI exit status
if [ $FASTAPI_EXIT_CODE -ne 0 ]; then
    echo ""
    echo "[WARNING] FastAPI exited with code: $FASTAPI_EXIT_CODE"
fi

# Cleanup will run automatically via trap
echo ""
echo "Press any key to exit."
read -n 1 -s -r
