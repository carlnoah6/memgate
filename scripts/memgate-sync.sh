#!/bin/bash
# memgate-sync.sh — 从 GitHub repo 同步 MemGate 到本地 privacy/ 目录
#
# 用法:
#   bash scripts/memgate-sync.sh          # 同步最新 main 分支
#   bash scripts/memgate-sync.sh v1.2.0   # 同步指定 tag/版本
#
# 流程: GitHub (main) → /tmp/memgate → privacy/ + scripts/privacy-check.py

set -e

REPO="carlnoah6/memgate"
BRANCH="${1:-main}"
REPO_DIR="/tmp/memgate"
PRIVACY_DIR="/home/ubuntu/.openclaw/workspace/privacy"
SCRIPTS_DIR="/home/ubuntu/.openclaw/workspace/scripts"

echo "=== MemGate Sync ==="
echo "Source: github.com/$REPO @ $BRANCH"
echo ""

# Step 1: Clone/pull latest
if [ -d "$REPO_DIR/.git" ]; then
    echo "[1/4] Pulling latest..."
    cd "$REPO_DIR"
    git fetch origin
    git checkout "$BRANCH"
    git reset --hard "origin/$BRANCH" 2>/dev/null || git reset --hard "$BRANCH"
else
    echo "[1/4] Cloning..."
    rm -rf "$REPO_DIR"
    git clone "https://github.com/$REPO.git" "$REPO_DIR"
    cd "$REPO_DIR"
    git checkout "$BRANCH" 2>/dev/null || true
fi

# Step 2: Get current version info
COMMIT=$(git rev-parse --short HEAD)
DATE=$(git log -1 --format=%ci)
echo "  Commit: $COMMIT ($DATE)"

# Step 3: Sync core files to privacy/
echo "[2/4] Syncing core modules to $PRIVACY_DIR..."
mkdir -p "$PRIVACY_DIR/knowledge" "$PRIVACY_DIR/patterns" "$PRIVACY_DIR/tests"

cp "$REPO_DIR/memgate/knowledge_store.py" "$PRIVACY_DIR/"
cp "$REPO_DIR/memgate/privacy_context.py" "$PRIVACY_DIR/"
cp "$REPO_DIR/memgate/privacy_review.py" "$PRIVACY_DIR/"
cp "$REPO_DIR/memgate/config.json" "$PRIVACY_DIR/"
cp "$REPO_DIR/memgate/tests/"*.py "$PRIVACY_DIR/tests/" 2>/dev/null || true

# Step 4: Sync CLI script
echo "[3/4] Syncing CLI to $SCRIPTS_DIR/privacy-check.py..."
cp "$REPO_DIR/memgate/cli.py" "$SCRIPTS_DIR/privacy-check.py"

# Step 5: Record version
echo "[4/4] Recording version..."
cat > "$PRIVACY_DIR/.version" << EOF
{
  "repo": "$REPO",
  "branch": "$BRANCH",
  "commit": "$COMMIT",
  "synced_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

echo ""
echo "=== Sync complete ==="
echo "Version: $COMMIT"
echo "Run tests: python3 -m pytest $PRIVACY_DIR/tests/ -v"
