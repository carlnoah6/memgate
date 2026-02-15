# Best Practices Guide

This document consolidates best practices for the Luna AI Agent System, covering development workflows, agent selection, code quality, and error handling.

## Table of Contents

1. [Agent Selection Decision Tree](#agent-selection-decision-tree)
2. [Code Review Checklist](#code-review-checklist)
3. [Common Error Handling](#common-error-handling)
4. [Performance Optimization](#performance-optimization)
5. [Git Workflow Best Practices](#git-workflow-best-practices)
6. [Task Management Guidelines](#task-management-guidelines)

---

## Agent Selection Decision Tree

### Overview

Choosing the right agent for a task is critical for efficiency and quality. Use this decision tree to determine whether to use Claude Code or Codex CLI.

### Primary Decision Factors

```
┌─────────────────────────────────────────────────────────────────────┐
│                     TASK CLASSIFICATION                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐          │
│  │   COMPLEXITY │    │   CREATIVE   │    │     RISK     │          │
│  │              │    │   REQUIRED   │    │              │          │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘          │
│         │                   │                   │                   │
│    High │              High │              High │                   │
│         ▼                   ▼                   ▼                   │
│    ┌─────────┐          ┌─────────┐          ┌─────────┐           │
│    │ CLAUDE  │          │ CLAUDE  │          │ CLAUDE  │           │
│    └─────────┘          └─────────┘          └─────────┘           │
│                                                                     │
│    Medium/Low │        Medium/Low │        Medium/Low              │
│         ▼                   ▼                   ▼                   │
│    ┌─────────┐          ┌─────────┐          ┌─────────┐           │
│    │  CODEX  │          │  CODEX  │          │  CODEX  │           │
│    └─────────┘          └─────────┘          └─────────┘           │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Detailed Decision Matrix

| Factor | Claude Code | Codex CLI |
|--------|-------------|-----------|
| **Complexity** | High — Architecture, design, refactoring | Low-Medium — Implementation, fixes |
| **Creativity** | High — Novel solutions, trade-off analysis | Low — Following patterns, templates |
| **Risk Level** | High — Core systems, security, data | Low — Utilities, scripts, tests |
| **Review Required** | Always — Quality gate | Optional — Fast iteration |
| **Time Sensitivity** | Low — Quality over speed | High — Speed over perfection |

### When to Use Claude Code

#### Architecture & Design
- System architecture design
- API design and review
- Database schema design
- Technology stack decisions
- Integration patterns

#### Quality Assurance
- Code review and feedback
- Refactoring planning
- Technical debt assessment
- Security review
- Performance optimization analysis

#### Complex Problem Solving
- Debugging complex issues
- Root cause analysis
- Race condition investigation
- Memory leak analysis
- Algorithm design

#### Documentation
- Technical specifications
- Architecture Decision Records (ADRs)
- API documentation
- Developer guides
- Onboarding docs

### When to Use Codex CLI

#### Rapid Implementation
- Following existing patterns
- Boilerplate generation
- CRUD operations
- Standard UI components
- Configuration updates

#### Testing
- Unit test generation
- Test data creation
- Mock/stub generation
- Regression test fixes
- Snapshot updates

#### Maintenance
- Dependency updates
- Lint fixes
- Formatting
- Simple bug fixes
- Log/message updates

#### Data Processing
- Log analysis scripts
- Data migration
- Bulk operations
- Report generation
- ETL tasks

### Codex Mode Selection

| Mode | Use Case | Safety | Speed |
|------|----------|--------|-------|
| `exec` | Standard development | High | Medium |
| `exec --full-auto` | CI/CD, batch tasks | High | Fast |
| `--yolo` | Prototyping, trusted changes | Medium | Fastest |

### Anti-Patterns

❌ **Don't Use Codex For:**
- Security-critical code without review
- Database migrations without backup plan
- Breaking API changes
- Core algorithm implementation
- Complex state management

❌ **Don't Use Claude For:**
- Simple text replacements
- Bulk file renames
- Standard CRUD scaffolding
- Configuration value updates
- Running simple scripts

---

## Code Review Checklist

### Pre-Review Checklist (Author)

Before requesting a review, ensure:

- [ ] **Self-review completed** — Read your own code once
- [ ] **Tests added/updated** — All new code has tests
- [ ] **Documentation updated** — README, comments, wiki
- [ ] **Linting passes** — No style violations
- [ ] **Type checking passes** — No type errors
- [ ] **Commit messages clear** — Explain the "why"
- [ ] **No debug code** — Remove console.log, print, debugger
- [ ] **No secrets** — No API keys, passwords in code

### Review Checklist (Reviewer)

#### Functionality
- [ ] Code does what the description claims
- [ ] Edge cases are handled
- [ ] Error conditions are covered
- [ ] Input validation is present
- [ ] Business logic is correct

#### Code Quality
- [ ] Functions are focused and small
- [ ] Variables are well-named
- [ ] No magic numbers/strings
- [ ] No code duplication (DRY)
- [ ] Complexity is appropriate

#### Testing
- [ ] Tests cover happy path
- [ ] Tests cover error cases
- [ ] Tests are readable
- [ ] Mock usage is appropriate
- [ ] Test data is realistic

#### Security
- [ ] No SQL injection vulnerabilities
- [ ] No XSS vulnerabilities
- [ ] Input is sanitized
- [ ] Authentication/authorization checked
- [ ] Secrets not hardcoded

#### Performance
- [ ] No N+1 queries
- [ ] No unnecessary loops
- [ ] Memory usage is reasonable
- [ ] Async/await used appropriately
- [ ] Caching considered where applicable

#### Maintainability
- [ ] Code is readable
- [ ] Comments explain "why", not "what"
- [ ] Documentation is clear
- [ ] Dependencies are necessary
- [ ] Breaking changes are documented

### Review Comment Severity

| Level | Description | Action Required |
|-------|-------------|-----------------|
| 🔴 **Blocker** | Security risk, data loss, crash | Must fix before merge |
| 🟡 **Major** | Significant bug, performance issue | Should fix before merge |
| 🟢 **Minor** | Style, readability, suggestions | Address if time permits |
| 💡 **Nit** | Personal preference, trivial | Optional |

### Review Response Guidelines

**As Author:**
1. Acknowledge all comments
2. Ask for clarification if unclear
3. Pushback respectfully if disagree
4. Resolve when fixed

**As Reviewer:**
1. Be specific and constructive
2. Explain the "why"
3. Suggest alternatives
4. Distinguish opinion from fact

---

## Common Error Handling

### Task System Errors

#### Task Stuck in "running" State

**Symptoms:**
- Task shows running but no agent is active
- Session key registered but no process

**Diagnosis:**
```bash
# Check active sessions
python3 scripts/session-overview.py

# Check process status
ps aux | grep <task_id>
```

**Resolution:**
```bash
# Force cleanup
python3 scripts/session-cleanup.py --force <task_id>

# Mark as failed if needed
task-manager.py fail <task_id> "Session lost"
```

**Prevention:**
- Always register session keys
- Implement heartbeat checks
- Set task timeouts

#### Worktree Creation Failed

**Symptoms:**
- "Failed to create worktree" error
- Permission denied on /tmp/luna-worktrees

**Diagnosis:**
```bash
# Check worktree status
git worktree list

# Check disk space
df -h /tmp
```

**Resolution:**
```bash
# Clean stale worktrees
rm -rf /tmp/luna-worktrees/<task_id>
git worktree prune

# Recreate
python3 scripts/agent-orchestrator.py cleanup
```

#### Dependency Resolution Failed

**Symptoms:**
- Task remains queued despite dependencies being done
- "Blocked by X" shows already completed tasks

**Diagnosis:**
```bash
# Check task dependencies
task-manager.py list
# Look for mismatched dependency IDs
```

**Resolution:**
```bash
# Force dependency update
task-manager.py complete <dep_id> "Force unlock"
# Or manually edit data/task-board.json (careful!)
```

### Agent Execution Errors

#### Claude Code Timeout

**Symptoms:**
- Task hangs indefinitely
- No output in log file

**Resolution:**
```bash
# Check if process exists
pgrep -f "claude.*<task_id>"

# Kill if stuck
pkill -f "claude.*<task_id>"

# Restart with thinking mode if complex
claude --thinking "<task>"
```

#### Codex Sandbox Violation

**Symptoms:**
- "Sandbox policy violation" error
- Files not written as expected

**Resolution:**
- Review sandbox restrictions
- Use `codex exec` instead of `--yolo` for file operations
- Or use `--yolo` if files are within workspace

#### Git Operation Failed

**Symptoms:**
- "Merge conflict" during worktree creation
- "Branch already exists" error

**Resolution:**
```bash
# Clean up branches
git branch -D agent/<task_id>

# Clean worktree
git worktree remove /tmp/luna-worktrees/<task_id>
git worktree prune
```

### Lark/Feishu Integration Errors

#### Message Send Failed

**Symptoms:**
- "send failed" in logs
- Messages not appearing in chat

**Diagnosis:**
```bash
# Check token validity
python3 scripts/lark-token-refresh.py

# Check rate limits
# (Look for 429 errors in logs)
```

**Resolution:**
```bash
# Refresh token
python3 scripts/lark-token-refresh.py --force

# Check gateway status
openclaw gateway status
```

#### Dashboard Update Failed

**Symptoms:**
- Dashboard card not updating
- "refresh_dashboard" callback errors

**Resolution:**
```bash
# Reset dashboard state
echo '{}' > data/dashboard-state.json

# Resend dashboard
python3 scripts/lark-task-dashboard.py
```

### System-Level Errors

#### Gateway Not Responding

**Symptoms:**
- "Connection refused" errors
- No agent responses

**Resolution:**
```bash
# Check status
openclaw gateway status

# Restart if needed
openclaw gateway restart

# Check logs
tail -f logs/gateway/*.log
```

#### Disk Space Full

**Symptoms:**
- "No space left on device"
- Worktree creation fails

**Resolution:**
```bash
# Clean logs
find logs/ -name "*.log" -mtime +7 -delete

# Clean worktrees
rm -rf /tmp/luna-worktrees/*

# Clean old tasks
task-manager.py cleanup 30
```

---

## Performance Optimization

### Agent Scheduler Optimization

#### Reduce Unnecessary Git Operations

**Problem:** Frequent git worktree create/remove operations are slow.

**Solutions:**
1. **Batch similar tasks** — Group tasks that touch same files
2. **Reuse worktrees** — For related sequential tasks
3. **Lazy cleanup** — Don't remove worktrees immediately
4. **Parallel worktrees** — Limit concurrent, not total

#### Optimize State Save Frequency

**Current:** Save state after every operation.
**Optimized:** Batch state saves.

```python
# Before: Save on every change
def update_task(task_id, status):
    task.status = status
    save_state()  # Disk write every time

# After: Batch saves
@debounce(seconds=5)
def save_state_debounced():
    save_state()

def update_task(task_id, status):
    task.status = status
    save_state_debounced()  # Batched writes
```

#### Agent Pool Management

**Optimal Concurrency Settings:**

| Resource | Recommended Max |
|----------|----------------|
| CPU-bound tasks | Number of cores |
| IO-bound tasks | 2-4x cores |
| Git operations | 2-3 concurrent |
| API calls | 5-10 concurrent |

### Memory Optimization

#### Log Rotation

```bash
# Add to crontab
0 0 * * * find logs/ -name "*.log" -size +100M -exec gzip {} \;
0 0 * * 0 find logs/ -name "*.gz" -mtime +30 -delete
```

#### Task History Cleanup

```bash
# Automated cleanup (add to daily cron)
task-manager.py cleanup 7  # Keep 7 days
```

---

## Git Workflow Best Practices

### Branch Naming

| Type | Pattern | Example |
|------|---------|---------|
| Feature | `feature/<description>` | `feature/task-scheduler` |
| Bugfix | `fix/<description>` | `fix/session-timeout` |
| Agent work | `agent/<task-id>` | `agent/t001-auth` |
| Hotfix | `hotfix/<description>` | `hotfix/memory-leak` |

### Commit Message Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**
- `feat` — New feature
- `fix` — Bug fix
- `docs` — Documentation
- `refactor` — Code restructuring
- `test` — Adding tests
- `chore` — Maintenance

**Example:**
```
feat(scheduler): add priority-based task queue

- Implement priority queue for task scheduling
- Add dependency resolution
- Update task manager CLI

Fixes: #123
```

### Worktree Best Practices

1. **Clean up on completion** — Always remove when done
2. **Use descriptive names** — Include task ID
3. **Don't commit to worktree directly** — Merge back to main
4. **Regular pruning** — Run `git worktree prune` weekly

---

## Task Management Guidelines

### Task Creation Best Practices

#### Description Format

```
[<Type>] <Action> <Target> [<Context>]

- Type: [Feature], [Fix], [Refactor], [Docs], [Test]
- Action: Implement, Fix, Update, Create, Remove
- Target: Component or file
- Context: Optional reference
```

**Examples:**
- `[Feature] Implement task dependency resolution`
- `[Fix] Handle session timeout in agent orchestrator`
- `[Docs] Update API reference for task manager`

#### Priority Guidelines

| Priority | Description | Response Time |
|----------|-------------|---------------|
| 🔴 P0 | Critical — System down | Immediate |
| 🟠 P1 | High — Major feature/blocker | Same day |
| 🟡 P2 | Medium — Normal work | 1-2 days |
| 🟢 P3 | Low — Nice to have | As scheduled |

### Dependency Management

#### When to Use Dependencies

✅ **Use When:**
- Task B requires output from Task A
- Sequential workflow (deploy after build)
- Resource constraints (can't run simultaneously)

❌ **Don't Use When:**
- Tasks are truly independent
- Only soft relationship ("related to")
- Can be parallelized

#### Setting Dependencies

```bash
# Single dependency
task-manager.py add "Deploy API" --after t001

# Multiple dependencies
task-manager.py add "Run integration tests" --after t002,t003,t004

# Chain of dependencies
task-manager.py add "Build" --no-chat
task-manager.py add "Test" --after <build_id>
task-manager.py add "Deploy" --after <test_id>
```

### Session Management

#### Session Key Registration

Always register session keys for long-running tasks:

```bash
# Start task
task-manager.py start t001 agent:main:feishu:...

# Or set after the fact
task-manager.py set-session t001 agent:main:feishu:...
```

#### Session Cleanup

```bash
# Check for zombie sessions
python3 scripts/session-overview.py

# Cleanup specific session
python3 scripts/session-cleanup.py <task_id>

# Bulk cleanup
python3 scripts/cleanup-zombies.py
```

---

## Summary

### Quick Reference

| Decision | Use |
|----------|-----|
| Complex design | Claude Code |
| Fast implementation | Codex CLI |
| Security-critical | Claude Code + Review |
| Bulk operations | Codex Full-auto |
| Documentation | Claude Code |
| Testing | Codex CLI |

### Golden Rules

1. **Quality over speed** — Better to be right than fast
2. **Test everything** — No exceptions
3. **Document as you go** — Not after
4. **Small changes** — Easier to review, easier to revert
5. **Communicate** — Keep task status updated

---

*Last updated: 2026-02-15*
