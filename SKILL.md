---
name: memgate
description: "Privacy Guard for AI Agents. Detects and redacts sensitive PII (emails, secrets, names) in text content. Use this skill to audit generated content before sending it to users."
metadata:
  openclaw:
    emoji: "🛡️"
    requires:
      bins: ["memgate"]
    install:
      - id: pip
        kind: pip
        package: memgate
        bins: ["memgate"]
        label: "Install MemGate (pip)"
---

# MemGate Skill

MemGate is a privacy firewall for your agent memory. Use it to check content for sensitive information leaks.

## Usage

### Check text for privacy leaks

```bash
memgate check "Text to check"
```

Returns `SAFE` or `LEAK DETECTED` with details.

### Review a file

```bash
memgate review path/to/file.md
```

### Redact sensitive info

```bash
memgate redact "My password is supersecret"
# Output: "My password is <REDACTED_SECRET>"
```

## Examples

**Audit a draft response:**

```bash
memgate check "Here is your API key: sk-12345"
```

**Clean a log file:**

```bash
memgate redact --file memory/logs.txt > memory/logs_clean.txt
```
