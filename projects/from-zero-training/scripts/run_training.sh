#!/bin/bash
set -e

IMAGE_NAME="from-zero-training:v1"
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Check if nvidia-smi is available to decide on runtime
if command -v nvidia-smi &> /dev/null; then
    RUNTIME_FLAG="--gpus all"
    echo "NVIDIA GPU detected. Running with GPU support."
else
    RUNTIME_FLAG=""
    echo "No NVIDIA GPU detected. Running in CPU mode."
fi

echo "Running training container..."
sudo docker run --rm \
    $RUNTIME_FLAG \
    -v "$PROJECT_ROOT/src:/app/src" \
    -v "$PROJECT_ROOT/logs:/app/logs" \
    -v "$PROJECT_ROOT/checkpoints:/app/checkpoints" \
    "$IMAGE_NAME" python3 src/train.py
