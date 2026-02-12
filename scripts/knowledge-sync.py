#!/usr/bin/env python3
"""知识同步总线 v2 — Knowledge Sync Bus (Event-Driven)

检测工作区关键文件变更，生成带 diff 的通知，直接通过 `openclaw agent` 广播到活跃 session。

Usage:
  knowledge-sync.py check                              — 检测文件变更，输出需广播的 JSON
  knowledge-sync.py notify <file_path> <summary>       — 手动创建通知（输出 JSON）
  knowledge-sync.py status                             — 显示当前同步状态
  knowledge-sync.py init                               — 初始化/重置状态文件（记录当前 md5）
  knowledge-sync.py diff <file_path>                   — 显示某文件与上次快照的差异
  knowledge-sync.py broadcast [--file <name>] [--dry-run]  — 检测变更 → 生成带 diff 的通知 → 广播
  knowledge-sync.py watch                              — 启动 inotifywait 文件监听守护进程
  knowledge-sync.py stats [date]                       — 显示串台事件统计
  knowledge-sync.py incidents                          — 显示最近的串台事件日志

v2 变更：
  - broadcast: 直接通过 `openclaw agent --session-id` 注入通知到活跃 session
  - watch: 使用 inotifywait 事件驱动，写入即触发
  - 通知包含实际 diff 内容，不只是摘要
"""

import json
import sys
import os
import re
import hashlib
import difflib
import subprocess
# Group privacy cache: chat_id -> {"is_private": bool, "expires": timestamp}
_GROUP_PRIVACY_CACHE = {}
_GROUP_PRIVACY_CACHE_TTL = 3600  # 1 hour
import signal
import time
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

SGT = timezone(timedelta(hours=8))
WORKSPACE = "/home/ubuntu/.openclaw/workspace"
STATE_FILE = os.path.join(WORKSPACE, "data", "knowledge-sync-state.json")
PID_FILE = os.path.join(WORKSPACE, "data", "knowledge-watcher.pid")
LOG_FILE = os.path.join(WORKSPACE, "data", "knowledge-watcher.log")

# Debounce: ignore repeated changes within this window (seconds)
DEBOUNCE_SECONDS = 3

# Max diff content length in notification (chars)
MAX_DIFF_CHARS = 500

# ─── 监控文件配置 ─────────────────────────────────────────────
# priority: high / medium / low
# privacy: public (可发到任何群) / private (仅私聊/双人群)
WATCHED_FILES = {
    "SOUL.md": {
        "priority": "high",
        "privacy": "public",
        "label": "核心规则",
        "emoji": "🔴",
    },
    "MEMORY.md": {
        "priority": "medium",
        "privacy": "private",       # 含私密内容，不发到多人群
        "label": "长期记忆",
        "emoji": "🟡",
    },
    "AGENTS.md": {
        "priority": "medium",
        "privacy": "public",
        "label": "工作区规范",
        "emoji": "🟡",
    },
    "TOOLS.md": {
        "priority": "low",
        "privacy": "public",
        "label": "工具笔记",
        "emoji": "🟢",
    },
    "HEARTBEAT.md": {
        "priority": "low",
        "privacy": "public",
        "label": "心跳配置",
        "emoji": "🟢",
    },
    "USER.md": {
        "priority": "medium",
        "privacy": "private",
        "label": "用户档案",
        "emoji": "🟡",
    },
    "IDENTITY.md": {
        "priority": "medium",
        "privacy": "public",
        "label": "身份定义",
        "emoji": "🟡",
    },
}


# ─── Logging Setup ─────────────────────────────────────────────

def setup_logging(to_file=False):
    """Configure logging."""
    handlers = [logging.StreamHandler()]
    if to_file:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        handlers.append(logging.FileHandler(LOG_FILE))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
    )


# ─── State Management ──────────────────────────────────────────

def load_state():
    """Load sync state from disk."""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"files": {}, "last_check": None, "version": 2}


def save_state(state):
    """Persist sync state."""
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def now_iso():
    return datetime.now(SGT).isoformat()


# ─── File Hashing & Diffing ───────────────────────────────────

def file_md5(filepath):
    """Compute md5 of file. Returns None if file doesn't exist."""
    if not os.path.exists(filepath):
        return None
    h = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def read_file_lines(filepath):
    """Read file lines, return empty list if missing."""
    if not os.path.exists(filepath):
        return []
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        return f.readlines()


def generate_diff_text(old_content, new_content, filename):
    """Generate the actual diff text (added/removed lines with context).
    
    Returns:
        tuple: (diff_text, added_lines, removed_lines, line_range_desc)
    """
    old_lines = old_content if isinstance(old_content, list) else old_content.splitlines(keepends=True)
    new_lines = new_content if isinstance(new_content, list) else new_content.splitlines(keepends=True)
    
    diff = list(difflib.unified_diff(old_lines, new_lines, lineterm=""))
    
    if not diff:
        return None, [], [], None
    
    added = []
    removed = []
    line_ranges = []
    
    for line in diff:
        if line.startswith("@@"):
            # Parse @@ -a,b +c,d @@
            m = re.search(r'\+(\d+)(?:,(\d+))?', line)
            if m:
                start = int(m.group(1))
                count = int(m.group(2)) if m.group(2) else 1
                line_ranges.append(f"{start}-{start+count-1}")
        elif line.startswith("+") and not line.startswith("+++"):
            added.append(line[1:])
        elif line.startswith("-") and not line.startswith("---"):
            removed.append(line[1:])
    
    # Build readable diff text
    parts = []
    if added:
        added_text = "\n".join(l.rstrip() for l in added if l.strip())
        if added_text:
            parts.append(f"新增内容：\n{added_text}")
    if removed:
        removed_text = "\n".join(l.rstrip() for l in removed if l.strip())
        if removed_text:
            parts.append(f"删除内容：\n{removed_text}")
    
    diff_text = "\n\n".join(parts)
    range_desc = f"第 {', '.join(line_ranges[:3])} 行" if line_ranges else None
    
    return diff_text, added, removed, range_desc


def generate_diff_summary(old_content, new_content, filename):
    """Generate a human-readable diff summary.
    
    Returns:
        tuple: (summary_text, diff_lines_desc)
    """
    old_lines = old_content if isinstance(old_content, list) else old_content.splitlines(keepends=True)
    new_lines = new_content if isinstance(new_content, list) else new_content.splitlines(keepends=True)
    
    diff = list(difflib.unified_diff(old_lines, new_lines, lineterm=""))
    
    if not diff:
        return None, None
    
    added = []
    removed = []
    
    for line in diff:
        if line.startswith("+") and not line.startswith("+++"):
            content = line[1:].strip()
            if content:
                added.append(content)
        elif line.startswith("-") and not line.startswith("---"):
            content = line[1:].strip()
            if content:
                removed.append(content)
    
    # Build summary
    parts = []
    
    if added and removed:
        sections = extract_section_headers(added)
        if sections:
            parts.append(f"修改了 {', '.join(sections[:3])} 等部分")
        else:
            parts.append(f"修改了 {len(removed)} 行，新增 {len(added)} 行")
    elif added:
        sections = extract_section_headers(added)
        if sections:
            parts.append(f"新增：{', '.join(sections[:3])}")
        else:
            hint = next((l for l in added if len(l) > 5 and not l.startswith("#")), None)
            if hint:
                parts.append(f"新增 {len(added)} 行（如：{hint[:60]}…）" if len(hint) > 60 else f"新增 {len(added)} 行（如：{hint}）")
            else:
                parts.append(f"新增 {len(added)} 行")
    elif removed:
        sections = extract_section_headers(removed)
        if sections:
            parts.append(f"删除了 {', '.join(sections[:3])}")
        else:
            parts.append(f"删除了 {len(removed)} 行")
    
    summary = "；".join(parts) if parts else f"{filename} 有变更"
    diff_desc = f"+{len(added)}/-{len(removed)} 行"
    
    return summary, diff_desc


def extract_section_headers(lines):
    """Extract markdown section headers from lines."""
    headers = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            header = stripped.lstrip("#").strip()
            if header and len(header) > 2:
                headers.append(header)
    return headers


# ─── Session Discovery ─────────────────────────────────────────

def get_active_sessions(active_minutes=120):
    """Get active sessions from OpenClaw, filtered for broadcast targets.
    
    Returns list of session dicts with keys: key, kind, sessionId
    Skips:
      - subagent sessions (key contains ':subagent:')
      - main session (key == 'agent:main:main')
      - sessions with labels starting with t/tid (task sessions)
    """
    try:
        result = subprocess.run(
            ["openclaw", "sessions", "--json", "--active", str(active_minutes)],
            capture_output=True, text=True, timeout=30,
        )
        # Parse JSON from output (skip config warnings before the JSON)
        output = result.stdout
        # Find the start of JSON
        json_start = output.find("{")
        if json_start < 0:
            logging.error(f"No JSON found in sessions output: {output[:200]}")
            return []
        
        data = json.loads(output[json_start:])
        sessions = data.get("sessions", [])
    except Exception as e:
        logging.error(f"Failed to get sessions: {e}")
        return []
    
    targets = []
    for s in sessions:
        key = s.get("key", "")
        kind = s.get("kind", "")
        session_id = s.get("sessionId", "")
        label = s.get("label", "")
        
        # Skip subagent sessions
        if ":subagent:" in key:
            continue
        
        # Skip main CLI session
        if key == "agent:main:main":
            continue
        
        # Skip task sessions (label starts with t followed by digits)
        if label and re.match(r'^t\d', label):
            continue
        
        # Only include group and dm sessions (feishu/telegram/discord etc)
        # These have patterns like agent:main:feishu:group:xxx or agent:main:telegram:dm:xxx
        if kind not in ("group", "direct"):
            continue
        
        # For direct sessions, skip unless it's a real DM (not main)
        if kind == "direct" and ":" not in key.replace("agent:main:", "", 1):
            continue
        
        targets.append({
            "key": key,
            "kind": kind,
            "sessionId": session_id,
        })
    
    return targets




def check_group_privacy_cached(chat_id):
    """Check if a group chat is actually private (only Carl + Bot).
    
    Uses cache to avoid repeated API calls.
    Returns True if private (safe to send private content), False otherwise.
    """
    global _GROUP_PRIVACY_CACHE
    
    now = time.time()
    
    # Check cache
    if chat_id in _GROUP_PRIVACY_CACHE:
        cached = _GROUP_PRIVACY_CACHE[chat_id]
        if cached["expires"] > now:
            return cached["is_private"]
    
    # Not in cache or expired - need to check via API
    try:
        # Import lark_common functions
        sys.path.insert(0, os.path.join(WORKSPACE, "scripts"))
        from lark_common import get_tenant_token, get_bot_info, get_chat_members, CARL_OPEN_ID
        
        token = get_tenant_token()
        bot_info = get_bot_info(token=token)
        bot_open_id = bot_info.get("bot", bot_info).get("open_id", "")
        
        members = get_chat_members(chat_id, token=token)
        
        non_bot = []
        for m in members:
            mid = m["member_id"]
            if mid != bot_open_id:
                non_bot.append(mid)
        
        # Private = only Carl (no other humans)
        is_private = len(non_bot) <= 1 and all(m == CARL_OPEN_ID for m in non_bot)
        
        # Cache result
        _GROUP_PRIVACY_CACHE[chat_id] = {
            "is_private": is_private,
            "expires": now + _GROUP_PRIVACY_CACHE_TTL
        }
        
        return is_private
        
    except Exception as e:
        logging.warning(f"Failed to check group privacy for {chat_id}: {e}")
        # On error, be conservative - treat as non-private
        _GROUP_PRIVACY_CACHE[chat_id] = {
            "is_private": False,
            "expires": now + 60  # Short cache on error
        }
        return False


def is_group_session(session):
    """Check if a session is a multi-person group chat."""
    return session.get("kind") == "group"


# ─── Broadcast via openclaw agent ──────────────────────────────

def inject_message(session_id, message, dry_run=False):
    """Inject a message into a session via `openclaw agent --session-id`."""
    if dry_run:
        logging.info(f"[DRY-RUN] Would inject to session {session_id}: {message[:80]}...")
        return True
    
    try:
        result = subprocess.run(
            ["openclaw", "agent", "--session-id", session_id, "--message", message],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode == 0:
            logging.info(f"✅ Injected to session {session_id}")
            return True
        else:
            logging.error(f"❌ Failed to inject to {session_id}: {result.stderr[:200]}")
            return False
    except subprocess.TimeoutExpired:
        logging.error(f"⏰ Timeout injecting to {session_id}")
        return False
    except Exception as e:
        logging.error(f"❌ Error injecting to {session_id}: {e}")
        return False


# ─── Build Rich Notification ──────────────────────────────────

def build_rich_notification(change, include_diff=True):
    """Build a notification message with actual diff content.
    
    Args:
        change: dict with file, priority, emoji, label, summary, diff_text, etc.
        include_diff: whether to include the actual diff content
    
    Returns:
        tuple: (public_message, private_message)
    """
    filename = change["file"]
    emoji = change["emoji"]
    label = change["label"]
    priority = change["priority"]
    
    # Header
    header = f"📢 知识同步 — {filename} 更新"
    
    # Priority indicator
    if priority == "high":
        priority_line = "🔴 优先级：高 — 请立即重新加载此文件"
    elif priority == "medium":
        priority_line = "🟡 优先级：中 — 建议在下次操作前重新加载"
    else:
        priority_line = "🟢 优先级：低 — 知悉即可"
    
    # Diff content
    diff_text = change.get("diff_text", "")
    range_desc = change.get("range_desc", "")
    
    if include_diff and diff_text:
        # Truncate if too long
        if len(diff_text) > MAX_DIFF_CHARS:
            truncated_diff = diff_text[:MAX_DIFF_CHARS].rsplit("\n", 1)[0]
            diff_section = f"{truncated_diff}\n\n… 完整变更请读 {filename}"
        else:
            diff_section = diff_text
        
        if range_desc:
            message = f"{header}\n{priority_line}\n\n变更位置：{range_desc}\n\n{diff_section}"
        else:
            message = f"{header}\n{priority_line}\n\n{diff_section}"
    else:
        # No diff available, just summary
        summary = change.get("summary", "有更新")
        message = f"{header}\n{priority_line}\n\n{summary}"
    
    # For private files in group chats, create a sanitized version
    if change.get("privacy") == "private":
        public_message = f"{header}\n{priority_line}\n\n（此文件为私密文件，变更详情仅在私聊中可见）"
        private_message = message
    else:
        public_message = message
        private_message = message
    
    return public_message, private_message


# ─── Core Logic ────────────────────────────────────────────────

def check_changes(target_file=None):
    """Check watched files for changes. Return change list with diff content.
    
    Args:
        target_file: if set, only check this specific file
    """
    state = load_state()
    changes = []
    
    files_to_check = {target_file: WATCHED_FILES[target_file]} if target_file and target_file in WATCHED_FILES else WATCHED_FILES
    
    for filename, config in files_to_check.items():
        filepath = os.path.join(WORKSPACE, filename)
        current_md5 = file_md5(filepath)
        
        file_state = state.get("files", {}).get(filename, {})
        stored_md5 = file_state.get("md5")
        stored_content = file_state.get("content_snapshot")
        
        if current_md5 is None:
            if stored_md5 is not None:
                changes.append({
                    "file": filename,
                    "priority": config["priority"],
                    "privacy": config["privacy"],
                    "emoji": config["emoji"],
                    "label": config["label"],
                    "summary": f"{filename} 已被删除",
                    "diff_text": "",
                    "range_desc": "",
                    "diff_lines": "文件删除",
                    "change_type": "deleted",
                })
            continue
        
        if stored_md5 is None:
            # New file — just record, don't notify
            current_lines = read_file_lines(filepath)
            state.setdefault("files", {})[filename] = {
                "md5": current_md5,
                "content_snapshot": current_lines[:500],
                "last_synced": now_iso(),
            }
            continue
        
        if current_md5 != stored_md5:
            current_lines = read_file_lines(filepath)
            old_lines = stored_content if stored_content else []
            
            # Generate both summary and full diff text
            summary, diff_desc = generate_diff_summary(old_lines, current_lines, filename)
            diff_text, added, removed, range_desc = generate_diff_text(old_lines, current_lines, filename)
            
            if summary:
                changes.append({
                    "file": filename,
                    "priority": config["priority"],
                    "privacy": config["privacy"],
                    "emoji": config["emoji"],
                    "label": config["label"],
                    "summary": summary,
                    "diff_text": diff_text or "",
                    "range_desc": range_desc or "",
                    "diff_lines": diff_desc or "unknown",
                    "change_type": "modified",
                })
            
            # Update state
            state.setdefault("files", {})[filename] = {
                "md5": current_md5,
                "content_snapshot": current_lines[:500],
                "last_synced": now_iso(),
            }
    
    state["last_check"] = now_iso()
    save_state(state)
    
    return changes


def build_broadcast_output(changes):
    """Build the JSON output for the main session to consume (v1 compat)."""
    if not changes:
        return {
            "has_changes": False,
            "changes": [],
            "broadcast_message": None,
            "broadcast_message_private": None,
        }
    
    priority_order = {"high": 0, "medium": 1, "low": 2}
    changes.sort(key=lambda c: priority_order.get(c["priority"], 99))
    
    public_lines = []
    private_lines = []
    
    for c in changes:
        line = f"{c['emoji']} {c['file']}（{c['label']}）：{c['summary']}（{c['diff_lines']}）"
        
        if c["privacy"] == "public":
            public_lines.append(line)
            private_lines.append(line)
        else:
            private_lines.append(line)
            public_lines.append(f"{c['emoji']} {c['file']}（{c['label']}）：有更新（详情仅限私聊可见）")
    
    header = "📢 知识同步"
    public_msg = header + "\n\n" + "\n".join(public_lines)
    private_msg = header + "\n\n" + "\n".join(private_lines)
    
    highest = changes[0]["priority"]
    if highest == "high":
        public_msg += "\n\n⚠️ 请立即重新加载相关文件以获取最新规则。"
        private_msg += "\n\n⚠️ 请立即重新加载相关文件以获取最新规则。"
    elif highest == "medium":
        public_msg += "\n\n💡 建议在下次操作前重新加载相关文件。"
        private_msg += "\n\n💡 建议在下次操作前重新加载相关文件。"
    
    return {
        "has_changes": True,
        "changes": changes,
        "broadcast_message": public_msg,
        "broadcast_message_private": private_msg,
        "highest_priority": highest,
    }


# ─── Commands ──────────────────────────────────────────────────

def cmd_check():
    """Check for changes and output JSON."""
    changes = check_changes()
    result = build_broadcast_output(changes)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not changes else 1


def cmd_notify(filepath, summary):
    """Manually create a notification for a file change."""
    abs_path = os.path.abspath(filepath)
    if abs_path.startswith(WORKSPACE + "/"):
        rel_name = abs_path[len(WORKSPACE) + 1:]
    else:
        rel_name = filepath
    
    config = WATCHED_FILES.get(rel_name, {
        "priority": "low",
        "privacy": "public",
        "label": "其他文件",
        "emoji": "🟢",
    })
    
    changes = [{
        "file": rel_name,
        "priority": config["priority"],
        "privacy": config["privacy"],
        "emoji": config["emoji"],
        "label": config["label"],
        "summary": summary,
        "diff_text": "",
        "range_desc": "",
        "diff_lines": "手动通知",
        "change_type": "manual",
    }]
    
    result = build_broadcast_output(changes)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1


def cmd_status():
    """Show current sync status."""
    state = load_state()
    
    # Check watcher status
    watcher_running = False
    watcher_pid = None
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE) as f:
                watcher_pid = int(f.read().strip())
            os.kill(watcher_pid, 0)  # Check if process exists
            watcher_running = True
        except (ValueError, ProcessLookupError, PermissionError):
            watcher_running = False
    
    status = {
        "last_check": state.get("last_check", "never"),
        "version": state.get("version", 0),
        "watcher": {
            "running": watcher_running,
            "pid": watcher_pid if watcher_running else None,
            "pid_file": PID_FILE,
            "log_file": LOG_FILE,
        },
        "tracked_files": {},
    }
    
    for filename, config in WATCHED_FILES.items():
        filepath = os.path.join(WORKSPACE, filename)
        current_md5 = file_md5(filepath)
        file_state = state.get("files", {}).get(filename, {})
        stored_md5 = file_state.get("md5")
        
        status["tracked_files"][filename] = {
            "exists": os.path.exists(filepath),
            "current_md5": current_md5[:8] if current_md5 else None,
            "stored_md5": stored_md5[:8] if stored_md5 else None,
            "in_sync": current_md5 == stored_md5,
            "last_synced": file_state.get("last_synced", "never"),
            "priority": config["priority"],
            "privacy": config["privacy"],
        }
    
    print(json.dumps(status, ensure_ascii=False, indent=2))
    return 0


def cmd_init():
    """Initialize state file with current file hashes (no notifications)."""
    state = {"files": {}, "last_check": now_iso(), "version": 2}
    
    for filename in WATCHED_FILES:
        filepath = os.path.join(WORKSPACE, filename)
        md5 = file_md5(filepath)
        if md5 is not None:
            lines = read_file_lines(filepath)
            state["files"][filename] = {
                "md5": md5,
                "content_snapshot": lines[:500],
                "last_synced": now_iso(),
            }
    
    save_state(state)
    print(json.dumps({"status": "initialized", "files_tracked": len(state["files"]), "time": now_iso()}, ensure_ascii=False))
    return 0


def cmd_diff(filepath):
    """Show diff between stored snapshot and current file."""
    abs_path = os.path.abspath(filepath)
    if abs_path.startswith(WORKSPACE + "/"):
        rel_name = abs_path[len(WORKSPACE) + 1:]
    else:
        rel_name = filepath
    
    state = load_state()
    file_state = state.get("files", {}).get(rel_name)
    
    if not file_state:
        print(json.dumps({"error": f"No stored snapshot for {rel_name}. Run 'init' first."}, ensure_ascii=False))
        return 2
    
    filepath_full = os.path.join(WORKSPACE, rel_name)
    current_lines = read_file_lines(filepath_full)
    old_lines = file_state.get("content_snapshot", [])
    
    diff = list(difflib.unified_diff(
        old_lines, current_lines,
        fromfile=f"{rel_name} (stored)",
        tofile=f"{rel_name} (current)",
        lineterm=""
    ))
    
    if diff:
        print("\n".join(diff))
    else:
        print(f"No changes detected for {rel_name}")
    
    return 0


def cmd_broadcast(target_file=None, dry_run=False, skip_session_key=None):
    """Detect changes → generate notifications with diff → broadcast to active sessions.
    
    Args:
        target_file: only check this file (e.g. "SOUL.md")
        dry_run: if True, don't actually inject messages
        skip_session_key: session key to skip (the one that triggered the change)
    """
    setup_logging()
    
    logging.info(f"🔄 Broadcast started (target={target_file or 'all'}, dry_run={dry_run})")
    
    # 1. Detect changes
    changes = check_changes(target_file=target_file)
    
    if not changes:
        logging.info("No changes detected, nothing to broadcast.")
        print(json.dumps({"broadcast": False, "reason": "no_changes"}, ensure_ascii=False))
        return 0
    
    logging.info(f"📋 Found {len(changes)} change(s): {', '.join(c['file'] for c in changes)}")
    
    # 2. Get active sessions
    sessions = get_active_sessions(active_minutes=120)
    
    if not sessions:
        logging.warning("No active sessions found to broadcast to.")
        print(json.dumps({"broadcast": False, "reason": "no_sessions"}, ensure_ascii=False))
        return 0
    
    logging.info(f"👥 Found {len(sessions)} active session(s)")
    
    # 3. Broadcast to each session
    results = {"sent": 0, "skipped": 0, "failed": 0, "details": []}
    
    for change in changes:
        public_msg, private_msg = build_rich_notification(change)
        
        for session in sessions:
            session_key = session["key"]
            session_id = session["sessionId"]
            
            # Skip the triggering session
            if skip_session_key and session_key == skip_session_key:
                results["skipped"] += 1
                continue
            
            # Privacy filter: check if we can send private content to this session
            is_group = is_group_session(session)
            
            # For private files in group chats: check if it's actually private (only Carl + Bot)
            if change["privacy"] == "private" and is_group:
                # Extract chat_id from session key (e.g., agent:main:feishu:group:oc_xxx -> oc_xxx)
                chat_id = None
                if ':group:' in session_key:
                    chat_id = session_key.split(':group:')[-1]
                
                if chat_id:
                    is_actually_private = check_group_privacy_cached(chat_id)
                    if is_actually_private:
                        # Safe to send - treat as private chat
                        logging.info(f"[PRIVACY] Group {chat_id} is actually private (Carl+Bot), allowing broadcast")
                        is_group = False  # Treat as non-group for message selection
                    else:
                        # True multi-person group: SKIP entirely (no metadata leakage)
                        logging.info(f"[PRIVACY] Skipped private file {change['file']} for multi-person group {chat_id}")
                        log_cross_session_incident(change["file"], session_key, "private_to_group_skipped")
                        results["skipped"] += 1
                        results["details"].append({
                            "session_key": session_key,
                            "file": change["file"],
                            "success": True,
                            "is_group": True,
                            "privacy_filtered": True,
                            "reason": "private_file_in_multi_person_group",
                        })
                        continue  # Skip to next session
                else:
                    # Can't extract chat_id, be conservative and skip
                    logging.warning(f"[PRIVACY] Could not extract chat_id from {session_key}, skipping private file")
                    continue
            
            # For non-private files in groups, or any file in private chats: proceed
            message = public_msg if is_group else private_msg
            
            success = inject_message(session_id, message, dry_run=dry_run)
            
            if success:
                results["sent"] += 1
            else:
                results["failed"] += 1
            
            results["details"].append({
                "session_key": session_key,
                "file": change["file"],
                "success": success,
                "is_group": is_group,
                "privacy_filtered": change["privacy"] == "private" and is_group,
            })
    
    logging.info(f"📊 Broadcast complete: sent={results['sent']}, skipped={results['skipped']}, failed={results['failed']}")
    print(json.dumps({"broadcast": True, **results}, ensure_ascii=False, indent=2))
    
    return 0


def cmd_watch():
    """Start inotifywait-based file watcher daemon.
    
    Monitors watched files for changes and automatically triggers broadcast.
    Uses debouncing to avoid multiple triggers for the same save.
    """
    setup_logging(to_file=True)
    
    # Check inotifywait is available
    if not os.path.exists("/usr/bin/inotifywait"):
        logging.error("inotifywait not found. Install with: sudo apt install -y inotify-tools")
        print("ERROR: inotifywait not found. Install with: sudo apt install -y inotify-tools")
        return 1
    
    # Write PID file
    os.makedirs(os.path.dirname(PID_FILE), exist_ok=True)
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))
    
    logging.info(f"🚀 Knowledge sync watcher started (PID: {os.getpid()})")
    
    # Build file list to watch
    watch_files = []
    for filename in WATCHED_FILES:
        filepath = os.path.join(WORKSPACE, filename)
        watch_files.append(filepath)
    
    # Track last trigger time per file for debouncing
    last_trigger = {}
    
    # Graceful shutdown
    running = True
    def handle_signal(signum, frame):
        nonlocal running
        logging.info(f"📛 Received signal {signum}, shutting down watcher...")
        running = False
    
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)
    
    while running:
        try:
            # Start inotifywait
            # Use --format to get clean output
            # Watch the DIRECTORY (not individual files) — inotifywait on single files
            # misses changes from editors that unlink+create instead of modify in-place.
            # Use close_write to catch completed writes.
            cmd = [
                "inotifywait",
                "-m",                    # monitor mode (continuous)
                "-e", "close_write,moved_to",  # catch writes and atomic saves (rename)
                "--format", "%f",        # output just the filename
                WORKSPACE,               # watch the workspace directory
            ]
            
            logging.info(f"👁️ Watching {len(watch_files)} files: {', '.join(os.path.basename(f) for f in watch_files)}")
            
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            
            while running:
                line = proc.stdout.readline()
                if not line:
                    break
                
                triggered_file = line.strip()
                if not triggered_file:
                    continue
                
                # Map back to relative name
                # inotifywait with full paths outputs the full path
                rel_name = triggered_file
                for wf in WATCHED_FILES:
                    if triggered_file.endswith(wf) or triggered_file == wf:
                        rel_name = wf
                        break
                
                if rel_name not in WATCHED_FILES:
                    logging.debug(f"Ignoring untracked file: {triggered_file}")
                    continue
                
                # Debounce
                now = time.time()
                last = last_trigger.get(rel_name, 0)
                if now - last < DEBOUNCE_SECONDS:
                    logging.debug(f"Debounced {rel_name} (last trigger {now - last:.1f}s ago)")
                    continue
                last_trigger[rel_name] = now
                
                logging.info(f"📝 Change detected: {rel_name}")
                
                # Small delay to let writes finish (editor save might be multi-step)
                time.sleep(0.5)
                
                # Trigger broadcast IN BACKGROUND (don't block the watcher loop)
                try:
                    subprocess.Popen(
                        [sys.executable, __file__, "broadcast", "--file", rel_name],
                        cwd=WORKSPACE,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    logging.info(f"🚀 Broadcast spawned for {rel_name}")
                except Exception as e:
                    logging.error(f"❌ Broadcast spawn error: {e}")
            
            proc.terminate()
            
        except Exception as e:
            logging.error(f"Watcher error: {e}")
            if running:
                logging.info("Restarting watcher in 5 seconds...")
                time.sleep(5)
    
    # Cleanup
    if os.path.exists(PID_FILE):
        os.remove(PID_FILE)
    
    logging.info("🛑 Knowledge sync watcher stopped.")
    return 0


# ─── CLI Entry ─────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    
    cmd = sys.argv[1]
    
    if cmd == "check":
        return cmd_check()
    elif cmd == "notify":
        if len(sys.argv) < 4:
            print("Usage: knowledge-sync.py notify <file_path> <summary>")
            return 2
        return cmd_notify(sys.argv[2], sys.argv[3])
    elif cmd == "status":
        return cmd_status()
    elif cmd == "init":
        return cmd_init()
    elif cmd == "diff":
        if len(sys.argv) < 3:
            print("Usage: knowledge-sync.py diff <file_path>")
            return 2
        return cmd_diff(sys.argv[2])
    elif cmd == "broadcast":
        # Parse broadcast options
        target_file = None
        dry_run = False
        skip_session = None
        
        i = 2
        while i < len(sys.argv):
            if sys.argv[i] == "--file" and i + 1 < len(sys.argv):
                target_file = sys.argv[i + 1]
                i += 2
            elif sys.argv[i] == "--dry-run":
                dry_run = True
                i += 1
            elif sys.argv[i] == "--skip-session" and i + 1 < len(sys.argv):
                skip_session = sys.argv[i + 1]
                i += 2
            else:
                i += 1
        
        return cmd_broadcast(target_file=target_file, dry_run=dry_run, skip_session_key=skip_session)
    elif cmd == "stats":
        date_str = sys.argv[2] if len(sys.argv) > 2 else None
        stats = get_daily_cross_session_stats(date_str)
        print(json.dumps(stats, indent=2, ensure_ascii=False))
        return 0
    
    elif cmd == "incidents":
        # Show recent incidents log
        incidents_file = os.path.join(WORKSPACE, "data", "cross-session-incidents.jsonl")
        if not os.path.exists(incidents_file):
            print("No incidents logged yet.")
            return 0
        with open(incidents_file, "r") as f:
            lines = f.readlines()
        # Show last 20 lines
        for line in lines[-20:]:
            line = line.strip()
            if line:
                print(line)
        return 0

    elif cmd == "watch":
        return cmd_watch()
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        return 2


def log_cross_session_incident(file_changed, session_key, incident_type="private_to_group"):
    """Log a cross-session incident for daily reporting.
    
    Args:
        file_changed: The file that was being broadcast
        session_key: The session that was skipped
        incident_type: Type of incident (private_to_group, etc.)
    """
    incident = {
        "timestamp": now_iso(),
        "file": file_changed,
        "session_key": session_key,
        "type": incident_type,
        "prevented": True,  # We prevented the leak
    }
    
    # Append to incidents log file
    incidents_file = os.path.join(WORKSPACE, "data", "cross-session-incidents.jsonl")
    os.makedirs(os.path.dirname(incidents_file), exist_ok=True)
    
    with open(incidents_file, "a") as f:
        f.write(json.dumps(incident, ensure_ascii=False) + "\n")
    
    return incident

def get_daily_cross_session_stats(date_str=None):
    """Get cross-session incident stats for a specific date.
    
    Returns:
        dict: {"total_incidents": N, "by_file": {...}, "by_type": {...}}
    """
    if date_str is None:
        date_str = datetime.now(SGT).strftime("%Y-%m-%d")
    
    incidents_file = os.path.join(WORKSPACE, "data", "cross-session-incidents.jsonl")
    
    stats = {
        "date": date_str,
        "total_incidents": 0,
        "by_file": {},
        "by_type": {},
        "prevented": 0,  # How many we successfully prevented
        "leaked": 0,     # How many actually leaked (should be 0)
    }
    
    if not os.path.exists(incidents_file):
        return stats
    
    with open(incidents_file, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                incident = json.loads(line)
                ts = incident.get("timestamp", "")
                if date_str in ts:
                    stats["total_incidents"] += 1
                    
                    file_name = incident.get("file", "unknown")
                    stats["by_file"][file_name] = stats["by_file"].get(file_name, 0) + 1
                    
                    incident_type = incident.get("type", "unknown")
                    stats["by_type"][incident_type] = stats["by_type"].get(incident_type, 0) + 1
                    
                    if incident.get("prevented"):
                        stats["prevented"] += 1
                    else:
                        stats["leaked"] += 1
            except json.JSONDecodeError:
                continue
    
    return stats


if __name__ == "__main__":
    sys.exit(main())
