# Vizier MCP Server -- Deployment Guide

## Prerequisites

- Docker 24+ and Docker Compose v2
- Anthropic API key (for Sentinel Haiku evaluator)
- Git access to `ghcr.io/stranma/vizier` (for pre-built images)

## 1. Local Development

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

## 2. Docker Deployment

### Quick Start

```bash
# Copy and configure environment
cp .env.example .env
# Edit .env and set ANTHROPIC_API_KEY

# Create data directory
mkdir -p /data/vizier/projects

# Start the server
docker compose up -d

# Verify health
curl http://localhost:8080/health
```

### Build from Source

```bash
docker compose build
docker compose up -d
```

### Pre-built Image (CI/CD)

The GitHub Actions deploy workflow builds and pushes to GHCR on every merge to master:

```bash
docker pull ghcr.io/stranma/vizier:latest
```

## 3. Health and Readiness Endpoints

Both endpoints are automatically enabled inside Docker (port 8080).

### Liveness: `GET /health`

Quick liveness check for load balancers and Docker healthcheck:

```json
{
  "status": "ok",
  "version": "0.6.0",
  "tool_count": 11
}
```

### Readiness: `GET /readiness`

Deep readiness check that verifies tool registration, data directory,
and API key configuration. Returns 200 when ready, 503 when not:

```json
{
  "ready": true,
  "version": "0.6.0",
  "checks": {
    "tools": {"pass": true, "detail": "11/11 tools registered"},
    "vizier_root": {"pass": true, "detail": "/data/vizier"},
    "projects_dir": {"pass": true, "detail": "/data/vizier/projects"},
    "writable": {"pass": true, "detail": "data directory is writable"},
    "anthropic_api_key": {"pass": true, "detail": "set"}
  }
}
```

The Docker healthcheck uses `/health` (liveness). The deploy workflow
uses `/readiness` (deep check) after deployment to verify the server
is fully operational.

## 4. Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | Yes | -- | Anthropic API key for Sentinel Haiku evaluator |
| `VIZIER_ROOT` | No | `/data/vizier` | Root directory for project data |
| `HEALTH_PORT` | No | `8080` (Docker) | HTTP health endpoint port; auto-enabled in Docker |
| `AZURE_KEY_VAULT_URL` | No | -- | Azure Key Vault URL for production secrets |

## 5. Azure Key Vault (Production)

For production deployments, secrets can be read from Azure Key Vault instead of environment variables.

### Setup

1. Install Azure packages in the container (or add to dependencies):
   ```
   pip install azure-identity azure-keyvault-secrets
   ```

2. Set the vault URL:
   ```bash
   AZURE_KEY_VAULT_URL=https://vizier.vault.azure.net/
   ```

3. Configure authentication (Managed Identity or Service Principal):
   - **Managed Identity** (recommended for Azure VMs/AKS): No additional config needed
   - **Service Principal**: Set `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_CLIENT_SECRET`

### Secret Mapping

| Env Variable | Key Vault Secret Name |
|---|---|
| `ANTHROPIC_API_KEY` | `anthropic-api-key` |

When `AZURE_KEY_VAULT_URL` is set, the server tries Key Vault first, then falls back to env vars.

## 6. Volume Mounts

The server stores all project data under `VIZIER_ROOT`:

```
/data/vizier/
  projects/
    my-project/
      specs/           # Spec files (managed by spec_* tools)
      sentinel.yaml    # Sentinel security policy
      config.yaml      # Project configuration
```

In Docker Compose, this is a named volume (`vizier-data`). For production, consider:
- Bind mount to a persistent disk: `volumes: ["/opt/vizier-data:/data/vizier"]`
- Use a cloud-managed volume (EBS, Azure Disk, etc.)

## 7. CI/CD Pipeline

### Tests (`.github/workflows/tests.yml`)

Runs on every push and PR:
- Lint: `ruff check` + `ruff format --check`
- Tests: `pytest vizier-mcp/tests/`
- Type check: `pyright`

### Deploy (`.github/workflows/deploy.yml`)

Triggered after Tests workflow succeeds on master:
1. Builds Docker image and pushes to GHCR
2. SSHs to production server
3. Pulls image and runs `docker compose up -d`
4. Verifies health endpoint (30 retries, 2s interval)

### Publish (`.github/workflows/publish.yml`)

Manual or release-triggered PyPI publish for the `vizier-mcp` package.

## 8. Connecting to OpenClaw

OpenClaw runs as a co-located Docker container alongside vizier-mcp. It
connects to the MCP server via `docker exec` stdio transport. See
[OPENCLAW_SETUP.md](OPENCLAW_SETUP.md) for the standalone setup guide.

## 9. OpenClaw + Telegram Deployment

### Prerequisites

1. **Telegram bot token** from [@BotFather](https://t.me/BotFather):
   - Message @BotFather on Telegram
   - Send `/newbot` and follow the prompts
   - Copy the bot token (format: `123456:ABC-DEF...`)

2. **Anthropic API key** (already required for Sentinel)

### Configuration

Add the Telegram bot token to your server `.env`:

```bash
ssh vizier@your-server
cd /opt/vizier
echo "TELEGRAM_BOT_TOKEN=123456:ABC-DEF..." >> .env
```

### Deployment

The CI/CD pipeline deploys both containers automatically. On first deploy
with OpenClaw, ensure the `.env` file has `TELEGRAM_BOT_TOKEN` set before
running `docker compose up -d`.

```bash
# Verify both containers are running
docker compose ps

# Check vizier-mcp health
curl -s http://localhost:8080/health | python3 -m json.tool

# Check OpenClaw health
curl -s http://localhost:18789/ | python3 -m json.tool
```

### Telegram Pairing

OpenClaw uses pairing-based DM access for security. New users must pair
before they can interact with Vizier:

1. Find your bot in Telegram (search by the name you gave @BotFather)
2. Send `/start` to the bot
3. The bot replies with a time-limited pairing code
4. Approve the pairing on the server:
   ```bash
   docker exec openclaw openclaw approve-pairing <code>
   ```
5. After pairing, message the bot to interact with Vizier

A first-time setup script is provided:

```bash
bash scripts/openclaw-setup.sh
```

### Architecture

```
Telegram --> OpenClaw (port 18789) --docker exec--> vizier-mcp (port 8080)
                |                                        |
                v                                        v
         Agent sessions                           MCP tools (11)
         SOUL.md workspaces                       /data/vizier/projects/
```

- **OpenClaw** handles messaging, agent sessions, and tool routing
- **vizier-mcp** provides the 11 Vizier domain tools via MCP stdio
- OpenClaw connects via `docker exec -i vizier-mcp ...` (requires Docker socket)
- Agent workspace files (SOUL.md) are mounted read-only from `openclaw/workspaces/`

### Docker Socket Security

The OpenClaw container mounts `/var/run/docker.sock` to spawn MCP sessions
via `docker exec`. This gives it full Docker API access. For single-user
deployments this is acceptable. For hardening:

- Use [docker-socket-proxy](https://github.com/Tecnativa/docker-socket-proxy) to restrict API access
- Restrict to `exec` operations only

### Troubleshooting

**OpenClaw container won't start:**
- Check `TELEGRAM_BOT_TOKEN` is set in `.env`
- Check logs: `docker compose logs openclaw`
- Verify vizier-mcp is healthy first (OpenClaw depends on it)

**Bot doesn't respond in Telegram:**
- Verify the bot token is correct: `docker compose logs openclaw | grep -i telegram`
- Check that pairing was completed: `docker exec openclaw openclaw list-pairings`
- Restart: `docker compose restart openclaw`

**MCP tools fail:**
- Check vizier-mcp is running: `curl http://localhost:8080/health`
- Test docker exec manually: `docker exec -i vizier-mcp uv run --directory vizier-mcp python -m vizier_mcp.server`
- Check Docker socket is mounted: `docker exec openclaw ls /var/run/docker.sock`

## Troubleshooting

**Health check fails:**
- Check container logs: `docker compose logs vizier-mcp`
- Verify port 8080 is exposed: `docker compose ps`
- Ensure `HEALTH_PORT` is set (auto-enabled in Docker)

**"No such secret" from Key Vault:**
- Check secret name mapping (see Section 5)
- Verify Managed Identity has `Get` permission on the Key Vault

**Container exits immediately:**
- Check `VIZIER_ROOT` directory exists and is writable
- Verify `ANTHROPIC_API_KEY` is set (check `.env` file)
