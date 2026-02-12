#!/usr/bin/env python3
"""Luna OS - Lark task dashboard card (send/update)

Sends or updates the task dashboard card in the designated Lark group.
"""

import json
import os
import subprocess
import sys
import hashlib
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

SGT = timezone(timedelta(hours=8))
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
CARD_BUILDER = os.path.join(SCRIPTS_DIR, "lark-card-builder.py")
STATE_FILE = "/home/ubuntu/.openclaw/workspace/data/dashboard-state.json"
CHAT_ID = "oc_630995d9b870d2ff6ab3fa34a4e7315a"

APP_ID = "cli_a90c3a6163785ed2"
APP_SECRET = "***LARK_SECRET_REMOVED***"
BASE_URL = "https://open.larksuite.com/open-apis"


def get_tenant_token():
    req = urllib.request.Request(
        f"{BASE_URL}/auth/v3/tenant_access_token/internal",
        data=json.dumps({"app_id": APP_ID, "app_secret": APP_SECRET}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read())
    token = data.get("tenant_access_token")
    if not token:
        raise RuntimeError(f"Failed to get token: {data}")
    return token


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {}


def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def build_card():
    """Call lark-card-builder.py and return the card dict."""
    result = subprocess.run(
        ["python3", CARD_BUILDER],
        capture_output=True, text=True, timeout=15
    )
    if result.returncode != 0:
        raise RuntimeError(f"Card builder failed: {result.stderr}")
    return json.loads(result.stdout)


def send_new_card(token, card_json_str):
    """POST a new card message. Returns message_id."""
    body = json.dumps({
        "receive_id": CHAT_ID,
        "msg_type": "interactive",
        "content": card_json_str,
    }).encode()
    req = urllib.request.Request(
        f"{BASE_URL}/im/v1/messages?receive_id_type=chat_id",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
    if data.get("code") != 0:
        raise RuntimeError(f"Send failed: code={data.get('code')} msg={data.get('msg')}")
    return data["data"]["message_id"]


def update_card(token, message_id, card_json_str):
    """PATCH an existing card message. Returns True on success."""
    body = json.dumps({
        "content": card_json_str,
    }).encode()
    req = urllib.request.Request(
        f"{BASE_URL}/im/v1/messages/{message_id}",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="PATCH",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        return data.get("code") == 0
    except urllib.error.HTTPError:
        return False
    except Exception:
        return False


def main():
    # Session overview is refreshed by heartbeat locally.
    # Dashboard rebuild just reads existing data from workspace/data/.

    # 1. Build card
    card = build_card()
    card_json_str = json.dumps(card, ensure_ascii=False)

    # Check if content changed (skip unnecessary updates)
    content_hash = hashlib.md5(card_json_str.encode()).hexdigest()
    state = load_state()

    # 2. Get token
    token = get_tenant_token()

    # 3. Try PATCH if we have a message_id
    message_id = state.get("message_id")
    updated = False

    if message_id:
        updated = update_card(token, message_id, card_json_str)

    # 4. If PATCH failed or no message_id, POST new
    if not updated:
        message_id = send_new_card(token, card_json_str)

    # 5. Save state
    now = datetime.now(SGT)
    state = {
        "message_id": message_id,
        "chat_id": CHAT_ID,
        "last_updated": now.isoformat(),
        "last_hash": content_hash,
        "last_update_ts": now.timestamp(),
    }
    save_state(state)

    action = "updated" if updated else "sent_new"
    print(json.dumps({"ok": True, "action": action, "message_id": message_id}, ensure_ascii=False))


if __name__ == "__main__":
    # Accept optional "auto" argument (called from task-board-notify.py)
    # Behavior is the same regardless
    try:
        main()
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        sys.exit(1)
