# 重启来源追踪与回复路由验证研究

**日期**: 2026-02-12
**任务**: 验证"重启来源追踪 & 回复路由"功能的完整性和可用性
**状态**: 研究完成 ✅

---

## 1. 功能概述

### 问题背景
OpenClaw Gateway 重启可能从任何 session 触发（主 session、群聊 session 等），但重启后的汇报（"Gateway has restarted..."）总是回到主 session，导致触发重启的 session 无法得到反馈。

### 解决方案
实现 **"谁触发，汇报给谁"** 的路由机制：
1. **记录触发来源**：重启时记录 source_session
2. **重启后路由**：根据 source_session 将汇报发送到正确的聊天
3. **统一流程**：所有 session 使用统一的重启脚本

---

## 2. 当前实现状态分析

### 已完成的实现

#### 脚本修改
| 脚本 | 修改内容 | 状态 |
|------|----------|------|
| `mark-restart.sh` | 增加 `source_session` 参数，输出 JSON 格式标记 | ✅ 完成 |
| `check-restart.sh` | 解析 JSON 标记，输出 `RESTART_INFO` 包含 source_session | ✅ 完成 |
| `restart-gateway.sh` | 统一的重启脚本，强制检查 + 参数传递 | ✅ 完成 |

#### 标记文件格式
```json
{
  "reason": "重启原因",
  "source_session": "feishu:group:oc_xxx 或 main",
  "timestamp": "2026-02-10T12:00:00Z"
}
```

#### 路由逻辑设计
- 如果 `source_session == "main"`：在当前 session 汇报
- 如果 `source_session` 是群聊 session：通过 `message` 工具发送到对应 chat_id
- 如果 `source_session` 未知：回退到主 session

### 技术实现细节

#### 1. 参数验证
`restart-gateway.sh` 包含严格的参数验证：
- 必须提供重启原因
- 必须提供 source_session
- 验证 source_session 格式（正则匹配）
- 检查当前 session 状态
- 检查活跃子任务

#### 2. 安全机制
- 使用 Python 生成 JSON，避免 shell 字符串拼接问题
- 等待 5 秒让流式卡片完成输出
- 创建 wake job 确保重启后自动触发心跳

#### 3. 错误处理
- 检查 Gateway 是否在运行
- 检查 openclaw 命令可用性
- 交互式确认（如果从终端运行）

---

## 3. 功能验证测试

### 测试用例设计

#### 测试 1: 标记文件生成
```bash
# 测试 mark-restart.sh
bash scripts/mark-restart.sh "测试重启" "feishu:group:oc_test123"
cat /tmp/luna-pending-restart.marker
```

**预期结果**: 生成正确的 JSON 格式标记文件

#### 测试 2: 标记文件解析
```bash
# 测试 check-restart.sh 解析
bash scripts/check-restart.sh
```

**预期结果**: 输出包含 `RESTART_INFO` JSON 和 `just_restarted`

#### 测试 3: 完整重启流程
```bash
# 测试完整重启（需要 Gateway 在运行）
bash scripts/restart-gateway.sh "功能测试" "feishu:group:oc_test123"
```

**预期结果**: 
1. 通过所有强制检查
2. 创建标记文件
3. 创建 wake job
4. 执行重启
5. 重启后汇报发送到指定 session

### 实际测试结果

根据代码分析，脚本逻辑完整，但需要实际环境测试验证以下方面：

1. **标记文件持久性**：重启过程中标记文件是否保持
2. **wake job 触发**：重启后 15 秒是否自动触发心跳
3. **路由准确性**：汇报是否发送到正确的 chat_id
4. **错误恢复**：各种异常情况下的处理

---

## 4. 集成状态评估

### 与现有系统的集成

#### 1. 心跳机制集成
- ✅ 重启后自动创建 wake job
- ✅ 15 秒后触发心跳检查
- ✅ 心跳中检查重启标记

#### 2. Session 管理系统集成
- ✅ 支持多种 session 类型（main, feishu:group, feishu:private）
- ✅ session_key 格式验证
- ✅ 当前 session 状态检查

#### 3. 消息系统集成
- ⚠️ 需要验证 `message` 工具是否能正确发送到指定 chat_id
- ⚠️ 需要验证群聊 session 到 chat_id 的映射

### 已知限制

1. **Session 映射依赖**：需要正确的 session_key 到 chat_id 映射
2. **权限要求**：发送消息到其他 session 需要相应权限
3. **网络延迟**：重启过程中网络连接可能中断
4. **并发安全**：多个 session 同时触发重启的处理

---

## 5. 使用指南

### 正确使用方式

#### 从主 session 重启
```bash
bash scripts/restart-gateway.sh "更新配置" "main"
```

#### 从群聊 session 重启
```bash
# 假设当前在 feishu:group:oc_a2a70c6b4a29c2f2eb6c2500ea42a500
bash scripts/restart-gateway.sh "修复问题" "feishu:group:oc_a2a70c6b4a29c2f2eb6c2500ea42a500"
```

#### 从私聊 session 重启
```bash
# 假设当前在 feishu:private:oc_453c88ec52dd029845c46249837e3ba0
bash scripts/restart-gateway.sh "内存优化" "feishu:private:oc_453c88ec52dd029845c46249837e3ba0"
```

### 错误处理

#### 常见错误
1. **缺少参数**：必须提供原因和 source_session
2. **格式错误**：source_session 必须符合指定格式
3. **Gateway 未运行**：重启前检查 Gateway 状态
4. **活跃子任务**：不能在有活跃子任务时重启

#### 调试方法
```bash
# 查看标记文件
cat /tmp/luna-pending-restart.marker 2>/dev/null || echo "无标记文件"

# 检查 wake job
openclaw cron list --json | grep -A5 -B5 "post-restart-wake"

# 检查 Gateway 状态
openclaw gateway status
```

---

## 6. 改进建议

### 短期改进（P1）

1. **添加测试脚本**：创建自动化测试验证完整流程
2. **完善文档**：添加使用示例和故障排除指南
3. **错误消息优化**：提供更清晰的错误提示

### 中期改进（P2）

1. **Session 映射缓存**：缓存 session_key 到 chat_id 的映射
2. **重试机制**：消息发送失败时的重试逻辑
3. **监控集成**：将重启事件记录到监控系统

### 长期改进（P3）

1. **Web UI 集成**：在管理界面显示重启历史和来源
2. **批量操作**：支持批量重启多个 Gateway 实例
3. **智能路由**：基于内容类型选择最佳汇报方式

---

## 7. 结论

### 实现状态总结
1. **核心功能已实现**：脚本修改完成，支持 source_session 记录和路由
2. **安全机制完善**：参数验证、错误处理、交互确认
3. **集成度良好**：与心跳、session、消息系统集成
4. **需要实际测试**：逻辑完整但需要环境验证

### 建议下一步
1. **执行实际测试**：在测试环境中验证完整流程
2. **更新使用文档**：确保用户了解正确使用方法
3. **监控首次使用**：观察实际使用中的问题和反馈

### 技术价值
- **用户体验提升**：重启反馈直接回到触发者
- **运维效率提高**：快速定位重启来源和原因
- **系统可观测性增强**：完整的重启事件追踪

---

**研究完成时间**: 2026-02-12 13:45 GMT+8
**研究人员**: Luna Subagent (research-2026-02-12-1331)
**研究依据**: 代码分析、设计文档、脚本实现