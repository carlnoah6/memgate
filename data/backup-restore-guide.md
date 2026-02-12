# 🔄 工作区备份与恢复指南

## 备份位置

```
/home/ubuntu/backups/
└── workspace-2026-02-12-0139/   ← 按日期时间命名
```

## 查看可用备份

```bash
bash /home/ubuntu/.openclaw/workspace/scripts/restore-workspace.sh --list
```

输出示例：
```
Available backups in /home/ubuntu/backups:
  workspace-2026-02-12-0139  (2.4G, 74711 files)
```

## 恢复操作

### 一键恢复

```bash
bash /home/ubuntu/.openclaw/workspace/scripts/restore-workspace.sh workspace-2026-02-12-0139
```

**安全机制**：恢复前会自动创建当前工作区的快照（`pre-restore-HHMMSS`），所以即使恢复了错误的版本也能回退。

### 恢复后重启 Luna

恢复文件后，Luna 需要重启才能加载恢复的配置：

```bash
openclaw gateway restart
```

## 手动创建新备份

```bash
rsync -av \
  --exclude node_modules --exclude .git --exclude __pycache__ \
  --exclude .venv --exclude .next --exclude out --exclude '*.pt' \
  /home/ubuntu/.openclaw/workspace/ \
  /home/ubuntu/backups/workspace-$(date +%Y-%m-%d-%H%M)/
```

## 注意事项

- 备份**不包含**：`node_modules`、`.git`、`__pycache__`、`.venv`、模型文件（`*.pt`）
- 备份**包含**：所有脚本、配置、数据文件、记忆文件、patches 等
- 恢复是**覆盖式**的（rsync `--delete`），恢复后工作区会完全回到备份时的状态
- 恢复前自动创建安全快照，不用担心丢失当前状态
