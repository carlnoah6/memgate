# Carl 的人脉网络可视化方案

> 研究日期：2026-02-08 | 类型：内部参考文档 | 作者：Luna (子任务)

---

## 一、为什么需要人脉管理系统

人际关系是一种需要主动维护的资产。邓巴数（Dunbar's Number）研究表明，人类大脑能维持的稳定社交关系上限约 150 人，其中：
- **亲密圈（5 人）**：最核心的家人/伴侣
- **好友圈（15 人）**：可以倾诉心事的人
- **朋友圈（50 人）**：经常互动的朋友
- **熟人圈（150 人）**：认识并维持关系的人

超出 150 人后，关系维护的认知负担急剧上升。个人 AI 助手的价值在于：**帮你记住那些你在意但容易遗忘的关系**——提醒你该联系谁、记录上次聊了什么、标记重要日期。

---

## 二、个人 CRM 方法论

### 2.1 个人 CRM 的核心理念

个人 CRM（Customer Relationship Management 的个人化应用）不是把朋友当"客户"，而是借用系统化思维来：

1. **集中存储**：所有联系人信息一处可查
2. **主动追踪**：记录每次互动，而不是依赖记忆
3. **节奏管理**：按关系亲密度设定联系频率
4. **上下文回忆**：下次见面前快速回顾"上次聊了什么"

### 2.2 关系维护频率建议（分层策略）

基于邓巴圈层和个人 CRM 最佳实践，建议以下分层：

| 层级 | 代号 | 人数上限 | 建议频率 | 典型角色 |
|------|------|---------|---------|---------|
| T0 | 至亲 | ~5 | 每日/随时 | 伴侣、父母、至交 |
| T1 | 核心 | ~15 | 每周 1 次 | 好朋友、合伙人、导师 |
| T2 | 重要 | ~50 | 每月 1-2 次 | 同事、校友、行业友人 |
| T3 | 维护 | ~150 | 每季度 1 次 | 前同事、远方朋友、弱关系人脉 |
| T4 | 存档 | 不限 | 每半年/年度 | 偶尔联系的熟人 |

**AI 助手可以做的事：**
- 每天早上列出"今天可以联系的人"（从 T1-T3 中找超期未联系的）
- 标记联系人的生日/纪念日（提前 3 天提醒）
- 记录每次互动的简要笔记
- 检测"关系衰减"：某个 T1 联系人超过 2 周没联系 → 温和提醒

### 2.3 互动记录的最佳实践

每次互动记录应包含：
- **日期和渠道**：2026-02-08 / 微信语音
- **内容摘要**：聊了他最近的创业项目，提到在找天使轮
- **情感标记**：正面 / 中性 / 需关注
- **后续行动**：下次帮他介绍投资人王总
- **下次联系建议**：2 周后跟进创业进展

---

## 三、数据存储方案对比

### 3.1 图数据库 vs JSON 文件

对于个人人脉网络（通常 50-500 人），存储方案的选择关键在于**复杂度与维护成本的权衡**。

| 维度 | 图数据库（Neo4j） | JSON 文件 |
|------|-----------------|----------|
| **适用规模** | 1K+ 节点，复杂关系遍历 | <1K 节点，简单关系 |
| **查询能力** | Cypher 语言，N 度关系遍历强大 | 需要代码遍历，简单过滤可用 |
| **部署成本** | 需要服务器/容器运行 | 零成本，单文件即可 |
| **AI 助手友好** | 需要学习 Cypher | 直接读写 JSON |
| **版本控制** | 不友好 | Git 友好 |
| **可视化** | 内置浏览器 | 需要额外工具 |
| **备份** | 需要 dump/restore | cp 即可 |

**推荐方案：JSON 文件 + 按需可视化**

理由：
1. 个人人脉规模远不需要图数据库的遍历性能
2. JSON 文件可以直接被 AI 助手读写，零学习成本
3. 文件天然支持 Git 版本控制，可以追踪变化历史
4. 不需要额外进程，不占系统资源
5. 可以随时导出到任何可视化工具

### 3.2 为什么不用 SQLite？

SQLite 介于两者之间，也是合理选择。但对于 AI 助手维护场景：
- JSON 的**可读性**远胜数据库文件（AI 可以直接 `cat` 查看）
- JSON 的**修改简便性**更好（不需要 SQL 语句）
- 规模小到不需要索引优化

如果未来人脉规模超过 500 人或需要复杂查询，可以考虑迁移到 SQLite。

---

## 四、推荐数据结构设计

### 4.1 联系人节点（Contact Node）

```json
{
  "contacts": [
    {
      "id": "c001",
      "name": "张三",
      "nickname": "三哥",
      "tier": "T1",
      "tags": ["同事", "创业圈", "深圳"],
      "relation": "前同事 → 朋友",
      "company": "某科技公司",
      "title": "CTO",
      "contact_methods": {
        "wechat": "zhangsan_wx",
        "phone": "+86-138xxxx",
        "email": "zhangsan@example.com"
      },
      "important_dates": {
        "birthday": "1990-05-15",
        "first_met": "2022-03-01"
      },
      "notes": "对 AI 很感兴趣，去年开始做 AI 创业",
      "contact_cadence_days": 14,
      "last_contact": "2026-01-28",
      "last_contact_summary": "聊了他的 AI Agent 项目，进展顺利",
      "pending_actions": [
        "帮他介绍王总（投资人）"
      ],
      "created_at": "2026-01-15",
      "updated_at": "2026-02-08"
    }
  ]
}
```

### 4.2 关系边（Relationship Edge）

关系不仅仅是"认识"，还有类型和强度：

```json
{
  "relationships": [
    {
      "from": "carl",
      "to": "c001",
      "type": "friend",
      "subtype": "ex-colleague",
      "strength": 8,
      "since": "2022-03-01",
      "context": "在 XX 公司共事 2 年，后来一直保持联系"
    },
    {
      "from": "c001",
      "to": "c002",
      "type": "colleague",
      "subtype": "co-founder",
      "strength": 9,
      "since": "2024-01-01",
      "context": "张三和李四一起创业"
    }
  ]
}
```

**关系类型枚举：**

| type | 说明 | 典型 subtype |
|------|------|-------------|
| `family` | 家人 | parent, sibling, spouse, cousin |
| `friend` | 朋友 | close, casual, childhood, ex-colleague |
| `colleague` | 同事 | team, cross-dept, manager, report |
| `professional` | 职业关系 | mentor, mentee, client, partner |
| `community` | 社群关系 | online, alumni, interest-group |

**关系强度（strength）：** 1-10 分，主观评分
- 9-10：至亲至交
- 7-8：好朋友、重要合作伙伴
- 5-6：普通朋友、一般同事
- 3-4：认识、偶尔互动
- 1-2：仅有联系方式

### 4.3 互动记录（Interaction Log）

单独文件存储互动记录，避免主文件过大：

```json
{
  "interactions": [
    {
      "id": "i20260208001",
      "contact_id": "c001",
      "date": "2026-02-08",
      "channel": "wechat_voice",
      "duration_min": 30,
      "summary": "聊了他 AI Agent 项目的融资进展",
      "sentiment": "positive",
      "topics": ["创业", "AI", "融资"],
      "follow_up": "2 周后问融资结果",
      "follow_up_date": "2026-02-22"
    }
  ]
}
```

### 4.4 完整文件结构

```
workspace/data/contacts/
├── contacts.json          # 联系人主数据
├── relationships.json     # 关系图边数据
├── interactions.json      # 互动记录（可按年拆分）
├── interactions-2026.json # 2026 年互动记录
└── groups.json            # 联系人分组（可选）
```

---

## 五、可视化方案对比

### 5.1 方案对比表

| 工具 | 类型 | 优点 | 缺点 | 推荐度 |
|------|------|------|------|--------|
| **vis-network (vis.js)** | JS 库 | 轻量、交互好、力导向布局、JSON 原生支持 | 需要简单 HTML 页面 | ⭐⭐⭐⭐⭐ |
| **D3.js** | JS 库 | 最灵活、定制化极强 | 学习曲线陡，小项目杀鸡用牛刀 | ⭐⭐⭐ |
| **Obsidian Graph View** | 笔记工具 | 与知识管理融合 | 需要 Obsidian、非编程控制 | ⭐⭐⭐ |
| **Cytoscape.js** | JS 库 | 专业图分析、样式丰富 | 比 vis.js 重，API 复杂 | ⭐⭐⭐⭐ |
| **Sigma.js** | JS 库 | 大图性能好（WebGL） | 小规模过度工程 | ⭐⭐⭐ |
| **Mermaid.js** | 文本图表 | 纯文本定义、Markdown 友好 | 交互性差、不支持力导向 | ⭐⭐ |
| **Canvas（HTML）** | 自定义 | OpenClaw Canvas 可直接展示 | 需要自己画 | ⭐⭐⭐⭐ |

### 5.2 推荐方案：vis-network + OpenClaw Canvas

**为什么选 vis-network：**

1. **JSON 原生**：数据格式与我们的 contacts.json 直接兼容
2. **零配置力导向布局**：自动排列节点，不需要手动定位
3. **交互性好**：拖拽、缩放、点击查看详情、悬浮提示
4. **轻量**：单个 CDN 引入即可，不需要构建工具
5. **节点分组**：原生支持颜色分组（按关系层级/类型着色）
6. **与 OpenClaw Canvas 天然集成**：生成 HTML 后直接 `canvas present` 展示

**示例代码（最小可用版本）：**

```html
<!DOCTYPE html>
<html>
<head>
  <script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
  <style>
    #network { width: 100%; height: 600px; border: 1px solid #ddd; }
    body { font-family: -apple-system, sans-serif; margin: 20px; }
  </style>
</head>
<body>
  <h2>Carl 的人脉网络</h2>
  <div id="network"></div>
  <script>
    // 节点数据 - 从 contacts.json 生成
    var nodes = new vis.DataSet([
      {id: 'carl', label: 'Carl', color: '#ff6b6b', shape: 'circle', size: 30, font: {size: 16}},
      {id: 'c001', label: '张三\nT1·朋友', color: '#4ecdc4', group: 'T1'},
      {id: 'c002', label: '李四\nT2·同事', color: '#45b7d1', group: 'T2'},
      {id: 'c003', label: '王五\nT0·家人', color: '#f9ca24', group: 'T0'},
      // ... 从 JSON 动态生成
    ]);

    // 边数据 - 从 relationships.json 生成
    var edges = new vis.DataSet([
      {from: 'carl', to: 'c001', label: '朋友', color: {color: '#4ecdc4'}},
      {from: 'carl', to: 'c002', label: '同事', color: {color: '#45b7d1'}},
      {from: 'carl', to: 'c003', label: '家人', color: {color: '#f9ca24'}, width: 3},
      {from: 'c001', to: 'c002', label: '合伙人', dashes: true},
    ]);

    var container = document.getElementById('network');
    var data = { nodes: nodes, edges: edges };
    var options = {
      groups: {
        'T0': {color: '#f9ca24', shape: 'circle', size: 25},
        'T1': {color: '#4ecdc4', shape: 'circle', size: 20},
        'T2': {color: '#45b7d1', shape: 'circle', size: 15},
        'T3': {color: '#a29bfe', shape: 'circle', size: 12},
        'T4': {color: '#dfe6e9', shape: 'circle', size: 10}
      },
      physics: {
        barnesHut: { gravitationalConstant: -3000, springLength: 150 }
      },
      interaction: { hover: true, tooltipDelay: 200 }
    };

    var network = new vis.Network(container, data, options);

    // 点击节点显示详情
    network.on("click", function(params) {
      if (params.nodes.length > 0) {
        var nodeId = params.nodes[0];
        // 这里可以弹出联系人详情卡片
        console.log("Clicked:", nodeId);
      }
    });
  </script>
</body>
</html>
```

### 5.3 配色方案

按关系层级着色，直观表达亲密度：

| 层级 | 颜色 | HEX | 含义 |
|------|------|-----|------|
| T0 至亲 | 🟡 金色 | `#f9ca24` | 最重要，金色醒目 |
| T1 核心 | 🟢 青色 | `#4ecdc4` | 亲密朋友，温暖色调 |
| T2 重要 | 🔵 蓝色 | `#45b7d1` | 活跃关系 |
| T3 维护 | 🟣 紫色 | `#a29bfe` | 需要维护 |
| T4 存档 | ⚪ 灰色 | `#dfe6e9` | 低频联系 |
| Carl | 🔴 红色 | `#ff6b6b` | 中心节点 |

边的样式：
- **实线粗**：家人关系（width: 3）
- **实线细**：朋友/同事（width: 1）
- **虚线**：间接关系/他人之间的联系（dashes: true）

---

## 六、AI 助手集成方案

### 6.1 Luna 可以自动做的事

#### 日常维护（通过心跳/Cron）

```
每日早上 9:00：
1. 扫描 contacts.json
2. 找出 last_contact + contact_cadence_days < today 的联系人
3. 生成"今日推荐联系"列表
4. 检查近 7 天内是否有生日/纪念日
5. 推送提醒给 Carl
```

#### 互动记录（对话时触发）

当 Carl 说"我刚跟张三聊了电话"时：
1. 更新 `contacts.json` 中的 `last_contact`
2. 追加 `interactions.json` 记录
3. 如果有后续行动，记录 `follow_up`

#### 关系衰减预警

```
每周日晚：
1. 扫描所有 T1 联系人
2. 标记超过 cadence 2 倍天数未联系的（"正在疏远"）
3. 标记超过 cadence 3 倍天数的（"关系预警"）
4. 周报中汇总
```

### 6.2 与日历/邮件的关联

**目前可行的集成：**
- **飞书日历**：通过 Lark API 读取会议参与者，自动记录互动
- **邮件**：如果接入邮件 API，可以提取收发件人自动更新 `last_contact`
- **微信**：暂时无法自动化，依赖 Carl 手动告知或 Luna 推断

**数据流设计：**

```
飞书日历事件 → 提取参与者 → 匹配 contacts.json → 更新 last_contact
Carl 告知互动 → Luna 解析 → 更新 contacts.json + interactions.json
Luna 心跳检查 → 生成提醒 → 推送 Carl
```

### 6.3 可视化触发

Carl 可以随时说"让我看看人脉图"，Luna 的响应流程：

1. 读取 `contacts.json` 和 `relationships.json`
2. 动态生成 vis-network HTML
3. 通过 `canvas present` 展示交互式图表
4. Carl 可以在图上点击、拖拽、探索

也可以按需生成特定视图：
- "显示我的创业圈人脉" → 按 tag 过滤
- "哪些人我好久没联系了" → 按衰减状态高亮
- "张三认识谁" → 以张三为中心展示 2 度关系

---

## 七、实施路线图

### Phase 1：基础数据搭建（1-2 天）

- [ ] 创建 `workspace/data/contacts/` 目录结构
- [ ] 设计并创建 `contacts.json` 骨架（先录入 10-20 个核心联系人）
- [ ] 设计并创建 `relationships.json`
- [ ] Carl 花 30 分钟做初始数据录入（Luna 协助提问并格式化）

### Phase 2：可视化原型（1 天）

- [ ] 编写 vis-network HTML 生成脚本
- [ ] 实现 JSON → vis-network 数据转换
- [ ] 通过 Canvas 展示第一版人脉图
- [ ] 调整布局参数和配色

### Phase 3：日常集成（持续）

- [ ] 在心跳任务中加入"联系人提醒"检查
- [ ] 实现对话中的互动记录（Carl 说了就自动记）
- [ ] 设置每周日的关系衰减扫描
- [ ] 集成飞书日历数据（自动识别会议参与者）

### Phase 4：高级功能（可选）

- [ ] 关系网络分析（识别关键节点、桥接人物）
- [ ] 联系人推荐（"你应该把张三介绍给李四"）
- [ ] 社交图谱趋势（每月人脉增长/衰减报告）
- [ ] 多视图模式（按行业/地区/关系类型分组）

---

## 八、关键决策总结

| 决策项 | 推荐 | 理由 |
|--------|------|------|
| 存储方案 | **JSON 文件** | 轻量、AI 友好、Git 可追踪 |
| 可视化工具 | **vis-network** | 轻量、交互好、JSON 原生 |
| 展示方式 | **OpenClaw Canvas** | 零部署、即时展示 |
| 关系分层 | **T0-T4 五层** | 基于邓巴数，实用且不过度复杂 |
| 联系频率 | **按层级自动建议** | AI 驱动，不需要手动管理 |
| 数据录入 | **对话式 + 自动关联** | 低摩擦，Carl 只需自然说话 |

---

## 九、参考资源

- **邓巴数理论**：Robin Dunbar, "How Many Friends Does One Person Need?"
- **个人 CRM 工具参考**：Dex、UpHabit、Clay、Monica（开源）
- **vis-network 文档**：https://visjs.github.io/vis-network/docs/
- **D3.js 网络图**：https://d3-graph-gallery.com/network.html
- **个人 CRM 最佳实践**：Zapier "What is a personal CRM" (2025)

---

*本文档为 Luna 内部参考，不上传 Wiki。如 Carl 确认方向，可开始 Phase 1 实施。*
