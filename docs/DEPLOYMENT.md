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

## 3. Health Endpoint

The health endpoint is automatically enabled inside Docker (port 8080).

```
GET /health
```

Response:

```json
{
  "status": "ok",
  "version": "0.6.0",
  "tool_count": 11
}
```

The Docker healthcheck and deploy workflow both use this endpoint to verify the server is running.

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

After deployment, configure OpenClaw to connect to the running MCP server.
See [OPENCLAW_SETUP.md](OPENCLAW_SETUP.md) for the full guide.

For Docker deployments, OpenClaw spawns the MCP server process and
communicates over stdio (the same pattern as local development):

```json
{
  "mcp_servers": {
    "vizier": {
      "command": "docker",
      "args": ["exec", "-i", "vizier-mcp-vizier-mcp-1", "uv", "run", "--directory", "vizier-mcp", "python", "-m", "vizier_mcp.server"],
      "env": {
        "VIZIER_ROOT": "/data/vizier"
      }
    }
  }
}
```

Alternatively, if OpenClaw runs inside the same Docker Compose network, use
the `command`/`args` pattern from `docs/OPENCLAW_SETUP.md`.

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
