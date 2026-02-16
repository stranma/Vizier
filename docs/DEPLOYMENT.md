# Vizier Deployment Guide

## Server Requirements

- **OS:** Ubuntu 22.04+ or Debian 12+
- **CPU:** 2+ cores (4 recommended for multiple projects)
- **RAM:** 4 GB minimum (8 GB recommended)
- **Disk:** 20 GB+ for workspaces, reports, and logs
- **Docker:** 24+ with Compose plugin

## Quick Start (Docker)

### 1. Install Docker

```bash
# Install Docker Engine (https://docs.docker.com/engine/install/)
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker vizier
```

### 2. Create Config Directory

```bash
sudo mkdir -p /opt/vizier/config
```

### 3. Configure API Keys

```bash
sudo nano /opt/vizier/config/.env
```

Required keys:
- `ANTHROPIC_API_KEY` - for Opus/Sonnet/Haiku agents
- `TELEGRAM_BOT_TOKEN` - for Sultan communication
- `TELEGRAM_ALLOWED_USER_IDS` - comma-separated Telegram user IDs

Optional Azure Key Vault keys (for secret store backend):
- `AZURE_TENANT_ID`
- `AZURE_CLIENT_ID`
- `AZURE_CLIENT_SECRET`

### 4. Create config.yaml

```bash
sudo nano /opt/vizier/config/config.yaml
```

See [Configuration](#configyaml) below for the full schema.

### 5. Create projects.yaml

```bash
# Start with an empty registry (or copy from a previous install)
echo "projects: []" | sudo tee /opt/vizier/config/projects.yaml
```

### 6. Start the Daemon

```bash
cd /opt/vizier
docker compose up -d
```

### 7. Register Projects

```bash
docker exec vizier-daemon uv run vizier register myproject \
    --repo https://github.com/org/myproject.git \
    --root /opt/vizier
```

### 8. Verify

```bash
curl http://localhost:8080/health
```

## Volume Design

Docker Compose uses **bind mounts** for config files (editable from the host) and **named volumes** for runtime data (managed by Docker).

### Bind Mounts (host -> container)

| Host Path | Container Path | Mode | Purpose |
|-----------|---------------|------|---------|
| `/opt/vizier/config/config.yaml` | `/opt/vizier/config.yaml` | read-only | Daemon configuration |
| `/opt/vizier/config/projects.yaml` | `/opt/vizier/projects.yaml` | read-write | Project registry (daemon updates this) |
| `/opt/vizier/config/.env` | env_file | -- | API keys and secrets |

### Named Volumes

| Volume | Container Path | Purpose |
|--------|---------------|---------|
| `vizier-workspaces` | `/opt/vizier/workspaces` | Cloned project repos |
| `vizier-reports` | `/opt/vizier/reports` | Status reports |
| `vizier-ea` | `/opt/vizier/ea` | EA data (commitments, relationships, priorities) |
| `vizier-security` | `/opt/vizier/security` | Security audit logs |
| `vizier-logs` | `/opt/vizier/logs` | Rotated agent logs |

### Why This Design

The original `docker-compose.yml` used a `vizier-config` named volume mounted at `/opt/vizier`, which overlaid the entire directory. On first run, the volume was empty -- config files didn't exist, and the daemon exited immediately. Bind mounts for config files solve this: they reference real files on the host, while named volumes handle runtime data that doesn't need host-side editing.

## Directory Structure

```
/opt/vizier/                     # On the host
├── config/                      # Bind-mounted config files
│   ├── config.yaml
│   ├── projects.yaml
│   └── .env
└── docker-compose.yml

/opt/vizier/                     # Inside the container
├── config.yaml          -> bind mount (read-only)
├── projects.yaml        -> bind mount (read-write)
├── heartbeat.json       # Written by daemon
├── vizier.pid           # PID file
├── workspaces/          -> named volume
├── reports/             -> named volume
├── ea/                  -> named volume
├── security/            -> named volume
└── logs/                -> named volume
```

## Configuration

### config.yaml

```yaml
vizier_root: /opt/vizier
workspaces_dir: workspaces
reports_dir: reports
ea_data_dir: ea
max_concurrent_agents: 5
reconciliation_interval_seconds: 15
heartbeat_path: heartbeat.json
monthly_budget_usd: 100.0
health_check_port: 8080

autonomy:
  stage: 1                    # 1=Shadow, 2=Gated, 3=Supervised, 4=Autonomous
  auto_approve_plugins: []

telegram:
  token: "${TELEGRAM_BOT_TOKEN}"
  allowed_user_ids: []
```

### Environment Variable Substitution

Config values can reference environment variables using `${VAR_NAME}` syntax:

```yaml
telegram:
  token: "${TELEGRAM_BOT_TOKEN}"
```

## Progressive Autonomy (D44)

Vizier uses a four-stage deployment model:

| Stage | Name | Behavior |
|-------|------|----------|
| 1 | Shadow | EA proposes actions but requires Sultan approval for everything |
| 2 | Gated | Specs require Sultan approval before Worker starts |
| 3 | Supervised | Workers run autonomously, Sultan reviews results |
| 4 | Autonomous | Full autonomy with budget and security guardrails |

Change stage in `config.yaml` or via EA:
```yaml
autonomy:
  stage: 2
```

Stage transitions are logged in `autonomy.stage_history` for auditability.

## Monitoring

### Health Check

The daemon exposes an HTTP endpoint:

```bash
curl http://localhost:8080/health
```

Returns JSON with daemon status, project count, and heartbeat info.

### Dead-Man Switch

The daemon writes `heartbeat.json` every reconciliation cycle (default: 15 seconds). The heartbeat monitor queries the HTTP health endpoint (works in both Docker and bare-metal):

```bash
# Check heartbeat (exit 0=OK, 1=stale, 2=unreachable)
bash scripts/check_heartbeat.sh http://localhost:8080/health 45
```

Add to crontab for continuous monitoring:

```bash
(crontab -l 2>/dev/null; echo "* * * * * /opt/vizier-repo/scripts/check_heartbeat.sh http://localhost:8080/health 45 >> /opt/vizier/logs/heartbeat-check.log 2>&1") | crontab -
```

### Logs

View daemon logs:
```bash
docker compose logs -f vizier-daemon
```

Agent logs are written to the `vizier-logs` volume at `agent-log.jsonl` with automatic rotation:
- Max size: 10 MB per file (configurable)
- Backup count: 5 files

To read agent logs directly:
```bash
docker exec vizier-daemon cat /opt/vizier/logs/agent-log.jsonl | python3 -m json.tool
```

## CD Pipeline

Continuous deployment is handled by `.github/workflows/deploy.yml`. On every successful test run against `master`, the workflow:

1. **Builds** the Docker image from the repo
2. **Pushes** to GitHub Container Registry (`ghcr.io/stranma/vizier`) with SHA and `latest` tags
3. **SSHes** into the production server
4. **Pulls** the new image and runs `docker compose up -d`
5. **Verifies** the health endpoint responds

### Required GitHub Secrets

| Secret | Description |
|--------|-------------|
| `DEPLOY_HOST` | Server IP or hostname |
| `DEPLOY_SSH_KEY` | SSH private key for the `vizier` user |

`GITHUB_TOKEN` is provided automatically by GitHub Actions for GHCR authentication.

### Setup

1. Generate an SSH keypair for deployment: `ssh-keygen -t ed25519 -f vizier-deploy`
2. Add the public key to `~vizier/.ssh/authorized_keys` on the server
3. Add `DEPLOY_HOST` and `DEPLOY_SSH_KEY` as repository secrets in GitHub Settings
4. Ensure Docker is installed on the server and `vizier` user is in the `docker` group

## Langfuse Observability (Optional)

Langfuse is available via Docker Compose profiles. It is **not** started by default:

```bash
# Start with Langfuse
docker compose --profile observability up -d

# Langfuse UI at http://localhost:3000
```

This starts:
- **langfuse** - LLM observability dashboard (port 3000)
- **langfuse-db** - PostgreSQL backend

## Migration from Bare-Metal

If you previously deployed Vizier via systemd and bare-metal Python, use the migration script:

```bash
bash scripts/migrate_to_docker.sh
```

The script:
1. Stops and disables the systemd `vizier` service
2. Copies `config.yaml`, `projects.yaml`, `.env` to `/opt/vizier/config/`
3. Removes stale Docker volumes from previous attempts
4. Pulls the Docker image from GHCR
5. Copies `docker-compose.yml` to `/opt/vizier/`
6. Starts the container
7. Verifies the health endpoint

## CLI Commands

| Command | Description |
|---------|-------------|
| `vizier init` | Initialize directory structure |
| `vizier register <name>` | Register a project |
| `vizier start` | Start the daemon |
| `vizier start --once` | Run a single cycle |
| `vizier stop` | Stop the daemon |
| `vizier status` | Show daemon and project status |
| `vizier spec create <desc>` | Create a spec |
| `vizier spec ready <id>` | Mark spec as READY |
| `vizier spec list` | List all specs |

In Docker, prefix CLI commands with `docker exec vizier-daemon`:
```bash
docker exec vizier-daemon uv run vizier status --root /opt/vizier
```

## Troubleshooting

### Daemon won't start
1. Check `.env` has valid API keys: `cat /opt/vizier/config/.env`
2. Check `projects.yaml` has active projects
3. Check logs: `docker compose logs vizier-daemon`

### Container exits immediately
1. Check if config files exist: `ls /opt/vizier/config/`
2. The entrypoint runs `vizier init` if `config.yaml` is missing, but `.env` must exist
3. Check for port conflicts: `ss -tlnp | grep 8080`

### Heartbeat stale
1. Check container is running: `docker ps`
2. Check health: `curl http://localhost:8080/health`
3. Check for errors: `docker compose logs --tail 50 vizier-daemon`
4. Restart: `docker compose restart vizier-daemon`

### Budget exceeded
1. Check spending: send `/budget` via Telegram
2. Override: Sultan can approve continued work via EA
3. Adjust budget in `config.yaml`
