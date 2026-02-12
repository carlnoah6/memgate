# OpenClaw 升级方案文档

**制定时间**: 2026-02-12  
**当前版本**: 2026.2.3-1  
**目标版本**: 2026.2.9  
**升级路径**: 2.3-1 → 2.9 (跨 6 个版本)

---

## 1. 升级路径确认

### 1.1 版本跨度分析

| 版本 | 发布时间 | 主要变更 |
|------|----------|----------|
| 2026.2.3-1 | 当前 | Discord owner hint 修复, Cron xhigh→high 降级 |
| 2026.2.3 | 基准 | Telegram 类型完善, Cron announce delivery, 多账户路由 |
| 2026.2.2 | 落后1版 | **Feishu/Lark 插件支持**, Agents Dashboard, QMD Memory |
| 2026.2.6-3 | 中间 | (多个补丁版本) |
| 2026.2.9 | 目标 | iOS alpha, BlueBubbles, 设备配对插件, Grok web_search |

### 1.2 升级可行性确认

✅ **2.3-1 → 2.9 是合适的升级路径**

理由：
1. 没有 Breaking Changes 会阻断升级
2. Feishu 基础支持在 2.2 已引入，2.9 无重大重构
3. 跨度适中（约 3 周开发量），变更可控

### 1.3 关键变更点

**高风险区域**（需重点测试）：
- ⚠️ **Cron `every` 类型 job 已知有 bug**（不执行）— 我们用 heartbeat 绕过
- ⚠️ **Feishu streaming card 在 2.9 仍未修复** — 需保留 Luna patches
- ⚠️ **Config 验证增强** — 2.9 会拒绝无效配置项

---

## 2. Patch 清单分析

### 2.1 Patch 状态总览

| Patch | 状态 | 2.9后操作 | 说明 |
|-------|------|-----------|------|
| `apply-feishu-streaming-fix.py` | ✅ 已应用 | **保留重写** | Luna fix v4，修复跨 turn 重复 |
| `disable-queue-notification.py` | ✅ 已应用 | **保留** | 禁用误导性队列通知 |
| `fix-announce-cross-session.py` | ✅ 已应用 | **保留** | 防止 NO_REPLY 串台 |
| `fix-announce-no-reply.py` | ✅ 已应用 | **保留** | 抑制 NO_REPLY announce |
| `fix-feishu-command-authorized.py` | ✅ 已应用 | **保留** | 插件 CommandAuthorized 默认 true |
| `fix-feishu-group-session-key.py` | ✅ 已应用 | **保留** | 群聊 session key 用 chatId |
| `fix-feishu-group-wildcard.py` | ✅ 已应用 | **保留** | 群聊通配符 fallback |
| `fix-feishu-mention-stripped.py` | ✅ 已应用 | **保留** | 保留 @mention 信息 |
| `fix-lane-concurrency.py` | ✅ 已应用 | **保留** | lane 并发 1→4 |
| `fix-streaming-card-ux.py` | ✅ 已应用 | **保留** | 流式卡片 UX 改进 |
| `fix-streaming-cross-session.py` | ✅ 已应用 | **保留** | 防止跨 session 污染 |
| `fix-streaming-race-condition.py` | ✅ 已应用 | **保留** | 修复竞态条件 |
| `add-oauth-handler.py` | ✅ 已应用 | **保留** | OAuth callback 处理 |

### 2.2 需要重新应用的 Patches（全部）

**结论：所有 13 个 patches 都需要在升级后重新应用**

原因：
1. 2.9 版本未合并任何 Luna patches（GitHub issue #13267 仍在 open 状态）
2. Feishu streaming card 相关修复仍为 Luna 本地独有
3. OpenClaw 官方计划后续版本才支持 card rendering

### 2.3 Patch 应用顺序

```bash
# 升级后按此顺序应用 patches

# 1. 基础功能修复（先应用不影响流式卡片的）
python3 patches/fix-feishu-command-authorized.py
python3 patches/fix-feishu-group-session-key.py
python3 patches/fix-feishu-group-wildcard.py
python3 patches/fix-feishu-mention-stripped.py
python3 patches/fix-lane-concurrency.py
python3 patches/add-oauth-handler.py

# 2. 流式卡片相关（核心 patches）
python3 patches/fix-streaming-race-condition.py
python3 patches/fix-streaming-cross-session.py
python3 patches/fix-streaming-card-ux.py
python3 patches/apply-feishu-streaming-fix.py      # Luna fix v4

# 3. Announce/队列相关（最后应用）
python3 patches/disable-queue-notification.py
python3 patches/fix-announce-cross-session.py
python3 patches/fix-announce-no-reply.py
```

---

## 3. 流式卡片解决方案

### 3.1 当前方案状态

**Luna 已实现**: 
- ✅ 跨 turn 内容累积（Patch 9 + Luna fix v4）
- ✅ 流式卡片竞态条件修复
- ✅ 跨 session 污染隔离
- ✅ UX 优化（标题移除、长短内容区分处理）
- ✅ 工具状态中文显示

**已知限制**:
- Feishu CardKit API 有 ~30KB 大小限制（内容过长会被截断）
- 非流式模式仍使用纯文本（灰底）

### 3.2 2.9 升级后流式卡片状态

| 功能 | 2.3-1 + patches | 2.9 原生 | 2.9 + patches |
|------|-----------------|----------|---------------|
| 流式卡片基础 | ✅ | ✅ | ✅ |
| 跨 turn 累积 | ✅ Luna fix | ❌ | ✅ Luna fix |
| 竞态条件修复 | ✅ Luna patch | ❌ | ✅ Luna patch |
| 跨 session 隔离 | ✅ Luna patch | ❌ | ✅ Luna patch |
| UX 优化 | ✅ Luna patch | ❌ | ✅ Luna patch |
| 30KB 截断问题 | ⚠️ 存在 | ⚠️ 存在 | ⚠️ 存在 |

### 3.3 长期解决方案

**方案 A: 等待官方修复**（被动）
- GitHub issue #13267 已提交，等待官方实现
- 预计时间：未知

**方案 B: 实现自动分片**（主动）
- 当内容接近 30KB 时自动分片到多张卡片
- 需要修改 `plugin-sdk/index.js` 中的 deliver 逻辑
- 工作量：中等（~2-3 天）

**推荐**: 升级后保持现有 patches，后续评估方案 B

---

## 4. 回滚方案

### 4.1 升级前备份

```bash
# 1. 备份当前 node_modules
sudo cp -r /home/ubuntu/.npm-global/lib/node_modules/openclaw \
          /home/ubuntu/.npm-global/lib/node_modules/openclaw-backup-$(date +%Y%m%d)

# 2. 备份配置
cp ~/.openclaw/config.json ~/.openclaw/config.json.backup-$(date +%Y%m%d)
cp -r ~/.openclaw/state ~/.openclaw/state-backup-$(date +%Y%m%d)

# 3. 记录当前版本
npm list -g openclaw > ~/openclaw-version-before.txt
```

### 4.2 升级步骤

```bash
# 1. 停止 gateway
openclaw gateway stop

# 2. 执行更新
npm update -g openclaw

# 3. 验证版本
openclaw --version  # 应显示 2026.2.9

# 4. 重新应用 patches（按 2.3 节的顺序）
cd /home/ubuntu/.openclaw/workspace
python3 patches/fix-feishu-command-authorized.py
... # 其他 patches

# 5. 启动 gateway
openclaw gateway start
```

### 4.3 回滚步骤

```bash
# 如果升级后出现问题，执行回滚：

# 1. 停止 gateway
openclaw gateway stop

# 2. 恢复 node_modules
sudo rm -rf /home/ubuntu/.npm-global/lib/node_modules/openclaw
sudo cp -r /home/ubuntu/.npm-global/lib/node_modules/openclaw-backup-YYYYMMDD \
          /home/ubuntu/.npm-global/lib/node_modules/openclaw

# 3. 恢复配置（如需要）
cp ~/.openclaw/config.json.backup-YYYYMMDD ~/.openclaw/config.json

# 4. 重新应用 patches
cd /home/ubuntu/.openclaw/workspace
for f in patches/*.py; do python3 "$f"; done

# 5. 启动 gateway
openclaw gateway start
```

### 4.4 验证检查清单

升级后验证以下功能：

- [ ] Gateway 正常启动无报错
- [ ] Feishu 私聊消息正常收发
- [ ] Feishu 群聊消息正常收发
- [ ] 流式卡片正常显示（跨 turn 不重复）
- [ ] 工具状态中文显示正常
- [ ] 子任务 announce 不回串台
- [ ] Planner 回调正常
- [ ] Heartbeat 正常触发
- [ ] Cron 任务正常（如有）

---

## 5. 风险评估

### 5.1 高风险项

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|----------|
| Patches 与 2.9 代码冲突 | 中 | 高 | 每个 patch 应用后检查输出，准备手动修复 |
| Config 验证失败 | 中 | 高 | 升级前运行 `openclaw doctor --fix` |
| 流式卡片功能退化 | 低 | 高 | 升级后立即测试流式卡片功能 |
| Cron every 类型 bug | 已存在 | 中 | 继续使用 heartbeat 绕过 |

### 5.2 中风险项

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|----------|
| Feishu 插件 API 变化 | 低 | 中 | 检查 2.9 changelog 中的 Feishu 相关变更 |
| 新依赖冲突 | 低 | 中 | 在测试环境先验证 |
| 性能退化 | 低 | 低 | 监控 gateway 启动时间和内存使用 |

### 5.3 建议

1. **选择低流量时段升级**（建议深夜 02:00-04:00 SGT）
2. **保留 Carl 的协助**（首次应用 patches 如有冲突需要人工处理）
3. **准备快速回滚**（备份已在 4.1 节说明）
4. **升级后观察 24 小时**再执行其他变更

---

## 6. 执行计划

### 6.1 前置准备（升级前 1 天）

- [ ] 阅读 2.9 完整 changelog
- [ ] 执行备份脚本（4.1 节）
- [ ] 通知 Carl 升级计划
- [ ] 准备 patches 应用脚本

### 6.2 升级日执行

```bash
# === 阶段 1: 备份与停止 ===
# 由主 session 执行
openclaw gateway stop

# === 阶段 2: 升级 ===
npm update -g openclaw

# === 阶段 3: 应用 Patches ===
# spawn 子任务执行，每个 patch 验证输出
cd /home/ubuntu/.openclaw/workspace
bash scripts/apply-all-patches.sh  # 需要创建此脚本

# === 阶段 4: 验证与启动 ===
openclaw gateway start
# 发送测试消息验证功能
```

### 6.3 升级后验证（1 小时内）

- [ ] 发送 Feishu 私聊测试消息
- [ ] 发送 Feishu 群聊测试消息
- [ ] 触发一次工具调用验证流式卡片
- [ ] 检查 gateway 日志无异常

---

## 7. 附录

### 7.1 相关文档链接

- OpenClaw 2.9 Release: https://github.com/openclaw/openclaw/releases/tag/v2026.2.9
- Feishu Card Issue #13267: https://github.com/openclaw/openclaw/issues/13267
- Luna Patches 目录: `/home/ubuntu/.openclaw/workspace/patches/`

### 7.2 关键脚本

**apply-all-patches.sh**（需在升级后创建）：

```bash
#!/bin/bash
set -e
cd /home/ubuntu/.openclaw/workspace

echo "=== Applying Feishu Patches ==="

# 基础功能
python3 patches/fix-feishu-command-authorized.py
python3 patches/fix-feishu-group-session-key.py
python3 patches/fix-feishu-group-wildcard.py
python3 patches/fix-feishu-mention-stripped.py
python3 patches/fix-lane-concurrency.py
python3 patches/add-oauth-handler.py

# 流式卡片
echo "=== Applying Streaming Card Patches ==="
python3 patches/fix-streaming-race-condition.py
python3 patches/fix-streaming-cross-session.py
python3 patches/fix-streaming-card-ux.py
python3 patches/apply-feishu-streaming-fix.py

# Announce/队列
echo "=== Applying Announce Patches ==="
python3 patches/disable-queue-notification.py
python3 patches/fix-announce-cross-session.py
python3 patches/fix-announce-no-reply.py

echo "=== All patches applied ==="
```

---

**文档版本**: 1.0  
**制定者**: Luna (tid-0212-33)  
**审核状态**: 待 Carl 确认
