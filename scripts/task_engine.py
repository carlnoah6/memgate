#!/usr/bin/env python3
"""TaskEngine — 统一任务管理引擎

融合 Board 状态 + SysMonitor 实况，消除代码重复。
所有任务管理逻辑的单一入口。

被以下 CLI 脚本调用：
  - task-manager.py    (状态管理 + 查询)
  - task-health-check.py (健康检查)
  - task-dashboard.py  (看板展示)
  - spawn-task.py      (任务创建调度)
"""

import json
import os
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Import centralized Lark API module
_scripts_dir = str(Path(__file__).parent)
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)
from lark_common import (
    get_tenant_token as _get_tenant_token,
    send_message as _lark_send_message,
    APP_ID as LARK_APP_ID,
    APP_SECRET as LARK_APP_SECRET,
    CARL_OPEN_ID as _CARL_OPEN_ID,
    BOT_OPEN_ID as _BOT_OPEN_ID,
    BASE_URL as _BASE_URL,
)

# Import dashboard auto-updater
from dashboard_updater import update_dashboard as _update_dashboard

# === Constants ===
SGT = timezone(timedelta(hours=8))
BASE = Path("/home/ubuntu/.openclaw/workspace")
TASK_BOARD = BASE / "data" / "task-board.json"
TASK_CHAT_SCRIPT = BASE / "scripts" / "task-chat.py"
MAX_CONCURRENT = 3

# Priority system
PRIORITY_MAP = {"critical": 4, "high": 3, "normal": 2, "low": 1}
PRIORITY_NAMES = {v: k for k, v in PRIORITY_MAP.items()}
PRIORITY_ICONS = {"critical": "🔴", "high": "🟡", "normal": "🟢", "low": "🔵"}
AGING_THRESHOLD = 6  # 心跳次数，约 30 分钟

# Health check thresholds
MAX_RUNNING_MINUTES = 60
STALLED_MINUTES = 10
CLEANUP_DAYS = 7

# Routine task patterns — auto-skip chat creation (code guarantee, not LLM-dependent)
ROUTINE_TASK_PATTERNS = [
    "定期检查", "邮件+日历", "每日日报", "日报生成", "早安提醒", "今日日程",
    "Wiki 同步", "wiki同步", "wikiSync", "periodic", "dailyReport", "morningGreeting"
]


class TaskEngine:
    """统一任务管理引擎，融合 Board 状态 + SysMonitor 实况"""

    def __init__(self):
        self._inspect_session = None  # lazy import

    # ─── Shared Infrastructure ────────────────────────────

    @staticmethod
    def load_board() -> dict:
        """统一加载任务面板（绝对路径，错误处理）"""
        if TASK_BOARD.exists():
            try:
                with open(TASK_BOARD) as f:
                    board = json.load(f)
            except (json.JSONDecodeError, ValueError):
                return {"tasks": [], "daily_date": "", "daily_seq": 0}
        else:
            return {"tasks": [], "daily_date": "", "daily_seq": 0}
        # Backward compat
        for t in board.get("tasks", []):
            t.setdefault("priority", "normal")
            t.setdefault("priority_value", 2)
            t.setdefault("priority_boosted", False)
            t.setdefault("queued_heartbeats", 0)
        return board

    @staticmethod
    def save_board(board: dict):
        """统一保存任务面板"""
        os.makedirs(os.path.dirname(TASK_BOARD), exist_ok=True)
        with open(TASK_BOARD, "w") as f:
            json.dump(board, f, indent=2, ensure_ascii=False)

    @staticmethod
    def parse_datetime(s: str) -> datetime:
        """统一日期解析"""
        if not s:
            return datetime.now(SGT)
        try:
            if s.endswith("Z"):
                s = s[:-1] + "+00:00"
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=SGT)
            return dt
        except Exception:
            return datetime.now(SGT)

    @staticmethod
    def now_iso() -> str:
        """当前时间 ISO 格式"""
        return datetime.now(SGT).isoformat()

    @staticmethod
    def send_notification(chat_id: str, message: str):
        """统一 Lark 消息发送"""
        if not chat_id:
            return
        try:
            _lark_send_message(chat_id, message)
        except Exception:
            pass

    @staticmethod
    def dissolve_chat(chat_id: str):
        """解散任务群聊（如果存在）"""
        if not chat_id:
            return
        try:
            subprocess.run(
                ["python3", str(TASK_CHAT_SCRIPT), "dissolve", chat_id],
                timeout=15, capture_output=True,
            )
        except Exception:
            pass

    # ─── SysMonitor Integration ───────────────────────────

    def _get_inspect_session(self):
        """Lazy import inspect_session module"""
        if self._inspect_session is None:
            try:
                import inspect_session
                self._inspect_session = inspect_session
            except ImportError:
                return None
        return self._inspect_session

    def _enrich_task(self, task: dict) -> dict:
        """为 running 任务融合 SysMonitor 实况数据"""
        enriched = dict(task)
        enriched.setdefault("priority", "normal")
        enriched.setdefault("priority_value", 2)
        enriched["priority_icon"] = PRIORITY_ICONS.get(enriched["priority"], "🟢")

        if task.get("started"):
            start = self.parse_datetime(task["started"])
            elapsed_min = round((datetime.now(SGT) - start).total_seconds() / 60, 1)
            enriched["elapsed_min"] = elapsed_min

        if task.get("status") == "running" and task.get("session_key"):
            inspector = self._get_inspect_session()
            if inspector:
                try:
                    info = inspector.analyze_session(task["session_key"])
                    if "error" not in info and info.get("status") != "empty":
                        enriched["real_status"] = info.get("status", "⚪ Unknown")
                        enriched["age_seconds"] = info.get("age_seconds", 0)
                        enriched["total_tokens"] = info.get("total_tokens", 0)
                        enriched["last_action"] = info.get("last_action", "")
                    else:
                        enriched["real_status"] = "⚪ No Data"
                except Exception:
                    enriched["real_status"] = "⚪ Error"
            else:
                enriched["real_status"] = "⚪ No Inspector"

        return enriched

    # ─── Internal Helpers ─────────────────────────────────

    CARL_OPEN_ID = _CARL_OPEN_ID
    BOT_OPEN_ID = _BOT_OPEN_ID

    def _create_task_chat(self, task_id: str, description: str) -> str | None:
        """创建任务群聊，返回 chat_id"""
        try:
            token = _get_tenant_token()
            display_name = description[:30] if len(description) > 30 else description
            body = json.dumps({
                "name": f"🤖 {task_id} {display_name}",
                "description": f"Luna OS 子任务: {description}",
                "user_id_list": [self.CARL_OPEN_ID],
                "chat_mode": "group",
                "chat_type": "private",
            }).encode()
            req = urllib.request.Request(
                f"{_BASE_URL}/im/v1/chats?set_bot_manager=true",
                data=body,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read())

            if result.get("code") != 0:
                return None

            chat_id = result["data"]["chat_id"]

            try:
                mod_body = json.dumps({
                    "moderation_setting": "moderator_list",
                    "moderator_added_list": [self.BOT_OPEN_ID],
                }).encode()
                req_mod = urllib.request.Request(
                    f"{_BASE_URL}/im/v1/chats/{chat_id}/moderation",
                    data=mod_body,
                    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                    method="PUT",
                )
                urllib.request.urlopen(req_mod, timeout=10)
            except Exception:
                pass

            self.send_notification(
                chat_id,
                f"🚀 任务 {task_id} 已创建\n\n📋 {description}\n\n子任务会在这里更新进度。"
            )
            return chat_id
        except Exception:
            return None

    def _detect_cycle(self, board: dict, new_task_id: str = None, new_deps: list = None) -> list:
        """检测依赖环"""
        adj = {}
        for t in board["tasks"]:
            adj[t["id"]] = list(t.get("depends_on", []))
        if new_task_id and new_deps:
            adj[new_task_id] = list(new_deps)

        WHITE, GRAY, BLACK = 0, 1, 2
        color = {node: WHITE for node in adj}
        parent = {}

        def dfs(u):
            color[u] = GRAY
            for v in adj.get(u, []):
                if v not in color: color[v] = WHITE
                if color.get(v) == GRAY:
                    cycle = [v, u]
                    cur = u
                    while cur != v and cur in parent:
                        cur = parent[cur]
                        cycle.append(cur)
                    cycle.reverse()
                    return cycle
                if color.get(v) == WHITE:
                    parent[v] = u
                    if dfs(v): return dfs(v)
            color[u] = BLACK
            return []

        for node in list(adj.keys()):
            if color.get(node) == WHITE:
                if dfs(node): return dfs(node)
        return []

    def _get_done_ids(self, board: dict) -> set:
        return {t["id"] for t in board["tasks"] if t["status"] == "done"}

    def _get_ready_tasks(self, board: dict, just_completed: str = None) -> list:
        done_ids = self._get_done_ids(board)
        ready = []
        for t in board["tasks"]:
            if t["status"] != "queued": continue
            deps = t.get("depends_on", [])
            if not deps or all(d in done_ids for d in deps):
                ready.append(t)
        ready.sort(key=lambda t: (-t.get("priority_value", 2), t.get("created", "")))
        return ready

    def _dissolve_task_chat(self, task: dict):
        """发送完成通知（不自动解散）"""
        chat_id = task.get("task_chat_id")
        if not chat_id: return
        status = task.get("status", "done")
        result = task.get("result", "")
        tid = task.get("id", "?")
        icon = "✅" if status == "done" else "❌" if status == "failed" else "🚫"
        msg = f"{icon} 任务 {tid} {status}\n\n{result}\n\n📌 此群不会自动解散，请手动关闭。"
        self.send_notification(chat_id, msg)

    def _kill_subagent_session(self, task: dict):
        """终止关联的 subagent session（如果正在运行）"""
        session_key = task.get("session_key")
        if not session_key:
            return
        # Only kill subagent sessions
        if "subagent" not in session_key:
            return
        
        import glob
        # Extract session UUID from session_key (format: agent:main:subagent:<uuid>)
        parts = session_key.split(":")
        if len(parts) < 4:
            return
        session_uuid = parts[-1]
        
        # Find and truncate transcript file
        transcript_pattern = f"/home/ubuntu/.openclaw/agents/main/sessions/{session_uuid}.jsonl"
        transcript_files = glob.glob(transcript_pattern)
        if transcript_files:
            try:
                # Truncate transcript to effectively kill the session
                open(transcript_files[0], 'w').close()
            except Exception:
                pass
        
        # Reset session state in sessions.json
        sessions_json_path = Path("/home/ubuntu/.openclaw/agents/main/sessions/sessions.json")
        if sessions_json_path.exists():
            try:
                with open(sessions_json_path, 'r') as f:
                    sessions = json.load(f)
                if session_key in sessions:
                    sessions[session_key]["systemSent"] = False
                    sessions[session_key]["totalTokens"] = 0
                    with open(sessions_json_path, 'w') as f:
                        json.dump(sessions, f, indent=2)
            except Exception:
                pass

    def _notify_source_chat(self, task: dict, message: str):
        self.send_notification(task.get("source_chat"), message)

    # ─── State Management ───────────────

    def find_duplicate(self, description: str) -> str | None:
        board = self.load_board()
        desc_norm = description.strip().lower()
        for t in board["tasks"]:
            if t["status"] in ("running", "queued"):
                if t["description"].strip().lower() == desc_norm:
                    return t["id"]
        return None

    def _next_task_id(self, board: dict) -> str:
        today = datetime.now(SGT).strftime("%m%d")
        if board.get("daily_date") != today:
            board["daily_date"] = today
            board["daily_seq"] = 0
        board["daily_seq"] += 1
        return f"tid-{today}-{board['daily_seq']}"

    def add(self, description: str, source_chat: str = None, depends_on: list = None, priority: str = "normal", create_chat: bool = True) -> dict:
        dup_id = self.find_duplicate(description)
        if dup_id:
            raise ValueError(f"Duplicate task: {dup_id} (running/queued)")
        
        board = self.load_board()
        task_id = self._next_task_id(board)

        if depends_on:
            if self._detect_cycle(board, task_id, depends_on):
                raise ValueError("Cycle detected")

        task = {
            "id": task_id,
            "status": "queued",
            "description": description,
            "created": self.now_iso(),
            "started": None,
            "session_key": None,
            "source_chat": source_chat,
            "depends_on": depends_on or [],
            "result": None,
            "completed": None,
            "priority": priority,
            "priority_value": PRIORITY_MAP.get(priority, 2),
            "queued_heartbeats": 0,
        }
        board["tasks"].append(task)
        self.save_board(board)

        if create_chat and self._is_routine_task(description):
            create_chat = False
        
        if create_chat:
            cid = self._create_task_chat(task_id, description)
            if cid:
                task["task_chat_id"] = cid
                self.save_board(board)
        
        return task

    @staticmethod
    def _is_routine_task(description: str) -> bool:
        desc_lower = description.lower()
        return any(p.lower() in desc_lower for p in ROUTINE_TASK_PATTERNS)

    def start(self, task_id: str, session_key: str = ""):
        board = self.load_board()
        running = sum(1 for t in board["tasks"] if t["status"] == "running")
        if running >= MAX_CONCURRENT:
            raise RuntimeError(f"Queue full: {running}/{MAX_CONCURRENT}")
        
        for t in board["tasks"]:
            if t["id"] == task_id:
                t["status"] = "running"
                t["session_key"] = session_key
                t["started"] = self.now_iso()
                self.save_board(board)
                # Auto-update dashboard after state change
                _update_dashboard(trigger="task_start")
                res = {"id": task_id, "status": "running"}
                if not session_key:
                    res["warning"] = "⚠️ No session_key provided"
                return res
        raise ValueError(f"Task {task_id} not found")

    def complete(self, task_id: str, result: str = "") -> dict:
        board = self.load_board()
        for t in board["tasks"]:
            if t["id"] == task_id:
                t["status"] = "done"
                t["result"] = result
                t["completed"] = self.now_iso()
                self._dissolve_task_chat(t)
                self._notify_source_chat(t, f"✅ {task_id} 完成: {result}")
                self.save_board(board)
                # Auto-update dashboard after state change
                _update_dashboard(trigger="task_complete")
                unblocked = self._get_ready_tasks(board)
                out = {"id": task_id, "status": "done"}
                if unblocked:
                    out["unblocked"] = [u["id"] for u in unblocked]
                return out
        raise ValueError(f"Task {task_id} not found")

    def fail(self, task_id: str, error: str = "") -> dict:
        board = self.load_board()
        for t in board["tasks"]:
            if t["id"] == task_id:
                t["status"] = "failed"
                t["result"] = error
                t["completed"] = self.now_iso()
                self._dissolve_task_chat(t)
                self._notify_source_chat(t, f"❌ {task_id} 失败: {error}")
                self.save_board(board)
                # Auto-update dashboard after state change
                _update_dashboard(trigger="task_fail")
                return {"id": task_id, "status": "failed"}
        raise ValueError(f"Task {task_id} not found")

    def cancel(self, task_id: str) -> dict:
        board = self.load_board()
        for t in board["tasks"]:
            if t["id"] == task_id:
                t["status"] = "cancelled"
                t["completed"] = self.now_iso()
                # Kill associated subagent session if running
                self._kill_subagent_session(t)
                self._dissolve_task_chat(t)
                self.save_board(board)
                # Auto-update dashboard after state change
                _update_dashboard(trigger="task_cancel")
                return {"id": task_id, "status": "cancelled"}
        raise ValueError(f"Task {task_id} not found")

    def list_tasks(self, status_filter: str = None, enrich: bool = True) -> list:
        board = self.load_board()
        tasks = board["tasks"]
        if status_filter:
            tasks = [t for t in tasks if t["status"] == status_filter]
        if enrich:
            return [self._enrich_task(t) for t in tasks]
        return list(tasks)

    def status(self) -> dict:
        board = self.load_board()
        tasks = board["tasks"]
        today = datetime.now(SGT).strftime("%Y-%m-%d")
        ready = self._get_ready_tasks(board)
        running = [t for t in tasks if t["status"] == "running"]
        
        return {
            "running": len(running),
            "queued": sum(1 for t in tasks if t["status"] == "queued"),
            "ready": len(ready),
            "done_today": sum(1 for t in tasks if t["status"] == "done" and (t.get("completed") or "").startswith(today)),
            "failed_today": sum(1 for t in tasks if t["status"] == "failed" and (t.get("completed") or "").startswith(today)),
            "total": len(tasks),
        }

    def ready(self) -> list:
        board = self.load_board()
        return [
            {
                "id": t["id"],
                "description": t["description"],
                "source_chat": t.get("source_chat"),
                "depends_on": t.get("depends_on", [])
            }
            for t in self._get_ready_tasks(board)
        ]

    def active(self, enrich: bool = True) -> list:
        board = self.load_board()
        active = [t for t in board["tasks"] if t["status"] in ("queued", "running")]
        return [self._enrich_task(t) if enrich else t for t in active]

    def get_task(self, task_id: str) -> dict | None:
        """获取单个任务详情。"""
        board = self.load_board()
        for t in board["tasks"]:
            if t["id"] == task_id:
                return self._enrich_task(t)
        return None

    def set_session_key(self, task_id: str, session_key: str):
        board = self.load_board()
        for t in board["tasks"]:
            if t["id"] == task_id:
                t["session_key"] = session_key
                self.save_board(board)
                return {"id": task_id, "session_key": session_key}
        raise ValueError(f"Task {task_id} not found")

    def cleanup(self, days: int = 7) -> int:
        board = self.load_board()
        cutoff = datetime.now(SGT) - timedelta(days=days)
        before = len(board["tasks"])
        board["tasks"] = [
            t for t in board["tasks"]
            if t["status"] in ("queued", "running")
            or (t.get("completed") and self.parse_datetime(t["completed"]) > cutoff)
        ]
        self.save_board(board)
        return before - len(board["tasks"])

    def health_check(self) -> dict:
        """
        健康检查：检测卡死/超时任务，清理旧数据
        返回 {"stale": [...], "active": [...], "cleaned": N}
        """
        board = self.load_board()
        now = datetime.now(SGT)
        result = {"stale": [], "active": [], "cleaned": 0}

        inspector = self._get_inspect_session()

        # 1. Inspect running tasks
        for t in board.get("tasks", []):
            if t["status"] == "running":
                # Check 1: Zombie task (started > 2m ago but no session_key)
                # "cron-pending" means spawn is scheduled via cron, give it 5 min
                sk = t.get("session_key", "")
                zombie_threshold = 5 if sk == "cron-pending" else 2
                if (not sk or sk == "cron-pending") and t.get("started"):
                    try:
                        started = self.parse_datetime(t["started"])
                        elapsed = (now - started).total_seconds() / 60
                        if elapsed > zombie_threshold:
                            t["status"] = "failed"
                            t["result"] = f"僵尸任务：从未实际启动 ({elapsed:.0f}m)"
                            t["completed"] = self.now_iso()
                            result["stale"].append({
                                "id": t["id"],
                                "reason": "never_spawned",
                                "description": t["description"]
                            })
                            continue
                    except Exception:
                        pass

                # Check 2: Hard timeout
                elapsed_total = 0
                if t.get("started"):
                    try:
                        started = self.parse_datetime(t["started"])
                        elapsed_total = (now - started).total_seconds() / 60
                    except Exception:
                        pass

                is_dead = False
                dead_reason = ""

                # Kernel-level inspection (if available)
                if t.get("session_key") and t["session_key"] != "cron-pending" and inspector:
                    try:
                        info = inspector.analyze_session(t["session_key"])
                        if "error" in info:
                            is_dead = True
                            dead_reason = f"Session 异常: {info.get('error')}"
                        age = info.get("age_seconds", 0)
                        if not is_dead and age > STALLED_MINUTES * 60:
                            is_dead = True
                            dead_reason = f"无响应 ({age:.0f}s > {STALLED_MINUTES}m)"
                    except Exception:
                        pass

                if elapsed_total > MAX_RUNNING_MINUTES:
                    is_dead = True
                    dead_reason = f"超时 ({elapsed_total:.0f}m > {MAX_RUNNING_MINUTES}m)"

                if is_dead:
                    t["status"] = "failed"
                    t["result"] = f"健康检查失败: {dead_reason}"
                    t["completed"] = self.now_iso()
                    self._dissolve_task_chat(t)  # Notify chat
                    result["stale"].append({
                        "id": t["id"],
                        "description": t["description"],
                        "reason": dead_reason,
                    })
                else:
                    result["active"].append({
                        "id": t["id"],
                        "description": t["description"],
                        "elapsed_min": round(elapsed_total, 1),
                    })
            elif t["status"] == "queued":
                # Priority aging logic could go here
                pass

        # 2. Auto-dissolve old chats (>24h after completion)
        dissolve_cutoff = now - timedelta(hours=24)
        for t in board["tasks"]:
            if t["status"] in ("done", "failed", "cancelled") and t.get("task_chat_id"):
                if not t.get("completed"): continue
                try:
                    comp_time = self.parse_datetime(t["completed"])
                    if comp_time < dissolve_cutoff:
                        # Time to dissolve
                        self.dissolve_chat(t["task_chat_id"])
                        t["task_chat_id"] = None
                except Exception:
                    pass

        # 3. Cleanup old tasks
        before = len(board["tasks"])
        cutoff = now - timedelta(days=CLEANUP_DAYS)
        board["tasks"] = [
            t for t in board["tasks"]
            if t["status"] in ("queued", "running")
            or (t.get("completed") and self.parse_datetime(t["completed"]) > cutoff)
        ]
        result["cleaned"] = before - len(board["tasks"])

        if result["stale"] or result["cleaned"] > 0:
            self.save_board(board)
        
        # Heartbeat: update dashboard as fallback (with rate limiting)
        _update_dashboard(trigger="heartbeat")

        return result
