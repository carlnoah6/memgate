#!/usr/bin/env bash
# pre-commit hook — scan staged changes for secrets before committing.
# Install: cp this file to .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit
# Or use the install script: bash scripts/install-hooks.sh

set -euo pipefail

if ! command -v gitleaks &>/dev/null; then
    echo "⚠️  gitleaks not found, skipping secret scan"
    echo "   Install: https://github.com/gitleaks/gitleaks#installing"
    exit 0
fi

# Scan only staged changes (--staged), not the full repo history
echo "🔍 Scanning for secrets..."
gitleaks protect --staged --config .gitleaks.toml --verbose 2>&1

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ Secret leak detected! Commit blocked."
    echo ""
    echo "If this is a false positive, add to .gitleaks.toml allowlist"
    echo "or use: git commit --no-verify (use with caution!)"
    exit 1
fi

echo "✅ No secrets found"
