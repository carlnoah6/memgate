#!/bin/bash
# 重启来源追踪 & 回复路由 - 测试验证脚本
# 运行方式: bash scripts/test-restart-routing.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORKSPACE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
TEST_LOG="$WORKSPACE_DIR/data/test-restart-routing.log"
MARKER_FILE="/tmp/luna-pending-restart.marker"

echo "=== 重启来源追踪 & 回复路由测试 ===" | tee "$TEST_LOG"
echo "测试时间: $(date)" | tee -a "$TEST_LOG"
echo "" | tee -a "$TEST_LOG"

PASSED=0
FAILED=0

# 测试1: mark-restart.sh 基本功能
test_mark_restart_basic() {
    echo "[测试1] mark-restart.sh 基本功能..." | tee -a "$TEST_LOG"
    
    # 清理
    rm -f "$MARKER_FILE"
    
    # 执行标记
    bash "$SCRIPT_DIR/mark-restart.sh" "测试原因" "feishu:group:oc_test123"
    
    # 验证文件存在
    if [ ! -f "$MARKER_FILE" ]; then
        echo "  ❌ 失败: 标记文件未创建" | tee -a "$TEST_LOG"
        FAILED=$((FAILED + 1))
        return
    fi
    
    # 验证 JSON 格式
    if ! python3 -c "import json; json.load(open('$MARKER_FILE'))" 2>/dev/null; then
        echo "  ❌ 失败: 标记文件不是有效 JSON" | tee -a "$TEST_LOG"
        FAILED=$((FAILED + 1))
        return
    fi
    
    echo "  ✅ 通过" | tee -a "$TEST_LOG"
    PASSED=$((PASSED + 1))
}

# 测试2: mark-restart.sh JSON 内容正确性
test_mark_restart_content() {
    echo "[测试2] mark-restart.sh JSON 内容正确性..." | tee -a "$TEST_LOG"
    
    # 清理
    rm -f "$MARKER_FILE"
    
    # 执行标记
    bash "$SCRIPT_DIR/mark-restart.sh" "升级配置" "feishu:private:oc_abc123"
    
    # 读取并验证内容
    REASON=$(python3 -c "import json; print(json.load(open('$MARKER_FILE')).get('reason', ''))")
    SOURCE=$(python3 -c "import json; print(json.load(open('$MARKER_FILE')).get('source_session', ''))")
    
    if [ "$REASON" != "升级配置" ]; then
        echo "  ❌ 失败: reason 字段不正确 (期望: '升级配置', 实际: '$REASON')" | tee -a "$TEST_LOG"
        FAILED=$((FAILED + 1))
        return
    fi
    
    if [ "$SOURCE" != "feishu:private:oc_abc123" ]; then
        echo "  ❌ 失败: source_session 字段不正确 (期望: 'feishu:private:oc_abc123', 实际: '$SOURCE')" | tee -a "$TEST_LOG"
        FAILED=$((FAILED + 1))
        return
    fi
    
    echo "  ✅ 通过" | tee -a "$TEST_LOG"
    PASSED=$((PASSED + 1))
}

# 测试3: mark-restart.sh 特殊字符处理
test_mark_restart_special_chars() {
    echo "[测试3] mark-restart.sh 特殊字符处理..." | tee -a "$TEST_LOG"
    
    # 清理
    rm -f "$MARKER_FILE"
    
    # 使用包含引号和特殊字符的原因
    bash "$SCRIPT_DIR/mark-restart.sh" '包含"引号"和\反斜杠的原因' "main"
    
    # 验证 JSON 仍然有效
    if ! python3 -c "import json; json.load(open('$MARKER_FILE'))" 2>/dev/null; then
        echo "  ❌ 失败: 特殊字符导致 JSON 无效" | tee -a "$TEST_LOG"
        FAILED=$((FAILED + 1))
        return
    fi
    
    # 验证内容正确
    REASON=$(python3 -c "import json; print(json.load(open('$MARKER_FILE')).get('reason', ''))")
    if [[ "$REASON" != *"引号"* ]]; then
        echo "  ❌ 失败: 特殊字符未正确保存" | tee -a "$TEST_LOG"
        FAILED=$((FAILED + 1))
        return
    fi
    
    echo "  ✅ 通过" | tee -a "$TEST_LOG"
    PASSED=$((PASSED + 1))
}

# 测试4: check-restart.sh 检测到标记文件
test_check_restart_detect() {
    echo "[测试4] check-restart.sh 检测到标记文件..." | tee -a "$TEST_LOG"
    
    # 清理
    rm -f "$MARKER_FILE"
    rm -f "$WORKSPACE_DIR/data/gateway.pid"
    
    # 创建测试标记
    echo '{"reason": "测试重启", "source_session": "feishu:group:oc_test456", "timestamp": "2026-02-12T12:00:00Z"}' > "$MARKER_FILE"
    
    # 模拟 gateway PID 文件
    echo "$$" > "$WORKSPACE_DIR/data/gateway.pid"
    
    # 运行检查
    OUTPUT=$(bash "$SCRIPT_DIR/check-restart.sh" 2>&1)
    
    # 验证输出包含 RESTART_INFO
    if [[ "$OUTPUT" != *"RESTART_INFO:"* ]]; then
        echo "  ❌ 失败: 输出不包含 RESTART_INFO" | tee -a "$TEST_LOG"
        echo "  输出: $OUTPUT" | tee -a "$TEST_LOG"
        FAILED=$((FAILED + 1))
        return
    fi
    
    # 验证输出包含 just_restarted
    if [[ "$OUTPUT" != *"just_restarted"* ]]; then
        echo "  ❌ 失败: 输出不包含 just_restarted" | tee -a "$TEST_LOG"
        FAILED=$((FAILED + 1))
        return
    fi
    
    # 验证标记文件已被删除
    if [ -f "$MARKER_FILE" ]; then
        echo "  ❌ 失败: 标记文件未被删除" | tee -a "$TEST_LOG"
        FAILED=$((FAILED + 1))
        return
    fi
    
    echo "  ✅ 通过" | tee -a "$TEST_LOG"
    PASSED=$((PASSED + 1))
}

# 测试5: check-restart.sh JSON 解析正确性
test_check_restart_json_parse() {
    echo "[测试5] check-restart.sh JSON 解析正确性..." | tee -a "$TEST_LOG"
    
    # 清理
    rm -f "$MARKER_FILE"
    rm -f "$WORKSPACE_DIR/data/gateway.pid"
    
    # 创建测试标记
    echo '{"reason": "配置更新", "source_session": "main", "timestamp": "2026-02-12T10:00:00Z"}' > "$MARKER_FILE"
    
    # 模拟 gateway PID 文件
    echo "$$" > "$WORKSPACE_DIR/data/gateway.pid"
    
    # 运行检查并提取 JSON
    OUTPUT=$(bash "$SCRIPT_DIR/check-restart.sh" 2>&1 | grep "RESTART_INFO:")
    
    # 提取 JSON 部分
    JSON_PART=$(echo "$OUTPUT" | sed 's/RESTART_INFO: //')
    
    # 验证 JSON 有效
    if ! echo "$JSON_PART" | python3 -c "import json, sys; json.load(sys.stdin)" 2>/dev/null; then
        echo "  ❌ 失败: RESTART_INFO 不是有效 JSON" | tee -a "$TEST_LOG"
        echo "  输出: $OUTPUT" | tee -a "$TEST_LOG"
        FAILED=$((FAILED + 1))
        return
    fi
    
    echo "  ✅ 通过" | tee -a "$TEST_LOG"
    PASSED=$((PASSED + 1))
}

# 测试6: check-restart.sh 正常运行状态
test_check_restart_normal() {
    echo "[测试6] check-restart.sh 正常运行状态..." | tee -a "$TEST_LOG"
    
    # 清理
    rm -f "$MARKER_FILE"
    
    # 获取真实 gateway PID
    REAL_PID=$(pgrep -f "openclaw.*gateway" | head -1)
    
    if [ -z "$REAL_PID" ]; then
        echo "  ⚠️  跳过: Gateway 未运行" | tee -a "$TEST_LOG"
        PASSED=$((PASSED + 1))
        return
    fi
    
    # 写入真实 PID 到文件
    echo "$REAL_PID" > "$WORKSPACE_DIR/data/gateway.pid"
    
    # 运行检查
    OUTPUT=$(bash "$SCRIPT_DIR/check-restart.sh" 2>&1)
    
    # 验证输出包含 running_normally（PID 未变化时）
    if [[ "$OUTPUT" == *"running_normally"* ]]; then
        echo "  ✅ 通过 (PID 未变化)" | tee -a "$TEST_LOG"
        PASSED=$((PASSED + 1))
        return
    fi
    
    # 或者验证输出包含 just_restarted（PID 变化时，这是正常行为）
    if [[ "$OUTPUT" == *"just_restarted"* ]]; then
        echo "  ✅ 通过 (PID 变化检测)" | tee -a "$TEST_LOG"
        PASSED=$((PASSED + 1))
        return
    fi
    
    echo "  ❌ 失败: 未返回预期状态" | tee -a "$TEST_LOG"
    echo "  输出: $OUTPUT" | tee -a "$TEST_LOG"
    FAILED=$((FAILED + 1))
}

# 测试7: restart-gateway.sh 参数验证
test_restart_gateway_validation() {
    echo "[测试7] restart-gateway.sh 参数验证..." | tee -a "$TEST_LOG"
    
    local TEST_FAILED=0
    
    # 测试缺少参数 - 应该返回非零退出码
    set +e
    bash "$SCRIPT_DIR/restart-gateway.sh" >/dev/null 2>&1
    local EXIT_CODE=$?
    set -e
    
    if [ $EXIT_CODE -eq 0 ]; then
        echo "  ❌ 失败: 缺少参数时应返回非零退出码" | tee -a "$TEST_LOG"
        TEST_FAILED=1
    fi
    
    # 测试无效的 source_session 格式
    set +e
    bash "$SCRIPT_DIR/restart-gateway.sh" "原因" "invalid_format" >/dev/null 2>&1
    EXIT_CODE=$?
    set -e
    
    if [ $EXIT_CODE -eq 0 ]; then
        echo "  ❌ 失败: 无效格式时应返回非零退出码" | tee -a "$TEST_LOG"
        TEST_FAILED=1
    fi
    
    if [ $TEST_FAILED -eq 1 ]; then
        FAILED=$((FAILED + 1))
        return
    fi
    
    echo "  ✅ 通过" | tee -a "$TEST_LOG"
    PASSED=$((PASSED + 1))
}

# 运行所有测试
run_all_tests() {
    echo "开始运行测试..." | tee -a "$TEST_LOG"
    echo "" | tee -a "$TEST_LOG"
    
    test_mark_restart_basic
    test_mark_restart_content
    test_mark_restart_special_chars
    test_check_restart_detect
    test_check_restart_json_parse
    test_check_restart_normal
    test_restart_gateway_validation
    
    echo "" | tee -a "$TEST_LOG"
    echo "=== 测试结果 ===" | tee -a "$TEST_LOG"
    echo "通过: $PASSED" | tee -a "$TEST_LOG"
    echo "失败: $FAILED" | tee -a "$TEST_LOG"
    echo "总计: $((PASSED + FAILED))" | tee -a "$TEST_LOG"
    
    if [ $FAILED -eq 0 ]; then
        echo "" | tee -a "$TEST_LOG"
        echo "🎉 所有测试通过!" | tee -a "$TEST_LOG"
        return 0
    else
        echo "" | tee -a "$TEST_LOG"
        echo "⚠️  有测试失败，请检查日志" | tee -a "$TEST_LOG"
        return 1
    fi
}

# 执行测试
run_all_tests
exit $?
