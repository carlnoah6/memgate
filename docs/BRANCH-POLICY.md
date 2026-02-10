# Branch & Merge Policy — memgate

## 三条铁律

### 1. 🚫 禁止直接推 main
- 所有改动必须通过 Feature Branch → PR → Merge
- 唯一例外：紧急 hotfix（必须事后补 PR 记录）
- **GitHub 设置**：开启 Branch Protection → Require PR before merge

### 2. ✅ PR 合并前必须通过 CI
- 所有测试绿色才允许 merge
- **GitHub 设置**：Require status checks to pass → 选择 "test" workflow
- 不允许 "跳过的测试" 掩盖缺失代码（见第 3 条）

### 3. 🔍 CI 必须检测"孤立测试"
- 新增检查：`import_check` step
- 对所有 `from memgate.xxx import` 语句做 dry-run import
- 如果 import 失败 = CI 失败（而不是 skip）
- 防止"测试文件存在但被测代码不存在"的幽灵状态

## 分支命名规范
- `feat/xxx` — 新功能
- `fix/xxx` — Bug 修复
- `chore/xxx` — 维护/配置
- `docs/xxx` — 文档

## 合并策略
- 短期分支 (< 3 天)：Squash merge
- 长期分支 (> 3 天)：Regular merge（保留历史）
- 合并后删除远程分支

## PR Checklist（自动模板）
- [ ] 所有新文件都有对应的测试
- [ ] `__init__.py` 已更新 export
- [ ] CI 全绿（不靠 skip 过关）
- [ ] 没有 privacy-words 违规
- [ ] CHANGELOG.md 已更新

## 定期清理
- 每周检查悬空分支（未合并 > 7 天 → 要么合并要么关闭）
- 命令：`git branch -r --no-merged main`
