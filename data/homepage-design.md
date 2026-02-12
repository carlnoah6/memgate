# Carl (Bo Li) 个人主页 — 设计方案文档

> 最后更新: 2026-02-11

---

## 1. 参考案例研究

### 1.1 五个优秀个人主页分析

| # | 网站 | 所有者 | 风格特点 | 技术栈 |
|---|------|--------|----------|--------|
| 1 | [karpathy.ai](https://karpathy.ai) | Andrej Karpathy (Eureka Labs 创始人, 前 Tesla AI Director) | 极简单页、纯文字为主、timeline 式经历、大量超链接、无花哨动画 | 纯 HTML/CSS, GitHub Pages |
| 2 | [leerob.com](https://leerob.com) | Lee Robinson (Cursor, 前 Vercel VP) | 极简、个人叙事开头、Spotify 实时状态、精选文章列表、暗色/亮色切换 | Next.js + Tailwind CSS, Vercel |
| 3 | [jimfan.me](https://jimfan.me) | Jim Fan (NVIDIA AI Agents Lead) | 学术与工业并重、Hero section + 项目 showcase、媒体报道、出版物列表、时间线经历 | 静态站点 (Jekyll/Hugo 风格) |
| 4 | [pjreddie.com](https://pjreddie.com) | Joseph Redmon (YOLO 之父, Ai2) | 个性鲜明、幽默感十足、学术论文 + 项目 + 教学、有趣的 tagline | 纯 HTML/CSS, 自托管 |
| 5 | [rauchg.com](https://rauchg.com) | Guillermo Rauch (Vercel CEO, Next.js 创造者) | 极简博客式、typography 驱动、暗色主题、精选长文、无多余装饰 | Next.js, Vercel |

### 1.2 共性总结与最佳实践

**设计共性：**
- **极简主义**：所有优秀案例都采用「少即是多」的理念，移除一切不必要的视觉元素
- **内容为王**：以文字内容（而非视觉特效）作为核心呈现
- **清晰的身份声明**：首屏（Hero）用 1-2 句话精准定义「我是谁、我做什么」
- **Typography 驱动**：优秀的字体选择和排版层次感是区分质量的关键
- **Dark/Light 双模式**：现代个人站点标配，尊重用户偏好
- **快速加载**：所有案例都是近乎即时加载（<1s），零冗余 JS

**内容共性：**
- 开头是简短的 bio/intro（1-3 句话）
- 精选 项目/作品 showcase（3-5 个 highlight）
- 经历时间线（可选，学术背景重的人常用）
- 博客/写作入口
- 社交链接（GitHub, Twitter/X, LinkedIn）
- 联系方式

**技术共性：**
- 静态/SSG 优先（快速、安全、低维护成本）
- Markdown 驱动内容（便于持续更新）
- 部署到 Vercel / Cloudflare Pages / GitHub Pages

---

## 2. 设计方向

### 2.1 整体风格定义

**关键词**：`简洁` · `现代` · `技术感` · `精致` · `有温度`

**设计语言**：
- **结构化极简**（Structured Minimalism）— 不是 Karpathy 式的「纯文字」极简，而是有设计感的极简
- 受 Linear.app / Vercel 官网 的视觉语言影响：干净的线条、精心选择的字体、微妙的动画
- 暗色主题为默认（科技感），支持亮色切换
- 适当使用微动画（hover 效果、页面过渡），但绝不过度
- 留白大方，呼吸感充足

**差异化**：Carl 的独特之处在于 AI/LLM + 珠宝制作 的跨界组合。设计上可以在科技感中融入一丝手工艺/精致感（比如细腻的排版、精心选择的色彩点缀），避免纯「码农风」。

### 2.2 灵感板（Mood Board）

```
┌─────────────────────────────────────────────────┐
│  视觉参考                                         │
│                                                   │
│  · Linear.app — 干净的暗色 UI、微妙渐变            │
│  · Vercel.com — 黑白灰 + 蓝色点缀、极致排版        │
│  · Stripe.com — 优雅渐变、精致感                   │
│  · rauchg.com — 纯粹的 typography 之美             │
│  · Apple 产品页 — 大留白、精准对齐                  │
│                                                   │
│  氛围词                                           │
│  专业 · 克制 · 精密 · 温暖的科技感                  │
└─────────────────────────────────────────────────┘
```

---

## 3. 配色方案

### 3.1 暗色主题（默认）

| 用途 | 色值 | 说明 |
|------|------|------|
| **Background** | `#0a0a0b` | 近黑，比纯黑更柔和 |
| **Surface** | `#141416` | 卡片/区块背景 |
| **Border** | `#232328` | 微妙的分隔线 |
| **Text Primary** | `#ededef` | 主要文字，高对比 |
| **Text Secondary** | `#8b8b8e` | 辅助文字、描述 |
| **Text Muted** | `#55555a` | 日期、标签等次要信息 |
| **Accent** | `#6366f1` | Indigo — 主强调色（链接、按钮） |
| **Accent Hover** | `#818cf8` | 悬停状态 |
| **Accent Glow** | `rgba(99,102,241,0.15)` | 微妙的光晕效果 |
| **Warm Accent** | `#f59e0b` | 琥珀色 — 珠宝/手工艺呼应（偶尔点缀） |

### 3.2 亮色主题

| 用途 | 色值 | 说明 |
|------|------|------|
| **Background** | `#fafafa` | 温暖白 |
| **Surface** | `#ffffff` | 纯白卡片 |
| **Border** | `#e5e5e5` | 淡灰分隔 |
| **Text Primary** | `#171717` | 近黑文字 |
| **Text Secondary** | `#525252` | 辅助文字 |
| **Accent** | `#4f46e5` | 稍深的 Indigo |

### 3.3 字体方案

```css
/* 主标题 / 大字 */
--font-heading: 'Inter', 'SF Pro Display', system-ui, sans-serif;

/* 正文 */
--font-body: 'Inter', 'SF Pro Text', system-ui, sans-serif;

/* 代码 / 技术内容 */
--font-mono: 'JetBrains Mono', 'Fira Code', 'SF Mono', monospace;
```

**排版节奏**：
- Hero 标题：`text-4xl` / `text-5xl` (36-48px)，`font-bold`
- 段落：`text-base` (16px)，`leading-relaxed` (1.75)
- 小标签：`text-sm` (14px)，`uppercase`，`tracking-wider`

---

## 4. 内容结构

### 4.1 页面架构

```
carl.dev (或类似域名)
├── / (首页 — 单页 + 分区锚点)
│   ├── Hero Section
│   ├── About / Bio
│   ├── Featured Projects
│   ├── Writing / Blog (最新 3 篇)
│   └── Footer (社交链接 + 联系)
│
├── /blog (博客列表)
│   └── /blog/[slug] (文章详情)
│
├── /projects (项目详情 — 可选)
│
└── /about (完整 Bio — 可选, 也可在首页展开)
```

### 4.2 各区块详细设计

#### Hero Section
```
┌────────────────────────────────────────────────┐
│                                                │
│  Carl Li                                       │
│                                                │
│  Building at the intersection of               │
│  AI and craftsmanship.                         │
│                                                │
│  AI Engineer · LLM Trainer · Jeweler           │
│  📍 Singapore                                  │
│                                                │
│  [GitHub]  [Twitter/X]  [LinkedIn]  [Email]    │
│                                                │
└────────────────────────────────────────────────┘
```

**设计要点**：
- 名字用大号加粗字体，下方一句精炼 tagline
- 三个身份标签用 `font-mono` 小字展示
- 社交图标为细线条风格，hover 有颜色变化
- 可选：名字旁一个微妙的渐变光效（indigo → amber），呼应 AI + 珠宝的跨界

#### About / Bio
```
┌────────────────────────────────────────────────┐
│                                                │
│  I'm Carl (Bo Li), an AI engineer based in     │
│  Singapore. I spend my days training LLMs and  │
│  building AI systems, and my evenings at the   │
│  jewelry bench.                                │
│                                                │
│  Currently exploring: [具体项目/方向]           │
│  Previously: [简要经历]                         │
│                                                │
└────────────────────────────────────────────────┘
```

**设计要点**：
- 2-3 段自然叙事，避免简历式罗列
- 可以有一个 "Currently" 状态区（类似 leerob.com 的实时状态）

#### Featured Projects
```
┌────────────────────────────────────────────────┐
│  Featured Work                                 │
│                                                │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐     │
│  │ Project 1│  │ Project 2│  │ Project 3│     │
│  │          │  │          │  │          │     │
│  │ AI/LLM   │  │ Open Src │  │ Jewelry  │     │
│  │ 一句描述  │  │ 一句描述  │  │ 一句描述  │     │
│  └──────────┘  └──────────┘  └──────────┘     │
│                                                │
└────────────────────────────────────────────────┘
```

**设计要点**：
- 3 列网格（响应式：移动端单列）
- 每个卡片：项目名 + 一行描述 + 技术标签
- Hover 时卡片有微妙的边框发光效果（accent glow）
- 可选择展示 1 个珠宝项目，体现跨界特质

#### Writing / Blog
```
┌────────────────────────────────────────────────┐
│  Writing                                       │
│                                                │
│  2026-02-01  Training LLMs at Scale: ...       │
│  2026-01-15  My Jewelry Making Setup           │
│  2025-12-20  Building with AI Agents           │
│                                                │
│              → View all posts                  │
│                                                │
└────────────────────────────────────────────────┘
```

**设计要点**：
- 简洁列表式，日期 + 标题
- 日期用 `text-muted`，标题用 `text-primary`
- Hover 时标题颜色变为 accent

#### Footer
```
┌────────────────────────────────────────────────┐
│                                                │
│  [GitHub]  [Twitter]  [LinkedIn]  [Email]      │
│                                                │
│  Built with Astro & Tailwind CSS               │
│  © 2026 Carl Li                                │
│                                                │
└────────────────────────────────────────────────┘
```

---

## 5. 技术栈推荐

### 5.1 推荐方案：Astro + Tailwind CSS

| 层面 | 技术选择 | 理由 |
|------|----------|------|
| **框架** | **Astro 5.x** | 零 JS by default、Markdown 原生支持、极致性能、Content Collections |
| **样式** | **Tailwind CSS 4.x** | 快速开发、一致的设计系统、内置 dark mode、OKLCH 色彩 |
| **内容** | **MDX** (Markdown + JSX) | 博客文章用 .mdx，支持嵌入交互组件 |
| **动画** | **CSS transitions** + 可选 **Motion One** | 轻量微动画，不需要 Framer Motion 的重量 |
| **图标** | **Lucide Icons** (或 Phosphor) | 统一的细线条图标，开源免费 |
| **字体** | **Inter** (Google Fonts / self-hosted) | 免费、为 UI 设计优化、变量字体支持 |
| **代码高亮** | **Shiki** (Astro 内置) | 支持 VS Code 主题、零运行时 JS |
| **部署** | **Vercel** 或 **Cloudflare Pages** | 全球 CDN、自动 HTTPS、零配置部署 |
| **域名** | carl.dev / carlbo.li / carl-li.com | 简短、专业、好记 |

### 5.2 为什么选 Astro 而不是 Next.js？

| 比较项 | Astro | Next.js |
|--------|-------|---------|
| 个人网站适配度 | ⭐⭐⭐⭐⭐ — 专为内容站设计 | ⭐⭐⭐ — 功能更全但过重 |
| 初始 JS 大小 | **~0 KB** (零 JS by default) | ~85-100 KB (React runtime) |
| 首次加载速度 | **极快** (<0.5s) | 快 (~1s) |
| Markdown 支持 | **原生 Content Collections** | 需要额外配置 |
| 学习曲线 | 低（会 HTML 就能用） | 中（需懂 React） |
| 交互能力 | 按需 hydrate（islands） | 全页面 hydrate |
| 维护成本 | **极低** | 中（版本升级频繁） |

**结论**：对于以内容展示为主的个人主页，Astro 是 2025/2026 年的最佳选择。它提供最好的性能和最低的维护成本。如果未来需要复杂的交互功能，可以通过 Astro Islands 按需引入 React/Svelte 组件。

### 5.3 备选方案

如果 Carl 更熟悉 React 生态系统：

| 方案 | 说明 | 适合场景 |
|------|------|----------|
| **Next.js 15 + Tailwind** | 全功能 React 框架 | 如果未来想加复杂交互（AI demo 等） |
| **纯 HTML/CSS** | Karpathy 式极简 | 如果追求极致简单、零依赖 |
| **Hugo** | Go 模板引擎 | 如果主要写 blog，不需要 JS |

### 5.4 项目结构

```
carl-homepage/
├── public/
│   ├── fonts/           # Self-hosted Inter + JetBrains Mono
│   ├── images/          # 优化过的图片
│   └── favicon.svg
├── src/
│   ├── components/
│   │   ├── Header.astro
│   │   ├── Hero.astro
│   │   ├── About.astro
│   │   ├── ProjectCard.astro
│   │   ├── BlogList.astro
│   │   ├── Footer.astro
│   │   └── ThemeToggle.astro   # 暗/亮色切换
│   ├── content/
│   │   ├── blog/               # .mdx 博客文章
│   │   └── projects/           # .yaml 项目数据
│   ├── layouts/
│   │   ├── BaseLayout.astro
│   │   └── BlogLayout.astro
│   ├── pages/
│   │   ├── index.astro         # 首页
│   │   ├── blog/
│   │   │   ├── index.astro     # 博客列表
│   │   │   └── [...slug].astro # 文章详情
│   │   └── rss.xml.ts          # RSS feed
│   └── styles/
│       └── global.css          # Tailwind + 自定义变量
├── astro.config.mjs
├── tailwind.config.mjs
├── tsconfig.json
└── package.json
```

---

## 6. 补充设计规范

### 6.1 响应式设计断点

| 断点 | 宽度 | 布局调整 |
|------|------|----------|
| **Mobile** | `< 640px` | 单列布局，Hero 文字缩小至 `text-3xl`，项目卡片堆叠 |
| **Tablet** | `640px - 1024px` | 双列项目卡片，侧边 padding 增大 |
| **Desktop** | `> 1024px` | 三列项目卡片，最大内容宽度 `max-w-3xl` (prose) / `max-w-5xl` (grid) |

**移动端优先**：Tailwind 默认就是 mobile-first，所有样式从小屏写起，用 `sm:` / `md:` / `lg:` 向上覆盖。

### 6.2 可访问性 (A11y)

- **色彩对比度**：所有文字 / 背景组合满足 WCAG 2.1 AA 标准（对比度 ≥ 4.5:1）
- **键盘导航**：所有交互元素可通过 Tab 键聚焦，focus 样式清晰可见（`ring-2 ring-accent`）
- **语义化 HTML**：使用 `<header>`, `<main>`, `<article>`, `<nav>`, `<footer>` 等语义标签
- **图片 Alt 文本**：所有图片提供描述性 alt 属性
- **暗色/亮色切换**：尊重 `prefers-color-scheme` 系统偏好，同时允许手动切换
- **Reduced Motion**：`prefers-reduced-motion: reduce` 时禁用动画

### 6.3 SEO 与社交分享

**Meta 标签清单**：
```html
<!-- 基础 SEO -->
<title>Carl Li — AI Engineer & Jeweler</title>
<meta name="description" content="AI Engineer, LLM Trainer, and Jeweler based in Singapore. Building at the intersection of AI and craftsmanship." />
<link rel="canonical" href="https://carl.dev/" />

<!-- Open Graph (Facebook, LinkedIn, 飞书等) -->
<meta property="og:title" content="Carl Li — AI Engineer & Jeweler" />
<meta property="og:description" content="Building at the intersection of AI and craftsmanship." />
<meta property="og:image" content="https://carl.dev/og-image.png" />  <!-- 1200x630 推荐 -->
<meta property="og:type" content="website" />

<!-- Twitter Card -->
<meta name="twitter:card" content="summary_large_image" />
<meta name="twitter:title" content="Carl Li" />
<meta name="twitter:image" content="https://carl.dev/og-image.png" />
```

**其他 SEO**：
- `sitemap.xml` — Astro 官方 `@astrojs/sitemap` 集成，自动生成
- `robots.txt` — 允许全站索引
- 博客文章使用 JSON-LD 结构化数据（`@type: Article`）
- RSS feed（`/rss.xml`）— 方便订阅

### 6.4 图片优化策略

| 格式 | 用途 | 说明 |
|------|------|------|
| **WebP** | 项目截图、照片 | Astro `<Image>` 组件自动转换，比 PNG/JPG 小 25-35% |
| **AVIF** | 高质量照片（珠宝作品） | 更高压缩比，现代浏览器支持 >93% |
| **SVG** | 图标、Logo | 矢量无损，Lucide Icons 原生 SVG |
| **Favicon** | 站点图标 | SVG favicon（支持暗色适配）+ PNG fallback |

使用 Astro 内置的 `astro:assets` 进行构建时图片优化（自动 resize、format 转换、lazy loading）。

### 6.5 分析与监控

推荐 **隐私优先** 的方案（无需 cookie banner）：

| 工具 | 说明 | 成本 |
|------|------|------|
| **Plausible Analytics** | 轻量（<1KB）、隐私友好、GDPR 合规 | $9/mo 或自托管免费 |
| **Umami** | 开源自托管、功能类似 Plausible | 免费（自托管） |
| **Vercel Analytics** | 如果部署在 Vercel，零配置集成 | 免费 (Hobby plan) |

**推荐**：如果部署到 Vercel，直接启用 Vercel Web Analytics（零配置、免费）。否则选 Umami 自托管。

---

## 7. 开发路线图

> 预计总开发时间：**7-11 小时**（不含内容撰写）

### Phase 1：基础搭建（~2-3h）
- [ ] 初始化 Astro 项目 + Tailwind CSS
- [ ] 设置配色变量 + dark/light mode
- [ ] 配置字体 (Inter + JetBrains Mono)
- [ ] 搭建 BaseLayout + Header + Footer

### Phase 2：首页开发（~2-3h）
- [ ] Hero Section
- [ ] About/Bio Section
- [ ] Featured Projects (3 cards)
- [ ] 响应式适配

### Phase 3：博客系统（~1-2h）
- [ ] Content Collections 配置
- [ ] 博客列表页
- [ ] 文章详情页（MDX 支持）
- [ ] RSS feed

### Phase 4：细节打磨（~1-2h）
- [ ] 微动画 (hover, 页面过渡)
- [ ] SEO meta tags + Open Graph
- [ ] Favicon + 站点图标
- [ ] 性能优化 + Lighthouse 检查

### Phase 5：部署上线（~30min）
- [ ] 连接 Git 仓库
- [ ] 部署到 Vercel/Cloudflare Pages
- [ ] 配置自定义域名
- [ ] 验证 HTTPS + 缓存策略

---

## 8. 总结

### 核心设计原则
1. **Content First** — 内容为王，设计服务于内容
2. **Performance** — 零冗余 JS，首屏 <0.5s
3. **Personality** — AI + 珠宝的跨界应在细节中体现
4. **Maintainability** — Markdown 写文章，零运维成本
5. **Progressive** — 起步极简，未来可渐进增强

### 技术栈一句话总结
> **Astro 5 + Tailwind CSS 4 + MDX + Vercel** — 极致性能、最低维护、现代技术感。
