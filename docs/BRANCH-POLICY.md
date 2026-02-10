# Branch & Merge Policy — memgate

## Three Iron Rules

### 1. 🚫 No Direct Pushes to Main
- All changes must go through Feature Branch → PR → Merge
- Sole exception: Emergency hotfix (must create a PR record afterwards)
- **GitHub Settings**: Enable Branch Protection → Require PR before merge

### 2. ✅ CI Must Pass Before Merge
- Merge allowed only when all tests are green
- **GitHub Settings**: Require status checks to pass → Select "test" workflow
- Do not allow "skipped tests" to mask missing code (see Rule 3)

### 3. 🔍 CI Must Detect "Orphaned Tests"
- New check: `import_check` step
- Perform dry-run import for all `from memgate.xxx import` statements
- If import fails = CI fails (not skip)
- Prevents "ghost states" where test files exist but tested code does not

## Branch Naming Convention
- `feat/xxx` — New features
- `fix/xxx` — Bug fixes
- `chore/xxx` — Maintenance/Config
- `docs/xxx` — Documentation

## Merge Strategy
- Short-term branches (< 3 days): Squash merge
- Long-term branches (> 3 days): Regular merge (preserve history)
- Delete remote branch after merge

## PR Checklist (Auto Template)
- [ ] All new files have corresponding tests
- [ ] `__init__.py` exports updated
- [ ] CI all green (no skips to pass)
- [ ] No privacy-words violations
- [ ] CHANGELOG.md updated

## Periodic Cleanup
- Weekly check for dangling branches (unmerged > 7 days → merge or close)
- Command: `git branch -r --no-merged main`
