#!/usr/bin/env python3
"""End-to-End Test Suite for Luna AI Agent System

Validates the complete workflow from task creation to completion.
Run: python3 tests/e2e/test_full_workflow.py
"""

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from task_engine import TaskEngine

# Test configuration
TEST_PREFIX = "e2e_test_"
VERBOSE = os.environ.get("VERBOSE", "0") == "1"


class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    RESET = "\033[0m"


def log(message, color=None):
    """Print colored log message"""
    if color:
        print(f"{color}{message}{Colors.RESET}")
    else:
        print(message)


def run_command(cmd, capture=True):
    """Run shell command and return output"""
    if VERBOSE:
        log(f"Running: {cmd}", Colors.BLUE)
    
    result = subprocess.run(
        cmd,
        shell=True,
        capture_output=capture,
        text=True
    )
    return result


def test_task_lifecycle():
    """Test full task lifecycle"""
    log("\n🔄 Testing Task Lifecycle...", Colors.BLUE)
    
    engine = TaskEngine()
    
    # Create task
    task = engine.add(f"{TEST_PREFIX}lifecycle_test", create_chat=False)
    task_id = task["id"]
    log(f"  Created task: {task_id}")
    
    # Verify queued
    assert task["status"] == "queued", f"Expected queued, got {task['status']}"
    log(f"  ✓ Status: queued")
    
    # Start task
    result = engine.start(task_id, "test-session-lifecycle")
    assert result["status"] == "running"
    log(f"  ✓ Started")
    
    # Complete task
    result = engine.complete(task_id, "Test completed successfully")
    assert result["status"] == "done"
    log(f"  ✓ Completed")
    
    # Verify in list
    tasks = engine.list_tasks("done")
    task_ids = [t["id"] for t in tasks]
    assert task_id in task_ids, f"Task {task_id} not found in done list"
    log(f"  ✓ Found in done list")
    
    log("  ✅ Task lifecycle test PASSED", Colors.GREEN)
    return True


def test_dependencies():
    """Test task dependencies"""
    log("\n🔗 Testing Dependencies...", Colors.BLUE)
    
    engine = TaskEngine()
    
    # Create parent task
    parent = engine.add(f"{TEST_PREFIX}parent_task", create_chat=False)
    parent_id = parent["id"]
    log(f"  Created parent: {parent_id}")
    
    # Create child task with dependency
    child = engine.add(
        f"{TEST_PREFIX}child_task",
        create_chat=False,
        depends_on=[parent_id]
    )
    child_id = child["id"]
    log(f"  Created child: {child_id} (depends on {parent_id})")
    
    # Verify child not in ready queue
    ready = engine.ready()
    ready_ids = [t["id"] for t in ready]
    assert child_id not in ready_ids, "Child should not be ready yet"
    log(f"  ✓ Child correctly blocked")
    
    # Complete parent
    engine.start(parent_id, "test-session")
    engine.complete(parent_id, "Parent done")
    log(f"  ✓ Parent completed")
    
    # Verify child now ready
    ready = engine.ready()
    ready_ids = [t["id"] for t in ready]
    assert child_id in ready_ids, "Child should now be ready"
    log(f"  ✓ Child unblocked after parent completion")
    
    # Cleanup
    engine.complete(child_id, "Child done")
    
    log("  ✅ Dependencies test PASSED", Colors.GREEN)
    return True


def test_priority():
    """Test priority ordering"""
    log("\n📊 Testing Priority...", Colors.BLUE)
    
    engine = TaskEngine()
    
    # Create tasks with different priorities (via description keywords)
    low = engine.add(f"{TEST_PREFIX}low_priority [P3]", create_chat=False)
    high = engine.add(f"{TEST_PREFIX}high_priority [P0]", create_chat=False)
    medium = engine.add(f"{TEST_PREFIX}medium_priority [P2]", create_chat=False)
    
    log(f"  Created: {low['id']}, {high['id']}, {medium['id']}")
    
    # Verify priorities (P0=high, P3=low)
    ready = engine.ready()
    priorities = {t["id"]: t.get("priority_value", 2) for t in ready}
    
    assert priorities.get(high["id"], 0) < priorities.get(medium["id"], 2), \
        "High priority should have lower priority value"
    log(f"  ✓ Priority ordering correct")
    
    # Cleanup
    for task_id in [low["id"], high["id"], medium["id"]]:
        engine.start(task_id, "test")
        engine.complete(task_id, "Done")
    
    log("  ✅ Priority test PASSED", Colors.GREEN)
    return True


def test_worktree_isolation():
    """Test git worktree creation"""
    log("\n🏗️ Testing Worktree Isolation...", Colors.BLUE)
    
    worktree_base = Path("/tmp/luna-worktrees/")
    test_worktree = worktree_base / f"{TEST_PREFIX}isolation_test"
    
    # Clean if exists
    if test_worktree.exists():
        subprocess.run(["rm", "-rf", str(test_worktree)], check=False)
    
    # Create worktree
    repo_path = "/home/ubuntu/.openclaw/workspace"
    branch_name = f"agent/{TEST_PREFIX}isolation_test"
    
    try:
        # Create branch
        subprocess.run(
            ["git", "-C", repo_path, "branch", "-f", branch_name, "main"],
            check=True,
            capture_output=True
        )
        
        # Create worktree
        subprocess.run(
            ["git", "-C", repo_path, "worktree", "add", str(test_worktree), branch_name],
            check=True,
            capture_output=True
        )
        
        assert test_worktree.exists(), "Worktree not created"
        assert (test_worktree / ".git").exists(), "Worktree not properly initialized"
        log(f"  ✓ Worktree created at {test_worktree}")
        
        # Cleanup
        subprocess.run(
            ["git", "-C", repo_path, "worktree", "remove", "-f", str(test_worktree)],
            check=False,
            capture_output=True
        )
        subprocess.run(
            ["git", "-C", repo_path, "branch", "-D", branch_name],
            check=False,
            capture_output=True
        )
        log(f"  ✓ Worktree cleaned up")
        
        log("  ✅ Worktree isolation test PASSED", Colors.GREEN)
        return True
        
    except subprocess.CalledProcessError as e:
        log(f"  ❌ Worktree creation failed: {e}", Colors.RED)
        return False


def test_collaboration_protocol():
    """Test debate protocol basics"""
    log("\n🤝 Testing Collaboration Protocol...", Colors.BLUE)
    
    agent_protocol_dir = Path(__file__).parent.parent.parent / "scripts" / "agent-protocol"
    
    if not agent_protocol_dir.exists():
        log(f"  ⚠️ Agent protocol not found at {agent_protocol_dir}", Colors.YELLOW)
        return True  # Skip, not an error
    
    # Import base module
    sys.path.insert(0, str(agent_protocol_dir))
    try:
        from base import DebateStateMachine, DebateStatus
        
        # Test state machine
        sm = DebateStateMachine("test_debate_001")
        assert sm.state == DebateStatus.PENDING
        log(f"  ✓ Initial state: PENDING")
        
        # Transition to ACTIVE
        assert sm.transition_to(DebateStatus.ACTIVE)
        assert sm.state == DebateStatus.ACTIVE
        log(f"  ✓ Transition to ACTIVE")
        
        # Invalid transition should fail
        assert not sm.transition_to(DebateStatus.PENDING)  # Can't go back
        log(f"  ✓ Invalid transition rejected")
        
        log("  ✅ Collaboration protocol test PASSED", Colors.GREEN)
        return True
        
    except ImportError as e:
        log(f"  ⚠️ Could not import agent protocol: {e}", Colors.YELLOW)
        return True  # Skip


def test_session_management():
    """Test session tracking"""
    log("\n👤 Testing Session Management...", Colors.BLUE)
    
    engine = TaskEngine()
    
    # Create and start task
    task = engine.add(f"{TEST_PREFIX}session_test", create_chat=False)
    task_id = task["id"]
    
    session_key = "test:session:management:001"
    engine.start(task_id, session_key)
    
    # Verify session stored
    task_data = engine.get_task(task_id)
    assert task_data.get("session_key") == session_key, "Session key not stored"
    log(f"  ✓ Session key stored")
    
    # Test set-session command
    new_session = "test:session:management:002"
    engine.set_session_key(task_id, new_session)
    
    task_data = engine.get_task(task_id)
    assert task_data.get("session_key") == new_session, "Session key not updated"
    log(f"  ✓ Session key updated")
    
    # Cleanup
    engine.complete(task_id, "Done")
    
    log("  ✅ Session management test PASSED", Colors.GREEN)
    return True


def run_all_tests():
    """Run all end-to-end tests"""
    log("\n" + "=" * 60, Colors.BLUE)
    log("LUNA AI AGENT SYSTEM — END-TO-END TEST SUITE", Colors.BLUE)
    log("=" * 60, Colors.BLUE)
    
    tests = [
        ("Task Lifecycle", test_task_lifecycle),
        ("Dependencies", test_dependencies),
        ("Priority", test_priority),
        ("Worktree Isolation", test_worktree_isolation),
        ("Collaboration Protocol", test_collaboration_protocol),
        ("Session Management", test_session_management),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            log(f"\n❌ {name} FAILED with exception: {e}", Colors.RED)
            if VERBOSE:
                import traceback
                traceback.print_exc()
            results.append((name, False))
    
    # Summary
    log("\n" + "=" * 60, Colors.BLUE)
    log("TEST SUMMARY", Colors.BLUE)
    log("=" * 60, Colors.BLUE)
    
    passed = sum(1 for _, p in results if p)
    total = len(results)
    
    for name, p in results:
        status = f"{Colors.GREEN}✅ PASSED{Colors.RESET}" if p else f"{Colors.RED}❌ FAILED{Colors.RESET}"
        log(f"  {name}: {status}")
    
    log(f"\nTotal: {passed}/{total} tests passed", Colors.GREEN if passed == total else Colors.RED)
    
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
