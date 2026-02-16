# Vizier Deployment Guide

## Server Requirements

- **OS:** Ubuntu 22.04+ or Debian 12+
- **CPU:** 2+ cores (4 recommended for multiple projects)
- **RAM:** 4 GB minimum (8 GB recommended)
- **Disk:** 20 GB+ for workspaces, reports, and logs
- **Python:** 3.11+
- **Docker:** 24+ (optional, for containerized deployment)

## Quick Start

### 1. Install Dependencies

```bash
# Install uv (Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone Vizier
git clone https://github.com/your-org/vizier.git
cd vizier
uv sync --all-packages
```

### 2. Run Server Setup

```bash
sudo bash scripts/setup_server.sh
```

This creates:
- `/opt/vizier/` directory structure
- `vizier` system user
- Default `config.yaml`
- `.env` template
- systemd service (if available)

### 3. Configure API Keys

```bash
sudo nano /opt/vizier/.env
```

Required keys:
- `ANTHROPIC_API_KEY` - for Opus/Sonnet/Haiku agents
- `TELEGRAM_BOT_TOKEN` - for Sultan communication
- `TELEGRAM_ALLOWED_USER_IDS` - comma-separated Telegram user IDs

### 4. Register Projects

```bash
vizier register myproject --repo https://github.com/org/myproject.git --root /opt/vizier
```

### 5. Start the Daemon

```bash
# Direct
vizier start --root /opt/vizier

# Via systemd
sudo systemctl enable vizier
sudo systemctl start vizier
```

## Directory Structure

```
/opt/vizier/
├── config.yaml          # Daemon configuration
├── projects.yaml        # Registered projects
├── heartbeat.json       # Dead-man switch heartbeat
├── vizier.pid           # PID file (when running)
├── .env                 # API keys and secrets
├── workspaces/          # Cloned project repositories
│   ├── project-a/
│   └── project-b/
├── reports/             # Cross-project status reports
├── ea/                  # EA data (commitments, relationships, priorities)
│   ├── commitments/
│   ├── relationships/
│   └── priorities.yaml
├── security/            # Security audit logs
├── checkout/            # File checkout tracking
└── logs/                # Rotated agent logs
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

The daemon writes `heartbeat.json` every reconciliation cycle (default: 15 seconds).

Monitor with the included script:

```bash
# Check heartbeat (exit 0=OK, 1=stale, 2=missing)
bash scripts/check_heartbeat.sh /opt/vizier 45
```

Add to crontab for continuous monitoring:

```cron
* * * * * /opt/vizier-repo/scripts/check_heartbeat.sh /opt/vizier 45 >> /opt/vizier/logs/heartbeat-check.log 2>&1
```

To install:

```bash
(crontab -l 2>/dev/null; echo "* * * * * /opt/vizier-repo/scripts/check_heartbeat.sh /opt/vizier 45 >> /opt/vizier/logs/heartbeat-check.log 2>&1") | crontab -
```

For email alerting on staleness:

```cron
* * * * * /opt/vizier-repo/scripts/check_heartbeat.sh /opt/vizier 45 || echo "Vizier heartbeat stale" | mail -s "ALERT" admin@example.com
```

### Logs

Agent logs are written to `logs/agent-log.jsonl` with automatic rotation:
- Max size: 10 MB per file (configurable)
- Backup count: 5 files

View recent activity:
```bash
tail -f /opt/vizier/logs/agent-log.jsonl | python3 -m json.tool
```

## CD Pipeline

Continuous deployment is handled by `.github/workflows/deploy.yml`. On every successful test run against `master`, the workflow SSHes into the server and:

1. Pulls latest code (`git fetch origin master && git reset --hard origin/master`)
2. Syncs dependencies (`uv sync --all-packages --no-dev`)
3. Restarts the service (`systemctl restart vizier`)
4. Verifies the service is active (`systemctl is-active vizier`)

### Required GitHub Secrets

| Secret | Description |
|--------|-------------|
| `DEPLOY_HOST` | Server IP or hostname |
| `DEPLOY_SSH_KEY` | SSH private key for the `vizier` user |

### Setup

1. Generate an SSH keypair for deployment: `ssh-keygen -t ed25519 -f vizier-deploy`
2. Add the public key to `~vizier/.ssh/authorized_keys` on the server
3. Add `DEPLOY_HOST` and `DEPLOY_SSH_KEY` as repository secrets in GitHub Settings

## Docker Deployment

### Build and Run

```bash
# Copy .env from template
cp .env.example .env
# Edit with your API keys
nano .env

# Start all services
docker compose up -d
```

This starts:
- **vizier-daemon** - Main daemon process
- **langfuse** - LLM observability (port 3000)
- **langfuse-db** - PostgreSQL for Langfuse

### Volumes

| Volume | Purpose |
|--------|---------|
| `vizier-workspaces` | Cloned project repos |
| `vizier-reports` | Status reports |
| `vizier-ea` | EA data (commitments, relationships) |
| `vizier-security` | Security audit logs |
| `vizier-logs` | Agent logs |
| `vizier-config` | Config and registry files |
| `langfuse-pgdata` | Langfuse database |

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

## Troubleshooting

### Daemon won't start
1. Check `.env` has valid API keys
2. Check `projects.yaml` has active projects
3. Check logs: `journalctl -u vizier -f`

### Heartbeat stale
1. Check if process is running: `vizier status`
2. Check for errors in logs
3. Restart: `systemctl restart vizier`

### Budget exceeded
1. Check spending: send `/budget` via Telegram
2. Override: Sultan can approve continued work via EA
3. Adjust budget in `config.yaml`
