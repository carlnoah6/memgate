# reflections.md - Luna 每日复盘记录

> 每天凌晨 4 点自动生成，记录提炼出的规律、教训和改进方向。
> 这个文件是 Luna 持续进化的知识库，只记录有价值的总结，不记录流水账。

---

## 2026-02-07（系统上线第二天）

### 💡 规律与教训

1. **规律：OpenClaw 配置字段必须查 schema 再改** → 因为有些字段名和直觉不同（如 `heartbeat.every` 而非 `heartbeatIntervalMinutes`）→ 以后修改配置前先 `config.schema` 确认字段名

2. **规律：心跳和用户请求共用主 session 会导致锁冲突** → 因为 `.jsonl.lock` 是排他锁，心跳持锁期间用户消息超时 → 定期检查应该用 cron isolated 模式，彻底消除竞争

3. **规律：邮件表格不能用空格对齐** → 因为邮件客户端使用比例字体 → 改用 `•` 列表格式 + K/M 数字简写

4. **规律：Himalaya 发邮件要用 `message.send.backend` 而非 `sender`** → 配置层级和字段名不同于直觉 → 查文档确认

5. **规律：API 代理的 streaming token 统计要分开累加** → `message_start` 有 input_tokens，`message_delta` 有 output_tokens → 不能互相覆盖

6. **规律：重启后必须立刻主动汇报** → 用户在手机上没法 SSH 查状态 → 写入 SOUL.md 作为硬性规则

7. **规律：Lark 群聊消息串台是严重事故** → 不同渠道/群聊的回复必须发回原渠道 → 写入 SOUL.md 作为硬性规则，绝不跨渠道回复

8. **规律：用户看到的不是你看到的（"半截话"问题）** → 冒号结尾后跟工具调用，Lark 用户只看到冒号 → 先发完整说明再执行工具，避免中间态输出

9. **规律：Session 日志的 token 用量在 message.message.usage 路径下** → 不是顶层 role/usage，而是 type=message → message.role=assistant → message.usage → 以后统计 token 要用正确路径

10. **规律：himalaya 发送邮件需要完整 raw 格式** → 包含 From/To/Subject/Content-Type headers → 不能用 template send 命令的 -t -s 参数（那些参数不存在）

### 🔍 安全发现
- API proxy 中有 API key 硬编码在 keys.json 中（可接受，因为服务器仅通过 Tailscale 暴露）
- 端口 8080（antigravity proxy）绑定 0.0.0.0 且无鉴权 ⚠️ 需要改为 loopback
- 端口 8180（admin API）绑定 0.0.0.0 但有 API Key 鉴权 ✅
- 端口 18789（OpenClaw gateway）仅绑定 loopback ✅

### 🎯 待改进
- Lark 日历权限还未获得，需要等 Carl 确认
- 日报内容经过 v1→v2→v3 三次迭代，加入了 7 维度复盘，格式已稳定
- 配额快照刚开始记录（20:30起），明天数据会更完整
- 待清理 6 个调试/过时文件（lark-webhook-*.js, validate-config*.sh）
- 8080 端口需改为 loopback 绑定

### 📊 Token 趋势
- 02-06: 27.7M tokens（上线首日）
- 02-07: 67.7M tokens（+144%，配置密集日）
- 预计系统稳定后会显著下降

---

## 2026-02-08（周日，系统上线第三天）

### 💡 规律与教训

1. **规律：子任务的 prompt 就是它的全部世界** → 子任务无历史上下文，不知道之前的约定 → 所有要求（格式、交付渠道、数据源）必须完整写进 prompt 文件，不能指望子任务"记得"

2. **规律：共享文档所有权原则** → 多子任务并发修改同一个 Wiki 文档导致重复/冲突 → 子任务只写自己的文档，共享索引由主流程"清空+重写"统一生成

3. **规律：绝不心算日期/时间** → LLM 心算星期几出错（2/8 周日算成周六）→ 所有日期/时间信息必须用代码计算，写入 prompt 作为强制规则

4. **规律：收到指令后立刻执行 + 持久化** → Carl 说"说一遍就够了"，配额记录功能之前讨论过但没落实 → 每次收到指令后，立刻执行 + 写入文件/脚本/配置，不要只是"理解了"就结束

5. **规律：用户视角第一** → Carl 在手机聊天窗口里，不能 SSH，不能翻前面的消息 → 链接可点击、信息自包含、结果直接可用

6. **规律：已有的成熟流程必须被新 session 发现和使用** → DAILY-REVIEW.md 已经存在但新 session 从零开始写简化版 → 每个重要流程文件都应在 MEMORY.md 中被引用

7. **规律：日报只是复盘的输出物** → 先做深度复盘，再生成报告 → 凌晨 4 点任务是"做复盘"不是"发日报"

### 🔧 问题与解法

- Wiki 索引重复 → 子任务不触碰共享文档 + 主流程清空重写
- 子任务无法发飞书消息 → 创建 `scripts/lark-send-message.sh` 脚本绕过
- Fallback 不触发 → `ERROR_PATTERNS.rateLimit` 添加 `"exhausted your capacity"` 匹配
- 日报数据全错 → 重写完整 prompt，强制代码计算 + API 获取
- 日报缺少 5 个章节 → prompt 中写明 7 个必须章节 + markdown 模板

### 🔍 安全发现
- Fallback 修复涉及 OpenClaw 内部文件 `pi-embedded-helpers-*.js`，更新后需重新 patch
- 端口 8180（api-proxy）仍绑定 0.0.0.0（有 API Key 鉴权）
- 系统磁盘使用 4%，内存 1.2G/7.6G，健康

### 📊 Token 趋势
- 02-07: 10.3M tokens (612 requests)
- 02-08: 50.8M tokens (2810 requests, +394%) — 大量后台研究任务

### 🎯 改进方向
- 完善日报自动化流程（已重写 prompt 文件）
- 研究文档输出到 Wiki 的批量写入效率
- 继续推进 Balatro AI、Lark 权限等 TODO 项

---

*（后续每天的反思会追加在这里）*
