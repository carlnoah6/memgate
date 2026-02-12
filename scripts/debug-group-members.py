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

# Import centralized token management
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lark_common import get_tenant_token


def dump_members(chat_id):
    token = get_tenant_token()
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
