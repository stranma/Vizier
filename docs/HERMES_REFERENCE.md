# Hermes Agent Reference

Reference for integrating Vizier with Hermes Agent by Nous Research.

## What Is Hermes

Hermes Agent is a self-improving AI agent framework by Nous Research (MIT license).
It provides agent runtime, session management, tool calling, sub-agent delegation,
messaging gateway (Telegram, Discord, Slack, WhatsApp), and MCP integration.

- **GitHub**: https://github.com/NousResearch/hermes-agent
- **Docs**: https://hermes-agent.nousresearch.com/docs

## Installation

One-line install (Linux/macOS/WSL2 only, no native Windows):

```bash
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash
```

Manual install:

```bash
git clone --recurse-submodules https://github.com/NousResearch/hermes-agent.git
cd hermes-agent
uv venv venv --python 3.11
export VIRTUAL_ENV="$(pwd)/venv"
uv pip install -e ".[all]"
uv pip install -e "./mini-swe-agent"
```

Post-install directories:

```
~/.hermes/
  config.yaml       # Primary config (YAML)
  .env              # Secrets / API keys
  auth.json         # OAuth credentials
  SOUL.md           # Agent personality
  memories/         # Persistent memory
  skills/           # Custom skills
  cron/             # Scheduled jobs
  sessions/         # Gateway sessions
  logs/             # Logs
```

Verify: `hermes doctor`, `hermes model`, `hermes chat -q "Hello!"`

## Authentication

Hermes supports subscription-based auth (preferred) and API key auth (fallback).

### Subscription Auth (Recommended)

Uses existing Claude Max/Pro or GitHub Copilot subscription. No API keys needed.

```bash
hermes login              # Anthropic (Claude Max/Pro) -- saves to ~/.hermes/auth.json
hermes login copilot      # GitHub Copilot (OpenAI models)
```

Credentials are saved to `~/.hermes/auth.json`. For Docker deployment, mount this
file into the container. See `docs/DEPLOYMENT.md` for details.

### API Key Auth

Set in `~/.hermes/.env`:

```bash
ANTHROPIC_API_KEY=sk-ant-...          # Anthropic direct
COPILOT_GITHUB_TOKEN=gho_...          # GitHub Copilot
```

### Vizier Docker Entrypoint Auth Logic

The entrypoint checks in order:
1. `auth.json` exists and is non-empty -> subscription auth
2. `ANTHROPIC_API_KEY` env var is set -> API key auth
3. Neither found -> fatal error with setup instructions

## Configuration (config.yaml)

Precedence: CLI args > config.yaml > .env > built-in defaults.

### Model Provider

```yaml
model:
  provider: "anthropic"
  default: "claude-opus-4-6"
  context_length: 200000

fallback_model:
  provider: openrouter
  model: anthropic/claude-sonnet-4
```

Anthropic auth methods:
1. `ANTHROPIC_API_KEY=sk-ant-...` in .env
2. `hermes model` interactive (prefers Claude Code credentials)
3. `ANTHROPIC_TOKEN=...` legacy

### Terminal Backend

```yaml
terminal:
  backend: "local"          # local | docker | ssh | singularity | modal | daytona
  cwd: "."
  timeout: 180
  # Docker-specific:
  docker_image: "nikolaik/python-nodejs:python3.11-nodejs20"
  docker_mount_cwd_to_workspace: false
  docker_forward_env: ["GITHUB_TOKEN"]
  docker_volumes: ["/host/path:/container/path"]
  container_cpu: 1
  container_memory: 5120
  container_disk: 51200
  container_persistent: true
```

### MCP Integration

```yaml
mcp_servers:
  # Stdio server (local subprocess):
  my_server:
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
    env:
      SOME_VAR: "value"
    tools:
      include: [tool_a, tool_b]   # whitelist (takes precedence)
      exclude: [tool_c]           # blacklist
      prompts: false              # disable prompt utilities
      resources: false            # disable resource utilities

  # HTTP server (remote):
  remote_api:
    url: "https://mcp.example.com"
    headers:
      Authorization: "Bearer ***"
    timeout: 30
    connect_timeout: 10
    enabled: true
```

Tool naming: `mcp_<server_name>_<tool_name>` (auto-prefixed).
Reload at runtime: `/reload-mcp`

### Messaging Gateway (Telegram)

```bash
hermes gateway setup       # Interactive wizard
hermes gateway install     # Install as system service
hermes gateway start/stop  # Manage service
```

Security: deny by default. Configure allowlists:
- `TELEGRAM_ALLOWED_USERS=123456789,987654321` in .env
- Or DM pairing: `hermes pairing approve telegram <code>`

Session config in `~/.hermes/gateway.json`.

### Delegation (Sub-agents)

```yaml
delegation:
  max_iterations: 50
  default_toolsets: [terminal, file, web]
  model: "google/gemini-3-flash-preview"
  provider: "openrouter"
```

### Agent Settings

```yaml
agent:
  max_turns: 90
  reasoning_effort: ""      # xhigh | high | medium | low | minimal | none

memory:
  memory_enabled: true
  user_profile_enabled: true
  memory_char_limit: 2200

compression:
  enabled: true
  threshold: 0.50
  summary_model: "google/gemini-3-flash-preview"
```

### Approval Mode

```yaml
approval_mode: "ask"        # ask | smart | off
# HERMES_YOLO_MODE=true     # skip all checks
```

Container backends (docker, singularity, modal, daytona) skip dangerous command
checks since the container IS the security boundary.

## Context Files

| File | Location | Purpose |
|------|----------|---------|
| **SOUL.md** | `~/.hermes/SOUL.md` | Agent personality/identity (slot #1 in system prompt) |
| **AGENTS.md** | Working directory (recursive) | Project instructions, conventions, architecture |
| **.cursorrules** | Working directory | Cursor IDE conventions (also loaded) |

- SOUL.md: max 20,000 chars, durable voice/personality, loaded from HERMES_HOME only
- AGENTS.md: max 20,000 chars per file, hierarchical (walks subdirectories), project-specific
- Both scanned for prompt injection before inclusion

## CLI Commands

| Command | Purpose |
|---------|---------|
| `hermes chat` | Interactive or one-shot conversation |
| `hermes chat -q "..."` | Non-interactive single query |
| `hermes model` | Select provider/model |
| `hermes gateway` | Run messaging gateway |
| `hermes gateway setup` | Configure messaging platforms |
| `hermes setup` | Full configuration wizard |
| `hermes config set KEY VAL` | Set config value |
| `hermes config check` | Validate config |
| `hermes doctor` | Diagnose issues |
| `hermes tools` | Configure tools/toolsets |
| `hermes pairing approve <platform> <code>` | Approve DM access |
| `hermes sessions list` | List sessions |
| `hermes cron list/create/edit` | Manage scheduled jobs |
| `hermes skills browse/install` | Manage skills |
| `hermes status` | Show agent status |

## Built-in Tools

- **Web**: web_search, web_extract
- **Terminal/Files**: terminal, process, read_file, patch
- **Browser**: browser_navigate, browser_snapshot, browser_vision
- **Media**: vision_analyze, image_generate, text_to_speech
- **Orchestration**: todo, clarify, execute_code, delegate_task
- **Memory**: memory, session_search, honcho_*
- **Automation**: cronjob, send_message

## Security Model (5 Layers)

1. User authorization (gateway allowlists + DM pairing)
2. Dangerous command approval (pattern matching + LLM classification)
3. Container isolation (Docker --cap-drop ALL, no-new-privileges, PID limits)
4. MCP credential filtering (only safe env vars forwarded)
5. Context file scanning (prompt injection detection)

## Key Differences from OpenClaw

| Aspect | OpenClaw | Hermes |
|--------|----------|--------|
| Agent definition | openclaw.json + SOUL.md in workspace | config.yaml + SOUL.md in ~/.hermes/ |
| Project context | Workspace SOUL.md per agent | AGENTS.md (hierarchical, recursive) |
| MCP integration | mcp-adapter plugin | Native mcp_servers config |
| Messaging | Built-in Telegram channel | Gateway service (Telegram, Discord, Slack, ...) |
| Model config | openclaw.json model field | config.yaml model section |
| Sub-agents | Sub-sessions | delegate_task tool |
| Terminal | Built-in workspace | Configurable backends (local, Docker, SSH, ...) |
| Auth | Built-in | ANTHROPIC_API_KEY or OAuth |
