#!/usr/bin/env python3
"""
群聊隐私级别检查 — 通过 Lark API 判断群聊是否为私密对话

用法:
  python3 scripts/check-group-privacy.py <chat_id>

输出 JSON:
  {
    "chat_id": "oc_xxx",
    "is_private": true/false,
    "reason": "说明",
    "members": [{"name": "...", "open_id": "...", "is_bot": bool, "is_carl": bool}],
    "non_bot_members": ["Carl"],
    "human_count": 1
  }

判断规则:
  - 获取 bot 自己的 open_id（通过 /bot/v3/info）
  - 获取群成员列表
  - 过滤掉 bot 自己
  - 如果剩余成员只有 Carl → is_private = true
  - 否则 → is_private = false（有其他人）
"""

import json
import os
import sys
from pathlib import Path

# Add scripts dir to path for lark_common import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lark_common import get_tenant_token, get_bot_info, get_chat_members, CARL_OPEN_ID


def check_group_privacy(chat_id):
    token = get_tenant_token()
    bot_info = get_bot_info(token=token)
    bot_open_id = bot_info.get("bot", bot_info).get("open_id", "")
    raw_members = get_chat_members(chat_id, token=token)
    members = raw_members

    annotated = []
    non_bot = []
    for m in members:
        mid = m["member_id"]
        name = m.get("name", "")
        is_bot = mid == bot_open_id
        is_carl = mid == CARL_OPEN_ID
        annotated.append({
            "name": name,
            "open_id": mid,
            "is_bot": is_bot,
            "is_carl": is_carl,
        })
        if not is_bot:
            non_bot.append({"name": name, "open_id": mid, "is_carl": is_carl})

    # Private = only Carl (no other humans)
    human_count = len(non_bot)
    all_carl = all(m["is_carl"] for m in non_bot)
    is_private = human_count <= 1 and all_carl

    if is_private:
        reason = "只有 Carl 和 Bot，视为私聊"
    else:
        other_names = [m["name"] for m in non_bot if not m["is_carl"]]
        reason = f"群内有其他成员: {', '.join(other_names)}"

    return {
        "chat_id": chat_id,
        "is_private": is_private,
        "reason": reason,
        "bot_open_id": bot_open_id,
        "members": annotated,
        "non_bot_members": [m["name"] for m in non_bot],
        "human_count": human_count,
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/check-group-privacy.py <chat_id>", file=sys.stderr)
        sys.exit(1)

    chat_id = sys.argv[1]
    result = check_group_privacy(chat_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))

    # Exit code: 0 = private, 1 = not private
    sys.exit(0 if result["is_private"] else 1)
