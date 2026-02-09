# Balatro（小丑牌）游戏机制与 AI 策略研究

> 研究日期：2026-02-08
> 研究者：Luna（后台研究子任务）
> 状态：完成

## 一、游戏概述

### 1.1 基本信息

**Balatro** 是一款扑克主题的 Roguelike 牌组构建游戏，由独立开发者 LocalThunk 使用 Löve 引擎开发，Playstack 发行。2024年2月20日正式发布，截至2025年1月已售出超过500万份。游戏名来源于古罗马语中的"职业小丑/弄臣"（balatrones）。

- **开发者**：LocalThunk（加拿大萨斯喀彻温省的匿名独立开发者）
- **引擎**：Löve（Love2D）
- **平台**：PC、macOS、Nintendo Switch、PS4/PS5、Xbox One/Series X|S、Android、iOS
- **开发周期**：约2.5年（2021年开始）
- **灵感来源**：广东纸牌游戏"锄大弟"（Big Two）+ Roguelike游戏 Luck Be a Landlord

### 1.2 核心玩法循环

1. **选择牌组** → 开始一局"run"
2. **通过 Ante**（每个 Ante 有三个 Blind）
   - Small Blind（基础分 × 1，可跳过获取 Tag）
   - Big Blind（基础分 × 1.5，可跳过获取 Tag）
   - Boss Blind（基础分 × 2，必须打，有特殊能力）
3. **打牌得分** → 在有限的出牌次数和弃牌次数内达到目标分数
4. **商店购物** → 用金币购买 Joker、消耗品、优惠券等
5. **通过 Ante 8** → 胜利（可继续无尽模式）

---

## 二、核心机制详解

### 2.1 计分系统

Balatro 的核心公式极为简洁：

```
手牌得分 = Chips × Mult
```

计分过程分四个阶段：

#### 阶段一：基础手牌筹码/倍率
根据打出的扑克手牌类型（Pair、Flush、Straight 等）和等级，获取基础 Chips 和 Mult。手牌等级可通过 Planet 卡升级。

**基础手牌数值（Lv.1）示例**：
| 手牌类型 | Chips | Mult |
|---------|-------|------|
| High Card | 5 | 1 |
| Pair | 10 | 2 |
| Two Pair | 20 | 2 |
| Three of a Kind | 30 | 3 |
| Straight | 30 | 4 |
| Flush | 35 | 4 |
| Full House | 40 | 4 |
| Four of a Kind | 60 | 7 |
| Straight Flush | 100 | 8 |
| Five of a Kind | 120 | 12 |
| Flush House | 140 | 14 |
| Flush Five | 160 | 16 |

#### 阶段二：打出卡牌的计分
- 只有**贡献于手牌类型的卡牌**才会计分（"scored" vs "played"）
- 卡牌从左到右依次计算
- 每张卡牌贡献其面值的 Chips
- 卡牌的增强（Enhancement）、版本（Edition）、封印（Seal）在此阶段生效

#### 阶段三：手中牌的效果
- Steel 卡（×1.5 Mult）
- Baron Joker 对手中 King 的效果
- 其他手持触发效果

#### 阶段四：Joker 效果
- Joker 从左到右依次触发
- **+Chips** 加法叠加
- **+Mult** 加法叠加
- **×Mult** 乘法叠加（最强！）
- 版本加成（Foil +50 Chips，Holographic +10 Mult，Polychrome ×1.5 Mult）在 Joker 自身效果后触发

**关键洞察**：Joker 排列顺序至关重要！
- +Mult Joker 应放在 ×Mult Joker **左边**
- Blueprint/Brainstorm 复制相邻 Joker 的效果
- 例：先 +100 Mult 再 ×10 = 得 1000 Mult；反过来只得约 +100 Mult

### 2.2 Ante 基础分数表

| Ante | 基础分 |
|------|--------|
| 1 | 300 |
| 2 | 800 |
| 3 | 2,800 |
| 4 | 6,000 |
| 5 | 11,000 |
| 6 | 20,000 |
| 7 | 35,000 |
| 8 | 50,000 |
| 9 | 110,000 |
| 10 | 560,000 |
| 11 | 7,200,000 |
| 12 | 300,000,000 |

分数需求呈指数增长，这意味着后期必须有强力的 ×Mult 引擎。

### 2.3 卡牌体系

#### 2.3.1 Joker 卡（150种）
游戏核心。分为以下功能类型：
- **+Chips 类**：Scary Face (+30)、Blue Joker、Stuntman (+250) 等
- **+Mult 类**：Smiley Face (+4)、Joker (+4)、Popcorn (+20) 等
- **×Mult 类**：最关键！如 Hologram、Obelisk、Acrobat (×3)
- **经济类**：Golden Joker、Egg、To the Moon 等
- **功能类**：Shortcut、Four Fingers、Smeared Joker、Splash 等
- **缩放类**：随游戏进展增强，如 Ride the Bus、Spare Trousers、Fortune Teller
- **传奇类**（5种）：Chicot（禁用 Boss Blind）、Perkeo、Triboulet 等

**S 级 Joker 一览**：
- **Blueprint / Brainstorm**：复制相邻 Joker 效果，创造指数级增长
- **Mime**：复制上方 Joker 效果
- **Hologram**：每次加入卡牌获得 ×Mult（缩放无上限）
- **Baron**：手中每张 King 提供 ×1.5 Mult
- **Shortcut**：让 Straight 可以跳一个点数，极大降低组成难度
- **Four Fingers**：4 张即可组 Flush/Straight
- **Steel Joker**：根据手中 Steel 卡数量给 ×Mult

#### 2.3.2 Tarot 卡（大阿尔卡纳）
一次性消耗品，用于：
- 改变卡牌花色
- 为卡牌添加增强（Mult Card、Wild Card、Glass Card、Steel Card、Stone Card、Gold Card 等）
- 摧毁卡牌（减少牌组以提高一致性）
- 复制卡牌

#### 2.3.3 Planet 卡
升级特定手牌类型的等级，增加该类型的基础 Chips 和 Mult。**投资于单一手牌类型**通常比分散投资更强。

#### 2.3.4 Spectral 卡
高风险高回报的消耗品：
- 复制卡牌
- 给 Joker/卡牌添加版本
- 调整金币（可能有负面效果）
- **The Soul**：直接给一张传奇 Joker

#### 2.3.5 Voucher（优惠券）
每个 Ante 商店有一张独特优惠券，提供永久加成：
- **Overstock**：商店多一个卡位
- **Grabber**：每回合多一次出牌
- **Wasteful**：每回合多一次弃牌
- **Clearance Sale / Liquidation**：打折

### 2.4 牌组系统（15种）

| 牌组 | 效果 | 适合策略 |
|------|------|---------|
| Red Deck | +1 弃牌 | 新手友好，灵活性高 |
| Blue Deck | +1 出牌 | 容错率高 |
| Yellow Deck | 开局 +$10 | 强化经济 |
| Green Deck | 残留手/弃=钱，无利息 | 经济型，激进打法 |
| Black Deck | +1 Joker 位, -1 出牌 | Joker 协同流 |
| Checkered Deck | 只有♠和♥ | **Flush 流神器**，公认最强爬梯牌组 |
| Plasma Deck | Chips 和 Mult 平衡后相乘 | 高分流 |
| Abandoned Deck | 无花牌 | 数字牌流 |
| Ghost Deck | 商店可能出 Spectral 卡 | 赌博流 |
| Erratic Deck | 随机花色和点数 | 混沌流 |

### 2.5 难度系统（8 个 Stake）

| Stake | 效果 |
|-------|------|
| White（白注） | 基础难度 |
| Red（红注） | Small Blind 不给钱 |
| Green（绿注） | 分数需求增长更快 |
| Black（黑注） | 30% Joker 带 Eternal（不可卖/毁） |
| Blue（蓝注） | -1 弃牌 |
| Purple（紫注） | 分数需求增长更更快 |
| Orange（橙注） | 30% Joker 带 Perishable（5回合后失效） |
| Gold（金注） | 30% Joker 带 Rental（每回合 $3 维护费） |

每个 Stake 叠加之前所有 Stake 的效果。Gold Stake 是终极挑战。

### 2.6 Boss Blind 系统

共 28 种 Boss Blind（23 种常规 + 5 种终结者）：

**高威胁 Boss Blind**：
- **The Wall**：需要 ×4 基础分（而非通常的 ×2）
- **The Arm**：每次出牌降低该手牌类型等级
- **The Needle**：只能出一手牌
- **The Flint**：基础 Chips 和 Mult 减半

**花色封锁类**：
- The Club/Goad/Window/Head：分别 debuff ♣/♠/♦/♥

**信息遮蔽类**：
- The House：第一手牌全部背面朝下
- The Fish：每手牌后抽到的牌背面朝下
- The Wheel：1/7 的牌背面朝下

**终结者 Blind（Ante 8）**：
- **Amber Acorn**：翻转所有 Joker
- **Verdant Leaf**：所有卡牌 debuffed 直到打出一手包含三种花色的牌
- **Violet Vessel**：×3 基础分
- **Crimson Heart**：每手牌随机 debuff 一个 Joker
- **Cerulean Bell**：每手牌强制打出一张选中的卡

---

## 三、高级策略体系

### 3.1 核心策略原则

#### 原则一：乘法思维优先
- **+Mult 是线性增长，×Mult 是指数增长**
- 后期（Ante 5+）没有 ×Mult 来源基本必死
- 理想 Joker 配置：至少 1 个 +Chips、1 个 +Mult、1-2 个 ×Mult

#### 原则二：聚焦单一手牌类型
- 将 Planet 卡集中投资于一种手牌（如 Flush 或 Full House）
- 配合该手牌类型的 Joker
- **Flush 和 Full House 是最稳定的后期手牌**
- Straight 中期后期不稳定（除非有 Shortcut + Four Fingers）

#### 原则三：系统思维 > 单卡思维
- 2-3 个 Joker 协同比 5 个独立 Joker 强
- 例：Baron + Mime + 全 Steel King 手牌 → 每张 King 约 ×5 Mult
- 例：Blueprint + 强力缩放 Joker → 双倍效果

#### 原则四：经济管理
- **前期（Ante 1-2）**：激进消费找关键 Joker
- **中期（Ante 3-5）**：保持 $25+ 赚利息，稳定引擎
- **后期（Ante 6-8）**：投资生存而非完美，花钱买消耗品过关
- **金币 > $25 才有利息**（每 $5 产生 $1 利息，上限 $5/回合）

#### 原则五：弃牌是投资
- 弃牌 = 循环牌组 = 更高概率拿到关键手牌
- 精简牌组（通过 Tarot 毁牌）= 一致性
- 某些 Joker 在弃牌时触发（Green Joker、Castle 等）

### 3.2 Build 分类

#### Flush 流
- **核心**：Checkered Deck + 花色 Joker + Planet 升级 Flush
- **关键卡**：Smeared Joker（减少花色数）、花色对应 +Mult/+Chips Joker
- **优势**：组建简单，一致性高
- **劣势**：被花色 debuff Boss Blind 克制

#### 缩放 ×Mult 流
- **核心**：缩放 Joker（Hologram、Obelisk、Ride the Bus 等）
- **关键卡**：Blueprint/Brainstorm 复制缩放效果
- **优势**：后期爆发力极强
- **劣势**：前期可能较弱

#### Baron/Steel 手持流
- **核心**：Baron（手中 King ×1.5）+ Mime + Steel 卡 + 增加手牌上限
- **关键卡**：Juggler/Troubadour（增加手牌上限）
- **优势**：不依赖打出什么牌，只要手中有卡就得分
- **劣势**：需要大量特定组件

#### 高牌（High Card）流
- **核心**：靠 Joker 效果而非手牌类型得分
- **优势**：不受大多数 Boss Blind 影响
- **劣势**：需要非常强的 Joker 组合
- **适合**：高难度 Stake（Gold Stake）

### 3.3 Boss Blind 应对策略

1. **通用应对**：Boss Tag 重骰、Luchador Joker 卖掉禁用、Chicot Joker 永久禁用
2. **花色 debuff**：保持备用手牌类型，不全押一种花色
3. **The Wall**：需要特别强的引擎，或禁用/重骰
4. **信息遮蔽**：多用弃牌翻开信息，尽量一手解决
5. **The Eye/Mouth**：准备多种/专精手牌类型
6. **消耗品储备**：永远为 Boss Blind 留消耗品

---

## 四、AI 与自动化策略

### 4.1 Balatro AI 的挑战

Balatro 作为 AI 研究目标有独特的挑战：

1. **巨大的决策空间**：
   - 出牌选择：从 8 张手牌中选 1-5 张打出 → C(8,1)+C(8,2)+...+C(8,5) = 218 种
   - 弃牌选择：从 8 张中选 0-5 张弃掉 → 同样巨大
   - 商店决策：买/不买/重骰/跳过 Blind
   
2. **稀疏奖励**：随机行动很难偶然触发高分手牌（如 Flush），导致 RL 代理学习困难
   
3. **长期规划**：需要跨越多个 Ante 的战略眼光（经济管理、Build 构建）
   
4. **不完全信息**：商店内容随机、Boss Blind 类型随机
   
5. **组合爆炸**：150 种 Joker × 各种卡牌增强/版本/封印 → 天文数字的状态空间

### 4.2 现有 AI 项目

#### balatro-gym（cassiusfive/balatro-gym）
- **类型**：Gymnasium 环境封装
- **框架**：OpenAI Gymnasium 标准接口
- **功能**：提供 Balatro v1.0.0 的 RL 训练环境
- **特点**：包含 expert agent、curriculum learning、progressive training 等多种训练脚本
- **方法**：Stable-Baselines3 + PPO

#### Balatro-AI（CzJLee/Balatro-AI）
- **类型**：强化学习项目
- **技术**：lovely-injector（Lua 代码注入）+ Steamodded 模组加载器
- **框架**：Stable-Baselines3
- **挑战**：奖励函数过于稀疏，纯 RL 效果不佳

#### game-playing-ai-balatro（proj-airi）
- **类型**：CV + LLM 混合方案
- **技术**：YOLO 目标检测 + RapidOCR/PaddleOCR 文字识别 + LLM 决策
- **理念**：用计算机视觉理解游戏画面，LLM 做策略决策

#### BalatroBot（coder/balatrobot）
- **类型**：Bot 开发框架
- **接口**：JSON-RPC 2.0 HTTP API
- **功能**：暴露完整游戏状态和控制接口（卡牌选择、商店交易、Blind 选择等）
- **适合**：开发自定义 Bot（规则引擎或 AI）

#### BalatroBot（besteon/balatrobot）
- **类型**：简单 Bot 模组
- **实现**：直接修改 Bot.lua
- **适合**：快速原型

#### BalatroBuddy
- **类型**：AI 辅助策略工具
- **功能**：实时手牌分析、Joker 优化建议
- **实现**：可能基于 LLM

### 4.3 AI 策略设计思路

#### 方案一：基于规则的 Expert System
最可行且效果最好的初始方案：

```
决策流程：
1. 手牌评估 → 列出所有可能的手牌组合
2. 分数预测 → 计算每种组合的预期得分（含 Joker 效果）
3. 差距分析 → 比较预期得分与目标分数
4. 弃牌优化 → 如果当前最优手牌不够，计算弃牌后改善的概率
5. 出牌决策 → 选择期望分数最高的组合
```

商店决策的规则引擎：
- 计算每个 Joker 对当前 Build 的边际贡献
- 维护"Build 完整度"指标
- 经济管理规则（利息阈值、紧急购买条件）

#### 方案二：RL + 课程学习
解决稀疏奖励问题：

1. **阶段一**：只训练出牌（固定简单局面）
2. **阶段二**：加入弃牌决策
3. **阶段三**：加入商店决策（简化 Joker 集合）
4. **阶段四**：完整游戏

奖励塑形（Reward Shaping）：
- 中间奖励：根据"目标达成百分比"给分
- 惩罚浪费弃牌
- 奖励经济管理（保持利息阈值）

#### 方案三：LLM 代理
利用 LLM 的推理能力：

- 优点：可以理解复杂的 Joker 交互、做长期规划
- 缺点：推理成本高、速度慢
- 适合：作为"教练"生成训练数据，而非实时决策

#### 方案四：Monte Carlo Tree Search (MCTS)
- 适合处理不确定性
- 可以模拟多个未来路径
- 挑战：Balatro 的分支因子太大

### 4.4 关键 AI 指标

评估 AI 表现的指标建议：
- **胜率**：各 Stake 难度的通关率
- **平均 Ante**：平均能打到第几个 Ante
- **经济效率**：金币使用效率
- **Build 质量**：最终 Joker 协同度评分
- **决策速度**：每步决策时间

---

## 五、游戏设计分析

### 5.1 为什么 Balatro 成功？

1. **数学之美**：表面简单（Chips × Mult），内核复杂（四阶段计分、Joker 排序）
2. **心流设计**：每一手牌都有即时反馈，数字飞涨的快感
3. **文化共鸣**：52 张标准扑克牌是全球共享的文化符号
4. **深度 vs 可及性**：新手可以打 High Card，高手可以构建 ×Mult 引擎
5. **Roguelike 循环**：每局不同，解锁机制驱动持续游玩
6. **独立开发精神**：一人开发，音乐是 Fiverr 上找的，总预算极低

### 5.2 设计中的数学

- **指数增长 vs 线性增长**：分数需求指数增长，逼迫玩家寻找 ×Mult（也是指数增长）
- **Scaling Laws 的游戏化**：与 LLM 训练中的 Scaling Laws 异曲同工
- **概率论的游戏化**：出牌/弃牌涉及条件概率、期望值计算
- **Ante 39 的 NaN 溢出**：双精度浮点数溢出到无穷大，存为 NaN，所有与 NaN 的比较都返回"无序"（unordered），导致无法继续

### 5.3 Mod 生态

- **Steamodded**：第三方模组加载器
- **Cryptid mod**：新增 100+ Joker，故意设计为不平衡
- **Multiplayer mod**：创新性地加入对战模式（Nemesis Blind）
- **lovely-injector**：Lua 代码注入框架，用于 AI 和 mod 开发

---

## 六、总结与启示

### 对 Carl 的价值

1. **作为游戏**：Balatro 是一个极其精巧的数学优化游戏，适合喜欢系统思维的人
2. **作为 AI 研究对象**：
   - 决策空间大但可枚举 → 适合 Expert System + MCTS 混合
   - 已有 Gymnasium 环境 → 可直接开始 RL 实验
   - 规则明确 → 可构建完美模拟器
3. **作为游戏设计学习素材**：
   - 简单规则产生复杂策略的典范
   - 独立开发者成功案例
   - 数学与游戏性完美融合

### 推荐阅读
- [Balatro Wiki (Fandom)](https://balatrogame.fandom.com/)
- [Steam Score Calculation Guide](https://steamcommunity.com/sharedfiles/filedetails/?id=3169032575)
- [balatro-gym (GitHub)](https://github.com/cassiusfive/balatro-gym)
- [BalatroBot Framework (GitHub)](https://github.com/coder/balatrobot)
- [Advanced Balatro Strategy (Medium)](https://hexshift.medium.com/advanced-balatro-strategy-going-beyond-the-basics-15437c514ff7)

---

*本文档由 Luna 后台研究子任务自动生成，基于公开网络资源整理。*
