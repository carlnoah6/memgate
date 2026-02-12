"""
Data Preparation Script: Raw Text → Tokenized Binary Shards.

Usage:
    python data/prepare_data.py \
        --input_dir data/raw/ \
        --output_dir data/tokenized/ \
        --tokenizer_path data/tokenizer.model \
        --shard_size 100000000 \
        --max_seq_len 4096

Pipeline:
    1. Read raw text files (one document per line, or one file = one document)
    2. Tokenize using SentencePiece
    3. Write token IDs to .bin shards (uint32 numpy memmap)
    4. Write metadata.json with shard info and total token count
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import struct
from pathlib import Path
from typing import Iterator, List, Optional

import numpy as np

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# ---------------------------------------------------------------------------
# Tokenizer wrapper (thin abstraction over SentencePiece)
# ---------------------------------------------------------------------------

class Tokenizer:
    """Wraps a SentencePiece model for encoding text → token IDs."""

    def __init__(self, model_path: str):
        import sentencepiece as spm
        self.sp = spm.SentencePieceProcessor()
        self.sp.Load(model_path)
        self.bos_id: int = self.sp.bos_id()
        self.eos_id: int = self.sp.eos_id()
        self.vocab_size: int = self.sp.GetPieceSize()

    def encode(self, text: str, add_bos: bool = True, add_eos: bool = True) -> List[int]:
        ids = self.sp.Encode(text)
        if add_bos and self.bos_id >= 0:
            ids = [self.bos_id] + ids
        if add_eos and self.eos_id >= 0:
            ids = ids + [self.eos_id]
        return ids


# ---------------------------------------------------------------------------
# Document iterator
# ---------------------------------------------------------------------------

def iter_documents(input_dir: str) -> Iterator[str]:
    """Yield documents from all text files under *input_dir*.

    Supports two modes:
      - *.jsonl files: each line is a JSON object with a "text" key
      - *.txt files: entire file content is one document
    """
    input_path = Path(input_dir)
    if input_path.is_file():
        files = [input_path]
    else:
        files = sorted(input_path.rglob("*"))

    for fpath in files:
        if fpath.suffix == ".jsonl":
            with open(fpath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                        text = obj.get("text", "")
                        if text:
                            yield text
                    except json.JSONDecodeError:
                        continue
        elif fpath.suffix == ".txt":
            text = fpath.read_text(encoding="utf-8").strip()
            if text:
                yield text


# ---------------------------------------------------------------------------
# Shard writer
# ---------------------------------------------------------------------------

HEADER_MAGIC = b"TOKN"  # 4-byte magic
HEADER_VERSION = 1
DTYPE = np.uint32  # supports vocab_size up to ~4B


class ShardWriter:
    """Writes tokenized sequences to binary shard files.

    Binary format per shard:
        [4B magic][4B version][8B num_tokens][tokens as uint32 array]

    Token values:
        - Regular tokens from the vocabulary
        - Document boundaries marked by BOS/EOS tokens
    """

    HEADER_SIZE = 16  # 4 + 4 + 8

    def __init__(self, output_dir: str, shard_size: int = 100_000_000):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.shard_size = shard_size  # max tokens per shard

        self._shard_idx = 0
        self._buffer: List[int] = []
        self._shard_infos: List[dict] = []
        self._total_tokens = 0

    def add_tokens(self, token_ids: List[int]):
        """Add a tokenized document's IDs to the current buffer."""
        self._buffer.extend(token_ids)
        while len(self._buffer) >= self.shard_size:
            self._flush_shard(self._buffer[: self.shard_size])
            self._buffer = self._buffer[self.shard_size:]

    def finalize(self) -> dict:
        """Flush remaining buffer and write metadata. Returns metadata dict."""
        if self._buffer:
            self._flush_shard(self._buffer)
            self._buffer = []

        metadata = {
            "format": "tokn_v1",
            "dtype": "uint32",
            "header_size": self.HEADER_SIZE,
            "total_tokens": self._total_tokens,
            "num_shards": len(self._shard_infos),
            "shards": self._shard_infos,
        }
        meta_path = self.output_dir / "metadata.json"
        with open(meta_path, "w") as f:
            json.dump(metadata, f, indent=2)
        logger.info(f"Metadata written → {meta_path}")
        return metadata

    def _flush_shard(self, tokens: List[int]):
        shard_name = f"shard_{self._shard_idx:05d}.bin"
        shard_path = self.output_dir / shard_name
        arr = np.array(tokens, dtype=DTYPE)

        with open(shard_path, "wb") as f:
            f.write(HEADER_MAGIC)
            f.write(struct.pack("<I", HEADER_VERSION))
            f.write(struct.pack("<Q", len(arr)))
            arr.tofile(f)

        n_tokens = len(arr)
        self._shard_infos.append({
            "filename": shard_name,
            "num_tokens": n_tokens,
        })
        self._total_tokens += n_tokens
        self._shard_idx += 1
        logger.info(f"Shard written: {shard_path} ({n_tokens:,} tokens)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def prepare_data(
    input_dir: str,
    output_dir: str,
    tokenizer_path: str,
    shard_size: int = 100_000_000,
    max_seq_len: Optional[int] = None,
):
    """End-to-end: read text → tokenize → write binary shards."""
    tokenizer = Tokenizer(tokenizer_path)
    writer = ShardWriter(output_dir, shard_size=shard_size)

    doc_count = 0
    for doc_text in iter_documents(input_dir):
        ids = tokenizer.encode(doc_text, add_bos=True, add_eos=True)
        writer.add_tokens(ids)
        doc_count += 1
        if doc_count % 10_000 == 0:
            logger.info(f"Processed {doc_count:,} documents …")

    metadata = writer.finalize()
    metadata["tokenizer_path"] = tokenizer_path
    metadata["vocab_size"] = tokenizer.vocab_size
    if max_seq_len is not None:
        metadata["max_seq_len"] = max_seq_len

    # Re-write metadata with extra fields
    meta_path = Path(output_dir) / "metadata.json"
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)

    logger.info(
        f"Done. {doc_count:,} documents → {metadata['total_tokens']:,} tokens "
        f"in {metadata['num_shards']} shards."
    )
    return metadata


def main():
    parser = argparse.ArgumentParser(description="Prepare tokenized binary data shards")
    parser.add_argument("--input_dir", type=str, required=True, help="Directory with raw text / jsonl files")
    parser.add_argument("--output_dir", type=str, required=True, help="Output directory for binary shards")
    parser.add_argument("--tokenizer_path", type=str, default="data/tokenizer.model",
                        help="Path to SentencePiece model")
    parser.add_argument("--shard_size", type=int, default=100_000_000,
                        help="Max tokens per shard file (default: 100M)")
    parser.add_argument("--max_seq_len", type=int, default=4096,
                        help="Max sequence length (recorded in metadata)")
    args = parser.parse_args()
    prepare_data(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        tokenizer_path=args.tokenizer_path,
        shard_size=args.shard_size,
        max_seq_len=args.max_seq_len,
    )


if __name__ == "__main__":
    main()
