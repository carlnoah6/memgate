# 重启来源追踪 & 回复路由 - 测试验证报告

**日期**: 2026-02-12
**任务**: 重启来源追踪 & 回复路由功能验证
**状态**: ✅ 已完成 (7/7 测试通过)

## 背景

此前 Gateway 重启后，无论由谁（Main Session 或某个群聊）触发，重启完成后的汇报总是出现在 Main Session。这导致在群聊中触发重启的用户无法得到反馈。

目标：实现 **"谁触发，汇报给谁"** 的路由机制。

## 实现组件

### 1. 核心脚本

| 脚本 | 功能 | 路径 |
|------|------|------|
| `mark-restart.sh` | 写入重启标记，记录来源 session | `scripts/mark-restart.sh` |
| `check-restart.sh` | 检测重启状态，返回来源信息 | `scripts/check-restart.sh` |
| `restart-gateway.sh` | 统一重启入口，包含完整检查 | `scripts/restart-gateway.sh` |
| `test-restart-routing.sh` | 自动化测试脚本 | `scripts/test-restart-routing.sh` |

### 2. 数据流

```
触发重启
    │
    ▼
restart-gateway.sh
    │
    ├── 强制检查（参数、session、子任务）
    ├── mark-restart.sh "原因" "source_session"
    ├── 创建 wake job (15秒后触发)
    └── openclaw gateway restart
              │
              ▼
        Gateway 重启完成
              │
              ▼
    cron wake job 触发心跳
              │
              ▼
check-restart.sh 检测标记文件
              │
              ▼
    返回 RESTART_INFO JSON
              │
              ▼
    Agent 路由消息到正确 session
```

## 测试验证

### 测试覆盖

创建自动化测试脚本 `scripts/test-restart-routing.sh`，覆盖以下场景：

| 测试 | 描述 | 结果 |
|------|------|------|
| 测试1 | mark-restart.sh 基本功能（创建有效 JSON 标记文件） | ✅ 通过 |
| 测试2 | JSON 内容正确性（reason 和 source_session 字段） | ✅ 通过 |
| 测试3 | 特殊字符处理（引号、反斜杠等） | ✅ 通过 |
| 测试4 | check-restart.sh 检测到标记文件 | ✅ 通过 |
| 测试5 | RESTART_INFO JSON 解析正确性 | ✅ 通过 |
| 测试6 | 正常运行状态检测 | ✅ 通过 |
| 测试7 | restart-gateway.sh 参数验证 | ✅ 通过 |

### 运行测试

```bash
cd /home/ubuntu/.openclaw/workspace
bash scripts/test-restart-routing.sh
```

### 测试结果

```
=== 重启来源追踪 & 回复路由测试 ===
测试时间: Thu Feb 12 05:43:11 UTC 2026

[测试1] mark-restart.sh 基本功能... ✅ 通过
[测试2] mark-restart.sh JSON 内容正确性... ✅ 通过
[测试3] mark-restart.sh 特殊字符处理... ✅ 通过
[测试4] check-restart.sh 检测到标记文件... ✅ 通过
[测试5] check-restart.sh JSON 解析正确性... ✅ 通过
[测试6] check-restart.sh 正常运行状态... ✅ 通过
[测试7] restart-gateway.sh 参数验证... ✅ 通过

=== 测试结果 ===
通过: 7
失败: 0
总计: 7

🎉 所有测试通过!
```

## 标记文件格式

```json
{
  "reason": "配置更新",
  "source_session": "feishu:group:oc_xxx",
  "timestamp": "2026-02-12T12:00:00Z"
}
```

## 使用方式

### 从主 Session 重启

```bash
bash scripts/restart-gateway.sh "升级配置" "main"
```

### 从群聊 Session 重启

```bash
bash scripts/restart-gateway.sh "修复问题" "feishu:group:oc_xxx"
```

### 重启后检查

```bash
bash scripts/check-restart.sh
# 输出: RESTART_INFO: {"reason": "...", "source_session": "..."}
```

## 强制检查项

`restart-gateway.sh` 包含以下强制检查：

1. ✅ 必须提供重启原因
2. ✅ 必须提供 source_session
3. ✅ source_session 格式验证 (main / feishu:group:oc_xxx / feishu:private:oc_xxx)
4. ✅ 当前 session 验证（可选确认）
5. ✅ 活跃子任务检查（防止数据丢失）
6. ✅ Gateway 运行状态检查
7. ✅ 交互式确认（如果从终端运行）

## 后续建议

1. **心跳集成**: 确保主 Agent 在启动时调用 `check-restart.sh` 并正确路由消息
2. **监控告警**: 可以添加重启失败告警机制
3. **日志记录**: 考虑将重启事件记录到持久化日志
4. **回滚机制**: 如果重启后发现问题，考虑自动回滚配置

## 相关文件

- `scripts/mark-restart.sh` - 标记重启来源
- `scripts/check-restart.sh` - 检测重启状态
- `scripts/restart-gateway.sh` - 统一重启入口
- `scripts/test-restart-routing.sh` - 自动化测试
- `docs/restart-source-tracking.md` - 设计文档
- `/tmp/luna-pending-restart.marker` - 临时标记文件
