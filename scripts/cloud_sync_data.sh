#!/bin/bash
set -e

# Configuration
CLOUD_VOLUME="cloud_volume"
DATA_DIR="${CLOUD_VOLUME}/data"
TOKENIZED_DIR="${DATA_DIR}/tokenized"
VENV_PYTHON="./venv/bin/python3"

echo "☁️  Starting Cloud Data Sync..."

# Ensure cloud volume exists (simulating mount)
if [ ! -d "$CLOUD_VOLUME" ]; then
    echo "📦 Creating cloud volume mount point: $CLOUD_VOLUME"
    mkdir -p "$CLOUD_VOLUME"
fi

# Check if data exists in volume
if [ -d "$TOKENIZED_DIR" ] && [ -f "$TOKENIZED_DIR/train.bin" ]; then
    echo "✅ Data already present in cloud volume."
    ls -lh "$TOKENIZED_DIR"
    exit 0
fi

echo "🔄 Data missing in volume. Initiating sync/download sequence..."

# 1. Download Sample Data (if not local)
if [ ! -f "data/corpus_sample.txt" ]; then
    echo "⬇️  Downloading dataset sample..."
    $VENV_PYTHON data/download/download_fineweb_edu.py --output_dir data/download/fineweb_temp --max_samples 1000 --batch_size 1000
    
    echo "📄 Preparing corpus text..."
    $VENV_PYTHON scripts/prepare_corpus.py
else
    echo "✅ Corpus text found locally."
fi

# 2. Tokenize (if not done)
if [ ! -f "data/tokenized/train.bin" ]; then
    echo "🔢 Tokenizing corpus..."
    $VENV_PYTHON scripts/tokenize_corpus.py data/corpus_sample.txt
fi

# 3. "Sync" to Volume
echo "🚀 Syncing data to cloud volume..."
mkdir -p "$DATA_DIR"
# In a real scenario, this might be 'aws s3 sync' or 'rclone copy'
# Here we verify the move we did earlier or copy if needed
if [ -d "data/tokenized" ]; then
    cp -r data/tokenized "$DATA_DIR/"
    echo "✅ Sync complete."
else
    echo "❌ Error: Source data not found to sync."
    exit 1
fi

echo "🎉 Cloud Data Sync & Volume Setup Complete!"
ls -R "$CLOUD_VOLUME"
