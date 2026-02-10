#!/bin/bash
# MemGate 版本发布脚本
# 用法: ./scripts/release.sh <版本号>
# 例如: ./scripts/release.sh 0.4.0

set -e

VERSION="$1"
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"

if [ -z "$VERSION" ]; then
    CURRENT=$(python3 -c "import tomllib; print(tomllib.load(open('$REPO_DIR/pyproject.toml','rb'))['project']['version'])")
    echo "用法: $0 <新版本号>"
    echo "当前版本: $CURRENT"
    echo ""
    echo "版本号规则 (Semantic Versioning):"
    echo "  MAJOR.MINOR.PATCH"
    echo "  - PATCH: 修 bug、小改动"
    echo "  - MINOR: 新功能、向后兼容"
    echo "  - MAJOR: 破坏性变更"
    exit 1
fi

# 验证版本号格式
if ! echo "$VERSION" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+$'; then
    echo "❌ 版本号格式错误: $VERSION (应为 X.Y.Z)"
    exit 1
fi

cd "$REPO_DIR"

# 检查是否在 main 分支
BRANCH=$(git branch --show-current)
if [ "$BRANCH" != "main" ]; then
    echo "❌ 必须在 main 分支发布 (当前: $BRANCH)"
    exit 1
fi

# 检查工作区干净
if ! git diff --quiet HEAD 2>/dev/null; then
    echo "❌ 工作区有未提交的修改，请先 commit"
    exit 1
fi

# 检查 tag 不存在
if git tag -l "v$VERSION" | grep -q .; then
    echo "❌ Tag v$VERSION 已存在"
    exit 1
fi

# 读取当前版本
CURRENT=$(python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])")
echo "📦 版本升级: $CURRENT → $VERSION"

# 更新 pyproject.toml 中的版本号
sed -i "s/^version = \"$CURRENT\"/version = \"$VERSION\"/" pyproject.toml

# 更新 memgate/__init__.py 中的版本号（如果存在）
if grep -q '__version__' memgate/__init__.py 2>/dev/null; then
    sed -i "s/__version__ = \"$CURRENT\"/__version__ = \"$VERSION\"/" memgate/__init__.py
fi

# 提交版本变更
git add pyproject.toml memgate/__init__.py 2>/dev/null
git commit -m "release: v$VERSION"

# 打 tag
git tag -a "v$VERSION" -m "Release v$VERSION"

echo ""
echo "✅ 版本 v$VERSION 已准备好"
echo ""
echo "下一步: 推送到 GitHub 触发自动发布"
echo "  git push origin main --tags"
echo ""
echo "这将自动:"
echo "  1. 运行测试 (Python 3.10/3.11/3.12)"
echo "  2. 构建并发布到 PyPI"
echo "  3. 创建 GitHub Release"
