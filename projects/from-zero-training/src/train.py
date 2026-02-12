import torch
import sys
import os

def main():
    print(f"Python version: {sys.version}")
    print(f"PyTorch version: {torch.__version__}")
    
    cuda_available = torch.cuda.is_available()
    print(f"CUDA available: {cuda_available}")
    
    if cuda_available:
        print(f"CUDA device count: {torch.cuda.device_count()}")
        print(f"Current device: {torch.cuda.current_device()}")
        print(f"Device name: {torch.cuda.get_device_name(0)}")
    else:
        print("Running on CPU")

    # Simple tensor operation check
    x = torch.rand(5, 3)
    print("Random Tensor:\n", x)
    
    print("\n✅ Environment check passed. Ready for From Zero Training.")

if __name__ == "__main__":
    main()
