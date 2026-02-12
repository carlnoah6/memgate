#!/usr/bin/env python3
"""get-source-chat.py — Resolve chat_id from a Lark message_id.

Usage:
    python3 get-source-chat.py <message_id>
    python3 get-source-chat.py om_x100b57fd0b0304a8e2d67df68d61bcd

Output: just the chat_id (oc_xxx), suitable for piping.
Exit 1 if lookup fails.
"""
import json
import sys
import urllib.request

APP_ID = "cli_a90c3a6163785ed2"
APP_SECRET = "***LARK_SECRET_REMOVED***"
BASE = "https://open.larksuite.com/open-apis"


def get_tenant_token() -> str:
    req = urllib.request.Request(
        f"{BASE}/auth/v3/tenant_access_token/internal",
        data=json.dumps({"app_id": APP_ID, "app_secret": APP_SECRET}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read()).get("tenant_access_token", "")


def get_chat_id(token: str, message_id: str) -> str:
    req = urllib.request.Request(
        f"{BASE}/im/v1/messages/{message_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read())
    if data.get("code") != 0:
        print(f"Lark API error: {data.get('code')} {data.get('msg')}", file=sys.stderr)
        sys.exit(1)
    items = data.get("data", {}).get("items", [])
    if not items:
        print("No message found", file=sys.stderr)
        sys.exit(1)
    return items[0].get("chat_id", "")


def main():
    if len(sys.argv) < 2:
        print("Usage: get-source-chat.py <message_id>", file=sys.stderr)
        sys.exit(1)

    message_id = sys.argv[1]
    token = get_tenant_token()
    chat_id = get_chat_id(token, message_id)
    if not chat_id:
        print("chat_id not found", file=sys.stderr)
        sys.exit(1)
    print(chat_id)


if __name__ == "__main__":
    main()
