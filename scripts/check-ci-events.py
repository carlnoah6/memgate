#!/usr/bin/env python3
"""check-ci-events.py — Process pending CI/CD webhook events

Reads JSON event files from data/ci-events/, outputs a summary,
and deletes processed files.

Output: JSON with "events" array. Empty array = nothing to do.
"""
import json
import os
import sys
from pathlib import Path

EVENT_DIR = Path("/home/ubuntu/.openclaw/workspace/data/ci-events")


def main():
    if not EVENT_DIR.exists():
        print(json.dumps({"events": []}))
        return

    events = []
    for f in sorted(EVENT_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text())
            events.append(data)
            f.unlink()  # Remove after reading
        except Exception:
            f.unlink()  # Remove corrupt files

    print(json.dumps({"events": events}, ensure_ascii=False))


if __name__ == "__main__":
    main()
