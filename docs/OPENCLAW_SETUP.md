# Connecting Vizier MCP Server to OpenClaw

This guide covers how to connect the Vizier MCP server to an OpenClaw gateway
so that agents (Vizier, Pasha, Worker, Quality Gate) can use the 21 tools.

## Prerequisites

- Python 3.11+ with uv installed
- OpenClaw gateway configured and running
- Anthropic API key (for Sentinel Haiku evaluator)

## 1. Install the MCP Server

```bash
cd vizier-mcp
uv sync
```

## 2. Configure the Vizier Root Directory

The MCP server needs a root directory for project data:

```bash
mkdir -p /path/to/vizier-root/projects
export VIZIER_ROOT=/path/to/vizier-root
```

Directory structure:

```
vizier-root/
  projects/
    my-project/
      specs/           # Spec files (managed by spec_* tools)
      sentinel.yaml    # Sentinel security policy
      config.yaml      # Project configuration (optional)
```

## 3. Create a Project

Create a project directory with a Sentinel policy:

```bash
mkdir -p /path/to/vizier-root/projects/my-project/specs

cat > /path/to/vizier-root/projects/my-project/sentinel.yaml << 'EOF'
write_set:
  - "src/**/*.py"
  - "tests/**/*.py"
  - "docs/**/*.md"

command_allowlist:
  - "pytest"
  - "ruff check"
  - "ruff format"
  - "pyright"
  - "echo"

command_denylist:
  - pattern: "rm\\s+-rf"
    reason: "Destructive command"
  - "sudo"

role_permissions:
  worker:
    can_write: true
    can_bash: true
    can_read: true
  quality_gate:
    can_write: false
    can_bash: true
    can_read: true
EOF
```

Optionally add a project config:

```bash
cat > /path/to/vizier-root/projects/my-project/config.yaml << 'EOF'
type: software
language: python
framework: fastapi
test_command: pytest
lint_command: ruff check .
type_command: pyright
settings:
  max_retries: 3
EOF
```

## 4. Configure OpenClaw

OpenClaw does not natively support `mcpServers` as a config key (see D84). Instead,
use the [`openclaw-mcp-adapter`](https://github.com/androidStern-personal/openclaw-mcp-adapter)
plugin, which connects to MCP servers and registers their tools as native OpenClaw agent tools.

### Install the adapter plugin

```bash
npx openclaw plugins install mcp-adapter
```

### Add plugin config to `openclaw/config/openclaw.json`

```json
{
  "plugins": {
    "entries": {
      "mcp-adapter": {
        "enabled": true,
        "config": {
          "toolPrefix": true,
          "servers": [
            {
              "name": "vizier",
              "transport": "http",
              "url": "http://vizier-mcp:8001/mcp"
            }
          ]
        }
      }
    }
  }
}
```

With `toolPrefix: true`, tools appear as `vizier_spec_create`, `vizier_budget_summary`, etc.

### Transport options

The Vizier MCP server supports two transports controlled by the `MCP_TRANSPORT` env var:

| Transport | Env var value | Use case |
|-----------|--------------|----------|
| stdio | `stdio` (default) | Local development, testing |
| Streamable HTTP | `streamable-http` | Docker deployment (default in Dockerfile) |

For HTTP transport, `MCP_PORT` (default: `8001`) controls the listen port.

## 5. Run the MCP Server Standalone (for Testing)

```bash
# stdio transport (default)
cd vizier-mcp
VIZIER_ROOT=/path/to/vizier-root uv run python -m vizier_mcp

# HTTP transport
MCP_TRANSPORT=streamable-http MCP_PORT=8001 VIZIER_ROOT=/path/to/vizier-root uv run python -m vizier_mcp
```

The server exposes 21 tools via the configured transport.

## 6. Agent-to-Tool Mapping

Each agent role uses a specific subset of the 21 tools:

| Tool | Vizier | Pasha | Worker | QG |
|------|--------|-------|--------|-----|
| spec_create | x | | | |
| spec_read | x | x | x | x |
| spec_list | x | x | | |
| spec_transition | | x | x | x |
| spec_update | | x | | |
| spec_write_feedback | | | | x |
| sentinel_check_write | | | x | |
| run_command_checked | | | x | x |
| web_fetch_checked | | | x | |
| orch_write_ping | | x | x | |
| project_get_config | x | x | x | x |
| secret_check | x | x | | |
| system_get_logs | x | x | | |
| system_get_errors | x | x | | |
| system_get_status | x | | | |
| spec_analytics | x | x | | |
| budget_record | | x | x | |
| budget_summary | x | x | | |
| learnings_extract | | x | | |
| learnings_list | x | x | | |
| learnings_inject | | x | | |

## 7. Smoke Test (Manual)

After connecting the MCP server to OpenClaw, verify the tool contract:

1. **Vizier creates a spec:**
   ```
   spec_create(project_id="my-project", title="Test Spec", description="Verify MCP connection")
   ```
   Expected: Returns `{"spec_id": "001-test-spec", "path": "..."}`

2. **Pasha promotes the spec:**
   ```
   spec_transition(project_id="my-project", spec_id="001-test-spec", new_status="READY", agent_role="pasha")
   ```
   Expected: Returns `{"success": true, ...}`

3. **Worker claims and implements:**
   ```
   spec_transition(project_id="my-project", spec_id="001-test-spec", new_status="IN_PROGRESS", agent_role="worker")
   run_command_checked(project_id="my-project", command="echo hello", agent_role="worker")
   spec_transition(project_id="my-project", spec_id="001-test-spec", new_status="REVIEW", agent_role="worker")
   ```

4. **Quality Gate reviews:**
   ```
   spec_read(project_id="my-project", spec_id="001-test-spec")
   spec_write_feedback(project_id="my-project", spec_id="001-test-spec", verdict="ACCEPT", feedback="All criteria met")
   spec_transition(project_id="my-project", spec_id="001-test-spec", new_status="DONE", agent_role="quality_gate")
   ```

5. **Verify final state:**
   ```
   spec_read(project_id="my-project", spec_id="001-test-spec")
   ```
   Expected: `status == "DONE"`

## 8. SOUL.md Workspace Setup

Agent SOUL.md files are in `openclaw/workspaces/`:

```
openclaw/workspaces/
  vizier/SOUL.md            # Persistent session, Opus
  pasha-template/SOUL.md    # Persistent sub-session per project, Opus
  worker-template/SOUL.md   # Spawned per spec, Sonnet
  quality-gate-template/SOUL.md  # Spawned per review, Sonnet
```

These files are the system prompts for each agent role. They define:
- Role identity and responsibilities
- Process workflow (what tools to call and when)
- Escalation rules (One Voice Policy)
- Error handling and retry behavior

## Troubleshooting

**"Spec not found" errors:** Check that `VIZIER_ROOT` points to the correct directory
and the project exists under `projects/`.

**"Command denied" errors:** Check `sentinel.yaml` in the project directory. The
`command_allowlist` must include the command prefix.

**"Write not allowed" errors:** Check `write_set` patterns in `sentinel.yaml`.
Workers can only write to paths matching the glob patterns.

**"Invalid transition" errors:** Check the spec's current status. See the state
machine in `docs/ARCHITECTURE.md` section 10 for valid transitions.
