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
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lark_common import get_tenant_token, lark_api, LarkAPIError

# ─── 路径配置 ─────────────────────────────────────────────────────────────────

WORKSPACE = Path(__file__).resolve().parent.parent
TASK_BOARD_FILE = WORKSPACE / "data" / "task-board.json"
STATE_FILE = WORKSPACE / "data" / "group-title-state.json"
CONFIG_FILE = WORKSPACE / "data" / "group-title-config.json"

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


def update_chat_info(chat_id: str, title: str, description: str, dry_run: bool = False) -> bool:
    """更新群标题和描述。"""
    if dry_run:
        logger.info(f"[DRY-RUN] Title: {title}")
        logger.info(f"[DRY-RUN] Desc: {description[:80]}...")
        return True
    
    try:
        token = get_tenant_token()
        body = {"name": title}
        if description:
            body["description"] = description
        
        lark_api("PUT", f"/im/v1/chats/{chat_id}", body=body, token=token)
        logger.info(f"Updated chat {chat_id}: {title}")
        return True
    except Exception as e:
        logger.error(f"Failed to update chat: {e}")
        return False


# ─── 主入口 ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="自动更新 Lark 群标题")
    parser.add_argument("--chat-id", required=True, help="群聊 ID")
    parser.add_argument("--dry-run", action="store_true", help="测试模式")
    parser.add_argument("--analyze", action="store_true", help="只分析")
    args = parser.parse_args()
    
    config = load_config()
    board = load_task_board()
    task = get_primary_task(board, args.chat_id)
    
    title = format_group_title(task, config)
    description = format_group_description(task)
    
    if args.analyze:
        print(json.dumps({
            "title": title,
            "description": description,
            "task": task
        }, ensure_ascii=False, indent=2))
        return 0
    
    success = update_chat_info(args.chat_id, title, description, args.dry_run)
    
    if success:
        print(json.dumps({
            "success": True,
            "title": title,
            "description_preview": description[:100]
        }, ensure_ascii=False))
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
