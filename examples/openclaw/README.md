# OpenClaw Integration: Feishu Privacy Check

This example script demonstrates how to verify if a Feishu (Lark) group chat is "private" (i.e., only authorized users + the bot) or "public" (contains unauthorized members).

## Usage

Set your environment variables:

```bash
export LARK_APP_ID="cli_xxx"
export LARK_APP_SECRET="xxx"
export LARK_ADMIN_OPEN_ID="ou_xxx"  # The authorized user's open_id
```

Run the check:

```bash
python3 check_feishu_privacy.py <chat_id>
```

## Logic

1. Retrieves the bot's own `open_id`.
2. Lists all group members.
3. Filters out the bot itself.
4. Checks if remaining members match the `LARK_ADMIN_OPEN_ID`.

Returns exit code `0` for private, `1` for public.
