---
name: memgate
description: Privacy-aware memory isolation for AI agents. Prevents private data leakage in group chats by classifying knowledge as public/private per user, controlling access based on chat participants, and reviewing outgoing messages for privacy violations. Use when serving multiple users or participating in group conversations.
---

# MemGate

Privacy-aware memory isolation for AI agents.

## When to Use

- Multi-user AI setups where private data must not leak between users
- Group chats where the AI has access to private user knowledge
- Any scenario requiring knowledge-level (not just session-level) isolation

## Commands

```bash
# Get privacy context for current session
python3 memgate/cli.py context --channel-type group --participants "user1,user2"

# Review message before sending in group chat
python3 memgate/cli.py review --message "message text" --channel-type group --participants "user1,user2"

# Filter memory search results
python3 memgate/cli.py filter --results-json '[...]' --channel-type group --participants "user1,user2"
```

## Rules

1. **Private chat** → full access to user's knowledge (public + private)
2. **Group chat** → only public knowledge; private data blocked
3. **Always private**: calendar, family, finance, health, auth credentials, contacts
4. **Default** = private (safe side)

## Setup

Place user knowledge in `memgate/knowledge/<username>/`:
- `public.jsonl` — shared in any chat
- `private.jsonl` — only in private chats

See `references/knowledge-format.md` for JSONL schema.
