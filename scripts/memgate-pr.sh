#!/bin/bash
# memgate-pr.sh — 创建 MemGate 的 PR（从 feature branch 到 main）
#
# 用法:
#   bash scripts/memgate-pr.sh "fix/review-false-positive" "Fix false positive on short words"
#
# 流程: 创建分支 → 提交改动 → 推送 → 创建 PR

set -e

BRANCH_NAME="${1:?Usage: memgate-pr.sh <branch-name> <pr-title>}"
PR_TITLE="${2:?Usage: memgate-pr.sh <branch-name> <pr-title>}"
REPO_DIR="/tmp/memgate"

if [ ! -d "$REPO_DIR/.git" ]; then
    echo "ERROR: Repo not found at $REPO_DIR. Run memgate-sync.sh first."
    exit 1
fi

cd "$REPO_DIR"

# Ensure we're up to date
git fetch origin
git checkout main
git pull origin main

# Create feature branch
git checkout -b "$BRANCH_NAME"

echo ""
echo "Branch '$BRANCH_NAME' created."
echo "Make your changes in $REPO_DIR, then run:"
echo ""
echo "  cd $REPO_DIR"
echo "  git add -A"
echo "  git commit -m \"$PR_TITLE\""
echo "  git push origin $BRANCH_NAME"
echo "  gh pr create --title \"$PR_TITLE\" --body \"...\" --base main"
echo ""
