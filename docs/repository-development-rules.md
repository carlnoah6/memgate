# Repository Development Rules - Lessons Learned

**Date**: 2026-02-16  
**Incident**: Token Dashboard Development Process Failures

---

## 🔴 Critical Errors

### Error 1: Wrong Development Workflow

**What I did wrong**:
- Wrote all code locally
- Committed everything in one single commit
- Pushed directly to `main` branch
- No PR, no review, no discussion on GitHub

**Why this is wrong**:
- Code review should happen on GitHub via PRs
- Branch-based development enables collaboration
- PR workflow allows traceability of changes
- Each commit should be reviewable independently

**What I should have done**:
```bash
# 1. Create feature branch
git checkout -b feature/schema-design

# 2. Make incremental commits
git add prisma/schema.prisma
git commit -m "feat: add database schema with composite primary keys"

# 3. Push to GitHub
git push origin feature/schema-design

# 4. Create Pull Request via GitHub CLI
gh pr create --title "feat: database schema design" --body "..."

# 5. Wait for review (Claude + Codex dual-agent review)

# 6. Address review comments

# 7. Merge after approval
gh pr merge --squash
```

---

### Error 2: Chinese Text in Repository

**What I did wrong**:
- Wrote code comments in Chinese
- Used Chinese UI labels in components
- Created documentation in Chinese
- Mixed Chinese and English in the same codebase

**Why this is wrong**:
- Code repositories must be English-only
- UI text should be in English (i18n can be added later)
- Comments should be in English for global collaboration
- Decision records must be in English

**What I should have done**:
- Write all code comments in English
- Use English for all UI text
- Keep documentation in English
- If Chinese context is needed, keep it in external docs (Feishu Wiki), not in repo

---

## ✅ Correct Workflow (MUST FOLLOW)

### Step 1: Branch Creation
```bash
git checkout -b feature/<descriptive-name>
```

### Step 2: Incremental Development
- One feature per branch
- Small, focused commits
- Clear commit messages following conventional commits

### Step 3: Push and Create PR
```bash
git push origin feature/<name>
gh pr create --title "type: description" --body "Detailed explanation"
```

### Step 4: Dual-Agent Review on GitHub
- Claude Code reviews architecture and patterns
- Codex CLI reviews implementation details
- All discussions happen in PR comments

### Step 5: Iteration
- Address review comments
- Push fix commits
- Re-request review

### Step 6: Merge
```bash
gh pr merge --squash --delete-branch
```

---

## 📋 Language Policy (STRICT)

| Location | Language | Example |
|----------|----------|---------|
| Code comments | English only | `// Calculate time range` |
| Variable names | English only | `totalTokens`, `tenantRanking` |
| UI text | English only | `Total Usage`, `Tenant Ranking` |
| Commit messages | English only | `feat: add dashboard API` |
| PR descriptions | English only | `This PR adds...` |
| README | English only | `## Installation` |
| Decision records | English only | `DEC-001-database-schema.md` |

**Exception**: External documentation (Feishu Wiki, Lark docs) can be in Chinese for user-facing documentation.

---

## 🛡️ Prevention Checklist

Before every commit, ask:
- [ ] Am I on a feature branch, not main?
- [ ] Is this commit focused on one thing?
- [ ] Are all comments in English?
- [ ] Are all UI labels in English?
- [ ] Is the commit message in English?

Before every push, ask:
- [ ] Should I create a PR instead of pushing to main?
- [ ] Is the code ready for review?

---

## 📝 Incident Record

**Project**: Token Dashboard  
**Date**: 2026-02-16  
**Severity**: High (Process violation)  
**Reporter**: Carl  
**Root Causes**:
1. Did not follow GitHub PR workflow
2. Did not enforce English-only policy

**Corrective Actions**:
1. Deleted Chinese decision records from repo
2. Translated all UI text to English
3. Translated all comments to English
4. Created this rule document

**Prevention**:
- This document is now mandatory reading
- Pre-commit checklist enforced
- Future violations require immediate correction

---

## 🔗 Related Documents

- AGENTS.md - Multi-agent collaboration guidelines
- GitHub Workflow Guide - `data/github-workflow-README.md`
- Token Dashboard Repo - https://github.com/carlnoah6/token-dashboard

---

**Remember**: Code is written once, read many times. Follow the process.
