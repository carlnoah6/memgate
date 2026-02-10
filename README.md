# MemGate

**Privacy-Aware Memory Isolation Layer for AI Agents**

[![Website](https://img.shields.io/badge/Website-memgate-blue)](https://carlnoah6.github.io/memgate/) [![CI](https://github.com/carlnoah6/memgate/actions/workflows/test.yml/badge.svg)](https://github.com/carlnoah6/memgate/actions) [![PyPI](https://img.shields.io/pypi/v/memgate)](https://pypi.org/project/memgate/)

> 🛡️ **Current Version**: 0.4.0 (Provider Architecture)
>
> 📖 **[Documentation & Website →](https://carlnoah6.github.io/memgate/)**

MemGate acts as a firewall between your AI agent's long-term memory and its output channels. It ensures that private information (like calendar events, financial data, or family details) is never leaked into public contexts (like group chats), even if the LLM attempts to generate it.

## Features

- **Context-Aware Privacy**: Automatically distinguishes between Private (DM) and Public (Group) contexts.
- **Provider Architecture**: Pluggable platform adapters (Lark/Feishu built-in, extensible to Telegram, Discord, Slack).
- **Paranoid Check**: Detects hidden/invisible members by cross-referencing member count vs. member list — prevents privacy leaks from incomplete API data.
- **Pattern-Based Filtering**: Regex-based interception for high-risk categories (Phone, Email, Finance, Calendar).
- **Semantic Detection**: Embedding-based privacy detection (n-gram, OpenAI, or local models) catches rephrased leaks.
- **Knowledge Store**: JSONL-based store with public/private tagging and always-private category enforcement.
- **Red Team Arena**: Built-in adversarial testing with 8 attack strategies.
- **Strict Privacy Protocol**: CI/CD pipeline with CodeRabbit review ensuring no privacy regressions.

## Installation

```bash
pip install memgate
```

Or from source:

```bash
git clone https://github.com/carlnoah6/memgate.git
cd memgate
pip install -e .
```

## Usage

### CLI

```bash
# Check a message for privacy violations
memgate review \
  --message "My phone number is 13800138000" \
  --channel-type group \
  --participants "alice,bob"
```

### Provider API (Platform-Specific Privacy Detection)

```python
from memgate.providers.lark import LarkProvider

# Initialize with credentials
provider = LarkProvider(
    app_id="your_app_id",
    app_secret="your_app_secret",
    admin_open_id="ou_admin_user_id",
)

# Check if a chat is safe for private data
context = provider.fetch_context("oc_chat_id_here")
if provider.is_safe(context):
    print("Private chat — safe to share memory")
else:
    print(f"Unsafe: {context.reason}")
    if context.unsafe_reason:
        print(f"Integrity issue: {context.unsafe_reason}")
```

### Privacy Review API

```python
from memgate.privacy_review import PrivacyReviewer
from memgate.knowledge_store import KnowledgeStore

store = KnowledgeStore("path/to/knowledge")
reviewer = PrivacyReviewer(store=store)

result = reviewer.review(
    "Check out my salary: $50k",
    channel_id="group_chat_1",
    participants={"alice", "bob"},
)

if not result.passed:
    print(f"BLOCKED: {result.violations}")
```

### Custom Provider

```python
from memgate.providers.base import BaseProvider, ProviderContext

class TelegramProvider(BaseProvider):
    def fetch_context(self, chat_id: str) -> ProviderContext:
        # Your Telegram API logic here
        ...

    def is_safe(self, context: ProviderContext) -> bool:
        return context.is_private and context.unsafe_reason is None
```

## Development

### Running Tests

MemGate uses `pytest` for its test suite, including the "Red Team" mock scenarios.

```bash
pip install pytest
pytest
```

### Pre-commit Hooks

Ensure code quality and security (prevent API key leaks) before committing:

```bash
pip install pre-commit
pre-commit install
```

## License

MIT
