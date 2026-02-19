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

# Import centralized token management
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lark_common import get_tenant_token, BASE_URL

SGT = timezone(timedelta(hours=8))
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
CARD_BUILDER = os.path.join(SCRIPTS_DIR, "lark-card-builder.py")
STATE_FILE = "/home/ubuntu/.openclaw/workspace/data/dashboard-state.json"
DEFAULT_CHAT_ID = "oc_630995d9b870d2ff6ab3fa34a4e7315a"


def load_state(chat_id):
    """Load state for a specific chat_id."""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            all_state = json.load(f)
        # Support both old format (flat dict) and new format (keyed by chat_id)
        if "chat_id" in all_state and "message_id" in all_state:
            # Old flat format — migrate
            if all_state.get("chat_id") == chat_id:
                return all_state
            return {}
        return all_state.get(chat_id, {})
    return {}


def save_state(chat_id, state):
    """Save state for a specific chat_id."""
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    all_state = {}
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            all_state = json.load(f)
        # Migrate old flat format
        if "chat_id" in all_state and "message_id" in all_state:
            old_chat = all_state.pop("chat_id")
            all_state = {old_chat: all_state}
    all_state[chat_id] = state
    with open(STATE_FILE, "w") as f:
        json.dump(all_state, f, indent=2, ensure_ascii=False)


def build_card():
    """Call lark-card-builder.py and return the card dict."""
    result = subprocess.run(
        ["python3", CARD_BUILDER],
        capture_output=True, text=True, timeout=15
    )
    if result.returncode != 0:
        raise RuntimeError(f"Card builder failed: {result.stderr}")
    return json.loads(result.stdout)


def send_new_card(token, card_json_str, chat_id):
    """POST a new card message. Returns message_id."""
    body = json.dumps({
        "receive_id": chat_id,
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


def main(chat_id=None):
    chat_id = chat_id or DEFAULT_CHAT_ID

    # 1. Build card
    card = build_card()
    card_json_str = json.dumps(card, ensure_ascii=False)

    # Check if content changed (skip unnecessary updates)
    content_hash = hashlib.md5(card_json_str.encode()).hexdigest()
    state = load_state(chat_id)

    # 2. Get token
    token = get_tenant_token()

    # 3. Try PATCH if we have a message_id
    message_id = state.get("message_id")
    updated = False

    if message_id:
        updated = update_card(token, message_id, card_json_str)

    # 4. If PATCH failed or no message_id, POST new
    if not updated:
        message_id = send_new_card(token, card_json_str, chat_id)

    # 5. Save state
    now = datetime.now(SGT)
    state = {
        "message_id": message_id,
        "chat_id": chat_id,
        "last_updated": now.isoformat(),
        "last_hash": content_hash,
        "last_update_ts": now.timestamp(),
    }
    save_state(chat_id, state)

    action = "updated" if updated else "sent_new"
    print(json.dumps({"ok": True, "action": action, "message_id": message_id}, ensure_ascii=False))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("--help", "-h", "help"):
        print(__doc__)
        sys.exit(0)

    # Parse --chat-id argument
    target_chat = None
    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg == "--chat-id" and i + 1 < len(args):
            target_chat = args[i + 1]
            break

    try:
        main(chat_id=target_chat)
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        sys.exit(1)
