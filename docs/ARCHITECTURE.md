# Vizier Architecture

## Overview

Vizier is an autonomous multi-agent work system. It receives high-level tasks from humans, decomposes them into actionable specs, executes them through specialized agents, and reports back. It operates on a server, works on multiple projects in parallel, and communicates with humans through a EA agent.

The system is **project-type agnostic**. The orchestration loop is identical regardless of whether the project is software development, financial modeling, or document production. What varies per project type is implemented through a **plugin system** — Python packages that provide domain-specific Worker, Quality Gate, and Architect behaviors.

## Core Principles

1. **Fresh context per task** — agents start clean, read state from disk, do one thing, exit (Ralph Wiggum pattern)
2. **Filesystem is the message bus** — all inter-agent communication happens through files, not in-memory queues
3. **Specs are the contract** — the source of truth is always on disk, never in agent memory
4. **Human approval at boundaries** — EA handles all human communication; agents don't reach out independently
5. **Meta-improvement** — the system learns from failures and updates its own process
6. **Plugin extensibility** — new project types are Python packages, not framework changes

## System Topology

```
HUMAN (CEO/CTO)
  |
  |  Telegram / Slack / CLI
  |
EA / VIZIER (singleton, always-on — monolithic Opus-tier agent, Claude Code pattern)
  |  - Receives tasks, routes to projects
  |  - Aggregates progress, reports to human
  |  - Translates business language -> spec seeds
  |  - Manages commitments, calendar, relationships
  |  - Proactive: briefings, deadline warnings, risk escalation
  |  - Facilitates direct Pasha sessions
  |  - File checkout/checkin, cross-project coordination
  |
  +-- PROJECT A (plugin: software) ----------------------
  |   |
  |   PASHA (orchestration, event-driven)
  |   |  - Owns project lifecycle
  |   |  - Delegates to Architect
  |   |  - Writes progress reports
  |   |  - Escalates blockers to EA
  |   |
  |   ARCHITECT (decomposition, strongest model)
  |   |  - Reads codebase / project context
  |   |  - Uses plugin's decomposition patterns
  |   |  - Writes detailed specs with acceptance criteria
  |   |  - References plugin's criteria library
  |   |
  |   WORKER (plugin: SoftwareCoder)
  |   |  - Ralph-style: fresh context, one spec, exit
  |   |  - Tools restricted by plugin (bash, git, file ops)
  |   |  - Model tier set by spec complexity
  |   |
  |   QUALITY GATE (plugin: SoftwareQualityGate)
  |   |  - Runs Completion Protocol (PCC): hygiene → mechanical → tests → criteria → consistency
  |   |  - Deterministic passes first (no LLM), then LLM-assisted passes
  |   |  - Can REJECT back to Worker with feedback
  |   |
  |   RETROSPECTIVE (same inputs as Pasha)
  |      - Analyzes failures, stuck tasks, rejections
  |      - Updates learnings.md and agent prompts
  |      - Constrained: can change prompts/rules, not architecture
  |
  +-- PROJECT B (plugin: finance) -----------------------
  |   |
  |   PASHA -> ARCHITECT -> WORKER (FinanceModeler) -> QUALITY GATE (FinanceValidator)
  |   (same orchestration, different plugin)
  |
  +-- PROJECT C (plugin: documents) ---------------------
      |
      PASHA -> ARCHITECT -> WORKER (DocumentWriter) -> QUALITY GATE (DocumentReviewer)
      (same orchestration, different plugin)
```

## Plugin System

The plugin system is the primary extensibility mechanism. Each project type is a Python package that registers domain-specific agent implementations.

### Plugin Architecture

```
vizier-plugin-software/          # Separate Python package
  vizier_plugins/software/
    __init__.py                      # Plugin registration
    worker.py                        # SoftwareCoder(BaseWorker)
    quality_gate.py                  # SoftwareQualityGate(BaseQualityGate)
    architect_guide.py               # Decomposition patterns + criteria library
    tools.py                         # Domain-specific tool restrictions
    prompts/
      worker.md                      # Worker prompt template (Jinja2)
      quality_gate.md                # Quality Gate prompt template
      architect_guide.md             # Architect decomposition guide
    criteria/
      tests_pass.md                  # Reusable acceptance criteria
      lint_clean.md
      type_check.md
      no_debug_artifacts.md
```

### Plugin Interface (Python)

```python
from vizier.core.plugins import BasePlugin, BaseWorker, BaseQualityGate

class SoftwarePlugin(BasePlugin):
    name = "software"
    description = "Software development projects"

    worker_class = SoftwareCoder
    quality_gate_class = SoftwareQualityGate

    # Model tier defaults (overridable per-project)
    default_model_tiers = {
        "worker": "sonnet",
        "quality_gate": "sonnet",
        "architect": "opus",
    }

class SoftwareCoder(BaseWorker):
    """Worker that writes code, runs tests, commits."""

    allowed_tools = ["file_read", "file_write", "file_edit", "bash", "git", "glob", "grep"]

    tool_restrictions = {
        "bash": {
            "allowed_patterns": ["uv run pytest*", "uv run ruff*", "npm test*", "go test*"],
            "denied_patterns": ["rm -rf*", "curl*", "wget*"],
        }
    }

    git_strategy = "branch_per_spec"  # or "commit_to_main"
    commit_template = "feat({spec_id}): {summary}"

    def get_prompt(self, spec, context) -> str:
        """Render worker prompt from Jinja2 template with spec + context."""
        ...

class SoftwareQualityGate(BaseQualityGate):
    """Quality Gate that runs tests, lint, checks test meaningfulness."""

    automated_checks = [
        {"name": "tests", "command": "uv run pytest {spec_test_files} -v"},
        {"name": "lint", "command": "uv run ruff check {spec_files}"},
        {"name": "format", "command": "uv run ruff format --check {spec_files}"},
        {"name": "secrets", "command": "vizier scan-secrets {spec_files}"},
    ]

    def get_prompt(self, spec, diff, context) -> str:
        """Render quality gate prompt from Jinja2 template."""
        ...
```

### Plugin Discovery

Plugins are discovered via Python entry points:

```toml
# vizier-plugin-software/pyproject.toml
[project.entry-points."vizier.plugins"]
software = "vizier_plugins.software:SoftwarePlugin"
```

```toml
# vizier-plugin-finance/pyproject.toml
[project.entry-points."vizier.plugins"]
finance = "vizier_plugins.finance:FinancePlugin"
```

The core framework discovers all installed plugins at startup:

```python
from importlib.metadata import entry_points

def discover_plugins() -> dict[str, BasePlugin]:
    plugins = {}
    for ep in entry_points(group="vizier.plugins"):
        plugin_class = ep.load()
        plugins[ep.name] = plugin_class()
    return plugins
```

### Built-in Plugins (shipped with Vizier)

| Plugin | Package | Worker | Quality Gate |
|--------|---------|--------|-------------|
| `software` | `vizier-plugin-software` | `SoftwareCoder` | `SoftwareQualityGate` |
| `documents` | `vizier-plugin-documents` | `DocumentWriter` | `DocumentReviewer` |

### Third-party / Custom Plugins

Users can create project-specific plugins:

```toml
# my-project/pyproject.toml
[project.entry-points."vizier.plugins"]
my-domain = "my_project.vizier_plugin:MyPlugin"
```

Or install community plugins: `uv add vizier-plugin-finance`

### Per-project Plugin Selection

```yaml
# .vizier/config.yaml
plugin: software      # which plugin to use for this project

# Optional: override plugin defaults
model_tiers:
  worker: haiku       # this project is simple, use cheap model
  architect: opus     # keep architect strong

# Optional: additional tool restrictions
tool_restrictions:
  bash:
    denied_patterns:
      - "docker*"     # no docker in this project
```

## Deployment Model

### Components

| Component | What | Where |
|-----------|------|-------|
| **Vizier core** | Orchestration runtime, agent base classes, file protocol, CLI | `libs/core/` |
| **Vizier daemon** | Server process: project registry, agent lifecycle, EA | `apps/daemon/` |
| **Vizier CLI** | `vizier init`, `register`, `start`, `status` | `apps/cli/` |
| **Plugins** | Domain-specific Worker, Quality Gate, Architect behaviors | `plugins/software/`, `plugins/documents/`, or external packages |
| **`.vizier/` config** | Per-project: constitution, specs, learnings, config | Inside each project repo (committed to git) |
| **Workspaces** | Cloned project repos | Server filesystem |
| **Reports** | Cross-project progress files | Server filesystem (not in project repos) |

### Server Layout

```
/opt/vizier/
+-- src/                             # Vizier source (cloned from GitHub)
+-- venv/                            # Vizier's own environment
+-- config.yaml                      # API keys, server-wide settings (see config.example.yaml)
+-- .env                             # API keys and secrets (see .env.example)
+-- projects.yaml                    # Registered projects
|
+-- workspaces/                      # One clone per project
|   +-- project-alpha/               # git clone
|   |   +-- .vizier/              # Project-specific config (from repo)
|   |   |   +-- constitution.md      # Project principles (human-written)
|   |   |   +-- config.yaml          # Plugin selection, model overrides
|   |   |   +-- specs/               # Task specifications
|   |   |   +-- learnings.md         # Retrospective output
|   |   |   +-- state.json           # Runtime state (.gitignored)
|   |   +-- src/
|   |   +-- ...
|   +-- project-beta/
|       +-- ...
|
+-- reports/                         # EA watches this
|   +-- project-alpha/               # Pasha A writes here
|   |   +-- 2026-02-15-cycle-001.md
|   |   +-- status.json              # Current state summary
|   +-- project-beta/
|       +-- ...
|
+-- ea/                              # EA's own git repo (commitments, relationships)
|   +-- commitments/*.yaml
|   +-- relationships/*.yaml
|   +-- priorities.yaml
|   +-- sessions/
|
+-- security/                        # Sentinel data
|   +-- events.jsonl
|   +-- blocklist.yaml
|   +-- quarantine/
|
+-- checkout/                        # Sultan's file checkout area
```

### Daemon Architecture (D37)

The daemon is a single Python process running an asyncio event loop:

- **aiogram** (Telegram long polling, D36) runs on the event loop
- **watchdog** dispatches filesystem events to the event loop
- **Pasha** orchestration logic runs as async handlers on the event loop
- **Agent invocations** (Worker, Quality Gate, Architect) are launched as **separate Python subprocesses** for crash isolation
- **Concurrency** is limited by `asyncio.Semaphore(max_concurrent_agents)`
- **Agent communication** is through the filesystem (specs, reports) -- no IPC needed

### What gets committed to project repos

| File | In git? | Why |
|------|---------|-----|
| `.vizier/constitution.md` | Yes | Project principles are project knowledge |
| `.vizier/config.yaml` | Yes | Plugin selection and agent preferences |
| `.vizier/specs/**` | Yes | Work history is valuable |
| `.vizier/learnings.md` | Yes | Accumulated project knowledge |
| `.vizier/state.json` | No | Runtime state, server-specific |

## Model Routing

Rules-based, not agent-based. No LLM decides which LLM to call.

Default tiers (overridable per-plugin and per-project):

| Role | Default Model | Override Level |
|------|---------------|----------------|
| EA (Vizier) | Opus-class | Server config only |
| Pasha | Opus-class | Per-project config |
| Architect | Opus-class | Per-project config, per-plugin default |
| Worker | Sonnet-class | Per-project config, per-plugin default, per-spec complexity |
| Quality Gate | Sonnet-class | Per-project config, per-plugin default |
| Retrospective | Opus-class | Per-project config |

Resolution order: spec complexity > project config > plugin default > framework default.

The model router maps abstract tiers to concrete provider/model pairs:

```yaml
# /opt/vizier/config.yaml (server-wide)
providers:
  anthropic:
    api_key: ${ANTHROPIC_API_KEY}
  openai:
    api_key: ${OPENAI_API_KEY}

model_tiers:
  opus:    anthropic/claude-opus-4-6
  sonnet:  anthropic/claude-sonnet-4-5-20250929
  haiku:   anthropic/claude-haiku-4-5-20251001
```

## Event Model

All events are filesystem-based. No message queue infrastructure required. **Events are an optimization; the filesystem is the source of truth.** Periodic reconciliation (scan all specs, rebuild state from disk) ensures missed events don't cause stuck state.

| Event | Trigger | Mechanism |
|-------|---------|-----------|
| New spec created | Architect writes to `specs/` | Filesystem watch (`watchdog`) |
| Spec completed | Worker writes `DONE` status | Filesystem watch |
| Spec stuck | Worker exceeds retry limit | Filesystem watch on retry counter |
| Progress report | Pasha writes to `reports/` | Filesystem watch (EA) |
| Human message | Telegram/Slack incoming | EA's bot framework |
| Quality rejection | Quality Gate writes feedback | Filesystem watch |

## Communication Model — Three Layers

Vizier has three communication layers, matching how real executives work.

### Layer 1: EA (async, mobile — Telegram)

The Executive Assistant is the default, always-available interface. It handles:

- **Delegation**: "Build auth for project-alpha" -> EA creates DRAFT spec, routes to project
- **Status**: "How's everything?" -> EA reads status.json files, summarizes with risk assessment
- **Control**: "Stop work on project-beta auth" -> EA marks specs as cancelled
- **Briefings**: Proactive morning briefings, deadline warnings, follow-up reminders
- **Commitments**: Tracks promises, deadlines, correlates with project progress
- **Calendar**: Reads/writes calendar events, preps for meetings

EA is the gatekeeper of the human's attention. It decides what's worth reporting, when to suggest a working session, and when to let agents work silently.

### Layer 2: Pasha Session (sync, focused — CLI / desktop / dedicated chat)

For deep project discussions that require back-and-forth: spec design, architecture debates, trade-offs, project kickoff. The human connects directly to a project's Pasha.

- EA facilitates: "Let's work on project-alpha" -> EA opens a Pasha session
- Full project context loaded (constitution, specs, learnings, codebase)
- Extended conversation with Pasha (or Architect for technical depth)
- When session ends, Pasha writes a summary -> EA reads it for continuity
- EA holds non-urgent updates during active Pasha sessions

### Layer 3: Autonomous (no human involved)

Agents execute specs without human interaction. The human is only involved when:
- EA escalates a blocker
- EA warns about a deadline risk
- Retrospective proposes a process change for human approval

### EA's Real-World Model

EA maintains state beyond project specs:

**Commitments** (promises to people with deadlines):
```yaml
# data/commitments/board-deck.yaml
description: "Deliver board deck for Q1 review"
promised_to: "Board of Directors"
deadline: 2026-03-13
project: project-board-deck       # linked to Vizier project, or null for standalone
status: in_progress
```

**Relationships** (contacts and their context):
```yaml
# data/relationships/jan-novak.yaml
name: "Jan Novak"
role: "Potential partner"
open_commitments: ["commitment-002"]
last_contact: 2026-02-10
```

**Calendar** (via MCP server — Google Calendar / Outlook):
- Cross-references meetings with commitments and project status
- Prepares briefing materials before meetings

**Priorities** (derived from deadlines, commitments, project risk):
- EA continuously ranks what needs human attention
- Morning briefing = top priorities + risks + reminders

### EA Data Location

```
/opt/vizier/ea/
+-- commitments/*.yaml       # structured commitment tracking
+-- relationships/*.yaml     # contact + relationship state
+-- priorities.yaml          # current priority ranking (auto-updated)
+-- briefing-config.yaml     # schedule, channels, preferences
+-- sessions/                # Pasha session summaries
    +-- 2026-02-15-project-alpha.md
```

## Project Sync — Git Only

All project synchronization happens through git. No OneDrive, Syncthing, or cloud sync.

**Why:** Git provides atomic operations, history, conflict resolution, and works everywhere. Agents always operate on server-side clones. Sultan interacts through agents (Telegram, CLI, Claude Code), not by editing files on the server directly.

### File Checkout/Checkin (for direct Sultan edits)

When Sultan needs to edit a file directly (e.g., an Excel spreadsheet):

```
Sultan: "I need to edit the business plan"
EA: git pulls latest, copies file to ~/vizier-checkout/efm/business-plan_v5.xlsx
Sultan: edits file locally (Excel, whatever tool)
Sultan: "Done editing" (or drops the file back via Telegram)
EA: copies back to project workspace, commits, pushes
```

```
/opt/vizier/checkout/                   # Sultan's working area
+-- <project>/                          # One folder per project
    +-- <filename>                      # Checked-out files only
```

**Rules:**
- Only EA manages the checkout folder (copy out, copy back, cleanup)
- Only one checkout per file at a time (EA tracks in `ea/checkouts.yaml`)
- EA warns if a checked-out file is stale (project moved ahead)
- Agents do NOT write to checkout/ — it's Sultan's space

### Sync Flow

```
Sultan's machine                    Vizier server                   GitHub
      |                                  |                             |
      | (Telegram: "build auth")         |                             |
      +--------------------------------->|                             |
      |                            EA creates DRAFT spec               |
      |                            Pasha -> Architect -> Worker         |
      |                            Worker commits to branch            |
      |                                  +--- git push --------------->|
      |                                  |                             |
      |                            Quality Gate -> DONE                |
      |                            Pasha creates PR                    |
      |                                  +--- gh pr create ----------->|
      |                                  |                             |
      | (Telegram: "PR #12 ready")       |                             |
      |<---------------------------------+                             |
```

## Roles and Permissions

Vizier uses the Ottoman court metaphor: **Sultan** (human), **Vizier** (EA), project staff (Pasha, Architect, Worker, Quality Gate), **Sentinel** (security).

### Permission Matrix

| Role | Read | Write | Special |
|---|---|---|---|
| **Sultan** | Everything | Everything | Approves dangerous operations |
| **EA (Vizier)** | All projects, all reports, ea/ data, calendar | ea/ data only (commitments, relationships, priorities, sessions, checkouts) + DRAFT specs in any project | Relays files from Sultan to Pashas. Cannot modify project source code. |
| **Pasha** | Own project (.vizier/, source, reports) | Own project (state.json, specs status) + own reports/ | Spawns Architect, Worker, QG within own project. Cannot read other projects. |
| **Architect** | Own project source (full) + plugin guides | Own project specs only (creates sub-specs) | Cannot modify source code. |
| **Worker** | Own project source (any file, read-only beyond artifact list) + learnings.md | Own project source (artifacts listed in spec only) | Tools restricted by plugin, enforced by Sentinel (allowlist + denylist + Haiku). Reads beyond artifact list are logged. |
| **Quality Gate** | Own project source + spec + git diff | Spec feedback only (feedback/*.md, status transitions) | Cannot modify source code. |
| **Retrospective** | Own project (all specs, feedback, learnings, reports) | learnings.md (direct) + proposals/*.md | Cannot change architecture, code, or agent topology. |
| **Sentinel** | All outbound requests, all inbound files, all git operations | Security reports, blocklists, quarantine/ | Can block operations. Reports to EA. |

### EA ↔ Pasha Communication (filesystem-based)

Pasha reports to EA through the reports/ directory — the filesystem IS the channel:

```
Pasha writes:                           EA watches:
  reports/<project>/status.json     --> watchdog event --> EA reads
  reports/<project>/cycle-NNN.md    --> watchdog event --> EA reads, decides: ignore / queue / alert
  reports/<project>/escalations/    --> watchdog event --> EA alerts Sultan immediately
```

EA writes to projects through specs:
```
EA creates:                             Pasha watches:
  .vizier/specs/NNN/spec.md (DRAFT) --> watchdog event --> Pasha delegates to Architect
```

No direct calls between EA and Pasha. The reports/ folder is Pasha→EA. The specs/ folder is EA→Pasha.

### Inbound File Relay

EA can receive files from Sultan (WhatsApp photo, document, voice note) and relay them to a project:

```
Sultan sends photo via Telegram
  → EA saves to /opt/vizier/inbox/<timestamp>-<filename>
  → EA asks: "Which project? What should I do with this?"
  → Sultan: "Add to project-alpha, it's the whiteboard from today's meeting"
  → EA creates DRAFT spec: "Process whiteboard photo" with file reference
  → Pasha picks it up
```

## Security — Sentinel

The Sentinel is a **deterministic Python service** (not an LLM agent) that enforces security policies. It uses a Haiku-tier LLM only for content scanning of untrusted sources.

### Architecture

```
Sentinel (Python service, always-on)
  |
  +-- Policy Engine (deterministic)
  |   +-- Whitelist/blocklist enforcement
  |   +-- Secret pattern scanning (regex)
  |   +-- GitHub Actions change detection
  |   +-- Permission enforcement (who writes where)
  |   +-- Git operation classification (safe/dangerous)
  |
  +-- Content Scanner (Haiku-tier, spawned on demand)
      +-- Evaluate untrusted web content for prompt injection
      +-- Evaluate inbound files from unknown sources
      +-- Classify fetched URLs (safe/suspicious/malicious)
```

### Security Policies

| Domain | Trusted (auto-allow) | Untrusted (scan first) | Blocked |
|---|---|---|---|
| **Web search** | docs.python.org, github.com, stackoverflow.com, pypi.org, official docs | Unknown domains → Content Scanner evaluates | Known malicious, ad networks, URL shorteners |
| **Inbound files** | From Sultan (any channel) | From unknown sources via integrations | Executable files (.exe, .sh, .bat) |
| **Git operations** | commit, push, branch, PR create | Force push, branch delete → Sultan approval | History rewrite on shared branches |
| **GitHub Actions** | Existing workflow runs | Workflow file changes (.github/) → Sultan approval | New workflow creation without Sultan |
| **Dependencies** | Existing locked deps | New deps in pyproject.toml/package.json → flag for review | Known vulnerable packages |
| **External APIs** | Configured providers (Anthropic, OpenAI, LiteLLM) | Unknown endpoints → block + report | Any endpoint not in allowlist |
| **Secrets** | None (never auto-allow) | Pre-commit scan → block if detected | API keys, tokens, passwords, private keys |

### Sentinel Reports

Sentinel writes security reports to EA:

```
/opt/vizier/security/
+-- events.jsonl                        # Append-only event log
+-- blocklist.yaml                      # Current blocked sources
+-- quarantine/                         # Suspicious files held for review
+-- reports/
    +-- YYYY-MM-DD-summary.md           # Daily security summary for EA
```

EA includes security highlights in morning briefings: "Sentinel blocked 3 suspicious URLs yesterday. No incidents."

### Sultan Approval Queue

Operations requiring Sultan approval go through EA:

```
Sentinel detects: Worker wants to modify .github/workflows/tests.yml
  → Sentinel blocks the operation
  → Sentinel writes to /opt/vizier/security/approvals/<id>.yaml
  → EA picks up the approval request
  → EA messages Sultan: "Worker wants to modify CI pipeline. Allow?"
  → Sultan: "Show me the diff" / "Allow" / "Deny"
  → EA writes decision back
  → Sentinel unblocks (or keeps blocked)
```

## Open Questions

None — all resolved.

### Resolved

- [x] **Cross-project dependencies**: Deferred to Phase 6 (EA). EA will coordinate cross-project tasks by creating linked DRAFT specs in each project. Mechanism designed during EA implementation.
- [x] **Plugin Architect behaviors**: Plugins provide all three — Worker + Quality Gate + Architect guide (decomposition patterns, criteria library). Already reflected in plugin architecture docs.
- [x] **Calendar MCP**: Both Google and Microsoft. workspace-mcp for Google Calendar (personal), Microsoft 365 MCP Server for Outlook (company). EA presents unified calendar view from both sources.
- [x] **EA data git repo**: Yes — EA data (commitments, relationships, sessions, priorities) lives in its own git repo for version history, auditability, and recovery. Location: `/opt/vizier/ea/` backed by a dedicated git repo.
- [x] **Sentinel's trusted domain list**: Global (server-wide), not per-project. Managed in `/opt/vizier/security/blocklist.yaml`.
- [x] **Sultan offline**: Operations requiring Sultan approval block until Sultan responds. No timeout, no auto-approve. Agents continue working on tasks that don't need approval.
- [x] **Cost budget**: Degrade + alert. At 80% budget → alert Sultan. At 100% → degrade all agents to cheapest tier. At 120% → pause non-critical work. Sultan can override.
- [x] **Testing strategy**: Mock `litellm.completion()` in all automated tests. No API credits burned in CI. Real LLM calls only during manual development. Core runtime (file protocol, state machine, watcher, router, Sentinel, logging) is pure Python — standard pytest.
- [x] **EA structure**: Monolithic, powerful, Opus-tier (D21). Not split into router + handlers.
- [x] **Pasha naming**: Per-project orchestrator renamed from "Manager" to "Pasha" (D16). Ottoman court metaphor extended selectively.
