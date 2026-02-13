#!/usr/bin/env python3
"""群标题自动更新脚本 — 根据任务状态自动更新 Lark 群标题。

配置: data/group-title-config.json
"""

import argparse
import json
import logging
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lark_common import get_tenant_token, lark_api, LarkAPIError

# ─── 路径配置 ─────────────────────────────────────────────────────────────────

WORKSPACE = Path(__file__).resolve().parent.parent
TASK_BOARD_FILE = WORKSPACE / "data" / "task-board.json"
STATE_FILE = WORKSPACE / "data" / "group-title-state.json"
CONFIG_FILE = WORKSPACE / "data" / "group-title-config.json"
SESSIONS_DIR = Path("/home/ubuntu/.openclaw/agents/main/sessions")

# 保护群配置（不自动改名的特殊群）
PROTECTED_CHATS_FILE = WORKSPACE / "data" / "group-title-protected.json"

def is_protected_chat(chat_id: str) -> tuple:
    """检查群是否被保护，返回 (is_protected, protected_name)"""
    if not PROTECTED_CHATS_FILE.exists():
        return False, None
    
    try:
        with open(PROTECTED_CHATS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        protected = data.get("protected_chats", {})
        if chat_id in protected:
            return True, protected[chat_id].get("name")
    except Exception:
        pass
    
    return False, None
CONFIG_FILE = WORKSPACE / "data" / "group-title-config.json"
SESSIONS_DIR = Path("/home/ubuntu/.openclaw/agents/main/sessions")

SGT = timezone(timedelta(hours=8))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ─── 配置加载 ─────────────────────────────────────────────────────────────────

def load_config() -> dict:
    """加载配置文件，如果不存在返回默认值。"""
    default_config = {
        "verbs": {
            "running": ["正在", "升级", "修复", "重构", "开发", "配置", "集成"],
            "done": ["完成", "搞定", "修好", "写完"],
            "failed": ["失败", "报错", "卡住"]
        },
        "objects": {
            "openclaw": "OpenClaw",
            "api proxy": "API代理",
            "api-proxy": "API代理",
            "token": "Token统计",
            "表格": "表格",
            "群标题": "群标题",
            "多租户": "多租户",
            "规划器": "规划器",
            "任务面板": "任务面板",
            "日历": "日历",
            "部署": "部署",
            "ci": "CI",
            "pr": "PR",
            "feishu": "飞书",
            "lark": "飞书",
            "heartbeat": "心跳",
            "watchdog": "看门狗",
            "sync": "同步",
            "知识同步": "知识同步",
            "日报": "日报"
        },
        "filters": {
            "max_title_length": 15,
            "max_desc_length": 500
        },
        "icons": {
            "running": "🔄",
            "queued": "⏳",
            "done": "✅",
            "failed": "❌",
            "cancelled": "🚫",
            "idle": "🌙"
        }
    }
    
    if not CONFIG_FILE.exists():
        # 创建默认配置文件
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(default_config, f, indent=2, ensure_ascii=False)
            logger.info(f"Created default config: {CONFIG_FILE}")
        except Exception as e:
            logger.warning(f"Failed to create config: {e}")
        return default_config
    
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
            # 合并默认值
            for key, val in default_config.items():
                if key not in config:
                    config[key] = val
            return config
    except Exception as e:
        logger.error(f"Failed to load config: {e}, using defaults")
        return default_config


# ─── 核心逻辑 ─────────────────────────────────────────────────────────────────

def get_session_file(chat_id: str) -> Optional[Path]:
    """根据 chat_id 找到对应的 session 文件。"""
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
        except Exception:
            pass
    return None


def load_task_board() -> dict:
    """读取任务面板。"""
    if not TASK_BOARD_FILE.exists():
        return {"tasks": []}
    try:
        with open(TASK_BOARD_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to read task board: {e}")
        return {"tasks": []}


def get_primary_task(board: dict, chat_id: Optional[str] = None) -> Optional[dict]:
    """获取当前主要任务。"""
    tasks = board.get("tasks", [])
    now = datetime.now(SGT)
    
    # 过滤后台任务
    filtered = [t for t in tasks if not any(
        kw in t.get("description", "") for kw in ["Periodic Check", "定期检查", "[System]"]
    )]
    
    # 1. 当前群的 running 任务
    if chat_id:
        chat_running = [t for t in filtered 
                       if t.get("status") == "running" 
                       and (t.get("source_chat") == chat_id or t.get("task_chat_id") == chat_id)]
        if chat_running:
            return sorted(chat_running, key=lambda x: x.get("started", ""), reverse=True)[0]
    
    # 2. 全局 running 任务
    all_running = [t for t in filtered if t.get("status") == "running"]
    if all_running:
        return sorted(all_running, key=lambda x: x.get("started", ""), reverse=True)[0]
    
    return None


def format_group_title(task: Optional[dict], config: dict) -> str:
    """生成群标题。"""
    if task is None:
        return f"Luna {config['icons'].get('idle', '🌙')} 空闲中"
    
    status = task.get("status", "unknown")
    icon = config['icons'].get(status, '🌙')
    desc = task.get("description", "")
    
    verbs = config.get("verbs", {})
    objects = config.get("objects", {})
    max_len = config.get("filters", {}).get("max_title_length", 15)
    
    desc_lower = desc.lower()
    
    # 找对象
    obj = ""
    for key, val in objects.items():
        if key in desc_lower:
            obj = val
            break
    
    if not obj:
        clean = re.sub(r"[\[\]—:\-]", "", desc).strip()
        obj = clean[:10] + "…" if len(clean) > 10 else clean
    
    # 找动词
    verb_list = verbs.get(status, ["处理"])
    verb = verb_list[0] if verb_list else "处理"
    
    title = f"{verb}{obj}"
    if len(title) > max_len - 3:
        title = title[:max_len - 4] + "…"
    
    return f"Luna {icon} {title}"


def format_group_description(task: Optional[dict]) -> str:
    """生成群描述。"""
    if task is None:
        return "当前无活跃任务"
    
    lines = [
        f"任务ID: {task.get('id', 'unknown')}",
        f"状态: {task.get('status', 'unknown')}",
    ]
    
    desc = task.get('description', '')
    if desc:
        lines.append(f"描述: {desc}")
    
    created = task.get('created', '')
    if created:
        lines.append(f"创建: {created[:19]}")
    
    return "\n".join(lines)


def update_chat_info(chat_id: str, title: str, description: str, icon: str = "", image_key: str = "", dry_run: bool = False) -> bool:
    """更新群标题、描述和头像。
    
    Args:
        icon: emoji 字符（用于日志显示）
        image_key: Lark 图片 key（用于实际头像）
    """
    if dry_run:
        logger.info(f"[DRY-RUN] Title: {title}")
        logger.info(f"[DRY-RUN] Desc: {description[:80]}...")
        logger.info(f"[DRY-RUN] Icon: {icon}")
        return True
    
    try:
        token = get_tenant_token()
        body = {"name": title}
        if image_key:
            body["avatar"] = image_key
        if description:
            body["description"] = description
        
        lark_api("PUT", f"/im/v1/chats/{chat_id}", body=body, token=token)
        logger.info(f"Updated chat {chat_id}: {title}")
        return True
    except Exception as e:
        logger.error(f"Failed to update chat: {e}")
        return False


# ─── 主入口 ───────────────────────────────────────────────────────────────────

def read_recent_messages(file_path: Path, minutes: int = 180) -> list:
    """读取最近 N 分钟的消息。"""
    messages = []
    cutoff = datetime.now(SGT) - timedelta(minutes=minutes)
    
    try:
        with open(file_path, 'r') as f:
            for line in f:
                try:
                    msg = json.loads(line)
                    ts = msg.get("timestamp")
                    if ts:
                        if isinstance(ts, (int, float)):
                            ts = ts / 1000 if ts > 1e12 else ts
                            msg_time = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(SGT)
                        else:
                            msg_time = datetime.fromisoformat(str(ts).replace("Z", "+00:00")).astimezone(SGT)
                        
                        if msg_time >= cutoff:
                            message = msg.get("message", {})
                            role = message.get("role", "")
                            content = message.get("content", "")
                            if content and role in ["user", "assistant"]:
                                messages.append((msg_time, role, str(content)[:200]))
                except:
                    continue
    except Exception:
        pass
    
    return messages


def analyze_topic(messages: list, config: dict) -> tuple:
    """分析消息话题。"""
    if not messages:
        return "idle", "空闲"
    
    all_text = " ".join([content for _, _, content in messages]).lower()
    topic_keywords = config.get("topic_keywords", {})
    
    for topic, keywords in topic_keywords.items():
        for kw in keywords:
            if kw in all_text:
                display = config.get("topic_display_names", {}).get(topic, topic)
                return topic, display
    
    return "general", config.get("topic_display_names", {}).get("general", "聊天")


def get_active_planner_goal(chat_id: str) -> Optional[str]:
    """
    获取当前群聊活跃规划器的 goal 名称。
    从 data/planner/<chat_id后8位>.json 读取。
    """
    # 尝试不同的 chat_id 格式
    chat_id_clean = chat_id.replace("oc_", "")
    chat_suffixes = [
        chat_id_clean,                # 完整 ID（去掉 oc_）
        chat_id_clean[-8:],           # 后8位（实际文件名格式）
    ]
    
    planner_dir = WORKSPACE / "data" / "planner"
    
    for suffix in chat_suffixes:
        planner_file = planner_dir / f"{suffix}.json"
        if planner_file.exists():
            try:
                with open(planner_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # 检查规划器是否活跃（有 running 状态的步骤）
                    steps = data.get("steps", [])
                    has_running = any(s.get("status") == "running" for s in steps)
                    has_pending = any(s.get("status") == "pending" for s in steps)
                    
                    if has_running or has_pending:
                        goal = data.get("goal", "")
                        # 提取简短意图（去掉过长描述）
                        if len(goal) > 10:
                            # 取前10个字符或第一个语义完整的词
                            goal = goal[:10] + "…"
                        return goal
            except Exception as e:
                logger.debug(f"Failed to read planner file: {e}")
    
    return None


def get_chat_topic(chat_id: str, config: dict) -> Optional[str]:
    """
    分析群聊最近对话，提取话题关键词。
    返回话题显示名或 None。
    """
    # 找到对应的 session 文件
    session_file = get_session_file(chat_id)
    if not session_file:
        return None
    
    # 读取最近消息
    time_window = config.get("topic_tracking", {}).get("time_window_minutes", 180)
    messages = read_recent_messages(session_file, time_window)
    
    if not messages:
        return None
    
    # 分析话题
    topic_key, display_name = analyze_topic(messages, config)
    if topic_key == "idle":
        return None
    
    return display_name


def generate_title(chat_id: str, config: dict) -> Tuple[str, str, str, str]:
    """
    生成群标题、描述、图标和头像key。
    
    优先级：
    1. 有规划器任务 → "Luna 🤖 <规划器goal>"
    2. 有活跃对话话题 → "Luna 💬 聊xxxxx"
    3. 空闲 → "Luna 🌙 空闲"
    
    Returns:
        (title, description, icon, image_key)
    """
    avatar_keys = config.get("avatar_image_keys", {})
    
    # 1. 检查活跃规划器的 goal
    planner_goal = get_active_planner_goal(chat_id)
    if planner_goal:
        icon = config.get("icons", {}).get("planner", "🤖")
        title = f"Luna {icon} {planner_goal}"
        desc = f"当前规划器: {planner_goal}"
        image_key = avatar_keys.get("planner", "")
        return title, desc, icon, image_key
    
    # 2. 检查对话话题
    topic = get_chat_topic(chat_id, config)
    if topic:
        icon = config.get("icons", {}).get("chatting", "💬")
        verb = config.get("verbs", {}).get("chatting", "聊")
        title = f"Luna {icon} {verb}{topic}"
        desc = f"当前话题: {topic}"
        image_key = avatar_keys.get("chatting", "")
        return title, desc, icon, image_key
    
    # 3. 空闲
    icon = config.get("icons", {}).get("idle", "🌙")
    verb = config.get("verbs", {}).get("idle", "空闲")
    title = f"Luna {icon} {verb}"
    desc = "当前无活跃任务或对话"
    image_key = avatar_keys.get("idle", "")
    return title, desc, icon, image_key


def main():
    parser = argparse.ArgumentParser(description="自动更新 Lark 群标题（混合模式）")
    parser.add_argument("--chat-id", required=True, help="群聊 ID")
    parser.add_argument("--dry-run", action="store_true", help="测试模式")
    parser.add_argument("--analyze", action="store_true", help="只分析")
    args = parser.parse_args()
    
    # 检查是否是保护群
    is_protected, protected_name = is_protected_chat(args.chat_id)
    if is_protected:
        logger.info(f"Chat {args.chat_id} is protected, skipping auto-update")
        print(json.dumps({
            "success": True,
            "protected": True,
            "message": f"该群为保护群，不自动改名 (固定名称: {protected_name})"
        }, ensure_ascii=False))
        return 0
    
    config = load_config()
    title, description, icon, image_key = generate_title(args.chat_id, config)
    
    if args.analyze:
        print(json.dumps({
            "chat_id": args.chat_id,
            "generated_title": title,
            "description": description,
            "icon": icon,
            "image_key": image_key,
        }, ensure_ascii=False, indent=2))
        return 0
    
    success = update_chat_info(args.chat_id, title, description, icon, image_key, args.dry_run)
    
    if success:
        print(json.dumps({
            "success": True,
            "title": title,
            "description": description,
            "icon": icon,
            "image_key": image_key[:20] + "..." if image_key else "",
        }, ensure_ascii=False))
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
