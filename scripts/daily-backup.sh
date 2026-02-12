#!/bin/bash
set -e

# Configuration
WORKSPACE_DIR="/home/ubuntu/.openclaw/workspace"
BACKUP_DIR="${WORKSPACE_DIR}/backups"
DATE=$(date +%Y-%m-%d)
FILENAME="backup-${DATE}.tar.gz"
TARGET="${BACKUP_DIR}/${FILENAME}"

# Ensure backup directory exists
mkdir -p "$BACKUP_DIR"

echo "[$(date)] Starting Daily Backup..."

# Change to workspace directory
cd "$WORKSPACE_DIR"

# Create backup
# Explicitly including specified files/dirs
# Using --exclude for safety patterns
tar -czf "$TARGET" \
    --exclude='node_modules' \
    --exclude='.git' \
    --exclude='tmp' \
    --exclude='backups' \
    --exclude='.cache' \
    data memory people projects \
    SOUL.md AGENTS.md TOOLS.md USER.md IDENTITY.md 2>/dev/null || true

# Check success
if [ -f "$TARGET" ]; then
    SIZE=$(du -h "$TARGET" | cut -f1)
    echo "✅ Backup created: $FILENAME ($SIZE)"
else
    echo "❌ Backup failed to create file."
    exit 1
fi

# Cleanup old backups (older than 7 days)
echo "Cleaning up backups older than 7 days..."
find "$BACKUP_DIR" -name "backup-*.tar.gz" -mtime +7 -print -delete

echo "Backup process complete."
