#!/usr/bin/env python3
"""
Patch: Fix Feishu group wildcard ("*") not working as fallback.

Bug: resolveFeishuGroupConfig() does `groups[chatId]` directly.
If chatId is not explicitly configured, it returns undefined,
and requireMention defaults to true. The "*" wildcard key is never
used as a fallback.

Fix: After looking up by chatId, fall back to groups["*"] if no match.
"""

import re
import sys

TARGET = "/home/ubuntu/.npm-global/lib/node_modules/openclaw/dist/plugin-sdk/index.js"

# The buggy code:
OLD = '''function resolveFeishuGroupConfig(params) {
\treturn { groupConfig: resolveFeishuConfig({
\t\tcfg: params.cfg,
\t\taccountId: params.accountId
\t}).groups[params.chatId] };
}'''

# Fixed code: fall back to wildcard "*" if chatId not found
NEW = '''function resolveFeishuGroupConfig(params) {
\tconst _groups = resolveFeishuConfig({
\t\tcfg: params.cfg,
\t\taccountId: params.accountId
\t}).groups;
\treturn { groupConfig: _groups[params.chatId] ?? _groups["*"] };
}'''

with open(TARGET, "r") as f:
    content = f.read()

if NEW in content:
    print("✅ Patch already applied.")
    sys.exit(0)

if OLD not in content:
    print("❌ Could not find target code. Source may have changed.")
    print("Looking for resolveFeishuGroupConfig...")
    # Try to find what's actually there
    match = re.search(r'function resolveFeishuGroupConfig\(params\)\s*\{[^}]+\}', content)
    if match:
        print(f"Found: {match.group()}")
    sys.exit(1)

content = content.replace(OLD, NEW, 1)

with open(TARGET, "w") as f:
    f.write(content)

print("🔧 Patch applied: resolveFeishuGroupConfig now falls back to wildcard '*'.")
print("⚠️  Restart required: bash scripts/restart-gateway.sh 'fix feishu group wildcard'")
