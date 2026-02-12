#!/bin/bash
set -e

IMAGE_NAME="from-zero-training:v1"
PROJECT_ROOT="$(dirname "$0")/.."

echo "Building Docker image: $IMAGE_NAME..."
cd "$PROJECT_ROOT"
sudo docker build -t "$IMAGE_NAME" .
echo "Build complete."
