#!/usr/bin/env python3
"""
Privacy Guard — Integration Test

Tests the full flow: CLI Bridge -> Knowledge Store -> Reviewer.
Uses the installed 'memgate' package.
"""

import subprocess
import json
import sys
import os
import pytest
from pathlib import Path
import shutil

# Setup a temporary data directory for tests to avoid permission issues or side effects
TEST_DATA_DIR = Path("/tmp/memgate_test_data")


@pytest.fixture(scope="module", autouse=True)
def setup_teardown():
    # Setup
    if TEST_DATA_DIR.exists():
        shutil.rmtree(TEST_DATA_DIR)
    TEST_DATA_DIR.mkdir(parents=True, exist_ok=True)

    yield

    # Teardown
    if TEST_DATA_DIR.exists():
        shutil.rmtree(TEST_DATA_DIR)


def run_cmd(args: list, expect_exit=0) -> dict:
    """Run memgate CLI with args, return parsed JSON output."""
    # Use -m memgate.cli to invoke the installed package
    cmd = [sys.executable, "-m", "memgate.cli"] + args

    # Inject the test data directory into environment
    env = os.environ.copy()
    env["MEMGATE_DATA_DIR"] = str(TEST_DATA_DIR)

    proc = subprocess.run(cmd, capture_output=True, text=True, env=env)

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
    sys.exit(pytest.main([__file__]))
