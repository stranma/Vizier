# PRD: Vizier v2 MVP -- Container-First, Modular Agents

## Vision

A modular autonomous development system where Sultan (human) chats via Telegram with Vizier (CEO) and optionally directly with Pashas. Vizier manages the realm -- creates projects, provisions safe containerized environments, and delegates work. Pashas live inside containers and are modular/swappable.

## Core Concepts

### Realm
Everything Vizier manages:

- **Project**: A code repository inside a devcontainer. Has acceptance criteria, PRs as output.
- **Knowledge Project**: A reference repository (docs, standards, patterns). Readable by other projects.

### Agents

| Agent | Where | Runtime | Role |
|-------|-------|---------|------|
| **Sultan** | Telegram + GitHub | Human | Approves PRs, gives direction. Can talk to Vizier or Pashas directly. |
| **Vizier** | Host | OpenClaw (persistent, Opus) | CEO/manager. Creates safe environments, delegates to Pashas, can kill agents. Reluctant to do hands-on work. Has broad server rights. |
| **Pasha** | Inside devcontainer | OpenClaw (per-project) | Project governor. Opinionated about practices. Clones repo on start. Spawns Workers via Agent SDK. Validates criteria. Produces PRs. Modular/swappable per template. |
| **Workers** | Inside devcontainer | Agent SDK (spawned by Pasha) | Expendable. Fresh context. Make code changes. Spawned by Pasha programmatically via Agent SDK. |

### How Agent Spawning Works

```
Vizier (OpenClaw, host)
  |
  | starts container + launches OpenClaw Pasha inside it
  v
Pasha (OpenClaw agent, inside container)
  |-- clones repo, reads project docs
  |-- uses Agent SDK (Python) to spawn Workers programmatically
  v
Worker (Agent SDK, same container)
  |-- makes code changes, runs tests, commits
```

**Key**: Pasha is an OpenClaw agent (same runtime as Vizier, just in a container). For spawning Workers, Pasha uses Agent SDK programmatically -- this gives fine-grained control over Worker context, tools, and cost limits.

### Key Properties

- **Vizier is powerful but managerial** -- broad server rights (create/destroy containers, manage realm, kill agents) but prefers to delegate. CEO, not engineer.
- **Sultan can talk to Pashas directly** -- through Telegram. Not everything goes through Vizier.
- **Pasha implementation is modular** -- defined by project template. Default for Python: `stranma/claude-code-python-template` pattern.
- **Pasha runs INSIDE the container** -- same security boundary as Workers. Reads DECISIONS.md, ARCHITECTURE.md to stay informed.

### Work Unit: PR (not Spec)
Output is a **Pull Request**. Like `stranma/claude-code-python-template`:
- Pasha defines what needs to change (acceptance criteria)
- Workers make changes in branches
- Pasha validates the changes
- Result: PR ready for Sultan review on GitHub (not in Telegram)
- Sultan approves/merges on GitHub

## Architecture

```
Sultan (Telegram + GitHub)
  |
  +---> Vizier (OpenClaw, host-level, persistent)
  |       |-- manages realm (projects + knowledge)
  |       |-- creates/destroys containers (docker/devcontainer CLI)
  |       |-- launches OpenClaw Pasha inside containers
  |       |-- can kill agents (docker stop/kill)
  |       |-- calls MCP tools for realm state
  |       |-- tracks realm state via filesystem (realm.json + docker ps)
  |
  +---> Pasha (OpenClaw, inside devcontainer, per-project)
  |       |-- Sultan can talk to Pasha directly via Telegram
  |       |-- clones repo on start
  |       |-- reads project docs selectively
  |       |-- spawns Workers via Agent SDK (Python, programmatic)
  |       |-- validates acceptance criteria
  |       |-- creates PRs via gh CLI
  |       |-- has per-task cost limit (dead-man's switch)
  |       |
  |       +-- Worker (Agent SDK, same container)
  |             |-- makes code changes
  |             |-- runs tests
  |             |-- commits to branch
  |
  [devcontainer boundary: no sudo, firewall-restricted egress]
```

### Key Architectural Decisions

1. **OpenClaw everywhere, Agent SDK for Workers** -- Both Vizier (host) and Pasha (container) are OpenClaw agents. Same runtime, familiar patterns, SOUL.md for personality. Pasha uses Agent SDK (Python) to spawn Workers programmatically -- giving fine-grained control over context, tools, and cost.

2. **Pasha runs inside the container** -- Pasha is responsible for everything in the project: clones repo on start, reads docs, spawns workers, validates, creates PRs. Container is the security boundary for both Pasha and Workers.

3. **Modular Pasha** -- Pasha implementation is defined by the project template. Different project types can have different Pasha behaviors. First template: Python (following `stranma/claude-code-python-template`).

4. **Devcontainer = security boundary** -- No sudo. Firewall-restricted egress. Sultan pre-configures the image via Vizier.

5. **Filesystem + Git for project state** -- Projects are git repos. State is branches and PRs. Vizier tracks realm state via `realm.json` on host + `docker ps` queries.

6. **Sultan-Pasha direct line** -- Sultan can bypass Vizier and talk to a Pasha directly via Telegram.

7. **PR review on GitHub, not Telegram** -- Telegram is for steering and notifications. Code review on GitHub.

8. **Cost controls** -- Per-task cost limit on Pasha/Workers. Dead-man's switch. Vizier can kill agents.

## MCP Server Tools (v2 MVP)

### Realm Management
- `realm_list_projects()` -- List all projects and knowledge projects
- `realm_create_project(id, type, git_url?, template?)` -- Initialize a project or knowledge project
- `realm_get_project(id)` -- Get project config, status, recent PRs

### Container Lifecycle
- `container_start(project_id)` -- Build and start project devcontainer
- `container_stop(project_id)` -- Stop container
- `container_status(project_id)` -- Check container state

### Agent Control (Vizier-level)
- `pasha_launch(project_id, task, acceptance_criteria, cost_limit?)` -- Launch Pasha process in container with task
- `pasha_status(project_id)` -- Check Pasha status (running, idle, cost spent)
- `agent_kill(project_id)` -- Kill all agents in a project container
- `knowledge_link(project_id, knowledge_project_id)` -- Link a knowledge project

**Total: ~10 tools.**

## Gemini Critique: Addressed

| Critique | Response |
|----------|----------|
| **Telegram bad for code review** | Agreed. PR review on GitHub. Telegram for notifications + steering only. |
| **Git as message bus / polling** | Vizier tracks state via `realm.json` + `docker ps`. No git polling. Pasha works synchronously inside container. |
| **Budget dropped** | Re-added. `cost_limit` param on `pasha_launch`. Dead-man's switch. Vizier `agent_kill` as emergency stop. |
| **CLI headless issues** | Pasha uses Agent SDK programmatically to spawn Workers. No raw CLI invocation. |
| **Context bloat from reading docs** | Pasha reads selectively, not whole files. Workers get minimal context per task. |

## What We Keep from v1

### Code to preserve
- **Health endpoints** (`health.py`)
- **Structured logging** (`logging_structured.py`)
- **FastMCP server factory** pattern from `server.py`
- **Docker infrastructure** -- Dockerfile, docker-compose.yml patterns
- **Devcontainer + firewall** -- init-firewall.sh
- **OpenClaw integration** -- Vizier is an OpenClaw agent
- **SOUL.md files** -- agent personality/rules

### Code to drop
- Spec lifecycle tools (PRs replace specs)
- Sentinel subsystem (container boundary replaces it)
- Observability, budget, learnings, trace tools (add back when needed)
- All 88 decisions (start fresh, reference v1 where relevant)

## MVP Scope -- Focus: Vizier + Dockerization

### Phase 1: Foundation (NOW)
**Goal: Vizier can create safe containerized environments for templated Python projects.**

- MCP server with realm + container tools (~10 tools)
- Project creation from template (Python first, `stranma/claude-code-python-template` pattern)
- Container start/stop/status (devcontainer CLI)
- Firewall/security setup in containers (init-firewall.sh)
- Health endpoints
- Tests + CI

### Phase 2: Vizier Agent
- Vizier as OpenClaw agent (persistent, Opus)
- Vizier SOUL.md (managerial personality)
- Telegram integration (Sultan <-> Vizier)
- Agent control tools (launch, kill, status)
- `realm.json` state tracking

### Phase 3: Pasha + Workers
- Pasha as OpenClaw agent inside container (clones repo on start)
- Python Pasha template (default: `stranma/claude-code-python-template`)
- Worker spawning via Agent SDK (Python, programmatic)
- Sultan <-> Pasha direct Telegram channel
- Cost limits + dead-man's switch
- Acceptance criteria validation
- PR creation via `gh` CLI

### Phase 4: Knowledge + Linking
- Knowledge projects
- Cross-project linking
- Read-only volume mounts for knowledge repos

## Open Questions

1. **Telegram routing**: How does Sultan choose Vizier vs Pasha? Separate bot per project? Command prefix? Conversation threading?
2. **Pasha template format**: CLAUDE.md + agents/ directory? Python entrypoint? How does Vizier know how to launch it?
3. **Knowledge project access**: Read-only volume mounts?
4. **Pasha-Vizier communication**: How does Pasha report back to Vizier? Write status file? Webhook? Or Vizier just checks `docker ps` + git state?
5. **Container runtime requirements**: OpenClaw (for Pasha) + Agent SDK pip package (for Workers) + `ANTHROPIC_API_KEY`. How to inject API key securely?

## Verification

Phase 1 verification:
1. Create a Python project from template
2. Start its devcontainer
3. Verify container has firewall, no sudo, correct tools
4. Stop container
5. List projects shows the new project
6. `realm.json` is consistent with actual state
