# Quick Start Tutorial

Get started with Luna AI Agent System in 10 minutes.

## Prerequisites

- Python 3.10+
- Git
- Claude Code CLI (optional but recommended)
- Codex CLI (optional but recommended)

## Installation

### 1. Clone Repository

```bash
git clone <repository-url>
cd luna-ai-agent-system
```

### 2. Set Up Environment

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Environment Variables

```bash
# Required
export LUNA_WORKSPACE=/home/ubuntu/.openclaw/workspace

# Optional - Agent paths
export CLAUDE_CODE_PATH=$(which claude)
export CODEX_CLI_PATH=$(which codex)

# Optional - Lark/Feishu integration
export LARK_APP_ID=cli_xxx
export LARK_APP_SECRET=xxx
```

## Your First Task

### Step 1: Create a Task

```bash
# Add a simple task
task-manager.py add "Create a hello world Python script"
```

Output:
```json
{
  "id": "t001",
  "status": "queued"
}
```

### Step 2: Start the Task

```bash
# Start the task with your session key
task-manager.py start t001 agent:main:feishu:user:xxx
```

Output:
```json
{
  "id": "t001",
  "status": "running",
  "started_at": "2026-02-15T09:30:00+08:00"
}
```

### Step 3: Execute with an Agent

**Using Claude Code:**
```bash
claude --workdir /tmp/luna-worktrees/t001 "Create a hello_world.py script that prints 'Hello, Luna!'"
```

**Using Codex CLI:**
```bash
codex exec --full-auto --workdir /tmp/luna-worktrees/t001 "Create a hello_world.py script that prints 'Hello, Luna!'"
```

### Step 4: Complete the Task

```bash
# Mark task as complete
task-manager.py complete t001 "Created hello_world.py successfully"
```

Output:
```json
{
  "id": "t001",
  "status": "done",
  "completed_at": "2026-02-15T09:35:00+08:00"
}
```

## Working with Dependencies

### Create Dependent Tasks

```bash
# Task 1: Design API
task-manager.py add "Design user API endpoints" --no-chat
# Output: t002

# Task 2: Implement API (depends on t002)
task-manager.py add "Implement user API" --after t002
# Output: t003

# Task 3: Write tests (depends on t003)
task-manager.py add "Write tests for user API" --after t003
# Output: t004
```

### Check Ready Tasks

```bash
# List tasks ready to run (queued + dependencies met)
task-manager.py ready
```

Output:
```json
[
  {
    "id": "t002",
    "description": "Design user API endpoints",
    "status": "queued",
    "priority": 2
  }
]
```

## Using Collaboration Protocols

### Design Review

```bash
# Run a design debate between agents
cd scripts/agent-protocol
python3 design-debate.py \
  --topic "Design a task queue with priority support" \
  --max-rounds 3
```

### Code Review

```bash
# Review code with multiple agents
python3 code-review-debate.py \
  --file /tmp/luna-worktrees/t001/hello_world.py \
  --max-rounds 2
```

## Monitoring Tasks

### Dashboard

```bash
# Send dashboard to Lark/Feishu
python3 scripts/lark-task-dashboard.py

# Or view locally
python3 scripts/task-manager.py list
```

### Session Overview

```bash
# Check active sessions
python3 scripts/session-overview.py
```

## Common Workflows

### Workflow 1: Feature Development

```bash
# 1. Create design task
task-manager.py add "[Design] API authentication system"

# 2. Start and use Claude for design
task-manager.py start t005 <session>
claude --thinking "Design API authentication with JWT tokens"
task-manager.py complete t005 "Design document created"

# 3. Create implementation task
task-manager.py add "[Feature] Implement JWT auth" --after t005

# 4. Use Codex for implementation
task-manager.py start t006 <session>
codex exec --full-auto "Implement JWT authentication based on design.md"
task-manager.py complete t006 "Implementation complete"
```

### Workflow 2: Bug Fix

```bash
# 1. Create bug fix task (high priority)
task-manager.py add "[Fix] Handle null pointer in auth module"

# 2. Use Claude for debugging
task-manager.py start t007 <session>
claude "Find and fix null pointer exception in auth.py line 45"

# 3. Run tests to verify
codex exec "Run tests for auth module"

# 4. Complete
task-manager.py complete t007 "Fixed null check added"
```

### Workflow 3: Refactoring

```bash
# 1. Create refactoring task
task-manager.py add "[Refactor] Extract validation logic"

# 2. Use Codex for initial extraction
task-manager.py start t008 <session>
codex exec "Extract validation logic from user.py into validators.py"

# 3. Use Claude for review
claude --subagent "Review the refactored validation logic"

# 4. Complete
task-manager.py complete t008 "Validation logic extracted and reviewed"
```

## Troubleshooting

### Task Not Starting

```bash
# Check status
task-manager.py list

# Check if dependencies are met
task-manager.py ready

# Force start if needed
task-manager.py start t001 <session>
```

### Agent Not Responding

```bash
# Check gateway
openclaw gateway status

# Restart if needed
openclaw gateway restart
```

### Worktree Issues

```bash
# Clean worktree
rm -rf /tmp/luna-worktrees/<task_id>
git worktree prune

# Recreate
python3 scripts/agent-orchestrator.py cleanup
```

## Next Steps

- Read [AGENTS.md](../AGENTS.md) for detailed agent guidelines
- Check [BEST-PRACTICES.md](BEST-PRACTICES.md) for development workflows
- Explore [examples/](../examples/) for more sample code
- Review [docs/cli-commands.md](cli-commands.md) for command reference

## Tips

1. **Start small** — Begin with simple tasks to learn the system
2. **Use --no-chat** — For automated tasks that don't need a chat group
3. **Register sessions** — Always register session keys for tracking
4. **Check ready queue** — Use `task-manager.py ready` to find runnable tasks
5. **Clean up** — Run `task-manager.py cleanup 7` weekly to remove old tasks

---

Need help? Check [BEST-PRACTICES.md](BEST-PRACTICES.md) for troubleshooting.
