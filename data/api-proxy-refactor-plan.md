# API Proxy Refactor Plan: Native Format Support & GLM-5

## 1. Overview
The goal is to refactor `api-proxy` to support native format pass-through logic. Currently, the proxy assumes all external tiers are OpenAI-compatible and forces conversion for Anthropic clients. We want to support:
- **Anthropic Client (`/v1/messages`)** → **Anthropic Provider** (Native Pass-through)
- **Anthropic Client (`/v1/messages`)** → **OpenAI Provider** (Convert Request/Response)
- **OpenAI Client (`/v1/chat/completions`)** → **OpenAI Provider** (Native Pass-through)
- **GLM-5 Support**: Configure as an OpenAI-compatible provider.

## 2. Configuration Changes (`fallback.json`)
We need to extend the tier definition in `fallback.json` (and `src/fallback.py`) to include a `format` field.

**New Field:** `format` (enum: `"openai"`, `"anthropic"`). Default to `"openai"` for backward compatibility if missing.

**Example Configuration for GLM-5:**
```json
{
  "model": "glm-5",
  "name": "GLM-5",
  "type": "external",
  "base_url": "https://open.bigmodel.cn/api/paas/v4",
  "api_key": "sk-...",
  "format": "openai"
}
```

**Example Configuration for Native Anthropic:**
```json
{
  "model": "claude-3-opus-20240229",
  "name": "Claude 3 Opus (Native)",
  "type": "external",
  "base_url": "https://api.anthropic.com",
  "api_key": "sk-ant-...",
  "format": "anthropic"
}
```

## 3. Code Changes

### `src/app.py` - `call_external_tier`
The primary logic change happens here. We need to route based on `client_format` vs `tier_format`.

**Current Logic:**
- If `client_format` is "anthropic": Convert Request A→O, Call API, Convert Response O→A.
- If `client_format` is "openai": Pass Request, Call API, Pass Response.

**New Logic:**
Retrieve `tier_format` from the `tier` dict (default "openai").

1. **Match (Pass-through):**
   - If `client_format == tier_format`:
     - Copy body.
     - Update `model`.
     - Forward request to `tier['base_url']` + endpoint (need to map endpoints).
       - OpenAI: `/chat/completions`
       - Anthropic: `/v1/messages`
     - Return response directly (stream or non-stream).

2. **Mismatch (Conversion):**
   - **Case A: Client Anthropic → Tier OpenAI**:
     - Keep existing logic (A→O Request, O→A Response).
   - **Case B: Client OpenAI → Tier Anthropic**:
     - *Out of Scope for now / Not implemented*. Raise 400 or just don't configure this path yet.

### `src/proxy.py`
- Existing conversion functions (`anthropic_to_openai`, `openai_to_anthropic`, `openai_stream_to_anthropic_stream`) are sufficient for Case A.
- No new conversion logic needed unless we want to support Client OpenAI → Tier Anthropic (which requires `openai_to_anthropic_request`).

## 4. Implementation Steps

1.  **Update `src/fallback.py`**: Ensure `load_fallback_config` validates/allows the new `format` field in tiers.
2.  **Refactor `call_external_tier` in `src/app.py`**:
    - Add `tier_format = tier.get("format", "openai")`.
    - Implement the branching logic.
    - **Crucial**: Ensure correct endpoint usage.
        - If `tier_format` is "anthropic", destination is `{base_url}/v1/messages`.
        - If `tier_format` is "openai", destination is `{base_url}/chat/completions`.
3.  **Verify Headers**:
    - Anthropic requires `x-api-key` and `anthropic-version`.
    - OpenAI requires `Authorization: Bearer ...`.
    - Adjust header generation based on `tier_format`.

## 5. Verification Plan
- **Mock Test**: Create a test case in `tests/` with a mock Anthropic upstream.
- **Manual Test**: Configure a dummy tier for GLM-5 and verify routing.
