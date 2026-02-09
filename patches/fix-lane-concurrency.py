#!/usr/bin/env python3
"""
Patch: Increase global lane concurrency from 1 to 4.

Problem: All sessions share a global `main` lane with maxConcurrent=1.
When the DM session is processing, group chat messages are queued and
wait 60-120+ seconds before being handled.

Fix: Per-session lanes (session:*) stay at maxConcurrent=1 to prevent
concurrent writes to the same session. Global lanes (main, cron,
subagent, nested) are set to maxConcurrent=4 to allow different
sessions to process in parallel.
"""

import re
import sys

SDK_PATH = "/home/ubuntu/.npm-global/lib/node_modules/openclaw/dist/plugin-sdk/index.js"

ORIGINAL = '''\tconst existing = lanes.get(lane);
\tif (existing) return existing;
\tconst created = {
\t\tlane,
\t\tqueue: [],
\t\tactive: 0,
\t\tmaxConcurrent: 1,
\t\tdraining: false
\t};'''

PATCHED = '''\tconst existing = lanes.get(lane);
\tif (existing) return existing;
\t/* ── Patch: Allow concurrent processing on non-session lanes ── */
\t/* Per-session lanes (session:*) stay at 1 to prevent concurrent writes to the same session.
\t   Global lanes (main, cron, subagent, nested) can run concurrently. */
\tconst concurrency = lane.startsWith("session:") ? 1 : 4;
\tconst created = {
\t\tlane,
\t\tqueue: [],
\t\tactive: 0,
\t\tmaxConcurrent: concurrency,
\t\tdraining: false
\t};'''

def main():
    with open(SDK_PATH, "r") as f:
        content = f.read()

    if "Patch: Allow concurrent processing on non-session lanes" in content:
        print("✅ Patch already applied.")
        return 0

    if ORIGINAL not in content:
        print("❌ Could not find target code. SDK may have changed.")
        return 1

    content = content.replace(ORIGINAL, PATCHED, 1)

    with open(SDK_PATH, "w") as f:
        f.write(content)

    print("🔧 Patch applied: main lane concurrency 1 → 4 (session lanes unchanged)")
    return 0

if __name__ == "__main__":
    sys.exit(main())
