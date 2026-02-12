# Project Scaffolding Structure

## Directory Structure
```text
.
|-- configs
    |-- config.yaml
    |-- data
        |-- default.yaml
    |-- model
        |-- default.yaml
    |-- training
        |-- default.yaml
|-- data
    |-- backlog.md
    |-- calendar-categories.md
    |-- comment-state.json
    |-- daily-report-prompt.md
    |-- dashboard-state.json
    |-- dataset.py
    |-- gateway.pid
    |-- heartbeat-state.json
    |-- important-dates.json
    |-- lark-color-palette.json
    |-- lark-secrets.json
    |-- lark-user-token.json
    |-- periodic-check-prompt.md
    |-- personal-system.md
    |-- private-wiki.json
    |-- quota-snapshots
        |-- 2026-02-08.json
        |-- 2026-02-09.json
        |-- 2026-02-10.json
    |-- recurring-meetings.json
    |-- secrets
        |-- pypi-token.txt
    |-- spaceship-api.json
    |-- spawn-task-footer.md
    |-- task-board-notify-state.json
    |-- task-board.json
    |-- todo-state.json
    |-- tracked-docs.json
    |-- weekly-review-prompt.md
    |-- wiki-sync.json
    |-- yuanbao-birthday-party-2026.md
|-- model
    |-- __init__.py
    |-- model.py
|-- scripts
    |-- archive-backlog.py
    |-- check-calendar.py
    |-- check-doc-comments.sh
    |-- check-group-privacy.py
    |-- check-new-comments.py
    |-- check-restart.sh
    |-- check_comments_batch.py
    |-- check_comments_temp.py
    |-- cleanup-session-locks.sh
    |-- daily-backup.sh
    |-- debug-group-members.py
    |-- deliver-daily-report.sh
    |-- fetch_new_comments.py
    |-- generate_scaffold_report.py
    |-- heartbeat-scheduler.py
    |-- init-carl-knowledge.py
    |-- lark-calendar-create.py
    |-- lark-calendar-fix-colors.py
    |-- lark-calendar-today.py
    |-- lark-send-message.sh
    |-- lark-token-refresh.py
    |-- list-pending-comments.py
    |-- log-quota.sh
    |-- mark-restart.sh
    |-- md-to-email-text.py
    |-- md-to-lark-post.py
    |-- md-to-lark-wiki.py
    |-- memgate-pr.sh
    |-- memgate-sync.sh
    |-- migrate-wiki.mjs
    |-- oauth-callback.py
    |-- patch-openclaw.sh
    |-- privacy-check.py
    |-- privacy-hook.sh
    |-- process-comment-done.sh
    |-- research-spawn-checklist.md
    |-- restart-gateway.sh
    |-- rewrite-lark-doc.py
    |-- rewrite-wiki-1b-token.py
    |-- scan-comments.py
    |-- scan-new-comments.py
    |-- scan_comments.py
    |-- send-confirm-card.sh
    |-- skip-recurring-dates.py
    |-- sync-md-to-wiki.py
    |-- sync-tracked-docs.py
    |-- sync_memgate_wiki.py
    |-- sync_wiki_release.py
    |-- task-board-notify.py
    |-- task-chat.py
    |-- task-dashboard.py
    |-- task-health-check.py
    |-- task-manager.py
    |-- temp_calendar_check.py
    |-- token-hourly-stats.py
    |-- train.py
    |-- watchdog-log.py
|-- tests
    |-- __init__.py
|-- training
    |-- __init__.py
    |-- trainer.py

```

## Key Configurations

### Main Config (Hydra)
`configs/config.yaml`
```yaml
defaults:
  - _self_
  - model: default
  - data: default
  - training: default

hydra:
  run:
    dir: outputs/${now:%Y-%m-%d}/${now:%H-%M-%S}

```

### Model Config
`configs/model/default.yaml`
```yaml
# Model Configuration
name: "transformer_base"
d_model: 512
n_head: 8
num_encoder_layers: 6
num_decoder_layers: 6
dim_feedforward: 2048
dropout: 0.1

```

### Pre-commit Config
`.pre-commit-config.yaml`
```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.6
    hooks:
      - id: ruff
        args: [ --fix ]
      - id: ruff-format
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files

```

