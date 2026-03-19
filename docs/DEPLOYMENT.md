# Vizier -- Deployment Guide

## Prerequisites

- Docker 24+ and Docker Compose v2
- Hermes Agent credentials (subscription auth or Anthropic API key)
- Telegram bot token from @BotFather
- Git access to `ghcr.io/stranma/vizier` (for pre-built images)

## 1. Authentication

Hermes supports two authentication methods. Choose one:

### Option A: Subscription Auth (Recommended)

Use your existing Claude Max/Pro or GitHub Copilot subscription. No API keys.

```bash
# Install Hermes locally (one-time)
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash

# Authenticate (pick one):
hermes login              # Anthropic (Claude Max/Pro)
hermes login copilot      # GitHub Copilot (OpenAI models)

# Copy credentials to project
cp ~/.hermes/auth.json hermes/auth.json
```

The `auth.json` is mounted read-only into the Docker container at startup.

### Option B: API Key Auth

Set `ANTHROPIC_API_KEY` in `.env`:

```bash
cp .env.example .env
# Edit .env and uncomment/set ANTHROPIC_API_KEY
```

For GitHub Copilot via token, set `COPILOT_GITHUB_TOKEN` in `.env` and change
`model.provider` to `"copilot"` in `hermes/config.yaml`.

## 2. Local Development

Run the MCP server directly (stdio transport, no Docker):

```bash
cd vizier-mcp
uv sync
VIZIER_ROOT=/path/to/data uv run python -m vizier_mcp
```

To enable the health endpoint locally:

```bash
VIZIER_ROOT=/path/to/data HEALTH_PORT=8080 uv run python -m vizier_mcp
curl http://localhost:8080/health
```

## 3. Docker Deployment

### Quick Start

```bash
# Configure environment
cp .env.example .env
# Edit .env: set TELEGRAM_BOT_TOKEN and TELEGRAM_ALLOWED_USERS
# For API key auth: also set ANTHROPIC_API_KEY
# For subscription auth: ensure hermes/auth.json exists (see Section 1)

# Start the stack
docker compose up -d

# Verify health
curl http://localhost:8080/health
docker compose logs hermes --tail=10
```

### Build from Source

```bash
docker compose build
docker compose up -d
```

### Pre-built Images (CI/CD)

The GitHub Actions deploy workflow builds and pushes to GHCR on every merge to master:

```bash
docker pull ghcr.io/stranma/vizier:latest          # vizier-mcp
docker pull ghcr.io/stranma/vizier-hermes:latest    # hermes-vizier
```

### Architecture

```
Sultan (Telegram)
  --> Hermes Gateway (hermes-vizier container)
        |-- Anthropic API (Claude Opus for Vizier agent)
        |-- MCP HTTP --> vizier-mcp container (port 8001)
        |                   |-- Realm tools (list, create, get projects)
        |                   |-- Container tools (start, stop, status)
        |                   |-- Health endpoints (port 8080)
        |                   |-- /data/vizier/ (realm state)
        |-- Sessions, memories (Docker volumes)
```

- **hermes-vizier**: Hermes Agent running the Vizier Grand Vizier personality
- **vizier-mcp**: FastMCP server providing domain tools via HTTP transport
- Hermes connects to vizier-mcp via native MCP HTTP (`mcp_servers.vizier.url`)
- Agent config files (SOUL.md, AGENTS.md) are baked into the Hermes image

## 4. Health and Readiness Endpoints

Both endpoints run on vizier-mcp (port 8080), auto-enabled inside Docker.

### Liveness: `GET /health`

Quick liveness check for load balancers and Docker healthcheck:

```json
{
  "status": "ok",
  "version": "1.0.0",
  "tool_count": 6
}
```

### Readiness: `GET /readiness`

Deep readiness check. Returns 200 when ready, 503 when not:

```json
{
  "ready": true,
  "version": "1.0.0",
  "checks": {
    "tools": {"pass": true, "detail": "6/6 tools registered"},
    "vizier_root": {"pass": true, "detail": "/data/vizier"},
    "repos_dir": {"pass": true, "detail": "/data/vizier/repos"},
    "writable": {"pass": true, "detail": "data directory is writable"}
  }
}
```

The Hermes container healthcheck verifies the `hermes gateway` process is running.

## 5. Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | If no auth.json | -- | Anthropic API key (subscription auth preferred) |
| `COPILOT_GITHUB_TOKEN` | If using Copilot | -- | GitHub Copilot token |
| `TELEGRAM_BOT_TOKEN` | Yes | -- | Telegram bot token from @BotFather |
| `TELEGRAM_ALLOWED_USERS` | Yes | -- | Sultan's Telegram user ID (comma-separated for multiple) |
| `GITHUB_TOKEN` | No | -- | GitHub PAT for province-scoped repo access (later phases) |
| `HERMES_AUTH_JSON` | No | `./hermes/auth.json` | Path to subscription auth credentials |
| `VIZIER_ROOT` | No | `/data/vizier` | Root directory for project data |
| `HEALTH_PORT` | No | `8080` | HTTP health endpoint port (vizier-mcp) |
| `AZURE_KEY_VAULT_URL` | No | -- | Azure Key Vault URL for production secrets |

## 6. Azure Key Vault (Production)

Secrets are stored in Azure Key Vault (`https://vizier.vault.azure.net/`) and
fetched automatically by the deploy pipeline.

### Secret Mapping

| Env Variable | Key Vault Secret Name | Used By |
|---|---|---|
| `ANTHROPIC_API_KEY` | `anthropic-api-key` | Hermes (Vizier agent LLM), vizier-mcp (Sentinel, later) |
| `TELEGRAM_BOT_TOKEN` | `telegram-bot-token` | Hermes (Telegram gateway) |
| `TELEGRAM_ALLOWED_USERS` | `telegram-allowed-users` | Hermes (gateway access control) |
| `GITHUB_TOKEN` | `github-pat` | Province-scoped repo access (later phases) |

**Note**: For subscription auth in production, place `auth.json` on the server
at `/opt/vizier/hermes/auth.json` (one-time setup). The deploy pipeline does not
manage subscription credentials -- they are authenticated locally and copied once.

### GitHub Actions Secrets Required

| GitHub Secret | Value | Where to Find |
|---|---|---|
| `AZURE_CLIENT_ID` | App registration client ID | Azure Portal > App registrations > Vizier Deploy |
| `AZURE_TENANT_ID` | Directory tenant ID | Azure Portal > Entra ID > Overview |
| `AZURE_SUBSCRIPTION_ID` | Subscription ID | Azure Portal > Subscriptions |
| `DEPLOY_HOST` | Production server hostname | Your infrastructure |
| `DEPLOY_SSH_KEY` | SSH private key for deploy user | Generated for the `vizier` user |

### One-Time Azure Setup

1. **Create an App Registration** in Azure Entra ID
2. **Add a federated credential** for GitHub Actions OIDC (environment: `production`)
3. **Grant Key Vault access** (Secret permissions: Get, List)
4. **Add `telegram-allowed-users`** to Key Vault with your Telegram user ID
5. **Add GitHub secrets** to the repository's `production` environment

## 7. Telegram Setup

### Create a Bot

1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot` and follow the prompts
3. Copy the bot token (format: `123456:ABC-DEF...`)
4. Set `TELEGRAM_BOT_TOKEN` in `.env`

### Find Your User ID

1. Message [@userinfobot](https://t.me/userinfobot) on Telegram
2. It replies with your user ID (a number like `123456789`)
3. Set `TELEGRAM_ALLOWED_USERS` in `.env`

### Hermes Gateway Access Control

Hermes denies access by default. Only user IDs in `TELEGRAM_ALLOWED_USERS` can
interact with the bot. Multiple users can be comma-separated:

```
TELEGRAM_ALLOWED_USERS=123456789,987654321
```

## 8. Volume Mounts

| Volume | Container | Purpose |
|--------|-----------|---------|
| `vizier-data` | vizier-mcp | Realm state (`/data/vizier/`) |
| `hermes-data` | hermes-vizier | Gateway sessions |
| `hermes-memories` | hermes-vizier | Agent persistent memory |
| `auth.json` (bind) | hermes-vizier | Subscription auth credentials (read-only) |

For production, consider bind-mounting `vizier-data` to a persistent disk.

## 9. CI/CD Pipeline

### Tests (`.github/workflows/tests.yml`)

Runs on every push and PR:
- Lint: `ruff check` + `ruff format --check`
- Tests: `pytest vizier-mcp/tests/` + `pytest tests/`
- Type check: `pyright`
- Deploy dry-run: Docker build + health check + Hermes config validation

### Deploy (`.github/workflows/deploy.yml`)

Triggered after Tests workflow succeeds on master:
1. Builds Docker images (vizier-mcp + hermes-vizier) and pushes to GHCR
2. Fetches secrets from Azure Key Vault
3. SCPs config files to production server
4. Writes secrets to server `.env`
5. Pulls images and runs `docker compose up -d`
6. Runs 4-point health check (MCP liveness, readiness, HTTP transport, Hermes running)

## 10. Memory Snapshots (Git Versioning)

Vizier's state files are automatically versioned via a daily git snapshot inside
the `vizier-data` Docker volume. See `scripts/memory-snapshot-cron.sh`.

## Troubleshooting

**Hermes won't start:**
- Check auth: `docker compose logs hermes | head -5` (look for "Auth:" line)
- If "No authentication found": either set `ANTHROPIC_API_KEY` in `.env` or mount `auth.json`
- If "TELEGRAM_ALLOWED_USERS is not set": add it to `.env`

**Bot doesn't respond in Telegram:**
- Verify bot token: `docker compose logs hermes | grep -i telegram`
- Verify user ID is in `TELEGRAM_ALLOWED_USERS`
- Check Hermes is running: `docker compose ps hermes`

**MCP tools fail:**
- Check vizier-mcp health: `curl http://localhost:8080/health`
- Check MCP connectivity: `docker compose logs hermes | grep -i mcp`
- Verify vizier-mcp started first (hermes depends on it being healthy)

**Health check fails:**
- Check container logs: `docker compose logs vizier-mcp`
- Verify port 8080 is exposed: `docker compose ps`

**Container exits immediately:**
- Check `VIZIER_ROOT` directory exists and is writable
- Check entrypoint validation: `docker compose logs hermes | head -10`
