# MemGate

**Privacy-Aware Memory Isolation Layer for AI Agents**

[![Website](https://img.shields.io/badge/Website-memgate-blue)](https://carlnoah6.github.io/memgate/) [![CI](https://github.com/carlnoah6/memgate/actions/workflows/test.yml/badge.svg)](https://github.com/carlnoah6/memgate/actions) [![PyPI](https://img.shields.io/pypi/v/memgate)](https://pypi.org/project/memgate/)

> 🛡️ **Current Version**: 0.3.0 ("Little Crayfish" Protocol)
>
> 📖 **[Documentation & Website →](https://carlnoah6.github.io/memgate/)**

MemGate acts as a firewall between your AI agent's long-term memory and its output channels. It ensures that private information (like calendar events, financial data, or family details) is never leaked into public contexts (like group chats), even if the LLM attempts to generate it.

## Features

- **Context-Aware Privacy**: Automatically distinguishes between Private (DM) and Public (Group) contexts.
- **Pattern-Based Filtering**: Regex-based interception for high-risk categories (Phone, Email, Finance, Calendar).
- **Knowledge Store**: Simple JSON-based local vector store (extensible).
- **"Little Crayfish" Protocol**: Strict CI/CD pipeline ensuring no privacy regressions.
- **Red Team Arena**: Built-in adversarial testing framework (`memgate/tests/red_team/`).

## Installation

```bash
git clone https://github.com/carlnoah6/memgate.git
cd memgate
pip install -e .
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

## 🏟️ Red Team Arena — Adversarial Testing

MemGate includes a built-in red-blue adversarial testing framework to validate privacy defenses against social engineering attacks.

### Architecture

```
┌─────────────┐     attack prompt     ┌─────────────┐
│  🔴 Red Team │ ──────────────────── │  🔵 Blue Team │
│  (Attacker)  │                       │  (Defender)  │
│              │     raw response      │  + MemGate   │
│  LLM / Mock  │ ◄──────────────────  │  Review      │
└─────────────┘                       └──────┬───────┘
                                              │
                                    ┌─────────▼────────┐
                                    │  ⚖️ Evaluator     │
                                    │  (Judge)          │
                                    │  Pattern / LLM    │
                                    └──────────────────┘
```

**Three roles:**
- **Red Team (Attacker)** — Generates social engineering attack prompts
- **Blue Team (Defender)** — Responds to attacks; MemGate reviews all output
- **Evaluator (Judge)** — Independently judges whether secrets were leaked

**Eight attack strategies:**

| Strategy | Description |
|----------|-------------|
| `authority_impersonation` | Pose as HR, admin, or manager |
| `context_manipulation` | Frame questions as hypothetical or previously discussed |
| `emotional_appeal` | Use urgency, sympathy, or fear |
| `indirect_extraction` | Infer secrets through tangential questions |
| `multi_turn` | Build rapport gradually, then extract |
| `role_play` | Ask AI to role-play without restrictions |
| `language_switch` | Switch languages to bypass filters |
| `prompt_injection` | Override system instructions |

### Quick Start

```bash
# Mock mode (no API key needed) — great for CI
python3 -m memgate.red_team --mock --rounds 16 -v

# With real LLM
python3 -m memgate.red_team --api-base https://api.openai.com/v1 --api-key sk-xxx --rounds 24 -v

# Output as Markdown report
python3 -m memgate.red_team --mock --rounds 16 -f markdown -o report.md

# Single strategy deep-dive
python3 -m memgate.red_team --mock --strategy prompt_injection --rounds 10 -v
```

### Python API

```python
from memgate.red_team import Arena

# Mock mode (for CI/testing)
arena = Arena(rounds=16, mock=True, verbose=True)
report = arena.run()

print(f"Block rate: {report['summary']['overall_block_rate']:.0%}")
print(f"Leaked: {report['summary']['total_leaked']}")

# Generate Markdown report
md = arena.report_gen.report.to_markdown()
```

### Running Red Team Tests

```bash
# All mock tests (no API key needed)
pytest memgate/tests/test_red_team_mock.py -v

# Integration tests (mock)
pytest memgate/tests/test_red_team_integration.py -v -k mock

# Real LLM integration tests
MEMGATE_API_KEY=sk-xxx pytest memgate/tests/test_red_team_integration.py -v -k llm
```

## License

MIT
