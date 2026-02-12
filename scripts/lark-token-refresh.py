#!/usr/bin/env python3
"""Lark OAuth token refresh utility.
Usage: python3 lark-token-refresh.py [--check]
  --check: only refresh if token expires within 30 minutes
  (no flag): force refresh
"""
import json, os, sys, time, urllib.request

# Import centralized token management
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lark_common import get_app_token, USER_TOKEN_FILE

TOKEN_FILE = str(USER_TOKEN_FILE)

def load_token():
    with open(TOKEN_FILE) as f:
        return json.load(f)

def save_token(data):
    os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
    with open(TOKEN_FILE, "w") as f:
        json.dump(data, f, indent=2)

def refresh_token(refresh_token_str):
    app_token = get_app_token()
    req = urllib.request.Request(
        "https://open.larksuite.com/open-apis/authen/v1/oidc/refresh_access_token",
        data=json.dumps({
            "grant_type": "refresh_token",
            "refresh_token": refresh_token_str
        }).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {app_token}"
        })
    resp = urllib.request.urlopen(req)
    return json.loads(resp.read())

def main():
    check_only = "--check" in sys.argv
    
    token_data = load_token()
    
    # Check if we need to refresh
    mtime = os.path.getmtime(TOKEN_FILE)
    expires_in = token_data.get("expires_in", 7200)
    expires_at = mtime + expires_in
    remaining = expires_at - time.time()
    
    if check_only and remaining > 1800:  # 30 min buffer
        print(f"Token still valid ({int(remaining/60)} min remaining)")
        return
    
    print(f"Token {'expired' if remaining <= 0 else f'expiring in {int(remaining/60)} min'}, refreshing...")
    
    result = refresh_token(token_data["refresh_token"])
    if result.get("code") == 0:
        save_token(result["data"])
        print(f"✅ Token refreshed, new expiry: {result['data'].get('expires_in', '?')}s")
    else:
        print(f"❌ Refresh failed: {result.get('msg', 'unknown error')}")
        sys.exit(1)

if __name__ == "__main__":
    main()
