#!/usr/bin/env python3
"""
Debug script to dump raw member data from Lark API for a specific chat.
Usage: python3 scripts/debug-group-members.py <chat_id>
"""

import json
import os
import sys
import urllib.request
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
SECRETS_FILE = WORKSPACE / "data/lark-secrets.json"

def load_config():
    config = {
        "app_id": os.getenv("LARK_APP_ID"),
        "app_secret": os.getenv("LARK_APP_SECRET"),
    }

    if SECRETS_FILE.exists():
        try:
            with open(SECRETS_FILE, "r") as f:
                file_config = json.load(f)
                if file_config.get("app_id"):
                    config["app_id"] = file_config["app_id"]
                if file_config.get("app_secret"):
                    config["app_secret"] = file_config["app_secret"]
        except Exception as e:
            print(f"Warning: Failed to load secrets file: {e}", file=sys.stderr)
    
    return config

def get_tenant_token(app_id, app_secret):
    req = urllib.request.Request(
        "https://open.larksuite.com/open-apis/auth/v3/tenant_access_token/internal",
        data=json.dumps({"app_id": app_id, "app_secret": app_secret}).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
        return resp.get("tenant_access_token")
    except Exception as e:
        print(f"Error getting token: {e}")
        return None

def dump_members(chat_id):
    config = load_config()
    token = get_tenant_token(config["app_id"], config["app_secret"])
    if not token:
        print("Failed to get token")
        return

    print(f"--- Fetching members for {chat_id} ---")
    
    url = f"https://open.larksuite.com/open-apis/im/v1/chats/{chat_id}/members?page_size=100&member_id_type=open_id"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    
    try:
        raw_resp = urllib.request.urlopen(req, timeout=10).read()
        resp = json.loads(raw_resp)
        
        print(json.dumps(resp, indent=2, ensure_ascii=False))
        
        if resp.get("code") == 0:
            items = resp["data"].get("items", [])
            print(f"\nTotal items: {len(items)}")
            for item in items:
                print(f"- Name: {item.get('name')}")
                print(f"  ID: {item.get('member_id')}")
                print(f"  Type: {item.get('member_id_type')} (Note: API response might not have 'type' field directly, check structure)")
                print(f"  Is Tenant: {item.get('is_tenant_manager')}")
                
    except Exception as e:
        print(f"Error fetching members: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/debug-group-members.py <chat_id>")
        sys.exit(1)
    
    dump_members(sys.argv[1])
