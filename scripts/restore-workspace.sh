#!/usr/bin/env bash
#
# restore-workspace.sh — Restore workspace from a backup
#
# Usage:
#   bash scripts/restore-workspace.sh <backup-name>   # e.g. workspace-2026-02-12-0139
#   bash scripts/restore-workspace.sh --list           # list available backups
#
# Safety: Before restoring, creates a safety snapshot of the current workspace
#         so you can always get back to the pre-restore state.

set -euo pipefail

BACKUP_ROOT="/home/ubuntu/backups"
WORKSPACE="/home/ubuntu/.openclaw/workspace"

# Excluded directories (same as backup)
EXCLUDES=(
  --exclude='node_modules'
  --exclude='.git'
  --exclude='__pycache__'
  --exclude='.venv'
  --exclude='.next'
  --exclude='out'
  --exclude='*.pt'
)

# --- List mode ---
if [[ "${1:-}" == "--list" ]]; then
  echo "Available backups in $BACKUP_ROOT:"
  echo ""
  if [ -d "$BACKUP_ROOT" ]; then
    for d in "$BACKUP_ROOT"/workspace-*; do
      if [ -d "$d" ]; then
        SIZE=$(du -sh "$d" 2>/dev/null | cut -f1)
        COUNT=$(find "$d" -type f 2>/dev/null | wc -l)
        NAME=$(basename "$d")
        echo "  $NAME  ($SIZE, $COUNT files)"
      fi
    done
  else
    echo "  (no backups found)"
  fi
  exit 0
fi

# --- Restore mode ---
if [[ -z "${1:-}" ]]; then
  echo "Usage:"
  echo "  bash $0 <backup-name>   # restore from a backup"
  echo "  bash $0 --list          # list available backups"
  exit 1
fi

BACKUP_NAME="$1"
BACKUP_DIR="$BACKUP_ROOT/$BACKUP_NAME"

if [[ ! -d "$BACKUP_DIR" ]]; then
  echo "Error: Backup directory not found: $BACKUP_DIR"
  echo "Run '$0 --list' to see available backups."
  exit 1
fi

echo "=== Workspace Restore ==="
echo "Source:  $BACKUP_DIR"
echo "Target:  $WORKSPACE"
echo ""

# Safety: backup current state before overwriting
SAFETY_NAME="workspace-pre-restore-$(date +%Y-%m-%d-%H%M%S)"
SAFETY_DIR="$BACKUP_ROOT/$SAFETY_NAME"
echo "Creating safety snapshot: $SAFETY_NAME ..."
mkdir -p "$SAFETY_DIR"
rsync -a "${EXCLUDES[@]}" "$WORKSPACE/" "$SAFETY_DIR/"
echo "Safety snapshot created: $SAFETY_DIR"
echo ""

# Restore
echo "Restoring from $BACKUP_NAME ..."
rsync -av --delete "${EXCLUDES[@]}" "$BACKUP_DIR/" "$WORKSPACE/" 2>&1 | tail -5
echo ""
echo "✅ Restore complete!"
echo "   If anything went wrong, restore from: $SAFETY_NAME"
