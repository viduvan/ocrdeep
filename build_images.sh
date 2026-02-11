#!/bin/bash
set -e

echo "🚀 Building OCR Images (Split Approach)..."

# 1. Build vLLM image with Model (Heavy)
echo "📦 Building vLLM Image (Pre-downloading model - this may take a while)..."
docker-compose build vllm

# 2. Build API Image (Light)
echo "📦 Building API Image..."
docker-compose build api

echo "✅ Build Complete!"
echo "To start services:"
echo "  docker-compose up -d"
