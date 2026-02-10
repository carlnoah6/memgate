# OpenClaw Integration Examples

These scripts demonstrate how to integrate MemGate with OpenClaw running on Feishu/Lark.

## check_feishu_privacy.py

A script to determine if a Feishu group chat is "private" (only the user and the bot) or "public" (contains other humans).

### Usage

```bash
python3 check_feishu_privacy.py <chat_id>
```

### Logic

1. Gets the bot's own `open_id` via `/bot/v3/info`.
2. Lists all members of the group chat.
3. Filters out the bot itself.
4. Checks if the remaining members are ONLY the authorized user (Carl).
5. Returns JSON status and exit code (0 = private, 1 = public).

### Why this matters

MemGate needs to know if a conversation context is private or public. For group chats, OpenClaw provides the `chat_id`, but not the full member list in every message. This script allows OpenClaw to check the group's privacy status at runtime (e.g., during session startup or via a hook) to decide whether to load private knowledge.
