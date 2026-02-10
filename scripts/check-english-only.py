#!/usr/bin/env python3
"""
Pre-commit hook: reject Chinese characters in tracked files.

Open-source repos must be English-only.
Checks all tracked text files except those in explicitly allowed paths.
"""

import re
import subprocess
import sys

# Files/dirs where Chinese is allowed (internal tooling, not shipped)
ALLOWED_PATHS = {
    ".privacy-words.txt",  # Internal blocklist
    "memgate/knowledge_store.py",  # Functional regex patterns (Keep Chinese for detection)
    "memgate/privacy_review.py",  # Functional regex patterns (Keep Chinese for detection)
    "scripts/check-english-only.py",  # This script itself (contains comments about Chinese)
}

# Only check these extensions
CHECK_EXTENSIONS = {
    ".py",
    ".md",
    ".yml",
    ".yaml",
    ".toml",
    ".txt",
    ".json",
    ".rst",
    ".cfg",
    ".ini",
    ".html",
    ".css",
    ".js",
}

# Regex for CJK characters
CJK_PATTERN = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")


def get_all_files():
    """Get all tracked files."""
    result = subprocess.run(
        ["git", "ls-files"],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip().split("\n") if result.stdout.strip() else []


def check_file(filepath):
    """Returns list of (line_number, matched_text) tuples."""
    violations = []
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            for i, line in enumerate(f, 1):
                matches = CJK_PATTERN.findall(line)
                if matches:
                    violations.append((i, "".join(matches[:5])))
    except (IOError, UnicodeDecodeError):
        pass
    return violations


def main():
    files = get_all_files()
    has_violations = False

    # If files list is empty, it might be a new repo or not git initialized properly
    # Try to verify current directory files just in case
    if not files:
        result = subprocess.run(
            ["find", ".", "-type", "f", "-not", "-path", "*/.*"],
            capture_output=True,
            text=True,
        )
        files = [f.strip("./") for f in result.stdout.strip().split("\n") if f]

    for filepath in files:
        if filepath in ALLOWED_PATHS:
            continue

        ext = "." + filepath.rsplit(".", 1)[-1] if "." in filepath else ""
        if ext not in CHECK_EXTENSIONS:
            continue

        violations = check_file(filepath)
        if violations:
            if not has_violations:
                print(
                    "\n🚨 Chinese characters detected! This is an English-only repo.\n"
                )
                has_violations = True
            for line_num, chars in violations:
                print(f'  {filepath}:{line_num}  →  "{chars}"')

    if has_violations:
        print("\n❌ Fix: replace Chinese text with English.")
        return 1

    print("✅ All checked files are English-only.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
