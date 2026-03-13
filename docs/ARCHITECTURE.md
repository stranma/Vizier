# Vizier v2 Architecture

## System Topology

```
Sultan (Telegram -- talks to both Vizier and Sentinel)
  |
  +---> Vizier (OpenClaw agent, host, persistent, Opus)
  |       |
  |       +---> SentinelGate (MCP proxy, deterministic)
  |               |
  |               +---> Vizier MCP Server (realm, containers, agents)
  |
  +---> Sentinel (OpenClaw agent, host, persistent)
          |-- reads SentinelGate audit log
          |-- LLM-based cost/data-leak reasoning
          |-- alerts Sultan on violations
          |-- can update SentinelGate policies
```

## Components

### Vizier MCP Server (`vizier-mcp/`)

FastMCP server exposing domain tools. Runs as a container with streamable-http transport (port 8001) and a health endpoint (port 8080).

**Tool groups (10 tools):**

| Group | Tools | Purpose |
|-------|-------|---------|
| Realm | `realm_list_projects`, `realm_create_project`, `realm_get_project` | Project CRUD in realm.json |
| Container | `container_start`, `container_stop`, `container_status` | Devcontainer lifecycle |
| Agent | `pasha_launch`, `pasha_status`, `agent_kill` | Manifest-based Pasha control |
| Knowledge | `knowledge_link` | Cross-project knowledge linking |

### RealmManager

Manages persistent state in `realm.json` with atomic file writes (`tempfile` + `os.replace`) and a threading lock. Stores project metadata, container status, and Pasha state.

### Pasha (per-project agent)

Pashas run inside devcontainers. Vizier does not control Pasha internals -- it interacts via a manifest contract:

```
.pasha/
  manifest.json    # Name, runtime, entrypoint, status_file, capabilities
  SOUL.md          # Pasha personality (template-provided)
  launch.sh        # Start script (template-provided)
  task.json        # Written by Vizier at launch time
  status.json      # Written by Pasha, polled by Vizier
```

Vizier reads the manifest, writes the task, executes the entrypoint, and polls status.

### SentinelGate (Phase 3)

Deterministic MCP proxy (Go binary) between Vizier and the MCP server. CEL-based policies for cost limits, rate limiting, and RBAC. Full audit log of all tool calls.

### Sentinel Agent (Phase 4)

OpenClaw agent that reads SentinelGate audit logs, evaluates cost reasonableness, detects data leak patterns, and alerts Sultan on violations. Can update SentinelGate policies dynamically.

## Data Flow

1. Sultan sends task to Vizier via Telegram
2. Vizier creates project (`realm_create_project`) and starts container (`container_start`)
3. Vizier launches Pasha (`pasha_launch`) with task + acceptance criteria
4. Vizier polls Pasha status (`pasha_status`) for progress
5. On completion/failure, Vizier reports to Sultan
6. SentinelGate logs all tool calls; Sentinel agent reviews for anomalies

## State Management

- **realm.json**: Single source of truth for all project/container/Pasha state
- **Atomic writes**: `tempfile` + `os.replace` under threading lock
- **Reconciliation**: Container and Pasha status reconciled against Docker on read

## Security Boundaries

- **Devcontainer**: Each project runs in an isolated container
- **SentinelGate**: All Vizier tool calls pass through deterministic policy checks
- **Docker socket**: Mounted read-write for container management; Vizier runs as non-root user in docker group
