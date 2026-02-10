#!/usr/bin/env python3
"""
Privacy Guard — Integration Test

Tests the full flow: CLI Bridge -> Knowledge Store -> Reviewer.
Uses the installed 'memgate' package via the wrapper script.
"""

import subprocess
import json
import sys
import os
import pytest
from pathlib import Path

# Path to the wrapper script in workspace/scripts
WORKSPACE = Path(os.environ.get("WORKSPACE_DIR", "/home/ubuntu/.openclaw/workspace"))
SCRIPT = str(WORKSPACE / "scripts" / "privacy-check.py")


def run_cmd(args: list, expect_exit=0) -> dict:
    """Run privacy-check.py with args, return parsed JSON output."""
    cmd = [sys.executable, SCRIPT] + args
    # We run from workspace root
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(WORKSPACE))

    if proc.returncode != expect_exit:
        # If expected success but got error, print details
        if expect_exit == 0:
            print(f"\n[DEBUG] Command failed: {' '.join(cmd)}")
            print(f"[DEBUG] STDOUT: {proc.stdout}")
            print(f"[DEBUG] STDERR: {proc.stderr}")

        raise AssertionError(
            f"Expected exit {expect_exit}, got {proc.returncode}\n"
            f"stderr: {proc.stderr[:500]}"
        )

    # Parse JSON if output exists
    output = proc.stdout.strip()
    if not output:
        return {}
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        print(f"\n[DEBUG] Invalid JSON: {output}")
        return {}


# ── Status ──


def test_status():
    data = run_cmd(["status"])
    assert data["enabled"] is True
    # We don't check specific user counts as they depend on live data
    assert "knowledge_dir" in data


# ── Context ──


def test_ctx_dm():
    data = run_cmd(["context", "--channel-type", "dm", "--participants", "alice"])
    assert data["is_private"] is True


def test_ctx_group():
    data = run_cmd(
        ["context", "--channel-type", "group", "--participants", "alice,bob"]
    )
    assert data["is_private"] is False
    # Verify no private knowledge leaking
    for k in data.get("knowledge", []):
        assert k.get("visibility") == "public", f"Found private item in group: {k}"


# ── Review ──


def test_review_safe():
    data = run_cmd(
        [
            "review",
            "--message",
            "Python is a programming language",
            "--channel-type",
            "group",
            "--participants",
            "alice,bob",
        ]
    )
    assert data["passed"] is True


def test_review_calendar():
    # Attempt to leak calendar
    # Note: This requires patterns to be loaded correctly
    data = run_cmd(
        [
            "review",
            "--message",
            "Alice has a meeting tomorrow at 3pm",
            "--channel-type",
            "group",
            "--participants",
            "alice,bob",
        ],
        expect_exit=1,
    )  # Should block
    assert data["passed"] is False
    cats = [v["category"] for v in data["violations"]]
    assert "calendar" in cats


def test_review_finance():
    data = run_cmd(
        [
            "review",
            "--message",
            "Salary is 50k",
            "--channel-type",
            "group",
            "--participants",
            "alice,bob",
        ],
        expect_exit=1,
    )
    assert data["passed"] is False
    cats = [v["category"] for v in data["violations"]]
    assert "finance" in cats


if __name__ == "__main__":
    # Allow running as a script too
    sys.exit(pytest.main([__file__]))
