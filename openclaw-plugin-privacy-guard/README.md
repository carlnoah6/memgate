# OpenClaw Privacy Guard Plugin

A comprehensive privacy protection plugin for OpenClaw agents. It ensures that agents handle sensitive information correctly based on the conversation context (Direct Message vs. Group Chat).

## Features

1.  **Context Awareness**: Automatically detects if the agent is in a private chat or a group chat.
2.  **Prompt Injection**: Injects system instructions to remind the model of privacy boundaries.
3.  **Knowledge Filtering**: Intercepts `memory_search` (or similar knowledge retrieval tools) to filter out private documents when in a group setting.
4.  **Output Review**: Scans the agent's final response for accidental leakage of sensitive patterns (emails, phone numbers, financial data) before it is sent.

## Installation

```bash
npm install openclaw-plugin-privacy-guard
```

## Usage

Register the plugin in your OpenClaw agent configuration:

```typescript
import { PrivacyGuardPlugin } from 'openclaw-plugin-privacy-guard';

const privacyPlugin = new PrivacyGuardPlugin({
  knowledgePath: '/path/to/knowledge/base',
  enabled: true,
  blockOnViolation: true
});

// Register with your agent runtime (example)
agent.registerPlugin(privacyPlugin);
```

## Configuration

| Option | Type | Default | Description |
|---|---|---|---|
| `knowledgePath` | `string` | required | Root directory of the user knowledge base (organized by user folders). |
| `enabled` | `boolean` | `true` | Master switch to enable/disable the plugin. |
| `blockOnViolation` | `boolean` | `true` | If true, blocks messages that fail the privacy review. |
| `patterns` | `object` | `{}` | Custom regex patterns to add to the default privacy checks. |

## Knowledge Base Structure

The plugin expects a knowledge base structure similar to:

```text
/knowledge
  /alice
    public.jsonl   <-- Accessible in Groups & DM
    private.jsonl  <-- Accessible ONLY in DM
  /bob
    public.jsonl
    private.jsonl
```

## License

MIT
