# Research Task: Deploy MemGate Website (t103)

## 目标
将 `memgate` 的文档发布为官方网站 (GitHub Pages)。

## 任务清单
1. **生成文档静态站**:
   - 使用 `mkdocs-material` (推荐) 或 Sphinx。
   - 包含: Home, Getting Started, API Reference, Contributing。
   - 配置 `mkdocs.yml` (theme: material, features: navigation.tabs, search)。

2. **配置 GitHub Pages**:
   - 在 `.github/workflows/deploy-docs.yml` 中添加 workflow。
   - 触发条件: push to main。
   - 步骤: checkout -> setup python -> install mkdocs-material -> mkdocs gh-deploy。

3. **本地验证**:
   - 安装依赖 `pip install mkdocs-material`。
   - 运行 `mkdocs serve` 预览。
   - 截图或确认无误。

4. **同步到 Wiki**:
   - **Space ID**: `7604150806383693538`
   - **Parent Node Token**: `OZmqwn4yviwsY2k1JBblkgTYg5c` (MemGate 父节点)
   - **Title**: "MemGate Official Website"

## 资源与鉴权
- **Wiki 鉴权**: `data/lark-user-token.json`
- **消息发送**: `bash scripts/lark-send-message.sh ...`

## 任务管理
- 任务 ID: t103
- 完成后运行: `python3 scripts/task-manager.py complete t103 "结果摘要"`
- 失败时运行: `python3 scripts/task-manager.py fail t103 "错误原因"`
