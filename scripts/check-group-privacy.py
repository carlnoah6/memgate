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
import sys
import urllib.request
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
APP_ID = "cli_a90c3a6163785ed2"
APP_SECRET = "***LARK_SECRET_REMOVED***"
CARL_OPEN_ID = "ou_35f664e694dd100adf97b867e68e1d3a"


def get_tenant_token():
    req = urllib.request.Request(
        "https://open.larksuite.com/open-apis/auth/v3/tenant_access_token/internal",
        data=json.dumps({"app_id": APP_ID, "app_secret": APP_SECRET}).encode(),
        headers={"Content-Type": "application/json"},
    )
    resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
    return resp["tenant_access_token"]


def get_bot_open_id(token):
    """获取 bot 自己的 open_id，用于从群成员中排除自己"""
    req = urllib.request.Request(
        "https://open.larksuite.com/open-apis/bot/v3/info",
        headers={"Authorization": f"Bearer {token}"},
    )
    resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
    return resp["bot"]["open_id"]


def get_group_members(token, chat_id):
    """获取群聊所有成员"""
    members = []
    page_token = ""
    while True:
        url = f"https://open.larksuite.com/open-apis/im/v1/chats/{chat_id}/members?page_size=100"
        if page_token:
            url += f"&page_token={page_token}"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
        resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
        if resp.get("code") != 0:
            raise RuntimeError(f"API error: {resp}")
        members.extend(resp["data"].get("items", []))
        if not resp["data"].get("has_more"):
            break
        page_token = resp["data"].get("page_token", "")
    return members


def check_group_privacy(chat_id):
    token = get_tenant_token()
    bot_open_id = get_bot_open_id(token)
    members = get_group_members(token, chat_id)

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
