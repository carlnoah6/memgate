import torch
import numpy as np
import os
from torch.utils.data import Dataset

class PretokenizedDataset(Dataset):
    """
    Dataset for loading pre-tokenized binary data (numpy format).
    Expects data to be uint16 or uint32.
    """
    def __init__(self, data_path, seq_len, split="train"):
        self.seq_len = seq_len
        self.split = split
        
        bin_path = os.path.join(data_path, f"{split}.bin")
        if not os.path.exists(bin_path):
            raise FileNotFoundError(f"Data file not found: {bin_path}")
            
        # Determine dtype based on file size/content or just try uint32 as per tokenizer output
        # In a robust setup, we might save a metadata file. 
        # For now, we know it's uint32 from our tokenize script.
        self.dtype = np.uint32
        
        # Memory map the file for efficient reading of large datasets
        self.data = np.memmap(bin_path, dtype=self.dtype, mode='r')
        
        print(f"Loaded {split} dataset from {bin_path}")
        print(f"  Total tokens: {len(self.data)}")
        print(f"  Dtype: {self.dtype}")

    def __len__(self):
        # We return the number of possible sequences
        return len(self.data) - self.seq_len

    def __getitem__(self, idx):
        # Grab a chunk of data of length seq_len + 1 (input + target)
        # The target is just input shifted by 1
        
        d = self.data[idx : idx + self.seq_len + 1]
        
        # Handle edge case where we might run off the end (though __len__ should prevent this)
        if len(d) < self.seq_len + 1:
            # Pad or just error? For pretraining usually we just stop.
            # But let's just take a random slice if we hit the end for robustness in this simple impl
            d = self.data[0 : self.seq_len + 1]
            
        x = torch.from_numpy(d[:-1].astype(np.int64))
        y = torch.from_numpy(d[1:].astype(np.int64))
        
        return {"input_ids": x, "labels": y}
