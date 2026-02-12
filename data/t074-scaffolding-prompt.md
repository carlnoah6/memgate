# Research Task: Project Scaffolding (t074)

## 目标
完成 "从零训练模型" 项目的代码仓库脚手架搭建。

## 任务清单
1. **检查/创建项目结构**:
   - `configs/` (YAML 配置)
   - `model/` (模型定义)
   - `training/` (训练脚本)
   - `data/` (数据处理)
   - `scripts/` (工具脚本)
   - `tests/` (测试)
   - `notebooks/` (实验)

2. **配置开发工具**:
   - `.pre-commit-config.yaml` (black, isort, flake8/ruff)
   - `.github/workflows/test.yml` (CI 基础)
   - `.gitignore` (Python, PyTorch, data)

3. **同步到 Wiki**:
   - 将生成的目录结构（`tree` 或 `find` 输出）和说明写入 Wiki。
   - **Space ID**: `7604150806383693538`
   - **Parent Node Token**: `OZmqwn4yviwsY2k1JBblkgTYg5c`
   - **Title**: "Project Scaffolding & Structure"

4. **更新 Backlog**:
   - 修改 `data/backlog.md`: 将 "代码仓库脚手架 (Project Scaffolding)" 标记为完成。

## 资源与鉴权
- **Wiki 鉴权**: `data/lark-user-token.json` (user_access_token)
- **Wiki API**:
  - 创建节点: `POST /open-apis/wiki/v2/spaces/{space_id}/nodes`
  - 写入内容: `POST /open-apis/docx/v1/documents/{token}/blocks/{token}/children`
- **消息发送**:
  - 脚本: `bash /home/ubuntu/.openclaw/workspace/scripts/lark-send-message.sh "oc_a2a70c6b4a29c2f2eb6c2500ea42a500" "✅ t074 完成: ..."`
  - **禁止使用 `message` 工具**

## 任务管理
- 任务 ID: t074
- 完成后运行: `python3 scripts/task-manager.py complete t074 "结果摘要"`
- 失败时运行: `python3 scripts/task-manager.py fail t074 "错误原因"`

## ⚠️ Checkpoint
如果发现 `configs/` 等目录已经存在（可能是 t071 遗留），请**审查**其内容是否完整，补充缺失部分，然后同步 Wiki 即可，不要盲目覆盖。
