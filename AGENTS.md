# AGENTS.md - AI Agent Configuration Guide

## Overview

This document provides comprehensive guidelines for AI agents (Claude Code, Codex CLI, OpenCode) working on the Luna project. It covers workflows, decision criteria, best practices, and safety rules.

## Project Structure

```
/home/ubuntu/.openclaw/workspace/
├── docs/               # Documentation
├── scripts/            # Utility scripts
├── data/               # Data files and generated outputs
├── memory/             # Daily notes and logs
├── people/             # Contact information
└── extensions/         # OpenClaw extensions (read-only)
```

## Agent Types & Decision Tree

### When to Use Each Agent

```
                              New Task
                                 │
                    ┌────────────┴────────────┐
                    │                         │
           ┌────────▼────────┐       ┌───────▼────────┐
           │  Design Needed? │       │ Implementation │
           │                 │       │    Only?       │
           └────────┬────────┘       └───────┬────────┘
                    │                        │
           ┌────────▼────────┐       ┌───────▼────────┐
           │  Complex Arch?  │       │  Fast Fix?     │
           │  (System Design)│       │  (< 50 lines)  │
           └────────┬────────┘       └───────┬────────┘
                    │                        │
              ┌─────┴─────┐            ┌─────┴─────┐
              ▼           ▼            ▼           ▼
          CLAUDE      CLAUDE        CODEX      CODEX
         (Design)   (Review)     (YOLO)    (Full-auto)
           │           │            │           │
           └─────┬─────┘            └─────┬─────┘
                 │                        │
                 ▼                        ▼
         Architecture         Quick Implementation
         Documentation            & Fixes
```

### Detailed Decision Matrix

| Criteria | Claude Code | Codex Exec | Codex YOLO | Codex Full-Auto |
|----------|-------------|------------|------------|-----------------|
| **Complexity** | High | Medium | Low | Low-Medium |
| **Design Required** | ✅ Yes | ⚠️ Sometimes | ❌ No | ❌ No |
| **Code Quality Focus** | ✅ Yes | ✅ Yes | ⚠️ Fast | ✅ Yes |
| **Safety Level** | 🔒 High | 🔒 High | ⚠️ Medium | 🔒 High |
| **Speed** | 🐢 Slow | 🐇 Fast | 🚀 Fastest | 🐇 Fast |
| **Approval Needed** | ✅ Yes | ✅ Yes | ❌ No | ❌ Auto |

### Specific Use Cases

#### Use Claude Code When:
- 🏗️ **Architecture Design** — System structure, component relationships
- 📝 **API Design** — Interface definitions, data models
- 🔍 **Code Review** — Quality assurance, refactoring suggestions
- 📚 **Documentation** — Technical docs, README, guides
- 🐛 **Complex Debugging** — Root cause analysis, tracing issues
- 🔄 **Refactoring** — Large-scale code restructuring
- ⚡ **Performance Optimization** — Algorithm improvements

#### Use Codex CLI (exec) When:
- ⚙️ **Implementation** — Coding based on existing design
- 🧪 **Test Writing** — Unit tests, integration tests
- 🛠️ **Bug Fixes** — Straightforward fixes with clear scope
- 📦 **Scaffolding** — Boilerplate code generation
- 🔧 **Configuration** — Config file updates

#### Use Codex CLI (yolo) When:
- 🚀 **Quick Prototypes** — Proof of concept, experiments
- 📝 **Text Processing** — Bulk edits, transformations
- 🏃 **Emergency Fixes** — Critical hotfixes (with caution)
- 📊 **Data Processing** — Scripts, analytics

#### Use Codex CLI (full-auto) When:
- 🤖 **CI/CD Tasks** — Automated pipeline jobs
- 🔄 **Batch Operations** — Repetitive tasks with known patterns
- 📋 **Standard Templates** — Following established conventions

## Agent Workflows

### Starting a New Task

1. **Check current task status**:
   ```bash
   python3 scripts/task-manager.py list
   ```

2. **Register your session**:
   ```bash
   python3 scripts/task-manager.py set-session <task_id> <session_key>
   ```

3. **Read relevant documentation** before starting

### Task Lifecycle

```
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
│ PENDING │───▶│ QUEUED  │───▶│ RUNNING │───▶│  DONE   │
└─────────┘    └─────────┘    └─────────┘    └─────────┘
                                  │
                                  ▼
                            ┌─────────┐
                            │  FAILED │
                            └─────────┘
```

### Using Claude Code

```bash
# Quick task execution
claude "Your task description"

# With specific working directory
claude --workdir /path/to/project "Your task"

# With thinking mode (for complex problems)
claude --thinking "Analyze this architecture"

# As subagent (for task delegation)
claude --subagent "Handle subtask"
```

### Using Codex CLI

```bash
# One-shot execution with auto-approval
codex exec --full-auto "Your task"

# Sandbox mode (safest)
codex exec "Your task"

# No sandbox, no approvals (fastest, most dangerous)
codex --yolo "Your task"
```

### Using MCP Servers

```bash
# List configured MCP servers
claude mcp list

# The GitHub MCP server is available for:
# - Searching repositories
# - Reading file contents
# - Creating issues and PRs
# - Managing pull requests
```

## Collaboration Protocols

### Design Review Protocol

**Participants**: Architect (Claude) → Challenger (Codex) → Refiner (Claude)

```bash
# Initiate design debate
python3 scripts/agent-protocol/design-debate.py \
  --topic "Design task scheduling system" \
  --max-rounds 3
```

**Flow**:
1. Architect proposes design
2. Challenger identifies issues
3. Refiner incorporates feedback
4. Luna arbitrates final decision

### Code Review Protocol

**Participants**: Author (Codex) → Reviewer (Claude) → Responder (Codex) → Validator (Claude)

```bash
# Initiate code review
python3 scripts/agent-protocol/code-review-debate.py \
  --file path/to/code.py \
  --max-rounds 3
```

**Flow**:
1. Author submits code
2. Reviewer provides feedback
3. Author addresses comments
4. Validator approves/rejects

### Test Battle Protocol

**Participants**: Developer (Codex) → Breaker (Claude) → Fixer (Codex)

```bash
# Initiate test battle
python3 scripts/agent-protocol/test-battle.py \
  --feature "Implement thread-safe queue" \
  --max-rounds 3
```

**Flow**:
1. Developer implements feature
2. Breaker creates edge case tests
3. Fixer hardens implementation
4. Loop until stability achieved

## Best Practices

### Code Quality

1. **Always use git** — Create a branch for significant changes
2. **Test before committing** — Run tests if available
3. **Document changes** — Update relevant docs when making changes
4. **Follow existing patterns** — Match the codebase style
5. **Respect boundaries** — Don't modify system files without permission

### Task Management

1. **Clear descriptions** — Make task descriptions specific and actionable
2. **Dependency tracking** — Use `--after` flag for dependent tasks
3. **Session registration** — Always register session keys for running tasks
4. **Status updates** — Keep task status current (start/complete/fail)

### Communication

1. **Default to Chinese** — Use Chinese for general communication
2. **Technical terms** — Keep English technical terms untranslated
3. **Feishu formatting** — Use Markdown lists instead of tables
4. **Link sharing** — Always attach links when referencing docs

## Safety Rules

### Critical Boundaries

- ⚠️ **Never modify `extensions/` directory files directly**
- ⚠️ **Don't change OpenClaw core files without approval**
- ⚠️ **Use `trash` instead of `rm` for deletions**
- ⚠️ **Test in isolated environments when possible**

### Data Protection

- 🔒 **Private files stay private** — Don't share in group chats
- 🔒 **Privacy by open_id** — Use open_id for bot/person identification
- 🔒 **Token management** — Never commit API tokens to git

### System Stability

- 🛡️ **No core code changes** — Don't let agents modify their own core code
- 🛡️ **API Proxy isolation** — Use Git workflow, never direct code modification
- 🛡️ **Session management** — Clear jsonl + reset sessions.json, no restart needed

## Code Review Checklist

### Before Submitting Code

- [ ] **Functionality** — Code does what it claims to do
- [ ] **Tests** — Unit tests cover new functionality
- [ ] **Documentation** — README/comments updated
- [ ] **Style** — Follows project conventions
- [ ] **Security** — No hardcoded secrets, input validation
- [ ] **Performance** — No obvious bottlenecks
- [ ] **Error Handling** — Graceful failure handling
- [ ] **Edge Cases** — Boundary conditions considered

### During Review

- [ ] **Readability** — Code is clear and maintainable
- [ ] **Complexity** — Not unnecessarily complex
- [ ] **Duplication** — No code duplication
- [ ] **Naming** — Variables/functions well-named
- [ ] **Comments** — Necessary comments present
- [ ] **Dependencies** — No unnecessary dependencies

### After Review

- [ ] **Comments addressed** — All feedback incorporated
- [ ] **Tests pass** — CI/CD green
- [ ] **Documentation synced** — Wiki updated if needed

## Error Handling Guide

### Common Errors & Solutions

#### Task Stuck in Running
```bash
# Diagnose
python3 scripts/session-overview.py

# Cleanup
python3 scripts/session-cleanup.py --force <task_id>
```

#### Worktree Creation Failed
```bash
# Clean and retry
rm -rf /tmp/luna-worktrees/<task_id>
git worktree prune
```

#### Agent Not Responding
```bash
# Check status
openclaw gateway status

# Restart if needed
openclaw gateway restart
```

#### Git Conflicts
```bash
# Resolve manually in worktree
cd /tmp/luna-worktrees/<task_id>
git status
# Fix conflicts
git add .
git commit -m "Resolve conflicts"
```

### Escalation Path

1. **Level 1**: Check logs in `logs/` directory
2. **Level 2**: Run diagnostic scripts in `scripts/`
3. **Level 3**: Consult MEMORY.md for historical solutions
4. **Level 4**: Create task for human review

## Resources

- 📖 **OpenClaw Docs**: `docs/` or https://docs.openclaw.ai
- 🧠 **Memory**: `MEMORY.md` for long-term context
- 📅 **Daily Notes**: `memory/YYYY-MM-DD.md`
- 🛠️ **Tools**: `TOOLS.md` for environment specifics
- 📊 **Status**: `task-manager.py status`

## Quick Reference Card

```bash
# Task Management
task-manager.py add "description" [chat_id]     # Create task
task-manager.py start <id> <session>            # Start task
task-manager.py complete <id> [result]          # Complete task
task-manager.py list                            # List tasks
task-manager.py ready                           # Ready tasks

# Agent Execution
claude "task"                                   # Claude mode
codex exec "task"                               # Codex safe mode
codex --yolo "task"                             # Codex fast mode

# Collaboration
design-debate.py --topic "..."                  # Design review
code-review-debate.py --file ...                # Code review
test-battle.py --feature "..."                  # Test battle

# Monitoring
lark-task-dashboard.py                          # Send dashboard
session-overview.py                             # Session status
performance-metrics.py                          # System metrics
```

---

**Remember**: When in doubt, choose the safer option. It's better to take more time and do it right than to rush and break something.
