# Privacy Guard → 通用 OpenClaw 插件抽象与发布研究

**日期**: 2026-02-11
**任务**: Backlog #6 — 抽象为通用 OpenClaw 插件并发布
**状态**: 研究完成 ✅

---

## 1. 当前状态总览

### 已有资产

| 资产 | 位置 | 说明 |
|------|------|------|
| **原始 Privacy Guard** | `privacy/` | Luna 定制版本（5 个 Python 模块），与 workspace 紧耦合 |
| **MemGate Python 包** | `memgate/` | 已抽象为通用包（v0.4.2），含 CLI/Provider/SemanticDetector/RedTeam |
| **OpenClaw Skill** | `skills/privacy-guard/` | 旧版 skill，仅含基础模块（无 semantic/provider） |
| **MemGate SKILL.md** | `memgate/SKILL.md` | 新 skill，通过 `pip install memgate` 安装 |
| **PyPI 包** | pypi.org/project/memgate | 已发布 v0.3.x（本地安装的是 0.3.0） |
| **GitHub CI/CD** | `.github/workflows/publish.yml` | 自动：推 tag → 测试 → 构建 → PyPI 发布 → GitHub Release |

### MemGate 模块架构

```
memgate/
├── cli.py                    # 统一入口（context/review/filter/status）
├── config.json               # 默认配置
├── knowledge_store.py        # JSONL 知识存储 + 分类标记
├── privacy_context.py        # 上下文隔离引擎（DM vs Group）
├── privacy_review.py         # 输出审查器（regex + entity matching）
├── semantic_detector.py      # 语义级检测（ngram/OpenAI/local embedding）
├── providers/
│   ├── base.py               # BaseProvider 抽象类（fetch_context + is_safe）
│   └── lark.py               # Lark/Feishu 实现（含 Paranoid Check）
├── red_team/                 # 对抗测试框架（8 种攻击策略）
│   ├── arena.py              # Red-Blue 对抗竞技场
│   ├── attacker.py           # 攻击代理
│   ├── defender.py           # 防御代理
│   ├── evaluator.py          # 独立评判
│   ├── strategies.py         # 攻击策略库
│   └── report.py             # 报告生成
└── tests/                    # 完整测试套件
```

---

## 2. 发布渠道分析

### 渠道 A: PyPI（Python 包 — 已部分完成）

**当前状态**: 已发布到 PyPI（v0.3.x），但本地开发到了 v0.4.2

**完成所需工作**:
1. ✅ `pyproject.toml` 已配置好（hatch 构建系统）
2. ✅ CI/CD pipeline 已建好（tag → test → build → publish）
3. ⚠️ 需要推送最新代码 + 打 v0.4.2 tag 发布最新版
4. ⚠️ 本地安装的是 v0.3.0，需要更新到 v0.4.2

**用户安装方式**:
```bash
pip install memgate
# 或
pip install memgate[semantic]  # 含语义检测依赖
```

### 渠道 B: ClawHub（OpenClaw Skill 市场）

**当前状态**: 有 `memgate/SKILL.md` 但尚未发布到 ClawHub

**完成所需工作**:
1. 确保 `SKILL.md` frontmatter 规范（name + description）
2. 运行 `clawhub publish ./memgate --slug memgate --name "MemGate" --version 1.0.0`
3. 需要 clawhub CLI（`npm i -g clawhub`）和 GitHub 账号登录

**SKILL.md 评估**: 现有 SKILL.md 质量良好，包含：
- 正确的 frontmatter（name/description + metadata.openclaw）
- 安装方式（pip install）
- 使用示例（check/review/redact）
- 依赖声明（requires.bins: memgate）

### 渠道 C: GitHub 开源发布

**当前状态**: 已在 GitHub（carlnoah6/memgate），有完整 CI/CD
- CI: 测试 + Lint
- 文档: MkDocs → GitHub Pages（carlnoah6.github.io/memgate）
- 发布: Tag → PyPI + GitHub Release
- Pre-commit hooks: 隐私词检查（防止 API key 泄漏）

---

## 3. 插件抽象要点（从 Luna 定制 → 通用）

### 已完成的抽象

| 维度 | Luna 定制版 (`privacy/`) | 通用版 (`memgate/`) |
|------|--------------------------|---------------------|
| 知识存储 | 硬编码路径 | 可配置 `KnowledgeStore(base_dir)` |
| 上下文引擎 | 针对 Carl 的规则 | 通用 DM/Group 隔离 |
| 审查器 | 中文为主的 regex | 多语言 regex + entity matching |
| 语义检测 | 无 | ✅ ngram/OpenAI/local 三种 provider |
| 平台集成 | 硬编码 Lark | ✅ Provider 抽象（BaseProvider → LarkProvider） |
| 对抗测试 | 18 条手动测试 | ✅ 自动化 Red Team Arena |
| CLI | `privacy-check.py` bridge | ✅ `memgate` 统一命令 |
| 打包 | 无 | ✅ PyPI + hatchling |

### 仍需完善的差距

1. **更多 Provider 实现**: 
   - Lark/Feishu ✅
   - Telegram ❌（有 BaseProvider 接口，缺实现）
   - Discord ❌
   - Slack ❌
   - WhatsApp ❌

2. **文档**:
   - API 参考 ✅（MkDocs + Google docstrings）
   - 快速入门指南 ⚠️（README 有但较简略）
   - OpenClaw 集成指南 ⚠️（examples/openclaw 有但不完整）

3. **版本同步**:
   - PyPI 上是 v0.3.x
   - 本地代码是 v0.4.2
   - 需要推送并发布最新版

---

## 4. 发布行动计划

### Phase 1: PyPI 更新发布（优先级高，~30 min）

```bash
cd memgate/
# 确认测试通过
pip install -e ".[dev]"
pytest

# 推送代码
git add -A && git commit -m "chore: prepare v0.4.2 release"
git push origin main

# 打 tag 触发自动发布
git tag v0.4.2
git push origin v0.4.2
# CI 自动: test → build → publish to PyPI → GitHub Release
```

### Phase 2: ClawHub Skill 发布（~15 min）

```bash
# 安装 clawhub CLI
npm i -g clawhub

# 登录
clawhub login

# 发布 memgate skill
clawhub publish ./memgate --slug memgate --name "MemGate" --version 1.0.0 --tags latest
```

### Phase 3: 更新 workspace 集成（~10 min）

```bash
# 更新本地安装
pip install --upgrade memgate

# 确保 workspace 的 privacy-check.py bridge 指向 memgate 包
# （当前已正确配置）

# 安装 ClawHub 版到 skills/
clawhub install memgate
```

### Phase 4: 扩展 Provider（可选，P2）

按社区需求优先添加：
1. **Telegram** — OpenClaw 最常见的通道之一
2. **Discord** — OpenClaw 社区活跃
3. **Slack** — 企业用户需求

---

## 5. OpenClaw Skill 规范对照检查

| 要求 | 状态 |
|------|------|
| SKILL.md 存在 | ✅ |
| frontmatter: name | ✅ `memgate` |
| frontmatter: description | ✅ 包含触发条件 |
| metadata.openclaw.requires | ✅ `bins: ["memgate"]` |
| metadata.openclaw.install | ✅ pip 安装方式 |
| 无多余文件（README.md 等） | ⚠️ 有 README.md（但作为 PyPI 包需要） |
| progressive disclosure | ✅ SKILL.md 精简，详细文档在 docs/ |

### SKILL.md 改进建议

当前 SKILL.md 较好，建议增加：
1. 添加 `metadata.openclaw.emoji: "🛡️"`
2. 补充更多使用场景（OpenClaw agent 在群聊发消息前自动审查）
3. 添加 `references/integration-guide.md` 给 OpenClaw 用户的分步集成指南

---

## 6. 竞品分析

| 项目 | 定位 | 与 MemGate 区别 |
|------|------|-----------------|
| **ai-privacy-toolkit** (IBM) | 模型级隐私（差分隐私、匿名化） | MemGate 是 agent 输出级隐私 |
| **mem0ai** | AI agent 长期记忆 | 无隐私隔离功能 |
| **Presidio** (Microsoft) | PII 检测与匿名化 | MemGate 更聚焦于多用户 agent 场景 |
| **LangChain** | Agent 框架 | 无内置隐私隔离 |

**MemGate 的独特定位**: 专为 multi-user AI agent 设计的记忆隐私防火墙。唯一同时提供：
- 知识分级（public/private）
- 上下文隔离（DM vs Group）
- 输出审查（regex + semantic）
- 平台集成（Provider 架构）
- 对抗测试（Red Team Arena）

---

## 7. 安全考量

发布到 ClawHub 需注意（鉴于近期 ClawHub 恶意 skill 事件）：
1. ✅ 代码开源（GitHub），用户可审查
2. ✅ 有 pre-commit hooks 防止泄漏密钥
3. ✅ PyPI 包签名（通过 GitHub Actions 发布）
4. ⚠️ 需确保 SKILL.md 中无执行危险命令
5. ✅ MemGate 本身就是安全工具，不含破坏性操作

---

## 8. 总结与建议

### 核心发现
1. **MemGate 已经基本完成了从 Luna 定制到通用包的抽象**——模块化、Provider 架构、CLI、PyPI 打包都已就绪
2. **主要差距是发布同步**——本地 v0.4.2 vs PyPI v0.3.x，以及尚未发布到 ClawHub
3. **实施工作量很小**——主要是 git push + tag + clawhub publish，估计 1 小时内可完成全部发布

### 推荐下一步
1. **立即**: 推送 v0.4.2 到 PyPI（最高优先级）
2. **立即**: 发布到 ClawHub（提升社区可见性）
3. **短期**: 完善集成文档（OpenClaw 用户如何 5 分钟内集成）
4. **中期**: 添加 Telegram/Discord Provider（扩大适用范围）
5. **长期**: 探索 MCP (Model Context Protocol) 集成可能性

---

*研究来源: OpenClaw 官方文档、ClawHub docs、GitHub repo 分析、PyPI 状态检查、skill-creator SKILL.md 规范*
