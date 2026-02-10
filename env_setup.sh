#!/bin/bash

# ============================================================
# ERROR HANDLERS (Must be defined first!)
# ============================================================
error_network() {
    echo ""
    echo "[FATAL ERROR] Network request failed."
    echo "Please check your internet connection and try again."
    read -p "Press any key to continue..."
    exit 1
}

error_extract() {
    echo ""
    echo "[FATAL ERROR] Failed to extract or compile Python."
    echo "The downloaded archive might be corrupt."
    echo "The script will delete it automatically on the next run."
    read -p "Press any key to continue..."
    exit 1
}

error_pip() {
    echo ""
    echo "[FATAL ERROR] Pip installation or Package install failed."
    read -p "Press any key to continue..."
    exit 1
}

error_ollama_install() {
    echo ""
    echo "[FATAL ERROR] Ollama installation failed."
    read -p "Press any key to continue..."
    exit 1
}

error_model() {
    echo ""
    echo "[FATAL ERROR] Model download failed."
    read -p "Press any key to continue..."
    exit 1
}

error_general() {
    echo ""
    echo "[FATAL ERROR] An unexpected error occurred."
    read -p "Press any key to continue..."
    exit 1
}

# ============================================================
# CONFIGURATION
# ============================================================
SCRIPTROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Use system Python instead of compiling
SYSTEM_PYTHON=$(which python3)
if [ -z "$SYSTEM_PYTHON" ]; then
    echo "[ERROR] Python3 not found on system!"
    echo "Please install Python 3.8+ using: sudo apt install python3 python3-pip python3-venv"
    error_general
fi

VENV_DIR="${SCRIPTROOT}/python"
PYTHON_EXE="${VENV_DIR}/bin/python3"

OLLAMA_DIR="${SCRIPTROOT}/ollama"
OLLAMA_TAR="ollama-linux-amd64.tgz"
OLLAMA_DOWNLOAD_URL="https://github.com/ollama/ollama/releases/download/v0.13.2/ollama-linux-amd64.tgz"
OLLAMA_CHECKSUM_URL="https://github.com/ollama/ollama/releases/download/v0.13.2/sha256sum.txt"

OLLAMA_BIN="${OLLAMA_DIR}/bin/ollama"
OLLAMA_HOST="http://127.0.0.1:11434"
OLLAMA_MODELS="${SCRIPTROOT}/models"

export OLLAMA_HOST
export OLLAMA_MODELS

# ============================================================
# 1. CREATE PYTHON VIRTUAL ENVIRONMENT
# ============================================================
echo "[1/6] Checking Python environment..."

if [ -f "$PYTHON_EXE" ]; then
    echo "- Python virtual environment found. Skipping creation."
else
    echo "- Creating Python virtual environment using system Python ($SYSTEM_PYTHON)..."
    "$SYSTEM_PYTHON" -m venv "$VENV_DIR" || error_extract
    echo "- Virtual environment created successfully."
fi

# Double check that venv creation worked
if [ ! -f "$PYTHON_EXE" ]; then
    error_extract
fi

# ============================================================
# 2. CONFIGURE ENVIRONMENT
# ============================================================
echo "[2/6] Configuring Python environment..."
echo "- Python environment configured."

# ============================================================
# 3. UPGRADE PIP
# ============================================================
echo "[3/6] Upgrading pip..."
"$PYTHON_EXE" -m pip install --upgrade pip --no-warn-script-location || error_pip

# ============================================================
# 4. INSTALL REQUIREMENTS
# ============================================================
echo "[4/6] Installing requirements..."
if [ -f "${SCRIPTROOT}/requirements.txt" ]; then
    "$PYTHON_EXE" -m pip install -r "${SCRIPTROOT}/requirements.txt" --no-warn-script-location || error_pip
else
    echo "[ERROR] requirements.txt not found!"
    error_general
fi

# ============================================================
# 5. DOWNLOAD Ollama
# ============================================================
echo "[5/6] Downloading Ollama..."
if [ -f "$OLLAMA_BIN" ]; then
    echo "- Ollama found in ${OLLAMA_DIR}. Skipping download."
else
    # Download checksum file
    echo "- Downloading checksums..."
    wget -q --show-progress -O sha256sum.txt "$OLLAMA_CHECKSUM_URL" || error_network
    
    # Extract expected hash
    EXPECTED_HASH=$(grep "$OLLAMA_TAR" sha256sum.txt | awk '{print $1}')
    
    # Verify existing tar if present
    if [ -f "$OLLAMA_TAR" ]; then
        if [ -n "$EXPECTED_HASH" ]; then
            echo "- Found ${OLLAMA_TAR}. Verifying checksum..."
            FILE_HASH=$(sha256sum "$OLLAMA_TAR" | awk '{print $1}')
            
            if [ "$FILE_HASH" != "$EXPECTED_HASH" ]; then
                echo "- Checksum mismatch. Deleting corrupt file..."
                rm -f "$OLLAMA_TAR"
            else
                echo "- Checksum verified."
            fi
        fi
    fi
    
    # Download if missing
    if [ ! -f "$OLLAMA_TAR" ]; then
        echo "- Downloading ${OLLAMA_TAR}..."
        wget -q --show-progress -O "$OLLAMA_TAR" "$OLLAMA_DOWNLOAD_URL" || error_network
        
        # Verify downloaded file
        if [ -n "$EXPECTED_HASH" ]; then
            FILE_HASH=$(sha256sum "$OLLAMA_TAR" | awk '{print $1}')
            if [ "$FILE_HASH" != "$EXPECTED_HASH" ]; then
                echo "[ERROR] Downloaded file checksum mismatch!"
                rm -f "$OLLAMA_TAR"
                error_network
            fi
        fi
    fi
    
    # Cleanup checksum file
    if [ -f "sha256sum.txt" ]; then
        rm -f "sha256sum.txt"
    fi
    
    echo "- Extracting to ${OLLAMA_DIR}..."
    mkdir -p "$OLLAMA_DIR"
    tar -xzf "$OLLAMA_TAR" -C "$OLLAMA_DIR" || error_ollama_install
    
    # Clean up tar
    rm -f "$OLLAMA_TAR"
    
    if [ ! -f "$OLLAMA_BIN" ]; then
        error_ollama_install
    fi
    
    # Make ollama executable
    chmod +x "$OLLAMA_BIN"
fi

# ============================================================
# 6. DOWNLOAD MODEL
# ============================================================
echo "[6/6] Downloading DeepSeek-OCR Model..."

echo "Starting Ollama..."
"$OLLAMA_BIN" serve > /dev/null 2>&1 &
OLLAMA_PID=$!
sleep 3

echo "Downloading deepseek-ocr:3b (FP16)..."
"$OLLAMA_BIN" pull deepseek-ocr:3b
if [ $? -ne 0 ]; then
    kill $OLLAMA_PID 2>/dev/null
    error_model
fi

echo "Stopping Ollama..."
kill $OLLAMA_PID 2>/dev/null

echo ""
echo "Environment setup complete."
echo "You can now run './run_api_localhost.sh'."
read -p "Press any key to continue..."
exit 0
