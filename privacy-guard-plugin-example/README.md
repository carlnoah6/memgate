# Privacy Guard Plugin for OpenClaw

A multi-user privacy isolation framework for OpenClaw that prevents private information leakage in group chats.

## Features

- **Context Isolation**: Automatically determines which knowledge is accessible based on chat context
- **Output Review**: Reviews messages before sending to detect privacy violations
- **Knowledge Classification**: Supports public/private classification of knowledge items
- **Multi-user Support**: Designed for scenarios with multiple users and group chats
- **Configurable Rules**: Customizable privacy rules and sensitivity levels

## Installation

```bash
# Clone the repository
git clone https://github.com/luna-os/openclaw-plugin-privacy-guard.git
cd openclaw-plugin-privacy-guard

# Install dependencies
npm install

# Build the plugin
npm run build
```

## Configuration

Add the plugin to your OpenClaw configuration:

```json
{
  "plugins": {
    "load": {
      "paths": [
        "/path/to/privacy-guard-plugin"
      ]
    },
    "entries": {
      "privacy-guard": {
        "enabled": true,
        "review": {
          "enabled": true,
          "blockOnViolation": true,
          "llmSelfReview": false
        },
        "knowledgeBase": {
          "path": "privacy/knowledge",
          "autoSync": true
        },
        "channels": {
          "autoDetect": true
        }
      }
    }
  }
}
```

## Knowledge Base Structure

The plugin uses a knowledge base with the following structure:

```
privacy/knowledge/
├── user1/
│   ├── public.jsonl    # Public knowledge items
│   └── private.jsonl   # Private knowledge items
├── user2/
│   ├── public.jsonl
│   └── private.jsonl
└── ...
```

Each knowledge item is stored in JSONL format:

```json
{"id": "k_001", "user": "carl", "content": "Knows Python programming", "visibility": "public", "category": "skill", "source": "user_declared", "created": "2026-02-10T07:00:00+08:00"}
{"id": "k_002", "user": "carl", "content": "Meeting with John at 2 PM tomorrow", "visibility": "private", "category": "calendar", "source": "calendar_sync", "created": "2026-02-10T07:00:00+08:00"}
```

## Usage Examples

### Private Chat
In a private chat with a single user, the agent can access all knowledge (public and private) of that user.

### Group Chat
In a group chat with multiple users, the agent can only access public knowledge of all participants.

### Message Review
Before sending a message in a group chat, the plugin reviews it for privacy violations:

```typescript
const result = privacyGuard.reviewMessage(
  "group_chat_id",
  "Carl has a meeting at 2 PM tomorrow",
  ["carl", "alice", "bob"],
  "assistant"
);

if (!result.passed) {
  console.log("Privacy violation detected:", result.violations);
  // Message will be blocked if blockOnViolation is true
}
```

## Privacy Rules

The plugin detects the following categories of private information:

- **Calendar/Schedule**: Meeting times, appointments, schedules
- **Family Information**: Family member details, children's information
- **Financial Information**: Income, investments, account balances
- **Health Information**: Medical appointments, health conditions
- **Contact Information**: Phone numbers, email addresses, physical addresses
- **Authentication**: Passwords, API keys, credentials
- **Private Messages**: Content from direct messages

## API Reference

### PrivacyGuardPlugin

Main plugin class that manages privacy contexts and reviewers.

#### Methods

- `initializeSession(sessionId, channelInfo)`: Initialize privacy context for a session
- `getContext(sessionId)`: Get privacy context for a session
- `reviewMessage(channelId, message, participants, sender)`: Review a message before sending
- `filterMemoryResults(sessionId, results)`: Filter memory search results
- `getStatus()`: Get plugin status

### PrivacyContext

Manages what knowledge is accessible in a given chat context.

#### Methods

- `getAccessibleKnowledge()`: Get all accessible knowledge items
- `canAccessItem(item)`: Check if a specific knowledge item is accessible
- `getAccessiblePaths()`: Get accessible file paths for filtering
- `filterMemoryResults(results)`: Filter memory search results
- `getContextSummary()`: Get human-readable context summary

### PrivacyReviewer

Reviews messages for privacy violations before sending.

#### Methods

- `review(message, channelId, participants, sender)`: Review a message
- `getStatus()`: Get reviewer status

## Testing

Run the test suite:

```bash
npm test
```

The test suite includes:
- Unit tests for core components
- Integration tests with OpenClaw
- Privacy violation detection tests
- Performance tests

## Development

### Project Structure

```
src/
├── index.ts              # Plugin entry point
├── types.ts              # TypeScript type definitions
├── privacy-context.ts    # Privacy context management
├── privacy-reviewer.ts   # Message review system
├── knowledge-store.ts    # Knowledge storage management
└── config-schema.ts      # Configuration schema
```

### Building

```bash
npm run build    # Build the plugin
npm run dev      # Watch mode for development
npm run lint     # Run ESLint
npm run format   # Format code with Prettier
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for your changes
5. Run the test suite
6. Submit a pull request

## License

MIT License - see LICENSE file for details.

## Support

- GitHub Issues: [https://github.com/luna-os/openclaw-plugin-privacy-guard/issues](https://github.com/luna-os/openclaw-plugin-privacy-guard/issues)
- Documentation: [https://luna-os.github.io/openclaw-plugin-privacy-guard](https://luna-os.github.io/openclaw-plugin-privacy-guard)