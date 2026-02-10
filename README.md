# MemGate

**Privacy-Aware Memory Isolation Layer for AI Agents**

> 🛡️ **Current Version**: 0.3.0 ("Little Crayfish" Protocol)

MemGate acts as a firewall between your AI agent's long-term memory and its output channels. It ensures that private information (like calendar events, financial data, or family details) is never leaked into public contexts (like group chats), even if the LLM attempts to generate it.

## Features

- **Context-Aware Privacy**: Automatically distinguishes between Private (DM) and Public (Group) contexts.
- **Pattern-Based Filtering**: Regex-based interception for high-risk categories (Phone, Email, Finance, Calendar).
- **Knowledge Store**: Simple JSON-based local vector store (extensible).
- **"Little Crayfish" Protocol**: Strict CI/CD pipeline ensuring no privacy regressions.
- **Red Team Arena**: Built-in adversarial testing framework (`memgate/tests/red_team/`).

## Installation

```bash
pip install memgate
```

### From Source

```bash
git clone https://github.com/carlnoah6/memgate.git
cd memgate
pip install -e ".[dev]"
```

## Usage

### CLI

```bash
# Check a message for privacy violations
python3 scripts/privacy-check.py review \
  --message "My phone number is 13800138000" \
  --channel-type group \
  --participants "alice,bob"
```

### Python API

```python
from memgate.privacy_review import PrivacyReviewer
from memgate.knowledge_store import KnowledgeStore

store = KnowledgeStore("path/to/knowledge")
reviewer = PrivacyReviewer(store=store)

result = reviewer.review(
    "Check out my salary: $50k",
    channel_id="group_chat_1",
    participants={"alice", "alice"}
)

if not result.passed:
    print(f"BLOCKED: {result.violations}")
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
