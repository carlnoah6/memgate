#!/usr/bin/env python3
"""
Privacy Guard — Bridge Script
Wraps the installed 'memgate' package.
"""
import sys
from pathlib import Path

# Add local memgate package to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "memgate"))

from memgate.cli import main

if __name__ == "__main__":
    sys.exit(main())
