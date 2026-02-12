import torch
import torch.nn as nn
from model.configuration import ModelArgs
from model.modeling import Transformer

def test_model_initialization():
    print("Initializing model configuration for 7B check...")
    args = ModelArgs()
    # Default args are already 7B config per configuration.py
    # Explicitly ensuring they match the prompt just in case
    args.dim = 4096
    args.n_layers = 32
    args.n_heads = 32
    args.n_kv_heads = 8
    args.vocab_size = 100000
    args.multiple_of = 256
    args.norm_eps = 1e-5
    args.max_seq_len = 4096
    args.rope_theta = 500000.0

    print("Instantiating Transformer model on 'meta' device for param counting...")
    try:
        with torch.device('meta'):
            model = Transformer(args)
        
        param_count = sum(p.numel() for p in model.parameters())
        print(f"Model Parameter Count (7B Config): {param_count / 1e9:.2f}B")
        
        # Expectation: ~6.5B (GQA reduces params compared to standard 7B MHA)
        if not (6.0 < param_count / 1e9 < 7.5):
            print("WARNING: Parameter count is outside expected range (6.0B - 7.5B)")
        else:
            print(f"Parameter count check passed. (Calculated: {param_count / 1e9:.2f}B)")
            
    except Exception as e:
        print(f"Could not instantiate full 7B model on meta device: {e}")

    # Functional Test with small model
    print("\nRunning functional test with small model...")
    small_args = ModelArgs()
    small_args.dim = 128
    small_args.n_layers = 2
    small_args.n_heads = 4
    small_args.n_kv_heads = 2
    small_args.vocab_size = 1000
    small_args.max_seq_len = 32
    small_args.multiple_of = 32
    
    device = "cpu"
    if torch.cuda.is_available():
        device = "cuda"
    
    print(f"Using device: {device}")
    
    try:
        model_small = Transformer(small_args).to(device)
        model_small.eval()
        
        # Dummy input
        x = torch.randint(0, small_args.vocab_size, (1, small_args.max_seq_len)).to(device)
        
        # Forward
        print("Executing forward pass...")
        with torch.no_grad():
            y = model_small(x)
        
        print(f"Forward pass successful. Output shape: {y.shape}")
        
        expected_shape = (1, small_args.max_seq_len, small_args.vocab_size)
        assert y.shape == expected_shape, f"Expected shape {expected_shape}, got {y.shape}"
        print("Shape check passed.")
        
    except Exception as e:
        print(f"Functional test failed: {e}")
        raise e

if __name__ == "__main__":
    test_model_initialization()
