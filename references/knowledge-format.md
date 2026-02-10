# Knowledge Store Format

Each user has two JSONL files:

```
memgate/knowledge/
└── username/
    ├── public.jsonl
    └── private.jsonl
```

## Entry Schema

```json
{
  "content": "Human-readable knowledge text",
  "category": "category_name",
  "visibility": "public|private",
  "source": "user_stated|observed|imported",
  "created_at": "2026-02-10T10:00:00Z"
}
```

## Categories

### Always Private (cannot be made public)
- `calendar` — schedules, appointments, travel
- `family` — family member details
- `finance` — income, investments
- `health` — medical info
- `auth` — passwords, API keys, emails
- `contact_private` — phone, address

### Can Be Public
- `skill` — programming, expertise
- `preference` — hobbies, interests
- `dm_content` — conversation preferences
