#!/usr/bin/env python3
"""
Apply all patches to staging environment.
"""
import subprocess
import sys
import os

STAGING_DIR = "/home/ubuntu/.openclaw/staging/node_modules/openclaw"
PATCHES = [
    "patches/apply-feishu-streaming-fix.py",
    "patches/fix-feishu-group-session-key.py", 
    "patches/fix-streaming-cross-session.py",
    "patches/fix-lane-concurrency.py",
    "patches/fix-feishu-group-wildcard.py",
    "patches/fix-announce-no-reply.py",
    "patches/disable-queue-notification.py",
]

def apply_patch(patch_file, target_dir):
    """Apply a single patch to target directory."""
    # Read the patch file
    with open(patch_file, 'r') as f:
        content = f.read()
    
    # Replace SDK_PATH
    modified = content.replace(
        'SDK_PATH = "/home/ubuntu/.npm-global/lib/node_modules/openclaw/dist/plugin-sdk/index.js"',
        f'SDK_PATH = "{target_dir}/dist/plugin-sdk/index.js"'
    )
    
    # Execute the modified script
    exec(modified, {'__name__': '__main__', 'sys': sys, 're': __import__('re')})
    return 0

if __name__ == "__main__":
    os.chdir("/home/ubuntu/.openclaw/workspace")
    
    for patch in PATCHES:
        if os.path.exists(patch):
            print(f"\n🔧 Applying: {patch}")
            try:
                apply_patch(patch, STAGING_DIR)
            except Exception as e:
                print(f"⚠️  Error applying {patch}: {e}")
        else:
            print(f"⚠️  Patch not found: {patch}")
    
    print("\n✅ Staging patches applied")
