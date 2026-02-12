# Privacy Guard Plugin for OpenClaw

A multi-user privacy isolation framework that provides context-based knowledge access control, output review, and memory filtering for OpenClaw agents.

## Features

- **Context-based Access Control**: Automatically determines which knowledge is accessible based on chat context (private vs group chats)
- **Output Review**: Scans messages for privacy violations before sending (configurable)
- **Knowledge Tagging**: Public/private classification of knowledge items
- **Memory Search Filtering**: Filters memory search results based on privacy context
- **File Read Protection**: Controls access to privacy knowledge files
- **Multi-user Support**: Designed for scenarios with multiple users and group chats

## Installation

### From ClawHub (Recommended)

```bash
openclaw plugin install privacy-guard
```

### Manual Installation

1. Clone or download the plugin:
```bash
git clone https://github.com/openclaw/privacy-guard.git
```

2. Install dependencies:
```bash
cd privacy-guard
pip install -e .
```

3. Add to OpenClaw configuration:
```json
{
  "plugins": {
    "load": {
      "paths": ["/path/to/privacy-guard"]
    },
    "entries": {
      "privacy-guard": {
        "enabled": true,
        "review": {
          "enabled": true,
          "llm_self_review": false,
          "block_on_violation": true
        },
        "knowledge_base": {
          "path": "./privacy/knowledge",
          "auto_tag": true
        },
        "defaults": {
          "visibility": "private",
          "always_private_categories": [
            "calendar", "family", "finance", "health",
            "auth", "contact_private", "dm_content"
          ]
        }
      }
    }
  }
}
```

## Configuration

### Basic Configuration

```json
{
  "enabled": true,
  "review": {
    "enabled": true,
    "llm_self_review": false,
    "block_on_violation": true
  },
  "knowledge_base": {
    "path": "./privacy/knowledge",
    "auto_tag": true
  },
  "defaults": {
    "visibility": "private",
    "always_private_categories": [
      "calendar", "family", "finance", "health",
      "auth", "contact_private", "dm_content"
    ]
  }
}
```

### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enabled` | boolean | `true` | Enable/disable the entire Privacy Guard framework |
| `review.enabled` | boolean | `true` | Enable output review before sending messages |
| `review.llm_self_review` | boolean | `false` | Use LLM for comprehensive review (slower) |
| `review.block_on_violation` | boolean | `true` | Block messages with privacy violations |
| `knowledge_base.path` | string | `./privacy/knowledge` | Path to knowledge store directory |
| `knowledge_base.auto_tag` | boolean | `true` | Automatically tag knowledge as public/private |
| `defaults.visibility` | string | `private` | Default visibility for new knowledge |
| `defaults.always_private_categories` | array | `["calendar", "family", "finance", "health", "auth", "contact_private", "dm_content"]` | Categories that are always private |

## Usage

### Knowledge Management

Knowledge items are stored with public/private classification:

```python
# Example knowledge item
{
  "id": "k_001",
  "user": "carl",
  "content": "会 Python 编程",
  "visibility": "public",
  "category": "skill",
  "source": "user_declared",
  "created": "2026-02-10T07:00:00+08:00"
}
```

### Access Control Rules

1. **Private Chats (1 participant)**:
   - Can access all knowledge (public + private) of that user
   - No output review needed

2. **Group Chats (2+ participants)**:
   - Can only access public knowledge of all participants
   - Output review is applied before sending
   - Memory search results are filtered

### Tools

The plugin provides these tools to agents:

#### `privacyContext`
Get current privacy context and accessible knowledge.

```python
# Returns:
{
  "is_private": true,
  "participants": ["carl"],
  "accessible_knowledge": [...],
  "summary": "[Privacy] Private chat (user: carl) - Access to all knowledge"
}
```

#### `privacyReview`
Review a message for privacy violations.

```python
# Parameters:
{
  "message": "Carl 明天 14:00 要见马原",
  "channelType": "group",
  "participants": ["carl", "alex"]
}

# Returns:
{
  "passed": false,
  "violations": [
    {
      "category": "calendar",
      "matched": "明天 14:00",
      "description": "Detected schedule/calendar information"
    }
  ],
  "suggestion": "Message contains private information, please rewrite"
}
```

#### `addKnowledge`
Add knowledge item to store.

```python
# Parameters:
{
  "user": "carl",
  "content": "会 Python 编程",
  "category": "skill",
  "visibility": "public",
  "source": "manual"
}

# Returns:
{
  "success": true,
  "item": {
    "id": "k_001",
    "user": "carl",
    "content": "会 Python 编程",
    "visibility": "public",
    "category": "skill",
    "source": "manual",
    "created": "2026-02-10T07:00:00+08:00"
  }
}
```

## Hooks

The plugin integrates with OpenClaw through these hooks:

### `session:init`
Injects privacy context into session prompt and initializes access control.

### `message:beforeSend`
Reviews messages for privacy violations before sending (in group chats).

### `memory:search`
Filters memory search results based on privacy context.

### `file:read`
Controls access to privacy knowledge files.

## Knowledge Storage Structure

```
privacy/knowledge/
├── carl/
│   ├── public.jsonl    # Public knowledge items
│   └── private.jsonl   # Private knowledge items
├── alex/
│   ├── public.jsonl
│   └── private.jsonl
└── ...
```

Each JSONL file contains knowledge items in JSON format, one per line.

## Testing

Run the test suite:

```bash
pytest tests/ -v
```

### Test Scenarios

The plugin includes comprehensive tests for:

1. **Context Isolation**: Private vs group chat access control
2. **Output Review**: Detection of privacy violations
3. **Memory Filtering**: Correct filtering of search results
4. **File Protection**: Access control for knowledge files
5. **Edge Cases**: Various multi-user scenarios

## Development

### Setup Development Environment

```bash
# Clone repository
git clone https://github.com/openclaw/privacy-guard.git
cd privacy-guard

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black .
ruff check --fix .
```

### Architecture

```
privacy_guard/
├── __init__.py          # Main plugin implementation
├── knowledge_store.py   # Knowledge storage and management
├── privacy_context.py   # Context-based access control
├── privacy_review.py    # Output review engine
└── tests/              # Test suite
```

### Adding New Privacy Patterns

To add new privacy detection patterns, modify the `load_patterns()` method in `privacy_review.py`:

```python
def load_patterns(self) -> Dict:
    return {
        "new_category": {
            "description": "Description of the category",
            "patterns": [
                r"pattern1",
                r"pattern2",
                # Add regex patterns here
            ],
        },
        # ... existing categories
    }
```

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Run test suite
6. Submit a pull request

Please ensure all tests pass and code follows the project's style guidelines.

## Support

- Documentation: [docs.openclaw.dev/plugins/privacy-guard](https://docs.openclaw.dev/plugins/privacy-guard)
- Issues: [GitHub Issues](https://github.com/openclaw/privacy-guard/issues)
- Discussions: [GitHub Discussions](https://github.com/openclaw/privacy-guard/discussions)

## Changelog

### v1.0.0 (2026-02-12)
- Initial release
- Context-based access control
- Output review with pattern matching
- Knowledge tagging (public/private)
- Memory search filtering
- File read protection
- Comprehensive test suite