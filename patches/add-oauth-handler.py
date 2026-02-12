#!/usr/bin/env python3
"""Patch feishu-webhook plugin to handle OAuth GET callbacks at /webhook/lark.

When a GET request comes with ?code= parameter, exchange it for user_access_token
and save to data/lark-user-token.json.
"""

import re

TARGET = "/home/ubuntu/.openclaw/plugins/feishu-webhook/src/channel.ts"
MARKER = "// [PATCH] OAuth callback handler"

with open(TARGET, "r") as f:
    content = f.read()

if MARKER in content:
    print("✅ OAuth handler patch already applied.")
    exit(0)

# Find the GET handler section and replace it
OLD = '''            // Handle GET requests (health check)
            if (req.method === "GET") {
              res.statusCode = 200;
              res.setHeader("Content-Type", "text/plain");
              res.end("OK");
              return;
            }'''

NEW = '''            // Handle GET requests (health check + OAuth callback)
            if (req.method === "GET") {
              // [PATCH] OAuth callback handler
              const reqUrl = new URL(req.url || "/", `http://${req.headers.host || "localhost"}`);
              const oauthCode = reqUrl.searchParams.get("code");
              if (oauthCode) {
                log?.info(`[${account.accountId}] OAuth callback received, exchanging code for token...`);
                try {
                  // Get app_access_token
                  const apiBase = (domain === "lark") 
                    ? "https://open.larksuite.com/open-apis" 
                    : "https://open.feishu.cn/open-apis";
                  const appTokenResp = await fetch(`${apiBase}/auth/v3/app_access_token/internal`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ app_id: appId, app_secret: appSecret }),
                  });
                  const appTokenData = await appTokenResp.json() as any;
                  const appToken = appTokenData.app_access_token;
                  if (!appToken) throw new Error(`Failed to get app_access_token: ${JSON.stringify(appTokenData)}`);
                  
                  // Exchange code for user_access_token
                  const tokenResp = await fetch(`${apiBase}/authen/v1/oidc/access_token`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json", "Authorization": `Bearer ${appToken}` },
                    body: JSON.stringify({ grant_type: "authorization_code", code: oauthCode }),
                  });
                  const tokenData = await tokenResp.json() as any;
                  
                  if (tokenData.code === 0 && tokenData.data) {
                    // Save token
                    const fs = await import("node:fs");
                    const path = await import("node:path");
                    const tokenPath = "/home/ubuntu/.openclaw/workspace/data/lark-user-token.json";
                    fs.writeFileSync(tokenPath, JSON.stringify(tokenData.data, null, 2));
                    log?.info(`[${account.accountId}] OAuth token saved to ${tokenPath}`);
                    
                    res.statusCode = 200;
                    res.setHeader("Content-Type", "text/html; charset=utf-8");
                    res.end("✅ Authorization successful! Token saved. You can close this page.");
                  } else {
                    log?.warn?.(`[${account.accountId}] OAuth token exchange failed: ${JSON.stringify(tokenData)}`);
                    res.statusCode = 400;
                    res.setHeader("Content-Type", "text/html; charset=utf-8");
                    res.end(`❌ Authorization failed: ${JSON.stringify(tokenData)}`);
                  }
                } catch (err) {
                  log?.warn?.(`[${account.accountId}] OAuth callback error: ${String(err)}`);
                  res.statusCode = 500;
                  res.setHeader("Content-Type", "text/html; charset=utf-8");
                  res.end(`❌ OAuth error: ${String(err)}`);
                }
                return;
              }
              
              res.statusCode = 200;
              res.setHeader("Content-Type", "text/plain");
              res.end("OK");
              return;
            }'''

if OLD not in content:
    print("❌ Cannot find target code block. Plugin may have been modified.")
    exit(1)

content = content.replace(OLD, NEW)

with open(TARGET, "w") as f:
    f.write(content)

print("🔧 OAuth handler patch applied to feishu-webhook plugin.")
print("⚠️  Need to rebuild plugin and restart gateway.")
