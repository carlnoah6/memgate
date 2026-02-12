import sys
import os
import sentencepiece as spm
import numpy as np
from tqdm import tqdm

def tokenize_corpus(corpus_path, tokenizer_path, output_dir, val_split=0.1):
    print(f"Loading tokenizer from {tokenizer_path}...")
    sp = spm.SentencePieceProcessor(model_file=tokenizer_path)

    print(f"Reading corpus from {corpus_path}...")
    with open(corpus_path, 'r', encoding='utf-8') as f:
        text = f.read()

    print(f"Tokenizing {len(text)} characters...")
    # Tokenize the entire text at once (for simplicity with small sample)
    # In production, you'd stream this.
    tokens = sp.encode(text)
    n_tokens = len(tokens)
    print(f"Encoded {n_tokens} tokens.")

    # Convert to numpy array (uint16 is usually enough for vocab < 65535)
    # Check vocab size
    vocab_size = sp.get_piece_size()
    dtype = np.uint16 if vocab_size < 65535 else np.uint32
    print(f"Vocab size: {vocab_size}, using dtype: {dtype}")

    token_array = np.array(tokens, dtype=dtype)

    # Split into train/val
    split_idx = int(n_tokens * (1 - val_split))
    train_tokens = token_array[:split_idx]
    val_tokens = token_array[split_idx:]

    os.makedirs(output_dir, exist_ok=True)
    train_path = os.path.join(output_dir, "train.bin")
    val_path = os.path.join(output_dir, "val.bin")

    print(f"Saving {len(train_tokens)} train tokens to {train_path}...")
    train_tokens.tofile(train_path)

    print(f"Saving {len(val_tokens)} val tokens to {val_path}...")
    val_tokens.tofile(val_path)
    
    print("Done.")

if __name__ == "__main__":
    corpus_path = "data/corpus_sample.txt"
    tokenizer_path = "data/tokenizer.model"
    output_dir = "data/tokenized"
    
    if len(sys.argv) > 1:
        corpus_path = sys.argv[1]
    
    if not os.path.exists(corpus_path):
        print(f"Error: Corpus not found at {corpus_path}")
        sys.exit(1)
        
    if not os.path.exists(tokenizer_path):
        # Fallback for running from different CWD
        tokenizer_path = "tokenizer.model"
        if not os.path.exists(tokenizer_path):
             print(f"Error: Tokenizer not found at {tokenizer_path}")
             sys.exit(1)

    tokenize_corpus(corpus_path, tokenizer_path, output_dir)
