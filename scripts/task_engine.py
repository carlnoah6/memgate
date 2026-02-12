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
# Tasks matching any of these patterns are routine/periodic and don't need a group chat.
ROUTINE_TASK_PATTERNS = [
    "定期检查",          # periodic check
    "邮件+日历",         # email+calendar check
    "每日日报",          # daily report
    "日报生成",          # daily report generation
    "早安提醒",          # morning greeting
    "今日日程",          # today's schedule
    "Wiki 同步",         # wiki sync
    "wiki同步",          # wiki sync alt
    "wikiSync",          # wiki sync key
    "periodic",          # periodic key
    "dailyReport",       # daily report key
    "morningGreeting",   # morning greeting key
]

# Lark API
LARK_APP_ID = "cli_a90c3a6163785ed2"
LARK_APP_SECRET = "***LARK_SECRET_REMOVED***"

# Add scripts dir to path for inspect_session import
_scripts_dir = str(Path(__file__).parent)
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)


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
        # Backward compat: ensure priority fields exist on old tasks
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
        """统一日期解析（处理 Z 后缀、时区、异常）"""
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
        """统一 Lark 消息发送（代码保证，不依赖 LLM）"""
        if not chat_id:
            return
        try:
            # Get tenant token
            token_req = urllib.request.Request(
                "https://open.larksuite.com/open-apis/auth/v3/tenant_access_token/internal",
                data=json.dumps({
                    "app_id": LARK_APP_ID,
                    "app_secret": LARK_APP_SECRET,
                }).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(token_req, timeout=10) as resp:
                token = json.loads(resp.read())["tenant_access_token"]

            # Send message
            send_body = json.dumps({
                "receive_id": chat_id,
                "msg_type": "text",
                "content": json.dumps({"text": message}),
            }).encode()
            send_req = urllib.request.Request(
                "https://open.larksuite.com/open-apis/im/v1/messages?receive_id_type=chat_id",
                data=send_body,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(send_req, timeout=10) as resp:
                pass
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
            pass  # health-check 会在下次心跳重试

    # ─── SysMonitor Integration ───────────────────────────

    def _get_inspect_session(self):
        """Lazy import inspect_session module"""
        if self._inspect_session is None:
            import inspect_session
            self._inspect_session = inspect_session
        return self._inspect_session

    def _enrich_task(self, task: dict) -> dict:
        """为 running 任务融合 SysMonitor 实况数据"""
        enriched = dict(task)

        # Ensure priority fields
        enriched.setdefault("priority", "normal")
        enriched.setdefault("priority_value", 2)
        enriched["priority_icon"] = PRIORITY_ICONS.get(enriched["priority"], "🟢")

        # Calculate elapsed time
        if task.get("started"):
            start = self.parse_datetime(task["started"])
            elapsed_min = round((datetime.now(SGT) - start).total_seconds() / 60, 1)
            enriched["elapsed_min"] = elapsed_min

        # For running tasks with session_key, fetch SysMonitor data
        if task.get("status") == "running" and task.get("session_key"):
            try:
                inspector = self._get_inspect_session()
                info = inspector.analyze_session(task["session_key"])
                if "error" not in info and info.get("status") != "empty":
                    enriched["real_status"] = info.get("status", "⚪ Unknown")
                    enriched["age_seconds"] = info.get("age_seconds", 0)
                    enriched["total_tokens"] = info.get("total_tokens", 0)
                    enriched["last_action"] = info.get("last_action", "")
                    enriched["last_active_ago"] = info.get("last_active_ago", "")
                    enriched["last_active_time"] = info.get("last_active_time", "")
                else:
                    enriched["real_status"] = "⚪ No Data"
                    enriched["age_seconds"] = None
                    enriched["total_tokens"] = 0
                    enriched["last_action"] = info.get("error", "")
            except Exception:
                enriched["real_status"] = "⚪ Error"
                enriched["age_seconds"] = None
                enriched["total_tokens"] = 0
                enriched["last_action"] = ""

        return enriched

    # ─── Internal Helpers ─────────────────────────────────

    # Carl's open_id for task group chats
    CARL_OPEN_ID = "ou_35f664e694dd100adf97b867e68e1d3a"
    BOT_OPEN_ID = "ou_88371dccab8541963f7f6a108990d7b3"

    def _create_task_chat(self, task_id: str, description: str) -> str | None:
        """创建任务群聊，返回 chat_id。失败返回 None（不阻塞任务创建）。"""
        try:
            # Get tenant token
            token_req = urllib.request.Request(
                "https://open.larksuite.com/open-apis/auth/v3/tenant_access_token/internal",
                data=json.dumps({
                    "app_id": LARK_APP_ID,
                    "app_secret": LARK_APP_SECRET,
                }).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(token_req, timeout=10) as resp:
                token = json.loads(resp.read())["tenant_access_token"]

            # Truncate name for Lark group name limit
            display_name = description[:30] if len(description) > 30 else description

            # Create group chat
            body = json.dumps({
                "name": f"🤖 {task_id} {display_name}",
                "description": f"Luna OS 子任务: {description}",
                "user_id_list": [self.CARL_OPEN_ID],
                "chat_mode": "group",
                "chat_type": "private",
            }).encode()
            create_req = urllib.request.Request(
                "https://open.larksuite.com/open-apis/im/v1/chats?set_bot_manager=true",
                data=body,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(create_req, timeout=15) as resp:
                result = json.loads(resp.read())

            if result.get("code") != 0:
                return None

            chat_id = result["data"]["chat_id"]

            # 设置发言权限：仅 Bot 可发言，Carl 只读（代码保证）
            try:
                mod_body = json.dumps({
                    "moderation_setting": "moderator_list",
                    "moderator_added_list": [self.BOT_OPEN_ID],
                }).encode()
                mod_req = urllib.request.Request(
                    f"https://open.larksuite.com/open-apis/im/v1/chats/{chat_id}/moderation",
                    data=mod_body,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                    },
                    method="PUT",
                )
                urllib.request.urlopen(mod_req, timeout=10)
            except Exception:
                pass  # 设置失败不阻塞

            # Send welcome message (best-effort)
            self.send_notification(
                chat_id,
                f"🚀 任务 {task_id} 已创建\n\n"
                f"📋 {description}\n\n"
                f"子任务会在这里更新进度。"
            )

            return chat_id
        except Exception:
            return None  # 建群失败不阻塞任务创建

    def _detect_cycle(self, board: dict, new_task_id: str = None, new_deps: list = None) -> list:
        """检测依赖图中的环。返回环路径（如 ['t001','t002','t001']），无环返回空列表。
        如果提供 new_task_id + new_deps，会模拟添加后再检测。"""
        # Build adjacency: task -> depends_on (edges point from task to its dependencies)
        adj = {}
        for t in board["tasks"]:
            adj[t["id"]] = list(t.get("depends_on", []))
        if new_task_id and new_deps:
            adj[new_task_id] = list(new_deps)

        # DFS cycle detection
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {node: WHITE for node in adj}
        parent = {}

        def dfs(u):
            color[u] = GRAY
            for v in adj.get(u, []):
                if v not in color:
                    color[v] = WHITE  # unknown node, treat as no deps
                if color.get(v) == GRAY:
                    # Found cycle, reconstruct path
                    cycle = [v, u]
                    cur = u
                    while cur != v and cur in parent:
                        cur = parent[cur]
                        cycle.append(cur)
                    cycle.reverse()
                    return cycle
                if color.get(v) == WHITE:
                    parent[v] = u
                    result = dfs(v)
                    if result:
                        return result
            color[u] = BLACK
            return []

        for node in list(adj.keys()):
            if color.get(node) == WHITE:
                result = dfs(node)
                if result:
                    return result
        return []

    def _build_graph_dot(self, board: dict) -> str:
        """生成 Graphviz DOT 格式的任务依赖图"""
        lines = ['digraph TaskGraph {']
        lines.append('  rankdir=LR;')
        lines.append('  node [shape=box, style=rounded, fontname="Noto Sans CJK SC", fontsize=10];')
        lines.append('  edge [color="#666666"];')
        lines.append('')

        # Status -> visual style
        style_map = {
            "queued":    'fillcolor="#FFF3E0", style="rounded,filled"',    # orange-light
            "running":   'fillcolor="#E3F2FD", style="rounded,filled"',    # blue-light
            "done":      'fillcolor="#E8F5E9", style="rounded,filled"',    # green-light
            "failed":    'fillcolor="#FFEBEE", style="rounded,filled"',    # red-light
            "cancelled": 'fillcolor="#F5F5F5", style="rounded,filled"',    # grey-light
        }

        # Status emoji (text fallback for graphviz)
        emoji_map = {
            "queued": "[排队]", "running": "[运行中]", "done": "[完成]",
            "failed": "[失败]", "cancelled": "[取消]",
        }

        for t in board["tasks"]:
            tid = t["id"]
            status = t.get("status", "queued")
            desc = t.get("description", "")[:40].replace('"', '\\"')
            emoji = emoji_map.get(status, "")
            style = style_map.get(status, '')
            pri = t.get("priority", "normal")
            pri_tag = f" [{pri.upper()}]" if pri != "normal" else ""
            label = f"{tid}{pri_tag}\\n{emoji} {desc}"
            lines.append(f'  "{tid}" [label="{label}", {style}];')

        lines.append('')

        # Edges: task -> dependency (reversed for visual: dependency -> task means "must finish before")
        for t in board["tasks"]:
            tid = t["id"]
            for dep in t.get("depends_on", []):
                lines.append(f'  "{dep}" -> "{tid}";')

        lines.append('}')
        return '\n'.join(lines)

    def render_graph(self, output_path: str = None, fmt: str = "png") -> str:
        """渲染任务依赖图。返回输出文件路径。"""
        board = self.load_board()
        dot_content = self._build_graph_dot(board)

        if output_path is None:
            output_path = str(BASE / "data" / f"task-graph.{fmt}")
        dot_path = output_path + ".dot"

        with open(dot_path, "w") as f:
            f.write(dot_content)

        # Try graphviz
        try:
            subprocess.run(
                ["dot", f"-T{fmt}", dot_path, "-o", output_path],
                check=True, capture_output=True
            )
            os.remove(dot_path)
            return output_path
        except (FileNotFoundError, subprocess.CalledProcessError):
            # graphviz not installed, return dot file
            return dot_path

    def check_cycle(self) -> list:
        """公开接口：检测当前任务图的环"""
        board = self.load_board()
        return self._detect_cycle(board)

    def _get_done_ids(self, board: dict) -> set:
        """Get set of completed task IDs"""
        return {t["id"] for t in board["tasks"] if t["status"] == "done"}

    def _get_ready_tasks(self, board: dict, just_completed: str = None) -> list:
        """Find tasks that are queued and have all dependencies met"""
        done_ids = self._get_done_ids(board)
        ready = []
        for t in board["tasks"]:
            if t["status"] != "queued":
                continue
            deps = t.get("depends_on", [])
            if not deps or all(d in done_ids for d in deps):
                ready.append(t)
        # Sort: priority_value DESC, then created ASC (FIFO within same priority)
        ready.sort(key=lambda t: (-t.get("priority_value", 2), t.get("created", "")))
        return ready

    def _dissolve_task_chat(self, task: dict):
        """发送完成通知到任务群聊（不解散，留给用户手动关闭）"""
        chat_id = task.get("task_chat_id")
        if not chat_id:
            return
        status = task.get("status", "done")
        result_text = task.get("result", "")
        task_id = task.get("id", "?")
        if status == "done":
            msg = f"✅ 任务 {task_id} 已完成\n\n{result_text}\n\n📌 此群不会自动解散，查看完毕后可手动关闭。"
        elif status == "failed":
            msg = f"❌ 任务 {task_id} 失败\n\n{result_text}\n\n📌 此群不会自动解散，查看完毕后可手动关闭。"
        elif status == "cancelled":
            msg = f"🚫 任务 {task_id} 已取消\n\n📌 此群不会自动解散，查看完毕后可手动关闭。"
        else:
            msg = f"任务 {task_id} 状态: {status}"
        self.send_notification(chat_id, msg)
        # 不再清除 task_chat_id，也不解散群

    def _notify_source_chat(self, task: dict, message: str):
        """发送结果消息到源 chat"""
        self.send_notification(task.get("source_chat"), message)

    # ─── State Management (原 task-manager) ───────────────

    def find_duplicate(self, description: str) -> str | None:
        """检查是否有相同描述的 running/queued 任务，返回 task_id 或 None"""
        board = self.load_board()
        desc_normalized = description.strip().lower()
        for t in board["tasks"]:
            if t["status"] in ("running", "queued"):
                if t["description"].strip().lower() == desc_normalized:
                    return t["id"]
        return None

    def _next_task_id(self, board: dict) -> str:
        """生成下一个任务 ID: tid-MMDD-N（每日计数，不补零）"""
        today = datetime.now(SGT).strftime("%m%d")
        daily = board.get("daily_date", "")
        seq = board.get("daily_seq", 0)
        if daily != today:
            # 新的一天，重置计数
            board["daily_date"] = today
            seq = 0
        seq += 1
        board["daily_seq"] = seq
        return f"tid-{today}-{seq}"

    def add(self, description: str, source_chat: str = None, depends_on: list = None, priority: str = "normal", create_chat: bool = True) -> dict:
        """创建新任务，返回 task dict。如果依赖会形成环则抛出 ValueError。重复任务会抛出 ValueError。"""
        # 去重：检查是否已有相同描述的 running/queued 任务
        dup_id = self.find_duplicate(description)
        if dup_id:
            raise ValueError(f"Duplicate task: {dup_id} already has the same description (status: running/queued). Use a different description or cancel the existing task first.")
        board = self.load_board()
        task_id = self._next_task_id(board)

        # 环检测：模拟添加后检测
        if depends_on:
            cycle = self._detect_cycle(board, task_id, depends_on)
            if cycle:
                cycle_str = " → ".join(cycle)
                raise ValueError(f"Cycle detected: {cycle_str}. Task not created.")

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
            "priority_boosted": False,
            "queued_heartbeats": 0,
        }
        board["tasks"].append(task)
        self.save_board(board)

        # 代码强制：自动创建任务群聊（不依赖 LLM 记得调用）
        # 自动检测例行任务 → 跳过建群（代码保证，不靠 LLM 传 --no-chat）
        if create_chat and self._is_routine_task(description):
            create_chat = False
        if create_chat:
            chat_id = self._create_task_chat(task_id, description)
            if chat_id:
                task["task_chat_id"] = chat_id
                self.save_board(board)

        return task

    @staticmethod
    def _is_routine_task(description: str) -> bool:
        """检测是否为例行任务（匹配 ROUTINE_TASK_PATTERNS）。代码保证，不依赖 LLM。"""
        desc_lower = description.lower()
        return any(p.lower() in desc_lower for p in ROUTINE_TASK_PATTERNS)

    def start(self, task_id: str, session_key: str = ""):
        """标记任务为运行中"""
        board = self.load_board()

        # Check concurrency limit
        running_count = sum(1 for t in board["tasks"] if t["status"] == "running")
        if running_count >= MAX_CONCURRENT:
            raise RuntimeError(f"Queue is full. Running: {running_count}/{MAX_CONCURRENT}")

        for t in board["tasks"]:
            if t["id"] == task_id:
                t["status"] = "running"
                t["session_key"] = session_key
                t["started"] = self.now_iso()
                self.save_board(board)
                result = {"id": task_id, "status": "running"}
                if not session_key:
                    result["warning"] = "⚠️ No session_key provided! Task cannot be recovered after restart. Use: task-manager.py set-session <id> <session_key>"
                return result
        raise ValueError(f"Task {task_id} not found")

    def set_session_key(self, task_id: str, session_key: str):
        """为已运行的任务补设 session_key（用于 spawn 返回后补绑定）"""
        if not session_key:
            raise ValueError("session_key cannot be empty")
        board = self.load_board()
        for t in board["tasks"]:
            if t["id"] == task_id:
                if t["status"] != "running":
                    raise ValueError(f"Task {task_id} is '{t['status']}', expected 'running'")
                old_key = t.get("session_key", "")
                t["session_key"] = session_key
                self.save_board(board)
                result = {"id": task_id, "session_key": session_key}
                if old_key:
                    result["replaced"] = old_key
                return result
        raise ValueError(f"Task {task_id} not found")

    def complete(self, task_id: str, result: str = "") -> dict:
        """标记任务完成（自动解锁依赖、解散群聊、通知源 chat）"""
        board = self.load_board()
        for t in board["tasks"]:
            if t["id"] == task_id:
                t["status"] = "done"
                t["result"] = result
                t["completed"] = self.now_iso()
                # 代码强制：解散群聊 + 通知源 chat
                self._dissolve_task_chat(t)
                self._notify_source_chat(
                    t, f"✅ {task_id} 完成: {result}" if result else f"✅ {task_id} 完成"
                )
                self.save_board(board)
                # Show newly unblocked tasks
                unblocked = self._get_ready_tasks(board, just_completed=task_id)
                out = {"id": task_id, "status": "done"}
                if unblocked:
                    out["unblocked"] = [u["id"] for u in unblocked]
                return out
        raise ValueError(f"Task {task_id} not found")

    def fail(self, task_id: str, error: str = "") -> dict:
        """标记任务失败（不级联——失败的任务可以 retry，下游继续等待）"""
        board = self.load_board()
        for t in board["tasks"]:
            if t["id"] == task_id:
                t["status"] = "failed"
                t["result"] = error
                t["completed"] = self.now_iso()
                # 代码强制：解散群聊 + 通知源 chat
                self._dissolve_task_chat(t)
                self._notify_source_chat(
                    t, f"❌ {task_id} 失败: {error}" if error else f"❌ {task_id} 失败"
                )
                self.save_board(board)
                out = {"id": task_id, "status": "failed"}
                # 检查是否有下游任务在等它
                dependents = [dt["id"] for dt in board["tasks"]
                              if dt["status"] == "queued" and task_id in dt.get("depends_on", [])]
                if dependents:
                    out["waiting_dependents"] = dependents
                return out
        raise ValueError(f"Task {task_id} not found")
        raise ValueError(f"Task {task_id} not found")

    def _cascade_cancel(self, board: dict, failed_task_id: str, reason: str) -> list:
        """级联取消所有直接或间接依赖 failed_task_id 的任务。返回被取消的 task_id 列表。"""
        cancelled = []
        # BFS: 找出所有依赖链上的 queued 任务
        queue = [failed_task_id]
        visited = {failed_task_id}
        while queue:
            current = queue.pop(0)
            for t in board["tasks"]:
                if t["status"] != "queued":
                    continue
                if current in t.get("depends_on", []) and t["id"] not in visited:
                    visited.add(t["id"])
                    t["status"] = "cancelled"
                    t["result"] = f"依赖 {failed_task_id} 已{reason}，级联取消"
                    t["completed"] = self.now_iso()
                    self._dissolve_task_chat(t)
                    cancelled.append(t["id"])
                    queue.append(t["id"])  # 继续查找依赖这个任务的下游
        return cancelled

    def cancel(self, task_id: str) -> dict:
        """取消任务（级联取消所有依赖它的下游任务）"""
        board = self.load_board()
        for t in board["tasks"]:
            if t["id"] == task_id:
                t["status"] = "cancelled"
                t["completed"] = self.now_iso()
                self._dissolve_task_chat(t)
                cascaded = self._cascade_cancel(board, task_id, "取消")
                self.save_board(board)
                out = {"id": task_id, "status": "cancelled"}
                if cascaded:
                    out["cascaded"] = cascaded
                return out
        raise ValueError(f"Task {task_id} not found")

    def set_priority(self, task_id: str, priority: str) -> dict:
        """修改任务优先级"""
        if priority not in PRIORITY_MAP:
            raise ValueError(f"Invalid priority: {priority}. Use: {', '.join(PRIORITY_MAP.keys())}")
        board = self.load_board()
        for t in board["tasks"]:
            if t["id"] == task_id:
                t["priority"] = priority
                t["priority_value"] = PRIORITY_MAP[priority]
                self.save_board(board)
                return {"id": task_id, "priority": priority}
        raise ValueError(f"Task {task_id} not found")

    def retry(self, task_id: str) -> dict:
        """重试失败的任务：保持 tid、依赖关系和 session_key 不变。
        
        session_key 保留是因为：
        - sessions_send 可以恢复已有 session（带完整上下文）
        - agent 知道之前做到哪了、错在哪，不重复已完成的步骤
        - 只有当 session 确认不可恢复时，spawn 流程才会清空并创建新 session
        """
        board = self.load_board()
        for t in board["tasks"]:
            if t["id"] == task_id:
                if t["status"] not in ("failed", "cancelled"):
                    raise ValueError(f"Task {task_id} status is '{t['status']}', only failed/cancelled tasks can be retried")
                old_session = t.get("session_key")
                t["status"] = "queued"
                # 保留 session_key！让调度器优先尝试 sessions_send 恢复
                t["result"] = None
                t["completed"] = None
                t["started"] = None
                t["queued_heartbeats"] = 0
                t["priority_boosted"] = False
                self.save_board(board)
                out = {"id": task_id, "status": "queued", "description": t["description"]}
                if old_session:
                    out["resume_session"] = old_session
                return out
        raise ValueError(f"Task {task_id} not found")

    # ─── Queries (with SysMonitor enrichment) ─────────────

    def list_tasks(self, status_filter: str = None, enrich: bool = True) -> list:
        """列出任务，enrich=True 时自动融合 SysMonitor 实况"""
        board = self.load_board()
        tasks = board["tasks"]
        if status_filter:
            tasks = [t for t in tasks if t["status"] == status_filter]
        if enrich:
            return [self._enrich_task(t) for t in tasks]
        return list(tasks)

    def status(self) -> dict:
        """快速状态概览（JSON），含 SysMonitor 融合数据"""
        board = self.load_board()
        tasks = board["tasks"]
        today = datetime.now(SGT).strftime("%Y-%m-%d")
        ready = self._get_ready_tasks(board)

        running_tasks = [t for t in tasks if t["status"] == "running"]
        # Enrich running tasks for status summary
        enriched_running = [self._enrich_task(t) for t in running_tasks]

        result = {
            "running": len(running_tasks),
            "queued": sum(1 for t in tasks if t["status"] == "queued"),
            "ready": len(ready),
            "done_today": sum(
                1 for t in tasks
                if t["status"] == "done" and (t.get("completed") or "").startswith(today)
            ),
            "failed_today": sum(
                1 for t in tasks
                if t["status"] == "failed" and (t.get("completed") or "").startswith(today)
            ),
            "total": len(tasks),
        }

        # Add running task details with SysMonitor data
        if enriched_running:
            result["running_details"] = []
            for t in enriched_running:
                detail = {
                    "id": t["id"],
                    "description": t["description"],
                    "elapsed_min": t.get("elapsed_min"),
                    "priority": t.get("priority", "normal"),
                }
                if "real_status" in t:
                    detail["real_status"] = t["real_status"]
                    detail["total_tokens"] = t.get("total_tokens", 0)
                    detail["last_action"] = t.get("last_action", "")
                result["running_details"].append(detail)

        return result

    def active(self, enrich: bool = True) -> list:
        """活跃任务（queued + running）+ 实况"""
        board = self.load_board()
        active_tasks = [t for t in board["tasks"] if t["status"] in ("queued", "running")]
        result = []
        for t in active_tasks:
            if enrich:
                enriched = self._enrich_task(t)
            else:
                enriched = dict(t)
                if t.get("started"):
                    start = self.parse_datetime(t["started"])
                    enriched["elapsed_min"] = round(
                        (datetime.now(SGT) - start).total_seconds() / 60, 1
                    )
            result.append({
                "id": enriched["id"],
                "status": enriched["status"],
                "description": enriched["description"],
                "elapsed_min": enriched.get("elapsed_min"),
                "session_key": enriched.get("session_key"),
                "depends_on": enriched.get("depends_on", []),
                "priority": enriched.get("priority", "normal"),
                "priority_icon": PRIORITY_ICONS.get(enriched.get("priority", "normal"), "🟢"),
                # SysMonitor fields (only present when enriched + running)
                **({
                    "real_status": enriched.get("real_status"),
                    "total_tokens": enriched.get("total_tokens"),
                    "last_action": enriched.get("last_action"),
                } if "real_status" in enriched else {}),
            })
        return result

    def ready(self) -> list:
        """可调度任务（queued + 依赖已满足）"""
        board = self.load_board()
        ready_tasks = self._get_ready_tasks(board)
        return [
            {
                "id": t["id"],
                "description": t["description"],
                "source_chat": t.get("source_chat"),
                "depends_on": t.get("depends_on", []),
                "priority": t.get("priority", "normal"),
                "priority_icon": PRIORITY_ICONS.get(t.get("priority", "normal"), "🟢"),
            }
            for t in ready_tasks
        ]

    # ─── Health Check (原 task-health-check) ──────────────

    def health_check(self) -> dict:
        """
        健康检查：遍历 running → inspect_session → 标记死任务 → dissolve → 保存
        返回 {"stale": [...], "active": [...], "cleaned": N}
        """
        board = self.load_board()
        now = datetime.now(SGT)
        result = {"stale": [], "active": [], "cleaned": 0}

        inspector = self._get_inspect_session()

        # 1. Inspect running tasks
        for t in board.get("tasks", []):
            if t["status"] != "running":
                continue

            # Basic elapsed time check
            elapsed_total = 0
            if t.get("started"):
                try:
                    started_ts = self.parse_datetime(t["started"])
                    elapsed_total = (now - started_ts).total_seconds() / 60
                except Exception:
                    pass

            # Kernel-level inspection
            key = t.get("session_key")
            is_dead = False
            dead_reason = ""

            if key:
                info = inspector.analyze_session(key)
                if "error" in info:
                    is_dead = True
                    dead_reason = f"Session 异常: {info.get('error', 'unknown')}"
                age = info.get("age_seconds", 0)
                if not is_dead and age > STALLED_MINUTES * 60:
                    is_dead = True
                    dead_reason = f"无响应 ({age:.0f}s > {STALLED_MINUTES}m)"

            # Hard timeout (absolute max)
            if elapsed_total > MAX_RUNNING_MINUTES:
                is_dead = True
                dead_reason = f"超时 ({elapsed_total:.0f}m > {MAX_RUNNING_MINUTES}m)"

            if is_dead:
                t["status"] = "failed"
                t["result"] = f"健康检查失败: {dead_reason}"
                t["completed"] = now.isoformat()
                result["stale"].append({
                    "id": t["id"],
                    "description": t["description"],
                    "reason": dead_reason,
                    "priority": t.get("priority", "normal"),
                })
            else:
                result["active"].append({
                    "id": t["id"],
                    "description": t["description"],
                    "elapsed": f"{elapsed_total:.0f}m",
                    "status": "Running",
                    "priority": t.get("priority", "normal"),
                })

        # 2. 不再自动解散群聊（Carl 要求保留，让用户手动关闭）
        # 仅对 stale 任务发通知（健康检查标记失败的）
        for stale_info in result["stale"]:
            for t in board["tasks"]:
                if t["id"] == stale_info["id"] and t.get("task_chat_id"):
                    self.send_notification(
                        t["task_chat_id"],
                        f"❌ 任务 {t['id']} 被健康检查标记失败\n\n原因: {stale_info['reason']}\n\n📌 此群不会自动解散，查看完毕后可手动关闭。"
                    )

        # 2.5 Priority aging for queued tasks
        aged = []
        for t in board.get("tasks", []):
            if t["status"] == "queued":
                t["queued_heartbeats"] = t.get("queued_heartbeats", 0) + 1
                if (t["queued_heartbeats"] >= AGING_THRESHOLD
                        and t.get("priority_value", 2) < 3
                        and not t.get("priority_boosted")):
                    t["priority_value"] = min(t.get("priority_value", 2) + 1, 3)
                    t["priority"] = PRIORITY_NAMES.get(t["priority_value"], "normal")
                    t["priority_boosted"] = True
                    aged.append(t["id"])
        if aged:
            result["aged"] = aged

        # 3. Auto-cleanup old completed/failed/cancelled tasks
        cutoff = now - timedelta(days=CLEANUP_DAYS)
        before = len(board["tasks"])
        kept_tasks = []
        for t in board["tasks"]:
            if t["status"] in ("queued", "running") or not t.get("completed"):
                kept_tasks.append(t)
                continue
            try:
                completed_dt = self.parse_datetime(t["completed"])
                if completed_dt > cutoff:
                    kept_tasks.append(t)
            except Exception:
                kept_tasks.append(t)
        board["tasks"] = kept_tasks
        result["cleaned"] = before - len(board["tasks"])

        if result["stale"] or result["cleaned"] > 0 or result.get("aged"):
            self.save_board(board)

        return result

    # ─── Cleanup ──────────────────────────────────────────

    def cleanup(self, days: int = 7) -> int:
        """清理 N 天前的已完成任务，返回清理数量"""
        board = self.load_board()
        cutoff = datetime.now(SGT) - timedelta(days=days)
        before = len(board["tasks"])
        board["tasks"] = [
            t for t in board["tasks"]
            if t["status"] in ("queued", "running")
            or (
                t.get("completed")
                and self.parse_datetime(t["completed"]) > cutoff
            )
        ]
        after = len(board["tasks"])
        self.save_board(board)
        return before - after
