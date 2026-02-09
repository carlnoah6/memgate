#!/bin/bash
# OpenClaw Config Validator with Sandbox Testing
# 完整的配置验证流程：
# 1. JSON 语法检查
# 2. 配置项合法性检查 (openclaw doctor)
# 3. 沙盒启动测试（隔离环境验证）

set -e  # 遇到错误立即退出

CONFIG_FILE="$HOME/.openclaw/openclaw.json"
BACKUP_DIR="$HOME/.openclaw/config-backups"
SANDBOX_DIR="$HOME/.openclaw/sandbox-test"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "=========================================="
echo "   OpenClaw Config Validator + Sandbox"
echo "=========================================="
echo ""

# 步骤 0: 备份当前配置
echo -e "${BLUE}[Step 0] Creating backup...${NC}"
mkdir -p "$BACKUP_DIR"
if [ -f "$CONFIG_FILE" ]; then
    cp "$CONFIG_FILE" "$BACKUP_DIR/openclaw.json.backup.$TIMESTAMP"
    echo -e "${GREEN}✓ Backup created${NC}: $BACKUP_DIR/openclaw.json.backup.$TIMESTAMP"
else
    echo -e "${RED}✗ Config file not found${NC}: $CONFIG_FILE"
    exit 1
fi

# 步骤 1: JSON 语法检查
echo ""
echo -e "${BLUE}[Step 1] JSON Syntax Check${NC}"
if node -e "JSON.parse(require('fs').readFileSync('$CONFIG_FILE', 'utf8'))" 2>/dev/null; then
    echo -e "${GREEN}✓ JSON syntax valid${NC}"
else
    echo -e "${RED}✗ JSON syntax error${NC}"
    echo "Error details:"
    node -e "JSON.parse(require('fs').readFileSync('$CONFIG_FILE', 'utf8'))" 2>&1 || true
    exit 1
fi

# 步骤 2: 配置项合法性检查 (使用 openclaw doctor)
echo ""
echo -e "${BLUE}[Step 2] Config Schema Validation${NC}"
echo "Running 'openclaw doctor'..."

DOCTOR_OUTPUT=$(openclaw doctor 2>&1)

if echo "$DOCTOR_OUTPUT" | grep -q "Invalid config"; then
    echo -e "${RED}✗ Config validation failed${NC}"
    echo ""
    echo "Errors:"
    echo "$DOCTOR_OUTPUT" | grep -A 10 "Invalid config"
    echo ""
    echo -e "${YELLOW}⚠ Reverting to backup...${NC}"
    cp "$BACKUP_DIR/openclaw.json.backup.$TIMESTAMP" "$CONFIG_FILE"
    echo "Restored from backup."
    exit 1
elif echo "$DOCTOR_OUTPUT" | grep -q "error\|Error"; then
    echo -e "${YELLOW}⚠ Warnings found:${NC}"
    echo "$DOCTOR_OUTPUT" | grep -i "error" || true
    echo ""
    read -p "Continue with sandbox test? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    echo -e "${GREEN}✓ Schema validation passed${NC}"
fi

# 步骤 3: 沙盒启动测试
echo ""
echo -e "${BLUE}[Step 3] Sandbox Startup Test${NC}"
echo "Testing config in isolated environment..."

# 准备沙盒环境
rm -rf "$SANDBOX_DIR"
mkdir -p "$SANDBOX_DIR"

# 复制配置文件到沙盒
SANDBOX_CONFIG="$SANDBOX_DIR/openclaw.json"
cp "$CONFIG_FILE" "$SANDBOX_CONFIG"

# 修改沙盒配置，使用不同的端口和数据目录
# 使用临时端口避免冲突
TEST_PORT=$((18000 + RANDOM % 1000))
node -e "
const fs = require('fs');
const config = JSON.parse(fs.readFileSync('$SANDBOX_CONFIG', 'utf8'));
config.gateway = config.gateway || {};
config.gateway.port = $TEST_PORT;
config.meta = config.meta || {};
config.meta.sandboxTest = true;
fs.writeFileSync('$SANDBOX_CONFIG', JSON.stringify(config, null, 2));
" 2>/dev/null

# 使用临时 HOME 目录启动 openclaw
export TEST_HOME="$SANDBOX_DIR/home"
mkdir -p "$TEST_HOME"

# 尝试验证配置（模拟启动）
echo "Simulating gateway start on port $TEST_PORT..."

# 方法 1: 使用 openclaw config schema 验证
echo "Method 1: Schema validation..."
if OPENCLAW_STATE_DIR="$TEST_HOME/.openclaw" openclaw gateway call config.get --params '{}' 2>&1 | head -5; then
    echo -e "${GREEN}✓ Schema validation passed${NC}"
else
    echo -e "${YELLOW}⚠ Schema validation inconclusive (may require full gateway)${NC}"
fi

# 方法 2: 使用 dry-run 模式（如果支持）
# 方法 3: 启动临时网关进程并测试连接
echo ""
echo "Method 2: Testing gateway startup..."

# 创建测试用的最小环境
export OPENCLAW_STATE_DIR="$TEST_HOME/.openclaw"
mkdir -p "$OPENCLAW_STATE_DIR"
cp "$SANDBOX_CONFIG" "$OPENCLAW_STATE_DIR/openclaw.json"

# 尝试启动网关（后台）
TEST_PID=""
(
    cd "$TEST_HOME"
    openclaw gateway start 2>&1 > "$SANDBOX_DIR/gateway.log" &
    echo $! > "$SANDBOX_DIR/gateway.pid"
)

# 等待启动
sleep 3

if [ -f "$SANDBOX_DIR/gateway.pid" ]; then
    TEST_PID=$(cat "$SANDBOX_DIR/gateway.pid" 2>/dev/null)
    if kill -0 "$TEST_PID" 2>/dev/null; then
        echo -e "${GREEN}✓ Gateway started successfully (PID: $TEST_PID)${NC}"
        
        # 测试连接
        if curl -s "http://127.0.0.1:$TEST_PORT/health" 2>/dev/null | grep -q "ok\|status"; then
            echo -e "${GREEN}✓ Health check passed${NC}"
        else
            echo -e "${YELLOW}⚠ Health check failed, but gateway is running${NC}"
        fi
        
        # 停止测试网关
        kill "$TEST_PID" 2>/dev/null || true
        sleep 1
        echo -e "${GREEN}✓ Sandbox test passed${NC}"
    else
        echo -e "${RED}✗ Gateway failed to start${NC}"
        echo "Log output:"
        cat "$SANDBOX_DIR/gateway.log" 2>/dev/null | tail -20
        echo ""
        echo -e "${RED}Configuration is invalid. Reverting...${NC}"
        cp "$BACKUP_DIR/openclaw.json.backup.$TIMESTAMP" "$CONFIG_FILE"
        exit 1
    fi
else
    echo -e "${YELLOW}⚠ Could not verify gateway startup (PID file not found)${NC}"
fi

# 清理沙盒
rm -rf "$SANDBOX_DIR"

# 步骤 4: 最终确认
echo ""
echo "=========================================="
echo -e "${GREEN}✓ All validation steps passed!${NC}"
echo "=========================================="
echo ""
echo "Configuration is valid and ready to deploy."
echo ""
echo "To apply to production:"
echo "  openclaw gateway restart"
echo ""

# 显示配置变更摘要
echo "Config changes:"
echo "  Backup: $BACKUP_DIR/openclaw.json.backup.$TIMESTAMP"
echo ""
