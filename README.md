# MemGate

**Privacy-aware memory isolation for AI agents.**

Control what your AI knows — and what it shares.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![OpenClaw Skill](https://img.shields.io/badge/OpenClaw-Skill-orange.svg)](https://clawhub.com)
[![Website](https://img.shields.io/badge/Web-memgate.ai-green.svg)](https://memgate.ai)

---

## The Problem

AI agents like OpenClaw have access to everything — your calendar, contacts, files, conversations. When they serve multiple users or participate in group chats, **private data can leak between contexts**.

OpenClaw isolates *sessions* (conversation history), but not *knowledge*. Every session shares the same workspace files, meaning your AI could accidentally reveal your schedule, family details, or financial information in a group chat.

## The Solution

MemGate adds **knowledge-level privacy isolation** to AI agents:

```
Private Chat (you + AI)     →  Full access to all your data
Group Chat (you + others)   →  Only public knowledge, private data blocked
```

### How It Works

```
┌─────────────────────────────────────────┐
│              AI Agent                    │
│                                         │
│  ┌───────────┐    ┌──────────────────┐  │
│  │  Context   │    │   Output         │  │
│  │  Engine    │───▶│   Reviewer       │  │
│  │            │    │                  │  │
│  │ Who's in   │    │ Check before     │  │
│  │ this chat? │    │ sending          │  │
│  └─────┬─────┘    └────────┬─────────┘  │
│        │                   │            │
│  ┌─────▼───────────────────▼─────────┐  │
│  │       Knowledge Store              │  │
│  │                                    │  │
│  │  ┌─────────┐    ┌──────────────┐  │  │
│  │  │ Public  │    │   Private     │  │  │
│  │  │         │    │              │  │  │
│  │  │ Skills  │    │ Calendar     │  │  │
│  │  │ Hobbies │    │ Family       │  │  │
│  │  │ Location│    │ Finances     │  │  │
│  │  │         │    │ Contacts     │  │  │
│  │  └─────────┘    └──────────────┘  │  │
│  └────────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

### Three Layers of Protection

1. **Context Engine** — Determines what knowledge is accessible based on chat participants
2. **Output Reviewer** — Scans outgoing messages for private data leaks before sending
3. **Knowledge Store** — Classifies all data as public or private per user

## Quick Start

### Install as OpenClaw Skill

```bash
# Copy to your OpenClaw skills directory
cp -r memgate ~/.openclaw/skills/memgate
```

### Standalone CLI

```bash
# Check what knowledge is accessible in a group chat
python3 memgate/cli.py context --channel-type group --participants "alice,bob"

# Review a message before sending
python3 memgate/cli.py review --message "Alice's meeting is at 3pm" \
  --channel-type group --participants "alice,bob"

# Filter memory search results
python3 memgate/cli.py filter --results-json '[...]' \
  --channel-type group --participants "alice,bob"
```

## Privacy Rules

### Default: Private

All knowledge is **private by default**. Only explicitly marked public knowledge is shared.

### Always Private (never shared in group chats)

| Category | Examples |
|----------|----------|
| 📅 Calendar | Schedules, appointments, travel plans |
| 👨‍👩‍👧‍👦 Family | Children's names, ages, routines |
| 💰 Finance | Income, investments, accounts |
| 🏥 Health | Medical appointments, conditions |
| 🔐 Auth | Passwords, API keys, emails |
| 📞 Contacts | Phone numbers, addresses |

### Public (shared when relevant)

| Category | Examples |
|----------|----------|
| 💻 Skills | Programming languages, expertise |
| 🎯 Interests | Hobbies, preferences |
| 📍 Location | City/country (not address) |

## Configuration

```json
{
  "enabled": true,
  "defaults": {
    "visibility": "private"
  },
  "review": {
    "enabled": true,
    "block_on_violation": true
  }
}
```

## Knowledge Store

User knowledge is stored in JSONL format:

```
knowledge/
└── alice/
    ├── public.jsonl    # Shared in any chat
    └── private.jsonl   # Only in private chats
```

Each entry:
```json
{
  "content": "Enjoys hiking on weekends",
  "category": "preference",
  "visibility": "public",
  "source": "user_stated",
  "created_at": "2026-02-10T10:00:00Z"
}
```

## Testing

```bash
# Run the test suite
python3 -m pytest memgate/tests/ -v

# 29/29 tests passing:
# - 18 unit tests (isolation, classification, access control)
# - 11 integration tests (CLI, end-to-end scenarios)
```

## How It Compares

| Feature | OpenClaw Built-in | MemGate |
|---------|------------------|---------|
| Session isolation | ✅ | ✅ |
| Knowledge isolation | ❌ | ✅ |
| Output review | ❌ | ✅ |
| Per-user data classification | ❌ | ✅ |
| Pattern-based leak detection | ❌ | ✅ |
| Private entity matching | ❌ | ✅ |

## License

MIT — see [LICENSE](LICENSE).

## Links

- 🌐 Website: [memgate.ai](https://memgate.ai)
- 📦 OpenClaw Skills: [ClawHub](https://clawhub.com)
- 🐛 Issues: [GitHub Issues](https://github.com/carlnoah6/memgate/issues)
