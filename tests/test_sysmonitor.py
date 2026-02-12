#!/usr/bin/env python3
"""SysMonitor Test Suite — Tests for inspect_session, task-dashboard, task-health-check, task_engine

Covers: normal paths, edge cases, error handling, integration with real logs.
Updated to test refactored TaskEngine-based modules.
"""

import json
import os
import sys
import tempfile
import time
import shutil
import unittest
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
from io import StringIO

# Add scripts directory to path
SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import inspect_session
import task_engine
from task_engine import TaskEngine

# Import task-dashboard and task-health-check (hyphenated names)
import importlib.util

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

task_dashboard = load_module("task_dashboard", SCRIPTS_DIR / "task-dashboard.py")
task_health_check = load_module("task_health_check", SCRIPTS_DIR / "task-health-check.py")


class TestTailJsonl(unittest.TestCase):
    """Tests for inspect_session.tail_jsonl"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _write(self, filename, content):
        p = os.path.join(self.tmpdir, filename)
        with open(p, 'w') as f:
            f.write(content)
        return p

    def test_normal_jsonl(self):
        """Normal JSONL file with valid lines"""
        path = self._write("test.jsonl", '{"a":1}\n{"b":2}\n{"c":3}\n')
        result = inspect_session.tail_jsonl(path, 2)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], {"b": 2})
        self.assertEqual(result[1], {"c": 3})

    def test_empty_file(self):
        """Empty file returns empty list"""
        path = self._write("empty.jsonl", "")
        result = inspect_session.tail_jsonl(path, 5)
        self.assertEqual(result, [])

    def test_blank_lines(self):
        """Blank lines are skipped"""
        path = self._write("blanks.jsonl", '{"a":1}\n\n\n{"b":2}\n\n')
        result = inspect_session.tail_jsonl(path, 10)
        self.assertEqual(len(result), 2)

    def test_corrupted_json_lines(self):
        """Corrupted JSON lines are skipped gracefully"""
        path = self._write("corrupt.jsonl",
            '{"good":1}\n{bad json\n{"good2":2}\nNOT JSON\n{"good3":3}\n')
        result = inspect_session.tail_jsonl(path, 10)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0]["good"], 1)
        self.assertEqual(result[2]["good3"], 3)

    def test_all_corrupted(self):
        """All corrupted lines returns empty list"""
        path = self._write("allbad.jsonl", "NOT JSON\n{bad\nwhat\n")
        result = inspect_session.tail_jsonl(path, 5)
        self.assertEqual(result, [])

    def test_nonexistent_file(self):
        """Non-existent file returns empty list without error"""
        result = inspect_session.tail_jsonl("/nonexistent/path.jsonl", 5)
        self.assertEqual(result, [])

    def test_single_line(self):
        """Single line file"""
        path = self._write("single.jsonl", '{"only":true}\n')
        result = inspect_session.tail_jsonl(path, 1)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], {"only": True})

    def test_request_more_lines_than_exist(self):
        """Requesting more lines than exist returns all valid lines"""
        path = self._write("few.jsonl", '{"a":1}\n{"b":2}\n')
        result = inspect_session.tail_jsonl(path, 100)
        self.assertEqual(len(result), 2)

    def test_unicode_content(self):
        """Unicode content in JSON"""
        path = self._write("unicode.jsonl", '{"msg":"你好世界"}\n{"msg":"🎉"}\n')
        result = inspect_session.tail_jsonl(path, 2)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["msg"], "你好世界")
        self.assertEqual(result[1]["msg"], "🎉")

    def test_large_line(self):
        """Very large JSON line (1MB+)"""
        big_content = "x" * (1024 * 1024)
        path = self._write("big.jsonl", json.dumps({"data": big_content}) + '\n')
        result = inspect_session.tail_jsonl(path, 1)
        self.assertEqual(len(result), 1)
        self.assertEqual(len(result[0]["data"]), 1024 * 1024)


class TestGetSessionFile(unittest.TestCase):
    """Tests for inspect_session.get_session_file"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.orig_session_dir = inspect_session.SESSION_DIR
        inspect_session.SESSION_DIR = Path(self.tmpdir)

    def tearDown(self):
        inspect_session.SESSION_DIR = self.orig_session_dir
        shutil.rmtree(self.tmpdir)

    def test_direct_uuid(self):
        """Direct UUID lookup"""
        p = Path(self.tmpdir) / "abc123.jsonl"
        p.touch()
        result = inspect_session.get_session_file("abc123")
        self.assertIsNotNone(result)
        self.assertEqual(result.stem, "abc123")

    def test_full_session_key(self):
        """Full session key 'agent:main:subagent:UUID' extracts UUID"""
        uuid = "550e8400-e29b-41d4-a716-446655440000"
        p = Path(self.tmpdir) / f"{uuid}.jsonl"
        p.touch()
        result = inspect_session.get_session_file(f"agent:main:subagent:{uuid}")
        self.assertIsNotNone(result)
        self.assertEqual(result.stem, uuid)

    def test_nonexistent_session(self):
        """Non-existent session returns None"""
        result = inspect_session.get_session_file("a0a0-dead")
        self.assertIsNone(result)

    def test_empty_string(self):
        """Empty string returns None"""
        result = inspect_session.get_session_file("")
        self.assertIsNone(result)

    def test_feishu_session_key(self):
        """Session key with feishu channel format"""
        uuid = "a0a0-feee"
        p = Path(self.tmpdir) / f"{uuid}.jsonl"
        p.touch()
        result = inspect_session.get_session_file(f"agent:main:feishu:group:{uuid}")
        self.assertIsNotNone(result)


class TestAnalyzeSession(unittest.TestCase):
    """Tests for inspect_session.analyze_session"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.orig_session_dir = inspect_session.SESSION_DIR
        inspect_session.SESSION_DIR = Path(self.tmpdir)

    def tearDown(self):
        inspect_session.SESSION_DIR = self.orig_session_dir
        shutil.rmtree(self.tmpdir)

    def _create_session(self, session_id, messages):
        p = Path(self.tmpdir) / f"{session_id}.jsonl"
        with open(p, 'w') as f:
            for msg in messages:
                f.write(json.dumps(msg) + "\n")
        return p

    def test_running_session(self):
        """Recently active session shows as Running"""
        now_ms = int(time.time() * 1000)
        now_iso = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        self._create_session("a0a0-0001", [
            {"type": "session", "timestamp": now_iso},
            {
                "type": "message",
                "timestamp": now_iso,
                "message": {
                    "role": "assistant",
                    "content": "Hello world",
                    "usage": {"totalTokens": 5000},
                    "timestamp": now_ms
                }
            }
        ])
        result = inspect_session.analyze_session("a0a0-0001")
        self.assertIn("🟢", result["status"])
        self.assertLess(result["age_seconds"], 60)
        self.assertEqual(result["total_tokens"], 5000)

    def test_stalled_session(self):
        """Session inactive 2-10 min shows as Stalled"""
        past = time.time() - 300  # 5 minutes ago
        past_iso = datetime.utcfromtimestamp(past).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        self._create_session("a0a0-0002", [
            {"type": "message", "timestamp": past_iso, "message": {
                "role": "assistant", "content": "test", "timestamp": int(past * 1000)
            }}
        ])
        result = inspect_session.analyze_session("a0a0-0002")
        self.assertIn("🟡", result["status"])

    def test_dead_session(self):
        """Session inactive >10 min shows as Dead"""
        past = time.time() - 1200  # 20 minutes ago
        past_iso = datetime.utcfromtimestamp(past).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        self._create_session("a0a0-0003", [
            {"type": "message", "timestamp": past_iso, "message": {
                "role": "assistant", "content": "old stuff", "timestamp": int(past * 1000)
            }}
        ])
        result = inspect_session.analyze_session("a0a0-0003")
        self.assertIn("🔴", result["status"])

    def test_nonexistent_session(self):
        """Non-existent session returns error"""
        result = inspect_session.analyze_session("no-such-session")
        self.assertIn("error", result)

    def test_empty_session_file(self):
        """Empty session file"""
        self._create_session("a0a0-0004", [])
        # Actually write an empty file
        p = Path(self.tmpdir) / "empty-sess.jsonl"
        p.write_text("")
        result = inspect_session.analyze_session("a0a0-0004")
        self.assertEqual(result["status"], "empty")

    def test_content_list_extraction(self):
        """Content as list (multi-part) extracts text and tool calls"""
        now_ms = int(time.time() * 1000)
        now_iso = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        self._create_session("a0a0-0005", [
            {
                "type": "message",
                "timestamp": now_iso,
                "message": {
                    "role": "assistant",
                    "content": [
                        {"type": "text", "text": "Running command now"},
                        {"type": "toolCall", "name": "exec"}
                    ],
                    "usage": {"totalTokens": 1000},
                    "timestamp": now_ms
                }
            }
        ])
        result = inspect_session.analyze_session("a0a0-0005")
        self.assertIn("Running command now", result["last_action"])
        self.assertIn("[Tool: exec]", result["last_action"])

    def test_iso_timestamp_with_z(self):
        """ISO timestamp ending with Z is parsed correctly"""
        now_iso = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        self._create_session("a0a0-0006", [
            {"type": "message", "timestamp": now_iso, "message": {
                "role": "assistant", "content": "test",
                "timestamp": now_iso  # string timestamp
            }}
        ])
        result = inspect_session.analyze_session("a0a0-0006")
        # Should not crash — the root timestamp is used (it's a string)
        self.assertIn("status", result)

    def test_numeric_timestamp(self):
        """Numeric (epoch ms) timestamp works"""
        now_ms = int(time.time() * 1000)
        self._create_session("a0a0-0007", [
            {"type": "message", "timestamp": now_ms, "message": {
                "role": "assistant", "content": "test", "timestamp": now_ms
            }}
        ])
        result = inspect_session.analyze_session("a0a0-0007")
        self.assertIn("🟢", result["status"])

    def test_usage_in_message_vs_root(self):
        """Usage can be in root or in message.usage"""
        now_ms = int(time.time() * 1000)
        now_iso = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        # Usage at root level
        self._create_session("a0a0-0008", [
            {
                "type": "message", "timestamp": now_iso,
                "usage": {"totalTokens": 9999},
                "message": {"role": "assistant", "content": "test", "timestamp": now_ms}
            }
        ])
        result = inspect_session.analyze_session("a0a0-0008")
        self.assertEqual(result["total_tokens"], 9999)


class TestTaskDashboard(unittest.TestCase):
    """Tests for task-dashboard.py (now uses TaskEngine)"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.orig_task_board = task_engine.TASK_BOARD
        task_engine.TASK_BOARD = Path(self.tmpdir) / "task-board.json"

    def tearDown(self):
        task_engine.TASK_BOARD = self.orig_task_board
        shutil.rmtree(self.tmpdir)

    def _write_board(self, data):
        task_engine.TASK_BOARD.parent.mkdir(parents=True, exist_ok=True)
        task_engine.TASK_BOARD.write_text(json.dumps(data, ensure_ascii=False))

    def test_load_board_no_file(self):
        """load_board returns empty structure when file doesn't exist"""
        result = TaskEngine.load_board()
        self.assertIn("tasks", result)
        self.assertEqual(result["tasks"], [])

    def test_load_board_valid(self):
        """load_board reads valid JSON"""
        self._write_board({
            "tasks": [{"id": "t001", "status": "running", "description": "test"}],
            "next_id": 2
        })
        result = TaskEngine.load_board()
        self.assertEqual(len(result["tasks"]), 1)

    def test_dashboard_no_active(self):
        """Dashboard with no active tasks"""
        self._write_board({
            "tasks": [{"id": "t001", "status": "done", "description": "finished"}]
        })
        captured = StringIO()
        sys.stdout = captured
        task_dashboard.generate_dashboard()
        sys.stdout = sys.__stdout__
        self.assertIn("No active", captured.getvalue())

    def test_dashboard_with_active_no_key(self):
        """Active task without session_key shows '⚪ No Key'"""
        self._write_board({
            "tasks": [{"id": "t001", "status": "running", "description": "test task", "session_key": ""}]
        })
        captured = StringIO()
        sys.stdout = captured
        task_dashboard.generate_dashboard()
        sys.stdout = sys.__stdout__
        output = captured.getvalue()
        self.assertIn("No Key", output)

    def test_dashboard_description_truncation(self):
        """Long descriptions are truncated in all branches including 'No Key'"""
        long_desc = "A" * 50
        self._write_board({
            "tasks": [{"id": "t001", "status": "running", "description": long_desc, "session_key": ""}]
        })
        captured = StringIO()
        sys.stdout = captured
        task_dashboard.generate_dashboard()
        sys.stdout = sys.__stdout__
        output = captured.getvalue()
        # After fix: "No Key" branch now truncates description too
        self.assertIn("A" * 30 + "...", output)
        self.assertNotIn("A" * 50, output)


class TestTaskHealthCheck(unittest.TestCase):
    """Tests for task-health-check.py (now uses TaskEngine)"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.orig_task_board = task_engine.TASK_BOARD
        task_engine.TASK_BOARD = Path(self.tmpdir) / "task-board.json"
        # Also mock session dir for inspect_session
        self.orig_session_dir = inspect_session.SESSION_DIR
        inspect_session.SESSION_DIR = Path(self.tmpdir) / "sessions"
        inspect_session.SESSION_DIR.mkdir()

    def tearDown(self):
        task_engine.TASK_BOARD = self.orig_task_board
        inspect_session.SESSION_DIR = self.orig_session_dir
        shutil.rmtree(self.tmpdir)

    def _write_board(self, tasks):
        task_engine.TASK_BOARD.parent.mkdir(parents=True, exist_ok=True)
        task_engine.TASK_BOARD.write_text(json.dumps({"tasks": tasks}, ensure_ascii=False))

    def _create_session(self, session_id, age_seconds=0):
        """Create a mock session file with last message at given age"""
        ts = time.time() - age_seconds
        ts_iso = datetime.utcfromtimestamp(ts).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        ts_ms = int(ts * 1000)
        p = inspect_session.SESSION_DIR / f"{session_id}.jsonl"
        with open(p, 'w') as f:
            f.write(json.dumps({
                "type": "message", "timestamp": ts_iso,
                "message": {"role": "assistant", "content": "test", "timestamp": ts_ms}
            }) + "\n")

    def test_empty_board(self):
        """No tasks = healthy"""
        self._write_board([])
        captured = StringIO()
        sys.stdout = captured
        task_health_check.check_health()
        sys.stdout = sys.__stdout__
        result = json.loads(captured.getvalue())
        self.assertEqual(result["stale"], [])
        self.assertEqual(result["active"], [])

    def test_active_running_task(self):
        """Recently active running task should be reported as active"""
        SGT = timezone(timedelta(hours=8))
        now = datetime.now(SGT)
        self._create_session("a0a0-000a", age_seconds=30)
        self._write_board([{
            "id": "t001", "status": "running",
            "description": "Active task",
            "started": (now - timedelta(minutes=5)).isoformat(),
            "session_key": "agent:main:subagent:a0a0-000a"
        }])
        captured = StringIO()
        sys.stdout = captured
        task_health_check.check_health()
        sys.stdout = sys.__stdout__
        result = json.loads(captured.getvalue())
        self.assertEqual(len(result["active"]), 1)
        self.assertEqual(len(result["stale"]), 0)

    def test_stale_by_inactivity(self):
        """Task with no session activity > STALLED_MINUTES marked stale"""
        SGT = timezone(timedelta(hours=8))
        now = datetime.now(SGT)
        self._create_session("a0a0-000b", age_seconds=900)  # 15 min inactive
        self._write_board([{
            "id": "t002", "status": "running",
            "description": "Stale task",
            "started": (now - timedelta(minutes=20)).isoformat(),
            "session_key": "agent:main:subagent:a0a0-000b"
        }])
        captured = StringIO()
        sys.stdout = captured
        task_health_check.check_health()
        sys.stdout = sys.__stdout__
        result = json.loads(captured.getvalue())
        self.assertEqual(len(result["stale"]), 1)
        self.assertIn("无响应", result["stale"][0]["reason"])

    def test_stale_by_timeout(self):
        """Task running > MAX_RUNNING_MINUTES marked stale regardless of activity"""
        SGT = timezone(timedelta(hours=8))
        now = datetime.now(SGT)
        self._create_session("a0a0-000c", age_seconds=10)  # Still active
        self._write_board([{
            "id": "t003", "status": "running",
            "description": "Timed out task",
            "started": (now - timedelta(minutes=90)).isoformat(),  # Started 90 min ago
            "session_key": "agent:main:subagent:a0a0-000c"
        }])
        captured = StringIO()
        sys.stdout = captured
        task_health_check.check_health()
        sys.stdout = sys.__stdout__
        result = json.loads(captured.getvalue())
        self.assertEqual(len(result["stale"]), 1)
        self.assertIn("超时", result["stale"][0]["reason"])

    def test_running_task_no_session_file(self):
        """Running task with missing session file — should be marked as potentially dead"""
        SGT = timezone(timedelta(hours=8))
        now = datetime.now(SGT)
        self._write_board([{
            "id": "t004", "status": "running",
            "description": "No session file",
            "started": (now - timedelta(minutes=5)).isoformat(),
            "session_key": "agent:main:subagent:a0a0-dead"
        }])
        captured = StringIO()
        sys.stdout = captured
        task_health_check.check_health()
        sys.stdout = sys.__stdout__
        result = json.loads(captured.getvalue())
        # After fix: missing session = error = treated as potentially dead
        self.assertEqual(len(result["stale"]), 1)
        self.assertIn("Session 异常", result["stale"][0]["reason"])

    def test_cleanup_old_tasks(self):
        """Completed tasks older than CLEANUP_DAYS are removed"""
        SGT = timezone(timedelta(hours=8))
        old_date = (datetime.now(SGT) - timedelta(days=10)).isoformat()
        recent_date = (datetime.now(SGT) - timedelta(days=1)).isoformat()
        self._write_board([
            {"id": "t-old", "status": "done", "description": "old", "completed": old_date},
            {"id": "t-recent", "status": "done", "description": "recent", "completed": recent_date},
            {"id": "t-running", "status": "running", "description": "active",
             "started": datetime.now(SGT).isoformat(), "session_key": ""},
        ])
        captured = StringIO()
        sys.stdout = captured
        task_health_check.check_health()
        sys.stdout = sys.__stdout__
        result = json.loads(captured.getvalue())
        self.assertEqual(result["cleaned"], 1)  # t-old removed
        # Verify board was saved
        board = json.loads(task_engine.TASK_BOARD.read_text())
        ids = [t["id"] for t in board["tasks"]]
        self.assertNotIn("t-old", ids)
        self.assertIn("t-recent", ids)

    def test_board_saved_only_when_changes(self):
        """Board is NOT saved when nothing changes"""
        self._write_board([
            {"id": "t-done", "status": "done", "description": "ok",
             "completed": datetime.now(timezone(timedelta(hours=8))).isoformat()}
        ])
        mtime_before = task_engine.TASK_BOARD.stat().st_mtime
        import time as _time
        _time.sleep(0.05)
        captured = StringIO()
        sys.stdout = captured
        task_health_check.check_health()
        sys.stdout = sys.__stdout__
        mtime_after = task_engine.TASK_BOARD.stat().st_mtime
        self.assertEqual(mtime_before, mtime_after)

    def test_done_task_not_inspected(self):
        """Done/failed/cancelled tasks are not session-inspected"""
        self._write_board([
            {"id": "t-done", "status": "done", "description": "finished",
             "completed": datetime.now(timezone(timedelta(hours=8))).isoformat()},
            {"id": "t-fail", "status": "failed", "description": "failed",
             "completed": datetime.now(timezone(timedelta(hours=8))).isoformat()},
        ])
        captured = StringIO()
        sys.stdout = captured
        task_health_check.check_health()
        sys.stdout = sys.__stdout__
        result = json.loads(captured.getvalue())
        self.assertEqual(result["stale"], [])
        self.assertEqual(result["active"], [])

    def test_task_without_started_field(self):
        """Running task without 'started' field doesn't crash"""
        self._write_board([{
            "id": "t-nostart", "status": "running",
            "description": "No start time",
            "session_key": ""
        }])
        captured = StringIO()
        sys.stdout = captured
        task_health_check.check_health()
        sys.stdout = sys.__stdout__
        result = json.loads(captured.getvalue())
        self.assertIsInstance(result, dict)


class TestTaskEngine(unittest.TestCase):
    """Tests for the unified TaskEngine class"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.orig_task_board = task_engine.TASK_BOARD
        task_engine.TASK_BOARD = Path(self.tmpdir) / "task-board.json"
        self.engine = TaskEngine()
        # Mock session dir
        self.orig_session_dir = inspect_session.SESSION_DIR
        inspect_session.SESSION_DIR = Path(self.tmpdir) / "sessions"
        inspect_session.SESSION_DIR.mkdir()

    def tearDown(self):
        task_engine.TASK_BOARD = self.orig_task_board
        inspect_session.SESSION_DIR = self.orig_session_dir
        shutil.rmtree(self.tmpdir)

    def _write_board(self, data):
        task_engine.TASK_BOARD.parent.mkdir(parents=True, exist_ok=True)
        task_engine.TASK_BOARD.write_text(json.dumps(data, ensure_ascii=False))

    def _create_session(self, session_id, age_seconds=0):
        ts = time.time() - age_seconds
        ts_iso = datetime.utcfromtimestamp(ts).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        ts_ms = int(ts * 1000)
        p = inspect_session.SESSION_DIR / f"{session_id}.jsonl"
        with open(p, 'w') as f:
            f.write(json.dumps({
                "type": "message", "timestamp": ts_iso,
                "message": {"role": "assistant", "content": "test",
                             "usage": {"totalTokens": 5000},
                             "timestamp": ts_ms}
            }) + "\n")

    def test_add_task(self):
        """TaskEngine.add creates a task and returns it"""
        task = self.engine.add("Test task", "chat123")
        self.assertEqual(task["status"], "queued")
        self.assertEqual(task["description"], "Test task")
        self.assertEqual(task["source_chat"], "chat123")
        self.assertIn("id", task)

    def test_start_task(self):
        """TaskEngine.start marks task as running"""
        task = self.engine.add("Test task")
        result = self.engine.start(task["id"], "session-key-123")
        self.assertEqual(result["status"], "running")

    def test_complete_task(self):
        """TaskEngine.complete marks task as done"""
        task = self.engine.add("Test task")
        self.engine.start(task["id"])
        result = self.engine.complete(task["id"], "All done")
        self.assertEqual(result["status"], "done")

    def test_fail_task(self):
        """TaskEngine.fail marks task as failed"""
        task = self.engine.add("Test task")
        self.engine.start(task["id"])
        result = self.engine.fail(task["id"], "Something broke")
        self.assertEqual(result["status"], "failed")

    def test_cancel_task(self):
        """TaskEngine.cancel marks task as cancelled"""
        task = self.engine.add("Test task")
        result = self.engine.cancel(task["id"])
        self.assertEqual(result["status"], "cancelled")

    def test_list_tasks(self):
        """TaskEngine.list_tasks returns all tasks"""
        self.engine.add("Task 1")
        self.engine.add("Task 2")
        tasks = self.engine.list_tasks(enrich=False)
        self.assertEqual(len(tasks), 2)

    def test_list_tasks_with_filter(self):
        """TaskEngine.list_tasks with status filter"""
        t1 = self.engine.add("Task 1")
        self.engine.add("Task 2")
        self.engine.start(t1["id"])
        running = self.engine.list_tasks(status_filter="running", enrich=False)
        self.assertEqual(len(running), 1)
        self.assertEqual(running[0]["id"], t1["id"])

    def test_list_tasks_enriched(self):
        """TaskEngine.list_tasks with enrich=True adds SysMonitor data for running tasks"""
        task = self.engine.add("Test task")
        self.engine.start(task["id"], "agent:main:subagent:a0a0-000e")
        self._create_session("a0a0-000e", age_seconds=10)
        tasks = self.engine.list_tasks(enrich=True)
        running = [t for t in tasks if t["status"] == "running"]
        self.assertEqual(len(running), 1)
        self.assertIn("real_status", running[0])
        self.assertIn("total_tokens", running[0])
        self.assertEqual(running[0]["total_tokens"], 5000)

    def test_status(self):
        """TaskEngine.status returns overview dict"""
        self.engine.add("Task 1")
        t2 = self.engine.add("Task 2")
        self.engine.start(t2["id"])
        result = self.engine.status()
        self.assertEqual(result["running"], 1)
        self.assertEqual(result["queued"], 1)
        self.assertEqual(result["total"], 2)

    def test_active(self):
        """TaskEngine.active returns queued + running tasks"""
        t1 = self.engine.add("Task 1")
        self.engine.add("Task 2")
        self.engine.start(t1["id"])
        result = self.engine.active(enrich=False)
        self.assertEqual(len(result), 2)

    def test_ready(self):
        """TaskEngine.ready returns queued tasks with deps met"""
        t1 = self.engine.add("Task 1")
        self.engine.add("Task 2", depends_on=[t1["id"]])
        self.engine.add("Task 3")
        ready = self.engine.ready()
        # t1 and t3 are ready, t2 is blocked
        self.assertEqual(len(ready), 2)

    def test_parse_datetime_z_suffix(self):
        """TaskEngine.parse_datetime handles Z suffix"""
        dt = TaskEngine.parse_datetime("2026-02-10T14:00:00Z")
        self.assertIsNotNone(dt)
        self.assertIsNotNone(dt.tzinfo)

    def test_parse_datetime_empty(self):
        """TaskEngine.parse_datetime handles empty string"""
        dt = TaskEngine.parse_datetime("")
        self.assertIsNotNone(dt)

    def test_parse_datetime_invalid(self):
        """TaskEngine.parse_datetime handles invalid string"""
        dt = TaskEngine.parse_datetime("not-a-date")
        self.assertIsNotNone(dt)

    def test_cleanup(self):
        """TaskEngine.cleanup removes old completed tasks"""
        self._write_board({
            "tasks": [
                {"id": "t001", "status": "done", "description": "old",
                 "completed": (datetime.now(timezone(timedelta(hours=8))) - timedelta(days=10)).isoformat()},
                {"id": "t002", "status": "queued", "description": "active",
                 "completed": None},
            ],
            "next_id": 3,
        })
        removed = self.engine.cleanup(days=7)
        self.assertEqual(removed, 1)

    def test_concurrency_limit(self):
        """TaskEngine.start raises when concurrency limit reached"""
        for i in range(3):
            t = self.engine.add(f"Task {i}")
            self.engine.start(t["id"])
        t4 = self.engine.add("Task 4")
        with self.assertRaises(RuntimeError):
            self.engine.start(t4["id"])

    def test_not_found_raises(self):
        """TaskEngine raises ValueError for non-existent task"""
        with self.assertRaises(ValueError):
            self.engine.start("t999")
        with self.assertRaises(ValueError):
            self.engine.complete("t999")
        with self.assertRaises(ValueError):
            self.engine.fail("t999")
        with self.assertRaises(ValueError):
            self.engine.cancel("t999")

    def test_health_check(self):
        """TaskEngine.health_check detects dead tasks"""
        SGT = timezone(timedelta(hours=8))
        now = datetime.now(SGT)
        self._create_session("a0a0-000d", age_seconds=900)
        self._write_board({
            "tasks": [{
                "id": "t001", "status": "running",
                "description": "Dead task",
                "started": (now - timedelta(minutes=20)).isoformat(),
                "session_key": "agent:main:subagent:a0a0-000d"
            }],
            "next_id": 2,
        })
        result = self.engine.health_check()
        self.assertEqual(len(result["stale"]), 1)
        self.assertIn("无响应", result["stale"][0]["reason"])


class TestIntegrationRealLogs(unittest.TestCase):
    """Integration tests using real OpenClaw session logs (if available)"""

    REAL_SESSION_DIR = Path("/home/ubuntu/.openclaw/agents/main/sessions")

    @unittest.skipUnless(
        Path("/home/ubuntu/.openclaw/agents/main/sessions").exists(),
        "Real session directory not available"
    )
    def test_analyze_real_session(self):
        """Can analyze a real session file without errors"""
        # Find a real .jsonl file
        files = list(self.REAL_SESSION_DIR.glob("*.jsonl"))
        if not files:
            self.skipTest("No .jsonl files found")
        session_id = files[0].stem
        result = inspect_session.analyze_session(session_id)
        self.assertIn("status", result)
        self.assertIn("age_seconds", result)

    @unittest.skipUnless(
        Path("/home/ubuntu/.openclaw/workspace/data/task-board.json").exists(),
        "Real task board not available"
    )
    def test_real_task_board_loads(self):
        """Real task board loads without errors"""
        with open("/home/ubuntu/.openclaw/workspace/data/task-board.json") as f:
            board = json.load(f)
        self.assertIn("tasks", board)
        self.assertIsInstance(board["tasks"], list)

    @unittest.skipUnless(
        Path("/home/ubuntu/.openclaw/agents/main/sessions").exists(),
        "Real session directory not available"
    )
    def test_tail_jsonl_real_file(self):
        """tail_jsonl works on real session files"""
        files = list(self.REAL_SESSION_DIR.glob("*.jsonl"))
        if not files:
            self.skipTest("No .jsonl files found")
        result = inspect_session.tail_jsonl(str(files[0]), 5)
        self.assertIsInstance(result, list)
        for item in result:
            self.assertIsInstance(item, dict)


class TestEdgeCases(unittest.TestCase):
    """Edge cases and potential issues"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.orig_session_dir = inspect_session.SESSION_DIR
        inspect_session.SESSION_DIR = Path(self.tmpdir)

    def tearDown(self):
        inspect_session.SESSION_DIR = self.orig_session_dir
        shutil.rmtree(self.tmpdir)

    def test_path_traversal_attempt(self):
        """Path traversal in session_id is blocked by validation"""
        # Create a file outside sessions dir
        (Path(self.tmpdir).parent / "secret.jsonl").touch()
        result = inspect_session.get_session_file("../secret")
        # Should be None because "../secret" fails regex validation
        self.assertIsNone(result)

    def test_path_traversal_dots_in_uuid(self):
        """Session IDs with dots are rejected"""
        result = inspect_session.get_session_file("../../etc/passwd")
        self.assertIsNone(result)

    def test_valid_uuid_format_accepted(self):
        """Valid hex-and-dash session IDs are accepted"""
        p = Path(self.tmpdir) / "550e8400-e29b-41d4-a716-446655440000.jsonl"
        p.touch()
        result = inspect_session.get_session_file("550e8400-e29b-41d4-a716-446655440000")
        self.assertIsNotNone(result)

    def test_timestamp_zero(self):
        """Timestamp of 0 treated as very old"""
        p = Path(self.tmpdir) / "a0a0-000f.jsonl"
        p.write_text(json.dumps({"type": "message", "timestamp": 0, "message": {
            "role": "assistant", "content": "test", "timestamp": 0
        }}) + "\n")
        result = inspect_session.analyze_session("a0a0-000f")
        self.assertIn("🔴", result["status"])

    def test_missing_timestamp_field(self):
        """Message without timestamp field"""
        p = Path(self.tmpdir) / "a0a0-0010.jsonl"
        p.write_text(json.dumps({"type": "message", "message": {
            "role": "assistant", "content": "test"
        }}) + "\n")
        result = inspect_session.analyze_session("a0a0-0010")
        # Should handle gracefully — timestamp defaults to 0
        self.assertIn("status", result)

    def test_content_as_toolresult(self):
        """Content with toolResult type entries"""
        now_ms = int(time.time() * 1000)
        now_iso = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        p = Path(self.tmpdir) / "a0a0-0011.jsonl"
        p.write_text(json.dumps({
            "type": "message", "timestamp": now_iso,
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "toolResult", "toolName": "web_search"}
                ],
                "timestamp": now_ms
            }
        }) + "\n")
        result = inspect_session.analyze_session("a0a0-0011")
        self.assertIn("[Result: web_search]", result["last_action"])

    def test_session_with_only_session_header(self):
        """Session file that only has the session header line (no messages)"""
        now_iso = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        p = Path(self.tmpdir) / "a0a0-0012.jsonl"
        p.write_text(json.dumps({
            "type": "session", "version": 3,
            "id": "a0a0-0012", "timestamp": now_iso
        }) + "\n")
        result = inspect_session.analyze_session("a0a0-0012")
        # Should work — the session header has a timestamp
        self.assertIn("status", result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
