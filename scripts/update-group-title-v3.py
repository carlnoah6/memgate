#!/usr/bin/env python3
"""
群标题自动更新脚本 v3 — 基于话题跟踪（而非任务跟踪）

核心逻辑：
1. 检查最近 N 分钟内的消息活跃度
2. 分析对话内容提取话题关键词
3. 同一话题持续期间保持相同标题
4. 长时间无对话则回到"空闲"

Usage:
    python3 update-group-title.py --chat-id oc_xxx
    python3 update-group-title.py --chat-id oc_xxx --dry-run
    python3 update-group-title.py --chat-id oc_xxx --analyze
"""

import argparse
import json
import gzip
import logging
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lark_common import get_tenant_token, lark_api

WORKSPACE = Path(__file__).resolve().parent.parent
CONFIG_FILE = WORKSPACE / "data" / "group-title-config.json"
STATE_FILE = WORKSPACE / "data" / "group-title-state.json"
SESSIONS_DIR = Path("/home/ubuntu/.openclaw/agents/main/sessions")

SGT = timezone(timedelta(hours=8))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def load_config() -> dict:
    """加载配置文件。"""
    default = {
        "topic_tracking": {
            "enabled": True,
            "time_window_minutes": 180,
            "cooldown_minutes": 360,
            "max_title_length": 20
        },
        "topic_keywords": {},
        "topic_display_names": {"general": "聊天中"},
        "verbs": {"active": "聊", "recent": "刚聊", "idle": "空闲"},
        "icons": {"active": "💬", "recent": "☕", "idle": "🌙"}
    }
    
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                config = json.load(f)
                # 合并默认值
                for k, v in default.items():
                    if k not in config:
                        config[k] = v
                return config
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
    return default


def get_session_file(chat_id: str) -> Optional[Path]:
    """根据 chat_id 找到对应的 session 文件。"""
    # 从 sessions.json 中查找
    sessions_file = SESSIONS_DIR / "sessions.json"
    if sessions_file.exists():
        try:
            with open(sessions_file) as f:
                data = json.load(f)
                for sess_key, sess_info in data.get("sessions", {}).items():
                    if chat_id in sess_key:
                        session_id = sess_info.get("session_id")
                        if session_id:
                            file_path = SESSIONS_DIR / f"{session_id}.jsonl"
                            if file_path.exists():
                                return file_path
                            # 尝试压缩文件
                            gz_path = SESSIONS_DIR / f"{session_id}.jsonl.gz"
                            if gz_path.exists():
                                return gz_path
        except Exception as e:
            logger.debug(f"Failed to read sessions.json: {e}")
    return None


def read_recent_messages(file_path: Path, minutes: int = 180) -> List[Tuple[datetime, str, str]]:
    """
    读取最近 N 分钟的消息。
    
    Returns: [(timestamp, role, content), ...]
    """
    messages = []
    cutoff = datetime.now(SGT) - timedelta(minutes=minutes)
    
    try:
        # 处理 gzip 文件
        if str(file_path).endswith('.gz'):
            opener = gzip.open
            mode = 'rt'
        else:
            opener = open
            mode = 'r'
        
        with opener(file_path, mode, encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                    timestamp = msg.get("timestamp")
                    if not timestamp:
                        continue
                    
                    # 解析时间
                    if isinstance(timestamp, (int, float)):
                        ts = timestamp / 1000 if timestamp > 1e12 else timestamp
                        msg_time = datetime.fromtimestamp(ts, tz=SGT)
                    else:
                        msg_time = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
                        msg_time = msg_time.astimezone(SGT)
                    
                    # 只取截止时间后的消息
                    if msg_time >= cutoff:
                        message = msg.get("message", {})
                        role = message.get("role", "")
                        content = message.get("content", "")
                        if content and role in ["user", "assistant"]:
                            messages.append((msg_time, role, content))
                except Exception:
                    continue
    except Exception as e:
        logger.error(f"Failed to read session file: {e}")
    
    return messages


def analyze_topic(messages: List[Tuple[datetime, str, str]], config: dict) -> Tuple[str, str]:
    """
    分析消息内容，提取话题。
    
    Returns: (topic_key, display_name)
    """
    if not messages:
        return "idle", "空闲"
    
    # 合并所有消息内容
    all_text = " ".join([content for _, _, content in messages]).lower()
    
    # 匹配话题关键词
    topic_keywords = config.get("topic_keywords", {})
    topic_scores = {}
    
    for topic, keywords in topic_keywords.items():
        score = 0
        for kw in keywords:
            count = all_text.count(kw.lower())
            score += count
        if score > 0:
            topic_scores[topic] = score
    
    if topic_scores:
        # 取匹配度最高的话题
        best_topic = max(topic_scores, key=topic_scores.get)
        display_name = config.get("topic_display_names", {}).get(best_topic, best_topic)
        return best_topic, display_name
    
    return "general", config.get("topic_display_names", {}).get("general", "聊天中")


def determine_state(messages: List[Tuple[datetime, str, str]], config: dict) -> str:
    """
    判断当前对话状态。
    
    Returns: "active", "recent", "idle"
    """
    if not messages:
        return "idle"
    
    now = datetime.now(SGT)
    time_window = config.get("topic_tracking", {}).get("time_window_minutes", 180)
    cooldown = config.get("topic_tracking", {}).get("cooldown_minutes", 360)
    
    # 最近一条消息的时间
    latest_msg_time = max([t for t, _, _ in messages])
    minutes_since_last = (now - latest_msg_time).total_seconds() / 60
    
    if minutes_since_last <= time_window:
        return "active"
    elif minutes_since_last <= cooldown:
        return "recent"
    else:
        return "idle"


def generate_title(topic_key: str, display_name: str, state: str, config: dict) -> str:
    """生成群标题。"""
    icons = config.get("icons", {})
    verbs = config.get("verbs", {})
    max_len = config.get("topic_tracking", {}).get("max_title_length", 20)
    
    icon = icons.get(state, "🌙")
    verb = verbs.get(state, "空闲")
    
    if state == "idle":
        return f"Luna {icon} {verb}"
    
    # 组合: Luna {icon} {verb}{话题}
    title = f"{verb}{display_name}"
    if len(title) > max_len - 3:
        title = title[:max_len - 4] + "…"
    
    return f"Luna {icon} {title}"


def update_chat_title(chat_id: str, title: str, dry_run: bool = False) -> bool:
    """更新群标题。"""
    if dry_run:
        logger.info(f"[DRY-RUN] Would update title to: {title}")
        return True
    
    try:
        token = get_tenant_token()
        lark_api("PUT", f"/im/v1/chats/{chat_id}", body={"name": title}, token=token)
        logger.info(f"Updated chat {chat_id}: {title}")
        return True
    except Exception as e:
        logger.error(f"Failed to update chat: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="基于话题跟踪自动更新群标题")
    parser.add_argument("--chat-id", required=True, help="群聊 ID")
    parser.add_argument("--dry-run", action="store_true", help="测试模式")
    parser.add_argument("--analyze", action="store_true", help="只分析")
    args = parser.parse_args()
    
    config = load_config()
    
    # 找到 session 文件
    session_file = get_session_file(args.chat_id)
    if not session_file:
        logger.error(f"Session file not found for chat {args.chat_id}")
        return 1
    
    # 读取最近消息
    time_window = config.get("topic_tracking", {}).get("time_window_minutes", 180)
    messages = read_recent_messages(session_file, time_window)
    
    # 分析话题
    topic_key, display_name = analyze_topic(messages, config)
    state = determine_state(messages, config)
    
    # 生成标题
    title = generate_title(topic_key, display_name, state, config)
    
    if args.analyze:
        print(json.dumps({
            "chat_id": args.chat_id,
            "session_file": str(session_file),
            "recent_messages": len(messages),
            "topic": topic_key,
            "display_name": display_name,
            "state": state,
            "generated_title": title
        }, ensure_ascii=False, indent=2))
        return 0
    
    # 更新标题
    success = update_chat_title(args.chat_id, title, args.dry_run)
    
    if success:
        print(json.dumps({"success": True, "title": title}, ensure_ascii=False))
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
