# MemGate Integration Examples

> Practical examples showing how to integrate MemGate's privacy-aware memory isolation into different AI agent frameworks.

## Quick Start

```bash
# Clone and install
git clone https://github.com/carlnoah6/memgate.git
cd memgate
pip install -e .

# Run any example (no API keys needed — all examples have mock mode)
python3 examples/langchain_example.py
python3 examples/openai_example.py
python3 examples/openclaw_example.py
```

## Architecture

MemGate acts as a privacy firewall between your AI agent's memory and its output channels:

```
                        ┌─────────────────────────────┐
                        │        MemGate Layer        │
                        │                             │
  User Query ──────────→│  1. Context Detection       │
                        │     (DM vs Group)           │
                        │                             │
  Knowledge Store ─────→│  2. Knowledge Filtering     │──→ LLM
                        │     (public only in group)  │
                        │                             │
  LLM Response ────────→│  3. Output Review           │──→ User
                        │     (block private leaks)   │
                        └─────────────────────────────┘
```

### Where MemGate Sits in the Agent Pipeline

```
┌──────────┐     ┌──────────────┐     ┌─────────────┐     ┌──────────────┐     ┌──────────┐
│  User    │────→│  MemGate     │────→│  LLM        │────→│  MemGate     │────→│  User    │
│  Input   │     │  Pre-Filter  │     │  (GPT, etc) │     │  Post-Review │     │  Output  │
└──────────┘     └──────────────┘     └─────────────┘     └──────────────┘     └──────────┘
                  │                                         │
                  │ Filters knowledge                       │ Scans for
                  │ by channel context                      │ privacy leaks
                  │ (DM → all,                              │ (schedule, finance,
                  │  Group → public only)                   │  family, health, etc.)
```

## Examples

### 1. LangChain Integration (`langchain_example.py`)

**Use case:** Multi-user chatbot with per-user knowledge isolation.

**Key components:**
- `MemGateMemory` — LangChain-compatible memory wrapper that loads context-filtered knowledge
- `MemGateOutputParser` — Output parser that blocks privacy violations in LLM responses

```python
from examples.langchain_example import MemGateMemory, MemGateOutputParser

# Load only knowledge visible in this group chat
memory = MemGateMemory(
    channel_id="group_123",
    channel_type="group",
    participants={"alice", "bob"},
)
knowledge = memory.load_memory_variables({})

# Review LLM output before sending
parser = MemGateOutputParser(
    participants={"alice", "bob"},
    channel_id="group_123",
)
safe_text = parser.parse(llm_response)  # raises if violation detected
```

**Also see:** `langchain_middleware.py` — A production-ready `BaseOutputParser` with retry logic.

---

### 2. OpenAI SDK Integration (`openai_example.py`)

**Use case:** Direct OpenAI API usage with automatic context filtering and response review.

**Key components:**
- `PrivacyChatClient` — Drop-in wrapper around OpenAI chat completions with privacy enforcement
- Pre-call knowledge filtering + post-call output review
- Auto-retry on violation

```python
from examples.openai_example import PrivacyChatClient

client = PrivacyChatClient(
    channel_id="group_team",
    channel_type="group",
    participants={"alice", "bob"},
)

# Automatically filters knowledge + reviews response
result = client.chat("Tell me about Alice's skills")
print(result["reply"])   # Safe response
print(result["passed"])  # True/False
```

**Also see:** `openai_wrapper.py` — A lightweight wrapper using raw `urllib` (no `openai` package needed).

---

### 3. OpenClaw Integration (`openclaw_example.py`)

**Use case:** Privacy-aware AI agent running across multiple platforms (Feishu, Discord, Slack).

**Key components:**
- `MemGateAgent` — Full integration with system prompt generation, knowledge loading, and reply review
- Multi-platform support (same privacy rules across all channels)
- Violation logging for monitoring

```python
from examples.openclaw_example import MemGateAgent, OpenClawChannel

agent = MemGateAgent()

# Different channels, different rules
group = OpenClawChannel(
    channel_id="oc_group_team",
    channel_type="group",
    platform="feishu",
    participants={"alice", "bob", "charlie"},
)

# Get privacy-aware system prompt
prompt = agent.get_system_prompt(group)

# Review reply before sending
reply = agent.review_reply(draft_text, group)
if not reply.blocked:
    send(reply.content)
```

**Also see:** `openclaw_plugin.py` — Event hook-based plugin pattern.

---

### 4. FastAPI Middleware (`fastapi_middleware.py`)

**Use case:** LLM-powered API service with automatic response privacy filtering.

```python
from fastapi import FastAPI
from examples.fastapi_middleware import MemGateMiddleware

app = FastAPI()
app.add_middleware(
    MemGateMiddleware,
    participants={"alice", "bob"},
    channel_id="api_v1",
)
```

---

### 5. Feishu Privacy Check (`openclaw/check_feishu_privacy.py`)

**Use case:** Determine if a Feishu/Lark group chat is private (admin-only) or public.

```bash
export LARK_APP_ID="cli_xxx"
export LARK_APP_SECRET="xxx"
python3 examples/openclaw/check_feishu_privacy.py <chat_id>
```

## Framework Comparison

| Feature | LangChain | OpenAI SDK | OpenClaw | FastAPI |
|---------|-----------|------------|----------|---------|
| **Integration style** | Memory + OutputParser | Client wrapper | Agent plugin | ASGI middleware |
| **Pre-call filtering** | ✅ via MemGateMemory | ✅ built-in | ✅ system prompt | ❌ response only |
| **Post-call review** | ✅ OutputParser | ✅ auto-retry | ✅ before reply | ✅ middleware |
| **Auto-retry** | ✅ with_retry() | ✅ configurable | ❌ block + fallback | ❌ returns 451 |
| **Multi-user** | ✅ | ✅ | ✅ | ✅ via header |
| **Context switching** | ✅ switch_context() | ✅ switch_context() | ✅ per channel | ✅ per request |
| **Mock mode** | ✅ | ✅ | ✅ | ✅ |
| **Extra dependencies** | langchain-core | openai (optional) | none | fastapi |

### Which one should I use?

- **LangChain** — If you're already using LangChain and want privacy as part of your chain pipeline
- **OpenAI SDK** — If you're calling OpenAI directly and want a simple wrapper
- **OpenClaw** — If you're building an AI agent that serves multiple chat platforms
- **FastAPI** — If you're building an API service and want transparent privacy filtering

## Core Concepts

### Knowledge Visibility

```
┌─────────────────────────────────────┐
│           Knowledge Store           │
│                                     │
│  Alice:                             │
│    🔓 "Python developer" (public)   │  ← visible to everyone
│    🔒 "Meeting at 3pm" (private)    │  ← only visible in Alice's DM
│                                     │
│  Bob:                               │
│    🔓 "React expert" (public)       │  ← visible to everyone
│    🔒 "Salary $120k" (private)      │  ← only visible in Bob's DM
└─────────────────────────────────────┘
```

### Context Rules

| Context | Knowledge Access | Output Review |
|---------|-----------------|---------------|
| DM (1 user) | All of that user's knowledge (public + private) | No filtering |
| Group (2+ users) | Only participants' **public** knowledge | Active — blocks private leaks |

### Always-Private Categories

These categories are **always** treated as private, even if the user tries to mark them public:

- 📅 `calendar` — Schedules, meetings, appointments
- 👨‍👩‍👧‍👦 `family` — Family members, children, spouses
- 💰 `finance` — Salary, investments, accounts
- 🏥 `health` — Medical appointments, conditions
- 🔐 `auth` — Passwords, API keys, tokens
- 📞 `contact_private` — Phone numbers, addresses

## API Reference

### `PrivacyReviewer.review()`

The core review function used by all integrations:

```python
from memgate.privacy_review import PrivacyReviewer

reviewer = PrivacyReviewer()
result = reviewer.review(
    message="Alice has a meeting tomorrow at 3pm",
    channel_id="group_chat_1",
    participants={"alice", "bob"},
    sender="assistant",
)

if not result.passed:
    for v in result.violations:
        print(f"[{v.category}] {v.description}: {v.matched}")
```

### `PrivacyContext.get_accessible_knowledge()`

Get knowledge items accessible in a given context:

```python
from memgate.privacy_context import ChannelInfo, PrivacyContext
from memgate.knowledge_store import KnowledgeStore

store = KnowledgeStore()
channel = ChannelInfo(
    channel_id="group_123",
    participants={"alice", "bob"},
    channel_type="group",
)
ctx = PrivacyContext(channel, store)
items = ctx.get_accessible_knowledge()  # public items only
```

### `KnowledgeStore.add()`

Add knowledge items to the store:

```python
from memgate.knowledge_store import KnowledgeStore, KnowledgeItem

store = KnowledgeStore()
store.add(KnowledgeItem.from_dict({
    "user": "alice",
    "content": "I know Python and Rust",
    "category": "skill",
    "visibility": "public",
    "source": "user_declared",
}))
```

## Running Tests

```bash
# Run all tests
pytest

# Run just the integration tests
pytest memgate/tests/test_integration.py -v

# Run the examples as integration tests
python3 examples/langchain_example.py
python3 examples/openai_example.py
python3 examples/openclaw_example.py
```

## License

MIT — see [LICENSE](../LICENSE)
