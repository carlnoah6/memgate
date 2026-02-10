#!/usr/bin/env python3
"""
Pre-commit hook: reject Chinese characters in staged files.

Open-source repos must be English-only.
Checks all text files except those in explicitly allowed paths.
"""

import re
import subprocess
import sys

# Files/dirs where Chinese is allowed (internal tooling, not shipped)
ALLOWED_PATHS = {
    ".privacy-words.txt",  # Internal blocklist
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

CJK_PATTERN = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")


def get_staged_files():
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
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
    files = get_staged_files()
    has_violations = False

    for filepath in files:
        # Skip allowed paths
        if filepath in ALLOWED_PATHS:
            continue

        # Skip non-checked extensions
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
        print("\nFix: replace Chinese text with English.")
        print(
            "Allowed exceptions: update ALLOWED_PATHS in scripts/check-english-only.py\n"
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
