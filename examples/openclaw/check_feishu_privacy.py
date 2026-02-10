#!/usr/bin/env python3
"""
Example: Check Feishu/Lark Group Privacy
========================================

Determines if a group chat is "private" (only specific users + bot) or "public".
Useful for privacy-aware context loading in AI agents.

Usage:
  export LARK_APP_ID="cli_xxx"
  export LARK_APP_SECRET="xxx"
  export LARK_ADMIN_OPEN_ID="ou_xxx"  # The user allowed in private chats
  python3 check_feishu_privacy.py <chat_id>

Logic:
  1. Get bot's own open_id (to exclude itself).
  2. Get group members.
  3. Private = (Members - Bot) ⊆ {AdminUser}
"""

import json
import os
import sys
import urllib.request

# Configuration via Environment Variables
APP_ID = os.getenv("LARK_APP_ID")
APP_SECRET = os.getenv("LARK_APP_SECRET")
ADMIN_OPEN_ID = os.getenv("LARK_ADMIN_OPEN_ID")  # The single human user allowed in private chats


def get_tenant_token():
    if not APP_ID or not APP_SECRET:
        raise ValueError("Please set LARK_APP_ID and LARK_APP_SECRET environment variables.")
        
    req = urllib.request.Request(
        "https://open.larksuite.com/open-apis/auth/v3/tenant_access_token/internal",
        data=json.dumps({"app_id": APP_ID, "app_secret": APP_SECRET}).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
        return resp.get("tenant_access_token")
    except Exception as e:
        print(f"Error getting token: {e}", file=sys.stderr)
        sys.exit(1)


def get_bot_open_id(token):
    """Get bot's own open_id to exclude it from human member count."""
    req = urllib.request.Request(
        "https://open.larksuite.com/open-apis/bot/v3/info",
        headers={"Authorization": f"Bearer {token}"},
    )
    resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
    return resp.get("bot", {}).get("open_id")


def get_group_members(token, chat_id):
    """List all members in the chat."""
    members = []
    page_token = ""
    while True:
        url = f"https://open.larksuite.com/open-apis/im/v1/chats/{chat_id}/members?page_size=100"
        if page_token:
            url += f"&page_token={page_token}"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
        resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
        
        if resp.get("code") != 0:
            print(f"API Error: {resp}", file=sys.stderr)
            return []
            
        members.extend(resp["data"].get("items", []))
        if not resp["data"].get("has_more"):
            break
        page_token = resp["data"].get("page_token", "")
    return members


def check_group_privacy(chat_id):
    token = get_tenant_token()
    if not token:
        return None

    bot_open_id = get_bot_open_id(token)
    members = get_group_members(token, chat_id)

    non_bot_members = []
    for m in members:
        mid = m["member_id"]
        # Exclude bot itself
        if mid != bot_open_id:
            non_bot_members.append({
                "name": m.get("name", "Unknown"),
                "open_id": mid,
                "is_admin": mid == ADMIN_OPEN_ID
            })

    # Privacy Rule:
    # A chat is private if there are human members AND all human members are the Admin.
    # (Adjust logic here if you want to allow multiple specific users)
    human_count = len(non_bot_members)
    all_admin = all(m["is_admin"] for m in non_bot_members)
    
    # Empty chat (bot only) or Admin+Bot only
    is_private = (human_count == 0) or (human_count == 1 and all_admin)

    return {
        "chat_id": chat_id,
        "is_private": is_private,
        "human_count": human_count,
        "details": non_bot_members
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 check_feishu_privacy.py <chat_id>", file=sys.stderr)
        sys.exit(1)

    if not ADMIN_OPEN_ID:
        print("Warning: LARK_ADMIN_OPEN_ID not set. Privacy check will fail for any human member.", file=sys.stderr)

    chat_id = sys.argv[1]
    result = check_group_privacy(chat_id)
    
    print(json.dumps(result, ensure_ascii=False, indent=2))
    
    # Exit code: 0 = Private, 1 = Public/Unsafe
    sys.exit(0 if result and result["is_private"] else 1)
