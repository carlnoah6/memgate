"""
Streaming Data Loader for Pre-training.

Features:
  - Memory-mapped reading of binary shard files (zero-copy)
  - Sequence packing: concatenate documents into fixed-length sequences
  - Document boundary tracking via attention masks
  - Distributed shard assignment (each rank gets a subset)
  - Multi-worker prefetching
  - Checkpoint-resumable data position
  - Padding-free dynamic batching

Binary shard format (produced by prepare_data.py):
    [4B magic "TOKN"][4B version][8B num_tokens][uint32 token array]
"""

from __future__ import annotations

import json
import logging
import math
import os
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

HEADER_MAGIC = b"TOKN"
HEADER_SIZE = 16  # 4 + 4 + 8

# ---------------------------------------------------------------------------
# Shard reader (memory-mapped)
# ---------------------------------------------------------------------------

class ShardReader:
    """Read a single binary shard via numpy memory-mapping."""

    def __init__(self, path: str):
        self.path = path
        with open(path, "rb") as f:
            magic = f.read(4)
            assert magic == HEADER_MAGIC, f"Bad magic in {path}"
            _version = struct.unpack("<I", f.read(4))[0]
            self.num_tokens = struct.unpack("<Q", f.read(8))[0]

        # Memory-map the token data (skip header)
        self.data = np.memmap(path, dtype=np.uint32, mode="r", offset=HEADER_SIZE,
                              shape=(self.num_tokens,))

    def __len__(self):
        return self.num_tokens

    def slice(self, start: int, end: int) -> np.ndarray:
        """Return a copy of tokens[start:end]."""
        return np.array(self.data[start:end], dtype=np.int64)


# ---------------------------------------------------------------------------
# Metadata loader
# ---------------------------------------------------------------------------

def load_metadata(data_dir: str) -> dict:
    meta_path = Path(data_dir) / "metadata.json"
    with open(meta_path, "r") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Data position state (for checkpoint resumability)
# ---------------------------------------------------------------------------

@dataclass
class DataPosition:
    """Tracks where we are in the data stream for resumability."""
    epoch: int = 0
    shard_idx: int = 0       # index into this rank's shard list
    token_offset: int = 0    # offset within the current shard

    def to_dict(self) -> dict:
        return {"epoch": self.epoch, "shard_idx": self.shard_idx, "token_offset": self.token_offset}

    @classmethod
    def from_dict(cls, d: dict) -> "DataPosition":
        return cls(epoch=d.get("epoch", 0), shard_idx=d.get("shard_idx", 0),
                   token_offset=d.get("token_offset", 0))


# ---------------------------------------------------------------------------
# Sequence Packer
# ---------------------------------------------------------------------------

class SequencePacker:
    """Packs a stream of tokens into fixed-length sequences with attention masks.

    Multiple documents are concatenated into a single sequence of length
    *max_seq_len*.  An attention mask is produced where each packed document
    gets a unique segment ID so that attention is restricted within documents.

    The packer consumes from a token iterator and yields
    ``(input_ids, labels, attention_mask)`` tuples.
    """

    def __init__(self, max_seq_len: int, pad_token_id: int = 0, eos_token_id: int = 2):
        self.max_seq_len = max_seq_len
        self.pad_token_id = pad_token_id
        self.eos_token_id = eos_token_id

    def pack_sequences(
        self, token_stream: Iterator[np.ndarray]
    ) -> Iterator[Tuple[np.ndarray, np.ndarray, np.ndarray]]:
        """Yield packed (input_ids, labels, segment_ids) each of length max_seq_len.

        *token_stream* yields 1-D arrays of token IDs (one per call, each
        representing a contiguous run of tokens, possibly spanning multiple
        documents separated by EOS tokens).

        ``segment_ids``:  An integer array where each position gets the ID
        of the document it belongs to inside the packed sequence.  The trainer
        can convert this to a block-diagonal attention mask.
        """
        buf = np.empty(0, dtype=np.int64)
        seq_len = self.max_seq_len + 1  # +1 so we can split into input / label

        for chunk in token_stream:
            buf = np.concatenate([buf, chunk])

            while len(buf) >= seq_len:
                tokens = buf[:seq_len]
                buf = buf[seq_len:]

                input_ids = tokens[:-1]   # [max_seq_len]
                labels = tokens[1:]       # [max_seq_len]

                # Build segment IDs by scanning for EOS
                segment_ids = self._build_segment_ids(input_ids)

                yield input_ids, labels, segment_ids

    def _build_segment_ids(self, ids: np.ndarray) -> np.ndarray:
        """Assign a monotonically-increasing segment ID each time we see EOS."""
        seg = np.zeros(len(ids), dtype=np.int32)
        current_seg = 0
        for i in range(len(ids)):
            seg[i] = current_seg
            if ids[i] == self.eos_token_id:
                current_seg += 1
        return seg


# ---------------------------------------------------------------------------
# Streaming Dataset (PyTorch IterableDataset)
# ---------------------------------------------------------------------------

try:
    import torch
    from torch.utils.data import IterableDataset, DataLoader

    class PretrainDataset(IterableDataset):
        """Memory-mapped, shard-distributed, sequence-packed iterable dataset.

        Args:
            data_dir:       Directory containing shards + metadata.json
            max_seq_len:    Sequence length for training.
            rank:           Current process rank (0-indexed).
            world_size:     Total number of processes.
            seed:           Random seed for shard shuffling.
            eos_token_id:   Token ID used as end-of-sequence marker.
            infinite:       If True, loop over data indefinitely (epochs).
        """

        def __init__(
            self,
            data_dir: str,
            max_seq_len: int = 4096,
            rank: int = 0,
            world_size: int = 1,
            seed: int = 42,
            eos_token_id: int = 2,
            pad_token_id: int = 0,
            infinite: bool = True,
        ):
            super().__init__()
            self.data_dir = Path(data_dir)
            self.max_seq_len = max_seq_len
            self.rank = rank
            self.world_size = world_size
            self.seed = seed
            self.eos_token_id = eos_token_id
            self.pad_token_id = pad_token_id
            self.infinite = infinite

            # Load metadata
            self.metadata = load_metadata(data_dir)
            all_shards = self.metadata["shards"]

            # Assign shards to this rank (interleaved for balance)
            self.shard_files = [
                str(self.data_dir / s["filename"])
                for i, s in enumerate(all_shards)
                if i % world_size == rank
            ]
            if not self.shard_files:
                raise ValueError(
                    f"Rank {rank} got 0 shards out of {len(all_shards)} "
                    f"(world_size={world_size}). Need at least world_size shards."
                )
            logger.info(
                f"[rank {rank}] assigned {len(self.shard_files)}/{len(all_shards)} shards"
            )

            # Position tracking for resume
            self.position = DataPosition()
            self.packer = SequencePacker(max_seq_len, pad_token_id, eos_token_id)

        def set_position(self, position: DataPosition):
            """Restore data position from checkpoint."""
            self.position = position

        def get_position(self) -> DataPosition:
            return self.position

        def _shard_token_stream(self) -> Iterator[np.ndarray]:
            """Yield token chunks from shards, handling epoch boundaries."""
            epoch = self.position.epoch
            shard_start = self.position.shard_idx
            token_start = self.position.token_offset

            while True:
                # Shuffle shard order per epoch (deterministic)
                rng = np.random.RandomState(self.seed + epoch)
                indices = rng.permutation(len(self.shard_files))

                for i, shard_local_idx in enumerate(indices):
                    if i < shard_start:
                        continue  # skip already-consumed shards on resume

                    shard_path = self.shard_files[shard_local_idx]
                    reader = ShardReader(shard_path)

                    start = token_start if i == shard_start else 0
                    # Yield in chunks to keep memory bounded
                    chunk_size = 1_000_000
                    for offset in range(start, len(reader), chunk_size):
                        end = min(offset + chunk_size, len(reader))
                        self.position.shard_idx = i
                        self.position.token_offset = end
                        yield reader.slice(offset, end)

                    token_start = 0  # reset after first resumed shard

                # Epoch done
                epoch += 1
                self.position.epoch = epoch
                self.position.shard_idx = 0
                self.position.token_offset = 0
                shard_start = 0

                if not self.infinite:
                    break

        def __iter__(self) -> Iterator[Dict[str, "torch.Tensor"]]:
            """Yield dicts: {input_ids, labels, segment_ids} as tensors."""
            # Handle multi-worker within a single rank
            worker_info = torch.utils.data.get_worker_info()
            if worker_info is not None:
                # Split shards across workers
                per_worker = math.ceil(len(self.shard_files) / worker_info.num_workers)
                start = worker_info.id * per_worker
                end = min(start + per_worker, len(self.shard_files))
                self.shard_files = self.shard_files[start:end]

            stream = self._shard_token_stream()
            for input_ids, labels, segment_ids in self.packer.pack_sequences(stream):
                yield {
                    "input_ids": torch.from_numpy(input_ids.copy()).long(),
                    "labels": torch.from_numpy(labels.copy()).long(),
                    "segment_ids": torch.from_numpy(segment_ids.copy()).long(),
                }

    def create_dataloader(
        data_dir: str,
        max_seq_len: int = 4096,
        batch_size: int = 4,
        rank: int = 0,
        world_size: int = 1,
        num_workers: int = 2,
        seed: int = 42,
        eos_token_id: int = 2,
        pad_token_id: int = 0,
        infinite: bool = True,
        pin_memory: bool = True,
    ) -> Tuple[DataLoader, PretrainDataset]:
        """Factory: create a ready-to-use DataLoader.

        Returns (dataloader, dataset) so caller can access dataset.get_position().
        """
        dataset = PretrainDataset(
            data_dir=data_dir,
            max_seq_len=max_seq_len,
            rank=rank,
            world_size=world_size,
            seed=seed,
            eos_token_id=eos_token_id,
            pad_token_id=pad_token_id,
            infinite=infinite,
        )
        loader = DataLoader(
            dataset,
            batch_size=batch_size,
            num_workers=num_workers,
            pin_memory=pin_memory and torch.cuda.is_available(),
            # No sampler needed — IterableDataset handles its own distribution
        )
        return loader, dataset

except ImportError:
    # Allow the module to be imported without torch (for prepare_data usage)
    logger.debug("torch not available — PretrainDataset / create_dataloader disabled")


# ---------------------------------------------------------------------------
# Standalone utilities (no torch dependency)
# ---------------------------------------------------------------------------

def inspect_shard(path: str, n_tokens: int = 20):
    """Print first N tokens of a shard (for debugging)."""
    reader = ShardReader(path)
    print(f"Shard: {path}  |  Tokens: {reader.num_tokens:,}")
    print(f"First {n_tokens}: {reader.slice(0, min(n_tokens, len(reader))).tolist()}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        inspect_shard(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 20)
    else:
        print("Usage: python dataloader.py <shard.bin> [n_tokens]")
