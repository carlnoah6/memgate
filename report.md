# Data Downloaders (FineWeb & StarCoder)

**Status**: Ready ✅
**Path**: `data/download/`

## Overview
We have implemented a robust toolchain for downloading and preprocessing the core training datasets for Phase 1. The scripts use the Hugging Face `datasets` library in **streaming mode** to handle large-scale data efficiently without requiring massive local disk space for cache.

## Tools

### 1. FineWeb-Edu Downloader
Optimized for high-quality educational web text.

- **Script**: `download_fineweb_edu.py`
- **Dataset**: `HuggingFaceFW/fineweb-edu`
- **Format**: Parquet (snappy compression)
- **Features**: Streaming download, batch processing, progress bar.

**Usage:**
```bash
# Download sample 10BT subset
python3 data/download/download_fineweb_edu.py --subset sample-10BT --output_dir data/fineweb

# Test with small sample
python3 data/download/download_fineweb_edu.py --max_samples 1000
```

### 2. StarCoder Downloader
Targeting code data (Python subset).

- **Script**: `download_starcoder.py`
- **Dataset**: `bigcode/starcoderdata`
- **Auth**: Requires Hugging Face Token (Gated Dataset).

**Usage:**
```bash
export HF_TOKEN="your_token_here"
python3 data/download/download_starcoder.py --subset python --output_dir data/starcoder
```

## Implementation Details

- **Streaming**: Data is streamed and buffered in memory (default 50k-100k samples) before writing to disk, minimizing memory footprint.
- **Parquet**: Output files are saved in Apache Parquet format for efficient columnar storage and fast loading during training.
- **Resilience**: Scripts handle `max_samples` accurately for testing and provide clear error messages for authentication failures.

## Validation

- **FineWeb-Edu**: Verified download of 100 samples. Throughput is high.
- **StarCoder**: Validated authentication logic. The script correctly identifies the gated nature of the dataset and prompts the user for a token if missing.

## Next Steps
- Obtain a valid `HF_TOKEN` for the production environment.
- Run full downloads on the target storage volume (ensure >200GB free space).
