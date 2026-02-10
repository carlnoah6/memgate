#!/usr/bin/env python3
"""Pre-commit hook: scan staged files for privacy-sensitive words.

Reads `.privacy-words.txt` from the repo root and checks every staged
file for matches (case-insensitive). Exits non-zero if any are found.
"""

import re
import subprocess
import sys
from pathlib import Path

BLOCKLIST_FILE = ".privacy-words.txt"
# Files that are allowed to contain the words (the blocklist itself, etc.)
EXEMPT_FILES = {BLOCKLIST_FILE, ".git", "scripts/check-privacy-words.py"}
# Patterns in lines to skip (e.g., GitHub URLs with username)
EXEMPT_LINE_PATTERNS = [
    r"github\.com/carlnoah6",  # repo URL is fine
    r"carlnoah6\.github\.io",  # pages URL is fine
]


def load_blocklist() -> list[str]:
    path = Path(BLOCKLIST_FILE)
    if not path.exists():
        return []
    words = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        words.append(line)
    return words


def get_staged_files() -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
        capture_output=True,
        text=True,
    )
    return [f for f in result.stdout.strip().splitlines() if f]


def main() -> int:
    words = load_blocklist()
    if not words:
        return 0

    # Build a single regex for speed
    pattern = re.compile("|".join(re.escape(w) for w in words), re.IGNORECASE)
    exempt_line_re = re.compile("|".join(EXEMPT_LINE_PATTERNS))

    staged = get_staged_files()
    violations = []

    for filepath in staged:
        if any(filepath.startswith(e) or filepath == e for e in EXEMPT_FILES):
            continue
        # Skip binary files
        path = Path(filepath)
        if not path.exists():
            continue
        try:
            content = path.read_text(errors="replace")
        except Exception:
            continue

        for lineno, line in enumerate(content.splitlines(), 1):
            if exempt_line_re.search(line):
                continue
            for match in pattern.finditer(line):
                violations.append((filepath, lineno, match.group()))

    if violations:
        print(
            "🚨 Privacy violation detected! The following files contain blocked words:"
        )
        print()
        for filepath, lineno, word in violations:
            print(f'  {filepath}:{lineno}  →  "{word}"')
        print()
        print(f"Blocklist: {BLOCKLIST_FILE}")
        print(
            "Fix: replace real names/locations with generic ones (Alice, Bob, Central Park, etc.)"
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
