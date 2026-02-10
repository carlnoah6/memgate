# Welcome to MemGate

**MemGate** is a privacy-aware memory isolation layer for AI agents. It ensures that sensitive information is handled correctly, preventing unauthorized access and leakage across different contexts.

## Key Features

- **Privacy Review**: Automatically scans and filters sensitive information.
- **Knowledge Store**: Securely stores and retrieves memory items.
- **Context Engine**: Manages context-aware access control.
- **Red Team Arena**: Built-in evaluation framework to test privacy resilience.

## Getting Started

```bash
pip install memgate
```

## Usage

```python
from memgate import MemGate

# Initialize
mg = MemGate()

# Add memory
mg.add_memory("user123", "My credit card is 1234-5678-9012-3456")

# Retrieve memory (privacy filtered)
print(mg.get_memory("user123"))
```
