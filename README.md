# Luna AI Agent System

🌙 **Luna** — Multi-Agent Collaborative System for AI-powered Development

## Overview

Luna is a sophisticated multi-agent AI system that orchestrates Claude Code and Codex CLI to collaboratively complete complex software development tasks. It implements intelligent task scheduling, agent collaboration protocols, and automated quality assurance.

## Key Features

- 🔄 **Multi-Agent Orchestration**: Seamlessly coordinates Claude Code and Codex CLI
- 📋 **Intelligent Task Scheduling**: Priority-based task queue with dependency management
- 🤝 **Collaborative Debate Protocol**: Design review, code review, and test battle cycles
- 🏗️ **Git Worktree Isolation**: Each task runs in isolated environment
- 📊 **Real-time Monitoring**: Dashboard for task status and session overview
- 🔔 **Lark/Feishu Integration**: Native messaging and notification support
- 🧠 **Knowledge Base Sync**: Automatic wiki synchronization

## Quick Start

```bash
# Add a new task
task-manager.py add "Implement user authentication API"

# Start a task (creates isolated worktree)
task-manager.py start t001 <session_key>

# Check task status
task-manager.py list

# Get ready tasks (queued + dependencies met)
task-manager.py ready
```

See [QUICKSTART.md](docs/QUICKSTART.md) for detailed tutorial.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Luna AI Agent System                    │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │ Task Manager │  │Agent Orchestra│  │  Lark Gateway    │   │
│  └──────────────┘  └──────────────┘  └──────────────────┘   │
│         │                 │                   │              │
│  ┌──────┴──────┐   ┌──────┴──────┐    ┌──────┴──────┐        │
│  │ Task Engine │   │ Collaboration│    │ Feishu API │        │
│  └─────────────┘   │  Protocol   │    └─────────────┘        │
│                    └─────────────┘                           │
│                           │                                  │
│              ┌────────────┴────────────┐                     │
│              │      Agent Pool         │                     │
│              │  ┌─────┐ ┌─────┐ ┌────┐ │                     │
│              │  │Claude│ │Codex│ │Luna│ │                     │
│              │  └─────┘ └─────┘ └────┘ │                     │
│              └─────────────────────────┘                     │
└─────────────────────────────────────────────────────────────┘
```

## Project Structure

```
/home/ubuntu/.openclaw/workspace/
├── AGENTS.md              # AI Agent configuration guide
├── MEMORY.md              # Long-term memory & context
├── TOOLS.md               # Environment-specific tools
├── docs/                  # Documentation
│   ├── BEST-PRACTICES.md  # Development best practices
│   ├── QUICKSTART.md      # Quick start tutorial
│   └── ...
├── scripts/               # Utility scripts
│   ├── task-manager.py    # Task management CLI
│   ├── agent-orchestrator.py  # Agent scheduler
│   ├── agent-protocol/    # Collaboration protocols
│   │   ├── design-debate.py
│   │   ├── code-review-debate.py
│   │   └── arbitrator.py
│   └── ...
├── data/                  # Data files & outputs
│   ├── task-board.json    # Task persistence
│   └── ...
├── memory/                # Daily notes & logs
└── tests/                 # Test suite
```

## Agent Types

### Claude Code
- **Strengths**: Complex architecture, design review, refactoring
- **Use for**: Design decisions, code quality, documentation
- **Command**: `claude "task description"`

### Codex CLI
- **Strengths**: Fast coding, bulk changes, scaffolding
- **Use for**: Implementation, testing, quick fixes
- **Modes**:
  - `codex exec` — Sandbox mode (safest)
  - `codex --yolo` — No sandbox, no approval (fastest)
  - `codex exec --full-auto` — One-shot with auto-approval

### Luna (Arbitrator)
- **Role**: Final decision maker, conflict resolution
- **Use for**: Breaking ties, quality gates, workflow orchestration

## Task Decision Tree

```
                        New Task
                           │
               ┌───────────┴───────────┐
               │                       │
        Requires Design?         Pure Implementation?
               │                       │
          ┌────┴────┐             ┌───┴────┐
          ▼         ▼             ▼        ▼
    Architecture   UI/UX      Fast Fix   Bulk Edit
        │           │          │          │
        ▼           ▼          ▼          ▼
     Claude      Claude     Codex      Codex
    (Design)   (Review)    (YOLO)    (Full-auto)
```

See [AGENTS.md](AGENTS.md) for detailed decision criteria.

## Collaboration Protocols

### 1. Design Review Debate
```bash
python3 scripts/agent-protocol/design-debate.py \
  --topic "Design API authentication system" \
  --max-rounds 3
```

### 2. Code Review Cycle
```bash
python3 scripts/agent-protocol/code-review-debate.py \
  --file path/to/code.py \
  --max-rounds 3
```

### 3. Test Battle
```bash
python3 scripts/agent-protocol/test-battle.py \
  --feature "Implement thread-safe queue" \
  --max-rounds 3
```

## Configuration

### Environment Variables
```bash
# Agent paths (optional)
export CLAUDE_CODE_PATH=$(which claude)
export CODEX_CLI_PATH=$(which codex)

# Workspace
export LUNA_WORKSPACE=/home/ubuntu/.openclaw/workspace

# Lark/Feishu
export LARK_APP_ID=cli_xxx
export LARK_APP_SECRET=xxx
```

### Task Configuration
```bash
# Max concurrent agents (default: 3)
export MAX_CONCURRENT_AGENTS=3

# Worktree base directory
export WORKTREE_BASE=/tmp/luna-worktrees/
```

## Commands Reference

### Task Management
| Command | Description |
|---------|-------------|
| `task-manager.py add "desc" [chat]` | Create new task |
| `task-manager.py start <id> <session>` | Mark task running |
| `task-manager.py complete <id> [result]` | Mark task complete |
| `task-manager.py fail <id> [error]` | Mark task failed |
| `task-manager.py list` | List all tasks |
| `task-manager.py ready` | List ready tasks |

### Agent Orchestration
| Command | Description |
|---------|-------------|
| `agent-orchestrator.py schedule` | Schedule pending tasks |
| `agent-orchestrator.py status` | Show system status |
| `agent-orchestrator.py watch` | Watch mode (continuous) |

### Dashboard
| Command | Description |
|---------|-------------|
| `lark-task-dashboard.py` | Send/refresh dashboard |
| `session-overview.py` | Generate session report |

## Testing

```bash
# Run all tests
pytest tests/

# Test collaboration protocols
python3 examples/agent-collaboration-demo/test_collaboration.py

# End-to-end test
python3 tests/e2e/test_full_workflow.py
```

## Monitoring

### Dashboard
```bash
# Send dashboard to Lark
python3 scripts/lark-task-dashboard.py

# Check system health
python3 scripts/performance-metrics.py
```

### Logs
```
logs/
├── agent-tasks/         # Agent execution logs
├── gateway/             # Gateway logs
└── errors/              # Error logs
```

## Development Guidelines

1. **Always use git** — Create branches for significant changes
2. **Test before committing** — Run tests if available
3. **Document changes** — Update relevant docs
4. **Follow patterns** — Match codebase style
5. **Respect boundaries** — Don't modify system files directly

See [BEST-PRACTICES.md](docs/BEST-PRACTICES.md) for complete guidelines.

## Troubleshooting

### Common Issues

**Task stuck in running state**
```bash
# Check session status
python3 scripts/session-overview.py

# Force cleanup
python3 scripts/session-cleanup.py --force
```

**Worktree creation failed**
```bash
# Clean worktree cache
rm -rf /tmp/luna-worktrees/

# Reinitialize
python3 scripts/agent-orchestrator.py cleanup
```

**Agent not responding**
```bash
# Restart gateway
openclaw gateway restart

# Check logs
tail -f logs/gateway/*.log
```

See [docs/best-practices/troubleshooting.md](docs/best-practices/troubleshooting.md) for more.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Follow best practices in [BEST-PRACTICES.md](docs/BEST-PRACTICES.md)
4. Submit PR for review

## License

MIT License — See [LICENSE](LICENSE) for details.

## Resources

- 📖 [Documentation](docs/)
- 🚀 [Quick Start](docs/QUICKSTART.md)
- 🤖 [Agent Guide](AGENTS.md)
- ⚡ [Best Practices](docs/BEST-PRACTICES.md)
- 🔧 [API Reference](docs/cli-commands.md)

---

**Luna** — *"Light in the dark, guidance in complexity"*
