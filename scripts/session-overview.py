#!/usr/bin/env python3
"""Session overview generator.

Reads OpenClaw session store + Lark chat name cache, generates a concise
overview of all active chat sessions (excludes subagent sessions).

Outputs JSON to data/session-overview.json and optionally to stdout.

Usage:
    python3 scripts/session-overview.py              # generate + save
    python3 scripts/session-overview.py --stdout      # also print to stdout
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta

SGT = timezone(timedelta(hours=8))

SESSIONS_FILE = "/home/ubuntu/.openclaw/agents/main/sessions/sessions.json"
SESSIONS_DIR = "/home/ubuntu/.openclaw/agents/main/sessions"
OUTPUT_FILE = "/home/ubuntu/.openclaw/workspace/data/session-overview.json"
CHAT_CACHE = "/home/ubuntu/.openclaw/workspace/data/lark-chats-cache.json"
PLANNERS_DIR = "/home/ubuntu/.openclaw/workspace/data/planners"
PLANNER_DIR = "/home/ubuntu/.openclaw/workspace/data/planner"  # Old format planners


def load_chat_names():
    """Load chat_id → name mapping from lark-lookup-chat cache."""
    mapping = {}
    if os.path.exists(CHAT_CACHE):
        try:
            with open(CHAT_CACHE) as f:
                data = json.load(f)
            for c in data.get("chats", []):
                mapping[c["chat_id"]] = c["name"]
        except Exception:
            pass
    return mapping


def load_planners():
    """Load chat_id -> planner info mapping from PostgreSQL."""
    mapping = {}
    try:
        from task_store import TaskStore
        store = TaskStore()
        all_plans_raw = store.list_plans() or []
        all_plans = [p.to_dict() if hasattr(p, 'to_dict') else p for p in all_plans_raw]
        now = datetime.now(timezone.utc)
        def _plan_still_relevant(p):
            """Filter out cancelled plans and completed/failed plans older than 24h."""
            status = p.get("status", "")
            if status == "cancelled":
                return False
            if status in ("completed", "failed"):
                created = p.get("created_at")
                if created and hasattr(created, 'timestamp'):
                    age_h = (now - created).total_seconds() / 3600
                    if age_h > 24:
                        return False
            return True
        plans = [p for p in all_plans if _plan_still_relevant(p)]
        # Sort by most recently updated first
        plans.sort(key=lambda p: p.get("updated_at") or p.get("created_at") or now, reverse=True)
        plans = plans[:30]
        for p in plans:
            chat_id = p.get("chat_id")
            if not chat_id:
                continue
            # Skip if we already have a higher-priority plan for this chat
            if chat_id in mapping:
                continue
            plan_id = p["id"]
            full_raw = store.get_plan(plan_id)
            if not full_raw:
                continue
            full = full_raw.to_dict() if hasattr(full_raw, 'to_dict') else full_raw
            steps = full.get("steps", [])
            total = len(steps)
            done = sum(1 for s in steps if s["status"] == "done")
            running_step = None
            for s in steps:
                if s.get("status") == "running":
                    running_step = s.get("title", "")
                    break
            status = p["status"]
            if status == "completed":
                status_text = "\u2705 完成"
            elif status == "failed":
                status_text = "\u274c 失败"
            elif status == "paused":
                status_text = f"\u23f8\ufe0f 暂停 ({done}/{total})"
            elif status == "draft":
                status_text = "\U0001f4dd 草稿"
            elif running_step:
                status_text = f"{running_step} ({done}/{total})"
            elif done > 0:
                status_text = f"步骤 {done}/{total}"
            else:
                status_text = "\U0001f7e1 进行中"
            mapping[chat_id] = {
                "goal": full.get("goal", "未命名规划"),
                "status": status,
                "current_step": done,
                "total_steps": total,
                "status_text": status_text,
                "plan_id": plan_id,
            }
    except Exception as e:
        import sys
        print(f"[session-overview] load_planners error: {e}", file=sys.stderr)
    return mapping


def fmt_relative_time(epoch_ms):
    """Format epoch milliseconds into human-readable relative time."""
    now_ms = time.time() * 1000
    diff_sec = (now_ms - epoch_ms) / 1000

    if diff_sec < 0:
        return "刚刚"
    if diff_sec < 60:
        return "< 1 分钟"
    if diff_sec < 3600:
        mins = int(diff_sec / 60)
        return f"{mins} 分钟"
    if diff_sec < 86400:
        hours = diff_sec / 3600
        if hours < 2:
            mins = int(diff_sec / 60)
            return f"{mins} 分钟"
        return f"{hours:.1f} 小时"
    days = diff_sec / 86400
    return f"{days:.1f} 天"


def get_last_message_summary(session_file, max_len=6):
    """Read the last meaningful assistant text from a JSONL transcript.
    Uses tail for efficiency (avoids reading entire large file).
    Returns a keyword-based short label (not truncated raw text).
    """
    if not session_file or not os.path.exists(session_file):
        return "—"

    try:
        # Read last 50 lines (usually enough to find last assistant msg)
        result = subprocess.run(
            ["tail", "-50", session_file],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode != 0:
            return "—"

        last_text = None
        for line in result.stdout.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            # JSONL uses nested format: {type, message: {role, content}}
            msg = entry.get("message", entry)
            role = msg.get("role", entry.get("role"))

            if role != "assistant":
                continue

            content = msg.get("content", "")
            if isinstance(content, list):
                texts = [
                    c.get("text", "")
                    for c in content
                    if isinstance(c, dict) and c.get("type") == "text"
                ]
                content = " ".join(texts).strip()
            elif not isinstance(content, str):
                continue

            # Skip silent replies
            if content in ("NO_REPLY", "HEARTBEAT_OK", ""):
                continue

            last_text = content

        if not last_text:
            return "—"

        # Keyword-based categorization instead of hard truncation
        return categorize_activity(last_text)

    except Exception:
        return "—"


def categorize_activity(text):
    """Categorize message text into a short 2-4 char label."""
    t = text.lower()

    # Order matters: more specific patterns first
    if any(w in t for w in ["定期检查", "邮件", "日历", "日程", "文档评论"]):
        return "定期检查"
    if any(w in t for w in ["token", "消耗", "用量"]):
        return "Token统计"
    if any(w in t for w in ["测试通过", "全链路测试"]):
        return "测试通过"
    if any(w in t for w in ["测试", "验证"]):
        return "测试中"
    if any(w in t for w in ["ci/cd", "ci", "pipeline", "部署"]):
        return "CI/CD"
    if any(w in t for w in ["pr", "pull request", "merge", "代码审"]):
        return "代码审查"
    if any(w in t for w in ["卡片", "看板", "dashboard"]):
        return "看板更新"
    if any(w in t for w in ["session", "概览", "上下文"]):
        return "Session"
    if any(w in t for w in ["重启", "restart"]):
        return "重启"
    if any(w in t for w in ["完成", "搞定", "done"]):
        return "已完成"
    if any(w in t for w in ["失败", "错误", "error", "fail"]):
        return "异常"
    if any(w in t for w in ["任务", "task", "状态"]):
        return "任务管理"
    if any(w in t for w in ["研究", "分析", "调查"]):
        return "研究"
    if any(w in t for w in ["修复", "fix", "patch", "bug"]):
        return "修复"
    if any(w in t for w in ["配置", "config", "设置"]):
        return "配置"
    if any(w in t for w in ["聊天", "对话"]):
        return "对话"

    return "活跃"


def extract_chat_id(session_key):
    """Extract chat_id (oc_xxx) from session key."""
    # agent:main:feishu:group:oc_xxx → oc_xxx
    parts = session_key.split(":")
    for p in parts:
        if p.startswith("oc_"):
            return p
    return None


def generate_overview():
    """Generate session overview data."""
    if not os.path.exists(SESSIONS_FILE):
        return {"sessions": [], "generated_at": datetime.now(SGT).isoformat()}

    with open(SESSIONS_FILE) as f:
        all_sessions = json.load(f)

    chat_names = load_chat_names()
    planners = load_planners()

    # Filter: only real chat sessions (group + dm + main)
    # Exclude: subagents, task auto-created groups (🤖 prefix)
    chat_sessions = []
    now_ms = time.time() * 1000
    max_age_ms = 24 * 3600 * 1000  # Only show sessions active in last 24h

    for key, meta in all_sessions.items():
        if "subagent" in key:
            continue

        updated_at = meta.get("updatedAt", 0)

        # Skip very old sessions
        if now_ms - updated_at > max_age_ms:
            continue

        total_tokens = meta.get("totalTokens", 0)
        context_tokens = meta.get("contextTokens", 200000)

        # Session name
        chat_id = extract_chat_id(key)
        if chat_id and chat_id in chat_names:
            name = chat_names[chat_id]
            # Skip task auto-created groups (🤖 prefix)
            if name.startswith("🤖"):
                continue
        elif "main:main" in key:
            name = "🫀 心跳 (main)"
        elif "dm:" in key:
            name = "私聊"
        else:
            # Skip sessions with unknown chat IDs (old/removed groups)
            continue

        # Session file for last message
        session_id = meta.get("sessionId", "")
        session_file = os.path.join(SESSIONS_DIR, f"{session_id}.jsonl")
        if not os.path.exists(session_file):
            session_file = meta.get("sessionFile", "")

        last_activity = get_last_message_summary(session_file)
        relative_time = fmt_relative_time(updated_at)

        # Usage percentage
        usage_pct = round((total_tokens or 0) / context_tokens * 100) if context_tokens else 0

        # Get planner info for this chat
        planner_info = planners.get(chat_id) if chat_id else None

        chat_sessions.append({
            "key": key,
            "name": name,
            "chat_id": chat_id,
            "tokens": total_tokens,
            "context_tokens": context_tokens,
            "usage_pct": usage_pct,
            "updated_at": updated_at,
            "relative_time": relative_time,
            "last_activity": last_activity,
            "compactions": meta.get("compactionCount", 0),
            "planner": planner_info,
        })

    # Sort by updatedAt descending (most recent first)
    chat_sessions.sort(key=lambda s: s["name"])

    result = {
        "sessions": chat_sessions,
        "total_count": len(all_sessions),
        "chat_count": len(chat_sessions),
        "subagent_count": len(all_sessions) - len(chat_sessions),
        "generated_at": datetime.now(SGT).isoformat(),
    }

    # Save
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    return result


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("--help", "-h", "help"):
        print(__doc__)
        sys.exit(0)
    result = generate_overview()
    if "--stdout" in sys.argv:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(json.dumps({
            "ok": True,
            "chat_sessions": len(result["sessions"]),
            "subagents": result["subagent_count"],
        }))
