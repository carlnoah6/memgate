# OpenClaw 2.3-1 → 2.9 升级执行清单

**版本**: 2026.2.12 v1.0  
**升级窗口**: 建议 02:00-04:00 SGT（低流量时段）  
**预估耗时**: 45-60 分钟（含验证）  
**回滚时间**: 5-10 分钟

---

## 📋 1. 步骤清单（含检查点）

### 阶段 0: 升级前 24 小时（准备）

| # | 步骤 | 检查点 | 负责人 |
|---|------|--------|--------|
| 0.1 | 阅读 2.9 完整 Release Notes | 确认无新增 breaking changes | Luna |
| 0.2 | 在 staging 环境预演升级流程 | Staging 升级成功且 patches 可应用 | Luna |
| 0.3 | 通知 Carl 升级计划和时间窗口 | Carl 确认时间可用 | Luna |
| 0.4 | 创建升级执行脚本 | `scripts/upgrade-openclaw.sh` 已创建并测试 | Luna |
| 0.5 | 创建回滚脚本 | `scripts/rollback-openclaw.sh` 已创建并测试 | Luna |

### 阶段 1: 升级前 1 小时（备份）

| # | 步骤 | 检查点 | 命令/脚本 |
|---|------|--------|-----------|
| 1.1 | 检查当前运行状态 | Gateway 运行正常 | `openclaw gateway status` |
| 1.2 | 备份当前 node_modules | 备份文件 > 100MB | `sudo tar czf /home/ubuntu/backup/openclaw-$(date +%Y%m%d-%H%M).tar.gz -C /home/ubuntu/.npm-global/lib/node_modules openclaw` |
| 1.3 | 备份配置文件 | config.json 已备份 | `cp ~/.openclaw/config.json ~/backup/config-$(date +%Y%m%d-%H%M).json` |
| 1.4 | 备份 state 目录 | state 目录已备份 | `cp -r ~/.openclaw/state ~/backup/state-$(date +%Y%m%d-%H%M)` |
| 1.5 | 记录当前版本 | 版本信息已保存 | `npm list -g openclaw > ~/backup/version-$(date +%Y%m%d-%H%M).txt` |
| 1.6 | 创建备份清单 | 备份完整性已确认 | 见下方备份验证命令 |

**备份验证命令**:
```bash
# 验证备份完整性
ls -lh ~/backup/openclaw-$(date +%Y%m%d)*.tar.gz
ls -lh ~/backup/config-$(date +%Y%m%d)*.json
ls -lh ~/backup/state-$(date +%Y%m%d)*
cat ~/backup/version-$(date +%Y%m%d)*.txt
```

### 阶段 2: 升级执行（10-15 分钟）

| # | 步骤 | 检查点 | 预估时间 | 命令 |
|---|------|--------|----------|------|
| 2.1 | 发送升级开始通知 | Carl 收到通知 | 1m | `lark-send-message.sh` |
| 2.2 | 停止 Gateway | 进程已停止 | 30s | `openclaw gateway stop` |
| 2.3 | 验证进程已停止 | 无 openclaw 进程 | 10s | `ps aux | grep -c openclaw` 应返回 0 |
| 2.4 | 执行 npm 更新 | 下载完成无错误 | 3-5m | `npm update -g openclaw` |
| 2.5 | 验证新版本 | 显示 2026.2.9 | 10s | `openclaw --version` |
| 2.6 | 检查 config 有效性 | 无 validation 错误 | 30s | `openclaw config validate` |

### 阶段 3: 应用 Patches（15-25 分钟）

**按顺序执行，每个 patch 应用后立即检查输出**：

| # | Patch 名称 | 检查点 | 预估时间 | 失败处理 |
|---|------------|--------|----------|----------|
| 3.1 | fix-feishu-command-authorized.py | 输出 "✅ Patch applied" | 1m | 记录错误，继续下一个 |
| 3.2 | fix-feishu-group-session-key.py | 输出 "✅ Patch applied" | 1m | 记录错误，继续下一个 |
| 3.3 | fix-feishu-group-wildcard.py | 输出 "✅ Patch applied" | 1m | 记录错误，继续下一个 |
| 3.4 | fix-feishu-mention-stripped.py | 输出 "✅ Patch applied" | 1m | 记录错误，继续下一个 |
| 3.5 | fix-lane-concurrency.py | 输出 "✅ Patch applied" | 1m | 记录错误，继续下一个 |
| 3.6 | add-oauth-handler.py | 输出 "✅ Patch applied" | 1m | 记录错误，继续下一个 |
| 3.7 | fix-streaming-race-condition.py | 输出 "✅ Patch applied" | 2m | **关键 patch，失败需回滚** |
| 3.8 | fix-streaming-cross-session.py | 输出 "✅ Patch applied" | 1m | **关键 patch，失败需回滚** |
| 3.9 | fix-streaming-card-ux.py | 输出 "✅ Patch applied" | 2m | 记录错误，继续下一个 |
| 3.10 | apply-feishu-streaming-fix.py | 输出 "✅ Patch applied" | 2m | **核心 patch，失败需回滚** |
| 3.11 | disable-queue-notification.py | 输出 "✅ Patch applied" | 1m | 记录错误，继续下一个 |
| 3.12 | fix-announce-cross-session.py | 输出 "✅ Patch applied" | 1m | 记录错误，继续下一个 |
| 3.13 | fix-announce-no-reply.py | 输出 "✅ Patch applied" | 1m | 记录错误，继续下一个 |

**Patch 应用脚本** (`scripts/apply-patches-2.9.sh`):
```bash
#!/bin/bash
set -e

cd /home/ubuntu/.openclaw/workspace
LOG_FILE="~/backup/patch-log-$(date +%Y%m%d-%H%M).txt"

echo "=== Applying Patches to OpenClaw 2.9 ===" | tee -a $LOG_FILE

apply_patch() {
    local patch=$1
    local critical=$2
    echo "Applying: $patch" | tee -a $LOG_FILE
    if python3 "patches/$patch" 2>&1 | tee -a $LOG_FILE; then
        echo "✅ $patch: SUCCESS" | tee -a $LOG_FILE
    else
        echo "❌ $patch: FAILED (critical=$critical)" | tee -a $LOG_FILE
        if [ "$critical" = "true" ]; then
            echo "Critical patch failed! Consider rollback." | tee -a $LOG_FILE
            exit 1
        fi
    fi
}

# 基础功能（非关键）
apply_patch "fix-feishu-command-authorized.py" "false"
apply_patch "fix-feishu-group-session-key.py" "false"
apply_patch "fix-feishu-group-wildcard.py" "false"
apply_patch "fix-feishu-mention-stripped.py" "false"
apply_patch "fix-lane-concurrency.py" "false"
apply_patch "add-oauth-handler.py" "false"

# 流式卡片（关键）
echo "=== Critical Streaming Patches ===" | tee -a $LOG_FILE
apply_patch "fix-streaming-race-condition.py" "true"
apply_patch "fix-streaming-cross-session.py" "true"
apply_patch "fix-streaming-card-ux.py" "false"
apply_patch "apply-feishu-streaming-fix.py" "true"

# Announce/队列（非关键）
apply_patch "disable-queue-notification.py" "false"
apply_patch "fix-announce-cross-session.py" "false"
apply_patch "fix-announce-no-reply.py" "false"

echo "=== All patches applied ===" | tee -a $LOG_FILE
```

### 阶段 4: 启动与验证（10-15 分钟）

| # | 步骤 | 检查点 | 预估时间 | 验证方法 |
|---|------|--------|----------|----------|
| 4.1 | 启动 Gateway | 进程启动成功 | 30s | `openclaw gateway start` |
| 4.2 | 等待 Gateway 就绪 | 日志显示 ready | 30s | `tail -f ~/.openclaw/logs/gateway.log` |
| 4.3 | 验证私聊功能 | 消息收发正常 | 2m | 发送测试消息到私聊 |
| 4.4 | 验证群聊功能 | 消息收发正常 | 2m | 发送测试消息到群聊 |
| 4.5 | 验证流式卡片 | 卡片显示正常 | 3m | 触发工具调用 |
| 4.6 | 验证子任务 | 子任务正常 | 3m | `sessions_spawn` 测试 |
| 4.7 | 验证心跳 | Heartbeat 触发 | 2m | 等待或手动触发 |
| 4.8 | 发送升级成功通知 | Carl 收到通知 | 1m | `lark-send-message.sh` |

### 阶段 5: 升级后观察（24 小时）

| # | 检查项 | 频率 | 检查方法 |
|---|--------|------|----------|
| 5.1 | Gateway 进程存活 | 每 30 分钟 | `pgrep -c openclaw` |
| 5.2 | 日志无错误 | 每 30 分钟 | `grep -i error ~/.openclaw/logs/gateway.log | tail -5` |
| 5.3 | 消息响应正常 | 持续观察 | 用户反馈 |
| 5.4 | 流式卡片功能 | 每次使用时 | 视觉检查 |
| 5.5 | 子任务正常 | 每次 spawn | 状态检查 |

---

## ⏱️ 2. 所需资源和时间估算

### 时间估算

| 阶段 | 乐观 | 正常 | 悲观 |
|------|------|------|------|
| 阶段 0: 准备 | 2h | 4h | 8h |
| 阶段 1: 备份 | 5m | 10m | 15m |
| 阶段 2: 升级 | 8m | 12m | 20m |
| 阶段 3: Patches | 15m | 20m | 35m |
| 阶段 4: 验证 | 8m | 12m | 20m |
| **总计（执行）** | **36m** | **54m** | **90m** |
| 阶段 5: 观察 | - | 24h | - |

### 人力资源

| 角色 | 需求 | 说明 |
|------|------|------|
| Luna (主执行) | 必需 | 执行所有自动化步骤 |
| Carl (待命) | 建议 | 处理 patches 冲突等意外情况 |
| 监控 | 自动 | 24 小时自动监控 |

### 系统资源

| 资源 | 需求 | 说明 |
|------|------|------|
| 磁盘空间 | 500MB | 备份 + 新版本 |
| 网络 | 稳定 | npm 下载需要 |
| 内存 | 2GB+ | Gateway 启动需要 |
| CPU | 正常 | patches 应用时需要 |

### 外部依赖

| 依赖 | 状态 | 说明 |
|------|------|------|
| npm registry | 必需 | 下载新版本 |
| Lark/Feishu API | 必需 | 消息收发验证 |
| GitHub | 非必需 | 查 release notes |

---

## 🧪 3. 测试方案

### 3.1 预升级测试（Staging 环境）

**测试环境准备**:
```bash
# 1. 克隆生产环境到 staging
sudo cp -r /home/ubuntu/.npm-global/lib/node_modules/openclaw \
          /home/ubuntu/.npm-global/lib/node_modules/openclaw-staging

# 2. 使用独立配置
export OPENCLAW_CONFIG_DIR=~/.openclaw-staging
```

**测试用例**:

| # | 测试项 | 预期结果 | 通过标准 |
|---|--------|----------|----------|
| T1 | 停止 Gateway | 进程终止 | `pgrep openclaw` 返回空 |
| T2 | 执行 npm update | 下载成功 | 无 ERROR 输出 |
| T3 | 启动 Gateway | 启动成功 | 日志显示 ready |
| T4 | 应用所有 patches | 全部成功 | 13/13 patches 应用成功 |
| T5 | 私聊消息 | 收发正常 | 消息送达 |
| T6 | 群聊消息 | 收发正常 | 消息送达 |
| T7 | 流式卡片 | 显示正常 | 无重复内容 |
| T8 | 工具调用 | 结果正确 | 工具执行成功 |
| T9 | 子任务 spawn | 正常执行 | 子任务完成 |
| T10 | Heartbeat | 触发正常 | 收到心跳消息 |
| T11 | 回滚测试 | 回滚成功 | 恢复到原版本 |

### 3.2 升级后验证测试（生产环境）

**冒烟测试**（立即执行）:

```bash
# 1. 版本验证
openclaw --version  # 期望: 2026.2.9

# 2. 进程验证
pgrep -a openclaw   # 期望: 显示运行中进程

# 3. 端口验证
ss -tlnp | grep 8080  # 期望: Gateway 监听端口

# 4. 日志验证
tail -20 ~/.openclaw/logs/gateway.log  # 期望: 无 ERROR
```

**功能测试**（5 分钟内）:

| # | 测试项 | 操作 | 预期结果 |
|---|--------|------|----------|
| F1 | 私聊响应 | 发送 "ping" | 收到回复 |
| F2 | 群聊响应 | 群聊中 @Luna | 收到回复 |
| F3 | 流式卡片 | 请求搜索 | 显示流式卡片 |
| F4 | 工具状态 | 触发工具调用 | 状态更新正常 |
| F5 | 子任务 | `sessions_spawn` 测试 | 子任务正常完成 |
| F6 | Planner | 触发 planner 回调 | 回调正常执行 |

**回归测试**（30 分钟内）:

| # | 测试项 | 操作 | 预期结果 |
|---|--------|------|----------|
| R1 | 跨 turn 对话 | 多轮对话 | 上下文保持 |
| R2 | 流式卡片跨 turn | 长对话 | 内容不重复 |
| R3 | 并发消息 | 快速发送多条 | 无丢失 |
| R4 | 大内容 | 请求长回复 | 不被截断 |
| R5 | 错误处理 | 发送无效指令 | 优雅处理 |

### 3.3 自动化测试脚本

**验证脚本** (`scripts/verify-upgrade.sh`):

```bash
#!/bin/bash

echo "=== OpenClaw 2.9 Upgrade Verification ==="

# 版本检查
VERSION=$(openclaw --version 2>/dev/null)
if [[ "$VERSION" == *"2026.2.9"* ]]; then
    echo "✅ Version: $VERSION"
else
    echo "❌ Version mismatch: $VERSION"
    exit 1
fi

# 进程检查
if pgrep -q openclaw; then
    echo "✅ Gateway is running"
else
    echo "❌ Gateway not running"
    exit 1
fi

# Patches 检查
PATCH_COUNT=$(find patches -name "*.py" | wc -l)
echo "ℹ️  Patches available: $PATCH_COUNT"

# 日志检查
ERRORS=$(grep -i "error" ~/.openclaw/logs/gateway.log 2>/dev/null | wc -l)
if [ "$ERRORS" -eq 0 ]; then
    echo "✅ No errors in log"
else
    echo "⚠️  Found $ERRORS errors in log"
fi

echo "=== Verification Complete ==="
```

---

## ✅ 4. 上线 Checklist

### 升级前确认

- [ ] **时间窗口确认**: Carl 确认升级时间可用
- [ ] **备份完成**: node_modules、config、state 已备份
- [ ] **脚本就绪**: `apply-patches-2.9.sh` 和 `verify-upgrade.sh` 已创建
- [ ] **staging 验证**: staging 环境升级测试通过
- [ ] **回滚准备**: 回滚脚本已测试可用
- [ ] **通知发送**: Carl 收到升级开始通知
- [ ] **无进行中的关键任务**: 检查 task-board.json 无关键任务

### 升级执行

- [ ] **Gateway 停止**: `openclaw gateway stop` 成功
- [ ] **npm 更新**: `npm update -g openclaw` 成功
- [ ] **版本确认**: `openclaw --version` 显示 2026.2.9
- [ ] **基础 patches 应用**: 6 个基础 patches 应用成功
- [ ] **流式卡片 patches**: 4 个流式 patches 应用成功（关键）
- [ ] **Announce patches**: 3 个 announce patches 应用成功
- [ ] **Gateway 启动**: `openclaw gateway start` 成功

### 升级验证

- [ ] **进程检查**: Gateway 进程运行中
- [ ] **私聊测试**: 私聊消息收发正常
- [ ] **群聊测试**: 群聊消息收发正常
- [ ] **流式卡片**: 流式卡片显示正常，无重复
- [ ] **工具调用**: 工具状态更新正常
- [ ] **子任务**: sessions_spawn 正常执行
- [ ] **Heartbeat**: 心跳正常触发
- [ ] **Planner**: 回调正常执行

### 升级后 24 小时

- [ ] **进程持续运行**: Gateway 未崩溃
- [ ] **日志无异常**: 无 ERROR 级别日志
- [ ] **消息响应**: 所有消息正常响应
- [ ] **流式卡片**: 功能正常
- [ ] **子任务**: 正常 spawn 和完成
- [ ] **清理备份**: 确认稳定后可清理旧备份（保留 7 天）

---

## 🚨 应急预案

### 触发回滚的条件

1. **Gateway 无法启动**（尝试 3 次后）
2. **关键 patch 应用失败**（流式卡片相关）
3. **消息收发完全失效**
4. **Carl 明确要求回滚**

### 快速回滚步骤

```bash
# 1. 停止当前 Gateway
openclaw gateway stop

# 2. 恢复备份
sudo rm -rf /home/ubuntu/.npm-global/lib/node_modules/openclaw
sudo tar xzf ~/backup/openclaw-YYYYMMDD-HHMM.tar.gz -C /home/ubuntu/.npm-global/lib/node_modules/

# 3. 恢复配置（如需要）
cp ~/backup/config-YYYYMMDD-HHMM.json ~/.openclaw/config.json

# 4. 重新应用 patches
cd /home/ubuntu/.openclaw/workspace
for f in patches/*.py; do python3 "$f"; done

# 5. 启动 Gateway
openclaw gateway start

# 6. 验证
openclaw --version  # 应显示 2026.2.3-1
```

### 联系与升级

| 情况 | 操作 |
|------|------|
| Patches 冲突 | 暂停升级，联系 Carl |
| Gateway 无法启动 | 立即回滚 |
| 功能异常 | 评估后决定回滚或修复 |
| 无法确定问题 | 优先回滚，保留现场 |

---

## 📝 附录

### A. 相关文件位置

| 文件 | 路径 |
|------|------|
| 升级方案文档 | `docs/openclaw-upgrade-plan-2.9.md` |
| 执行清单（本文档） | `docs/openclaw-upgrade-execution-checklist.md` |
| Patches 目录 | `patches/` |
| 升级脚本 | `scripts/apply-patches-2.9.sh` |
| 验证脚本 | `scripts/verify-upgrade.sh` |
| 备份目录 | `~/backup/` |
| Gateway 日志 | `~/.openclaw/logs/gateway.log` |

### B. 关键命令速查

```bash
# 状态检查
openclaw gateway status
openclaw --version
pgrep -a openclaw

# 启停
openclaw gateway start
openclaw gateway stop
openclaw gateway restart

# 升级
npm update -g openclaw

# Patches
cd /home/ubuntu/.openclaw/workspace && python3 patches/XXX.py

# 日志
tail -f ~/.openclaw/logs/gateway.log
journalctl -u openclaw -f
```

### C. 版本信息

| 项目 | 信息 |
|------|------|
| 当前版本 | 2026.2.3-1 |
| 目标版本 | 2026.2.9 |
| Patch 数量 | 13 |
| 关键 Patches | 4 (流式卡片相关) |
| 预估风险 | 中 |
| 建议时间 | 02:00-04:00 SGT |

---

**文档状态**: 待审核  
**制定者**: Luna (tid-0212-34)  
**审核**: 待 Carl 确认
