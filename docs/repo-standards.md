# Repository Standards

All repositories under our GitHub organization must follow these standards.
No exceptions. These are enforced by CI/CD and code review.

## Language

- **All code**: English only
- **All comments**: English only
- **All commit messages**: English only
- **All PR titles and descriptions**: English only
- **All documentation** (README, CHANGELOG, etc.): English only
- **All CI/CD workflow names and logs**: English only
- **Zero Chinese in any repository content** — internal workspace files (MEMORY.md, memory/, data/) are the only exception

## Repository Setup

Every new repository must include:

### 1. Branch Protection (main)

- Require PR before merging (no direct push to main)
- Require CI status checks to pass
- Squash merge preferred (clean history)

### 2. CI/CD Pipeline (.github/workflows/)

**CI workflow (ci.yml)** — runs on every PR:
- Lint (ruff for Python, eslint for JS/TS)
- Unit tests (pytest for Python, jest/vitest for JS/TS)
- Type checking where applicable

**CD workflow (deploy.yml)** — runs on push to main:
- Build artifact (Docker image / npm package / binary)
- Push to registry (ghcr.io for Docker, npm for JS)
- Deploy to target environment

### 3. Code Review

- **CodeRabbit** GitHub App installed on all repos
- Every PR gets automated review before merge
- Luna can self-review and merge without Carl's approval (Carl authorized 2026-02-11)

### 4. Docker (for deployable services)

- `Dockerfile` — multi-stage if needed, slim base image
- `docker-compose.yml` — for local dev and production
- `.dockerignore` — exclude .git, tests, docs, secrets
- **Code baked into image** (read-only, immutable)
- **Config files mounted as volumes** (environment-specific)
- **Never modify code inside containers** — rebuild image via CI/CD
- Images pushed to `ghcr.io/carlnoah6/<repo>:latest` + `:<sha>`

### 5. Secret Scanning (gitleaks)

Every repo must have secret leak detection at two layers:

**Pre-commit hook** (local, blocks commit):
- Copy `.gitleaks.toml` from `docs/gitleaks.toml` to repo root
- Install hook: `cp docs/pre-commit-hook.sh .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit`
- Scans staged changes for API keys, secrets, tokens, PII before commit
- Developers can bypass with `--no-verify` but CI will still catch it

**CI check** (remote, blocks merge):
- Add gitleaks step to `ci.yml`:
```yaml
      - name: Scan for secrets
        uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```
- Scans the full diff for every PR
- Must pass before merge (enforced by branch protection)

**What gets caught:**
- API keys and secrets (Lark, AWS, generic)
- Access tokens (tenant/user tokens)
- Hardcoded credentials
- Email addresses in code (allowed in .md, config files)
- Phone numbers in code
- Any pattern matching common secret formats

**Custom rules:** `.gitleaks.toml` at repo root (template: `docs/gitleaks.toml`)

### 6. Testing

- Minimum: unit tests for core logic
- Mock external dependencies (no real API calls in CI)
- Tests must pass before merge (enforced by branch protection)

### 7. Code Quality

- Linter config in repo (ruff for Python: `pyproject.toml`)
- Consistent formatting enforced by CI
- No hardcoded secrets — use environment variables or mounted config files
- Logging to stdout/stderr (Docker standard)

## File Structure Template

```
repo/
├── .github/
│   └── workflows/
│       ├── ci.yml          # Lint + test + secret scan on PR
│       └── deploy.yml      # Build + push + deploy on merge
├── .gitleaks.toml          # Secret scanning rules
├── src/                    # Application code
├── tests/                  # Test suite
├── scripts/                # Utility scripts (smoke tests, hooks)
├── Dockerfile              # Container definition
├── docker-compose.yml      # Service orchestration
├── .dockerignore           # Docker build exclusions
├── .gitignore              # Git exclusions
├── requirements.txt        # Python deps (or package.json for JS)
├── pyproject.toml          # Linter + tool config
├── README.md               # Project documentation
└── LICENSE                 # License (MIT default)
```

## Deployment Model

- **Semi-automatic**: merge to main → CI builds image → CD deploys
- **Rollback**: deploy previous image tag (`docker compose pull` with specific SHA)
- **No local code changes**: all changes go through PR → CI → CD
- **Smoke test after deploy**: automated health check in CD workflow

## Git Workflow

1. Create feature branch from main
2. Make changes, commit with descriptive English message
3. Push branch, create PR
4. CI runs automatically (lint + test)
5. CodeRabbit reviews automatically
6. Luna reviews code quality, security, correctness
7. Squash merge to main
8. CD builds and deploys automatically

## Commit Message Convention

```
type: short description

Longer explanation if needed.

Types: feat, fix, refactor, test, docs, ci, chore
```

Examples:
- `feat: add rate limiting per API key`
- `fix: handle 503 upstream errors in reactive fallback`
- `test: add mock upstream for fallback coverage`
- `ci: add Docker build step to CI pipeline`
