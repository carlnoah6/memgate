#!/usr/bin/env python3
"""Simple OAuth callback handler for Lark calendar authorization."""
import json
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import urllib.request

APP_ID = "cli_a90c3a6163785ed2"
APP_SECRET = "***LARK_SECRET_REMOVED***"
TOKEN_FILE = "/home/ubuntu/.openclaw/workspace/data/lark-user-token.json"

class OAuthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        
        code = params.get("code", [None])[0]
        
        if code:
            # Exchange code for user_access_token
            token_data = self.exchange_code(code)
            if token_data and token_data.get("code") == 0:
                # Save token
                os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
                with open(TOKEN_FILE, "w") as f:
                    json.dump(token_data.get("data", {}), f, indent=2)
                
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write("✅ 授权成功！Luna 已获得日历访问权限。你可以关闭这个页面了。".encode("utf-8"))
            else:
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                err = json.dumps(token_data, ensure_ascii=False) if token_data else "Unknown error"
                self.wfile.write(f"❌ 授权失败：{err}".encode("utf-8"))
        else:
            # Lark validation ping or direct access - return valid JSON
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode("utf-8"))
    
    def do_POST(self):
        # Handle POST requests too (Lark might POST for validation)
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else b""
        
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"status": "ok"}).encode("utf-8"))
    
    def exchange_code(self, code):
        """Exchange authorization code for user_access_token."""
        url = "https://open.larksuite.com/open-apis/authen/v1/oidc/access_token"
        
        # First get app_access_token
        app_token_url = "https://open.larksuite.com/open-apis/auth/v3/app_access_token/internal"
        req = urllib.request.Request(app_token_url, 
            data=json.dumps({"app_id": APP_ID, "app_secret": APP_SECRET}).encode(),
            headers={"Content-Type": "application/json"})
        resp = urllib.request.urlopen(req)
        app_data = json.loads(resp.read())
        app_token = app_data.get("app_access_token", "")
        
        # Exchange code
        req = urllib.request.Request(url,
            data=json.dumps({"grant_type": "authorization_code", "code": code}).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {app_token}"
            })
        resp = urllib.request.urlopen(req)
        return json.loads(resp.read())
    
    def log_message(self, format, *args):
        print(f"[OAuth] {args[0]}")

if __name__ == "__main__":
    server = HTTPServer(("127.0.0.1", 8190), OAuthHandler)
    print(f"OAuth callback server running on http://127.0.0.1:8190")
    server.serve_forever()
