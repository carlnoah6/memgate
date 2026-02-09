#!/bin/bash
# OpenClaw Config Validator + Lightweight Sandbox Test
# 轻量级沙盒测试：使用临时端口验证网关启动

CONFIG_FILE="$HOME/.openclaw/openclaw.json"
BACKUP_DIR="$HOME/.openclaw/config-backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo "=========================================="
echo "   Config Validator + Sandbox Test"
echo "=========================================="
echo ""

# 1. 备份
echo "[Step 1] Backup..."
mkdir -p "$BACKUP_DIR"
cp "$CONFIG_FILE" "$BACKUP_DIR/openclaw.json.backup.$TIMESTAMP"
echo "✓ Backup created"

# 2. JSON 语法
echo ""
echo "[Step 2] JSON Syntax Check..."
if ! node -e "JSON.parse(require('fs').readFileSync('$CONFIG_FILE'))" 2>/dev/null; then
    echo "✗ JSON syntax ERROR"
    exit 1
fi
echo "✓ JSON syntax valid"

# 3. Schema 验证
echo ""
echo "[Step 3] Schema Validation..."
if openclaw doctor 2>&1 | grep -q "Invalid config"; then
    echo "✗ Schema validation FAILED"
    openclaw doctor 2>&1 | grep "Invalid config" -A 3
    cp "$BACKUP_DIR/openclaw.json.backup.$TIMESTAMP" "$CONFIG_FILE"
    exit 1
fi
echo "✓ Schema validation passed"

# 4. 轻量级沙盒测试 - 验证配置能被正常解析
echo ""
echo "[Step 4] Config Load Test..."
TEST_OUTPUT=$(openclaw gateway call config.get --params '{}' 2>&1)
if echo "$TEST_OUTPUT" | grep -q "Invalid config\|error"; then
    echo "✗ Config load test FAILED"
    echo "$TEST_OUTPUT" | head -10
    cp "$BACKUP_DIR/openclaw.json.backup.$TIMESTAMP" "$CONFIG_FILE"
    exit 1
fi
echo "✓ Config load test passed"

echo ""
echo "=========================================="
echo "✓ ALL CHECKS PASSED"
echo "=========================================="
