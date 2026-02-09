# Coder 公司调研：从云开发到游戏 AI

> 调研日期：2026-02-09
> 调研起因：在研究 Balatro（小丑牌）AI 时发现 GitHub 上 `coder/balatrobot` 项目，引发对 Coder 公司的好奇

---

## 一、Coder 是什么公司？

### 基本信息

| 项目 | 详情 |
|------|------|
| 公司名称 | Coder Technologies, Inc. |
| 成立时间 | 2016–2017 年（创始人高中毕业后正式创立） |
| 总部 | 美国得克萨斯州奥斯汀（Austin, Texas） |
| 官网 | [coder.com](https://coder.com) |
| GitHub | [github.com/coder](https://github.com/coder)（200+ 仓库，12.2k+ stars 主仓库） |
| 员工规模 | 约 483 人（据 GetLatka 数据） |
| 收入 | 约 $53.1M ARR |
| 现任 CEO | Rob Whiteley（2023 年 5 月加入，曾任 NGINX CMO/GM） |

### 创始团队

三位创始人在**13 岁时在网上认识**，最初一起做 Minecraft 插件和游戏服务器：

- **Kyle Carberry** — 联合创始人（来自加拿大萨斯卡通）
- **Ammar Bandukwala** — 联合创始人
- **John Andrew Entwistle** — 联合创始人（来自纽约，13 岁时在家经营小型游戏服务器公司）

三人在高中毕业后（2016 年）正式创立 Coder，选择奥斯汀作为总部（因为纽约和加州太贵）。

> 💡 **有趣的巧合**：Coder 的创始人们从 Minecraft 游戏插件起家，多年后又做 Balatro 游戏 Bot —— 游戏基因一直在。

### 主营业务

**Coder 是企业级云开发环境（CDE, Cloud Development Environment）的领导者。**

核心产品：
1. **Coder（开源 + 企业版）**：自托管的云开发环境平台
   - 基于 Terraform 定义开发环境
   - 通过 WireGuard 安全隧道连接
   - 支持任何云（公有云、私有云、本地）
   - 支持多种编辑器（VS Code Remote、JetBrains Gateway、Web IDE）
   - 50M+ 开源下载量，12.2k GitHub stars

2. **Mux**：并行 AI 编程代理桌面应用
   - 浏览器端和桌面端应用
   - 让开发者将编程任务委托给 AI 代理
   - 在受管控的基础设施上运行
   - 灵感来自 Claude Code 的 UX
   - 1.1k GitHub stars

3. **Blink**：自托管的 AI 代理构建和运行平台

**一句话概括**：Coder 让企业在自己的基础设施上安全地运行开发环境和 AI 编程代理。

---

## 二、融资历史

| 时间 | 轮次 | 金额 | 领投方 |
|------|------|------|--------|
| 2018 | Seed | $4.5M | Bessemer Venture Partners |
| 2019 | Series A | $8.5M | Redpoint Ventures |
| 2020 | Series B | $30M | General Catalyst |
| 2024.06 | Series B2 | $35M | Georgian |
| **总计** | | **~$82.8–85.2M** | |

主要投资方包括：
- **Georgian**（领投 B2 轮，董事会席位）
- **Bessemer Venture Partners**
- **Redpoint Ventures**
- **Uncork Capital**
- **Notable Capital**
- **Founders Fund**
- **Capital Factory**
- **In-Q-Tel**（美国情报界的战略投资机构！）

> 注：2025 年 4 月有 M&A Offer 记录（据 GetLatka），具体未公开。

---

## 三、为什么 Coder 要做 Balatro Bot？

### 三个 Balatro 相关项目

Coder 在 GitHub 上有三个 Balatro 相关仓库，形成完整的**游戏 AI 基准测试系统**：

| 项目 | 说明 | Stars | 语言 |
|------|------|-------|------|
| [balatrobot](https://github.com/coder/balatrobot) | Balatro 游戏 API 框架（JSON-RPC 2.0） | 34 | Python + Lua |
| [balatrollm](https://github.com/coder/balatrollm) | 用 LLM 玩 Balatro 的机器人 | 25 | Python |
| [balatrobench](https://github.com/coder/balatrobench) | LLM 玩 Balatro 的基准测试和排行榜 | 4 | Python |

还有一个公开网站 **[BalatroBench.com](https://balatrobench.com/)** 展示不同 LLM 模型玩 Balatro 的排行榜，包含指标如：
- 平均到达的回合数
- 工具调用成功率
- 输入/输出 token 数
- 每次调用时间和成本

### 动机分析：为什么是 Balatro？

Coder 做 Balatro Bot **不是**要进军游戏行业，而是出于以下几个原因：

#### 1. LLM Agent 能力的基准测试

Coder 的核心产品方向已转向 **AI 编程代理**（Mux、Blink）。他们需要一种有趣、可量化的方式来评估不同 LLM 的**策略决策能力**和**工具调用（tool-call）能力**。

Balatro 是理想的测试场景，因为它：
- 需要**复杂的策略推理**（牌组构建、概率计算、资源管理）
- 需要**可靠的工具调用**（通过 JSON-RPC API 执行动作）
- 有**明确的评分标准**（通过几轮、得分多少）
- **状态空间丰富**但不像围棋那么大
- 结合了**确定性计算和概率决策**

#### 2. 创始人的游戏 DNA

三位创始人在 13 岁时就开始做 Minecraft 插件和游戏服务器。做游戏相关项目对他们来说是自然而然的兴趣。Balatro 很可能是团队内部有人热爱的游戏。

#### 3. 开发者社区建设

balatrobot 是从社区项目 [besteon/balatrobot](https://github.com/besteon/balatrobot) fork 过来的（README 中明确致谢了原作者 @phughesion、@besteon、@giewev）。Coder 接手后大幅扩展了这个框架：
- 增加了 Python SDK（原版只有 Lua）
- 建立了完整的文档站
- 创建了 LLM 集成和基准测试
- 发布到 Kaggle（数据集分享）
- 有专门的 Discord 社区

这类有趣的开源项目有助于提升 Coder 在开发者社区中的影响力。

#### 4. 产品验证

作为一家做 AI 代理基础设施的公司，用 Balatro 作为 AI 代理的测试环境，可以：
- 验证自家平台运行 AI 代理的能力
- 为 Mux 等产品积累实战经验
- 展示 AI 代理在复杂决策任务中的表现

---

## 四、Coder 是否为其他游戏做过类似工具？

**目前没有发现 Coder 为其他游戏做过类似的 Bot 框架或 AI 工具。**

在 Coder 的 200+ GitHub 仓库中，除了 Balatro 相关的三个项目外，没有其他游戏相关项目。Balatro 系列似乎是他们唯一的游戏 AI 尝试。

不过值得注意的是：
- 创始人们早年做过 **Minecraft 插件和服务器**（创业前的经历）
- 但那些不是 Coder 公司名下的项目

---

## 五、技术栈

### 主产品（CDE）
- **后端**：Go（主仓库 coder/coder 用 Go 编写）
- **前端**：TypeScript / React
- **基础设施即代码**：Terraform（用于定义开发环境模板）
- **网络**：WireGuard（安全隧道）
- **容器 / VM**：支持两者，最初只支持容器，后来因企业需求加入 VM 支持

### Mux（AI 代理应用）
- **前端**：TypeScript（Electron 桌面应用 + 浏览器端）
- **灵感**：Claude Code 的 UX（Plan/Exec 模式）

### Balatro 项目
- **balatrobot**：Lua（游戏 mod）+ Python（SDK 和客户端）
- **balatrollm**：Python
- **balatrobench**：Python + JavaScript（Playwright 测试）
- **API 协议**：JSON-RPC 2.0 over HTTP
- **包管理**：uv（Astral 的 Python 包管理器）
- **CDN**：BunnyCDN（用于基准测试数据托管）
- **数据集**：Kaggle（公开分享）

### 其他开源项目
- **websocket**：Go 的 WebSocket 库（5k stars）
- **guts**：Go → TypeScript 类型转换工具
- **litellm**：fork 的 LLM 网关
- **blink**：自托管 AI 代理平台（TypeScript，AGPL-3.0）

---

## 六、竞争格局

Coder 在 CDE 领域的主要竞争对手：
- **GitHub Codespaces**（微软/GitHub）
- **Gitpod**（开源 CDE）
- **Google Cloud Workstations**
- **AWS Cloud9**（已逐渐边缘化）
- **DevPod**（Loft Labs 的开源替代品）

Coder 的差异化：
- **自托管**（不依赖第三方 SaaS）
- **安全合规**（满足政府、金融等行业需求，In-Q-Tel 投资就是例证）
- **不锁定编辑器**（VS Code、JetBrains、Web IDE 均支持）
- **AI 代理优先**（Mux 产品直接面向 AI 编程代理场景）

---

## 七、总结与评价

### Coder 的商业逻辑

```
开发环境上云 → 在云上运行 AI 代理 → Balatro 作为 AI 代理能力的测试工具
```

Coder 从 CDE 起家，但现在的战略重心已转向 **AI 代理基础设施**。他们的产品演进路径清晰：

1. **2016–2019**：code-server（浏览器里运行 VS Code）
2. **2020–2023**：Coder Enterprise（企业级 CDE 平台）
3. **2024–2026**：AI 代理基础设施（Mux、Blink）+ LLM 基准测试（BalatroBot/LLM/Bench）

### 为什么 Balatro 对我们有参考价值

作为一个也在研究 Balatro AI 的人，Coder 的 Balatro 项目值得关注：

1. **BalatroBot API** 是目前最完善的 Balatro 游戏 API 框架之一（1,035 commits！）
2. **BalatroBench** 提供了不同 LLM 玩 Balatro 的公开基准数据
3. 数据集已发布到 Kaggle，可直接用于研究
4. 有活跃的 Discord 社区可以交流

### 关键链接

- 🏠 [coder.com](https://coder.com)
- 🐙 [github.com/coder](https://github.com/coder)
- 🃏 [github.com/coder/balatrobot](https://github.com/coder/balatrobot)
- 🎯 [github.com/coder/balatrollm](https://github.com/coder/balatrollm)
- 📊 [github.com/coder/balatrobench](https://github.com/coder/balatrobench)
- 🏆 [BalatroBench.com](https://balatrobench.com/) — LLM 玩 Balatro 排行榜
- 📦 [Kaggle 数据集](https://www.kaggle.com/datasets/s1m0n38/balatrobench)
- 💬 [Discord 社区](https://discord.gg/TPn6FYgGPv)
