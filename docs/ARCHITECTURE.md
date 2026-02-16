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
  |   |  - Delegates to Scout, then Architect
  |   |  - Writes progress reports
  |   |  - Escalates blockers to EA
  |   |
  |   SCOUT (research, sonnet-tier)
  |   |  - Researches prior art for DRAFT specs
  |   |  - Searches GitHub, PyPI, npm for existing solutions
  |   |  - Writes research.md report with recommendations
  |   |  - Deterministic triage: SKIP (bugfix/refactor) or RESEARCH (feature)
  |   |
  |   ARCHITECT (decomposition, strongest model)
  |   |  - Reads codebase / project context / research.md
  |   |  - Uses plugin's decomposition patterns
  |   |  - Writes detailed specs with acceptance criteria
  |   |  - References plugin's criteria library
  |   |  - Leverages Scout's findings (e.g., use existing library)
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

### Plugin MCP Exposure (D43)

Plugins can optionally expose lightweight capabilities as MCP tools via FastMCP. This allows the EA to handle quick queries ("are the tests passing?") without routing through the full spec lifecycle.

```python
class SoftwarePlugin(BasePlugin):
    def get_mcp_tools(self) -> list[MCPTool]:
        return [
            MCPTool(name="run_tests", description="Run project tests", handler=self._run_tests),
            MCPTool(name="lint_check", description="Check lint status", handler=self._lint_check),
            MCPTool(name="test_coverage", description="Get test coverage", handler=self._test_coverage),
        ]
```

**Discovery:** EA queries each registered project's plugin for MCP tools at startup. Tools are namespaced by project: `project-alpha.run_tests`.

**Constraints:**
- MCP tools are read-only by convention (they report status, not modify code)
- Complex work still goes through the spec lifecycle
- Sentinel applies the same tool-call enforcement to MCP tool invocations

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

### Dead-Man Switch

The daemon writes a `heartbeat.json` file on every reconciliation cycle (default: every 15 seconds):

```json
{
  "timestamp": "2026-02-15T10:30:15Z",
  "pid": 12345,
  "projects_active": 3,
  "agents_running": 2
}
```

An external monitor (cron job, systemd watchdog, or simple script) checks if `heartbeat.json` is stale (older than 3x the reconciliation interval). If stale, the monitor can:
1. Alert the Sultan via a backup channel (email, SMS)
2. Attempt daemon restart via systemd
3. Log the outage for post-mortem

This is deliberately external to the daemon -- if the daemon is frozen, it cannot monitor itself.

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
| Scout | Sonnet-class | Per-project config, per-plugin default |
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

All events are filesystem-based. No message queue infrastructure required. **Events are an optimization; the filesystem is the source of truth.** Periodic reconciliation (scan all specs, rebuild state from disk, default 15s interval) ensures missed events don't cause stuck state.

| Event | Trigger | Mechanism |
|-------|---------|-----------|
| New spec created | Architect writes to `specs/` | Filesystem watch (`watchdog`) |
| Spec completed | Worker writes `DONE` status | Filesystem watch |
| Spec stuck | Worker exceeds retry limit | Filesystem watch on retry counter |
| Progress report | Pasha writes to `reports/` | Filesystem watch (EA) |
| Human message | Telegram/Slack incoming | EA's bot framework |
| Quality rejection | Quality Gate writes feedback | Filesystem watch |

### Spec State-Age Monitoring

During each reconciliation cycle, Pasha checks `time_in_state` for every active spec (the difference between current time and the spec's `updated` timestamp). This detects silently stuck specs -- specs that remain in a state longer than expected without any event triggering escalation.

| State | Expected Duration | Action if Exceeded |
|-------|------------------|--------------------|
| IN_PROGRESS | Plugin-configurable (default: 30 min) | Log warning, check if agent subprocess is alive |
| REVIEW | Plugin-configurable (default: 15 min) | Log warning, verify Quality Gate was spawned |
| READY | Plugin-configurable (default: 60 min) | Queue starvation alert to EA |

State-age thresholds are configurable per-plugin because different domains have different expected durations (a software spec may take 10 minutes; a document spec may take 60 minutes).

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

### EA Prompt Assembly (D42)

The EA uses JIT (just-in-time) prompt assembly to keep context window usage efficient while maintaining the monolithic design (D21).

**Always loaded (~2,500 tokens):**
- Court context + EA identity preamble
- `priorities.yaml` content (current Sultan priorities)
- Active commitments summary (overdue + upcoming deadlines)
- Project registry + Pasha communication protocol
- Delegation + status instructions

**JIT modules (loaded by deterministic classifier based on incoming message):**
- Check-in protocol (~1,000 tokens) -- triggered by `/checkin`
- File checkout/checkin (~800 tokens) -- triggered by file-related keywords
- Calendar integration (~600 tokens) -- triggered by meeting/calendar keywords
- Cross-project coordination (~500 tokens) -- triggered by multi-project references
- Budget enforcement (~400 tokens) -- triggered by cost/budget keywords
- Morning briefing format (~500 tokens) -- triggered by scheduled briefing time
- Proactive behaviors (~500 tokens) -- triggered by scheduled proactive check

The classifier is deterministic (regex + keyword + slash command detection), not LLM-based. This means zero routing cost and consistent, testable behavior.

### Behavioral Anchor: priorities.yaml

The Sultan maintains a `priorities.yaml` file that EA reads on every LLM invocation. This provides a stable behavioral anchor -- the EA always knows the Sultan's current priorities, even across fresh LLM calls.

```yaml
# /opt/vizier/ea/priorities.yaml
current_focus: "Ship dashboard before board meeting Thursday"
priority_order:
  - project: project-alpha
    reason: "Board meeting demo, deadline March 13"
    urgency: critical
  - project: project-beta
    reason: "Client deliverable, flexible deadline"
    urgency: normal
standing_instructions:
  - "Always mention cost summary in morning briefings"
  - "Escalate anything blocking project-alpha immediately"
  - "Do not interrupt during focus mode unless emergency"
```

This file is Sultan-editable (via Telegram command `/priorities` or direct file edit) and EA-readable. It acts as the Sultan's standing orders to the Vizier.

### Telegram Slash Commands

EA supports structured slash commands for common operations:

| Command | Purpose | Example |
|---------|---------|---------|
| `/status` | Project status summary | `/status project-alpha` |
| `/ask` | Quick query to project Pasha | `/ask project-alpha what framework are we using?` |
| `/checkin` | Start structured check-in interview | `/checkin` |
| `/focus` | Enter focus mode (hold notifications) | `/focus 2h` |
| `/session` | Start deep Pasha session | `/session project-alpha` |
| `/approve` | Approve pending operation | `/approve spec-042` |
| `/budget` | View cost summary | `/budget` or `/budget project-alpha` |
| `/priorities` | View/edit priorities | `/priorities` |

Slash commands are handled by the JIT classifier and load the appropriate prompt module.

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

## Progressive Autonomy Rollout (D44)

Vizier deploys through four stages of increasing autonomy. Each stage has measurable graduation criteria and requires Sultan approval to advance.

| Stage | Name | EA Behavior | Worker Behavior |
|-------|------|-------------|-----------------|
| 1 | Shadow | Proposes all actions, Sultan approves | No Workers run |
| 2 | Gated | Creates specs, Sultan approves before Worker starts | Workers run after approval |
| 3 | Supervised | Autonomous execution, EA surfaces all completions | Full autonomous cycle |
| 4 | Autonomous | EA filters what to surface, full autonomy | Full autonomous cycle |

**Configuration:**

```yaml
# /opt/vizier/config.yaml
autonomy:
  stage: 2  # gated
  auto_approve_plugins: []  # empty = all need approval
  stage_history:
    - stage: 1
      entered: 2026-03-01
      graduated: 2026-03-15
      reason: "50 proposals, 2% override rate"
```

**Graduation criteria are measurable, not subjective:** Each stage has specific thresholds (proposal accuracy, spec completion rate, rejection rate, cost adherence) that must be met before the Sultan is asked about advancing.

## Observability

Vizier uses two complementary observability layers, each serving a different audience:

### Layer 1: Structured JSONL Logs (D28)

**Audience:** EA (for morning briefings), Sultan (via EA), Retrospective (for pattern analysis).

Every agent invocation produces a structured log entry appended to `reports/<project>/agent-log.jsonl`:

```json
{
  "timestamp": "2026-02-15T10:05:00Z",
  "agent": "worker",
  "spec_id": "001-auth/002-jwt",
  "model": "sonnet",
  "tokens_in": 4200,
  "tokens_out": 1800,
  "duration_ms": 12500,
  "cost_usd": 0.042,
  "result": "REVIEW",
  "project": "project-alpha"
}
```

This layer is always active and has zero external dependencies. EA uses it for cost summaries, budget enforcement (D33), and trend analysis in morning briefings.

### Layer 2: Langfuse Traces (D45)

**Audience:** Developer/Sultan debugging agent behavior.

Self-hosted Langfuse provides trace-level visibility: which prompt was sent, what the LLM returned, how long each step took, where failures occurred. Integrated via LiteLLM's native callback support:

```python
import litellm
litellm.success_callback = ["langfuse"]
litellm.failure_callback = ["langfuse"]
```

Langfuse runs as a Docker Compose service alongside the Vizier daemon. It is optional -- the system works fully without it (JSONL logs are the primary layer).

**Key capabilities:** Prompt versioning, per-trace cost breakdown, latency analysis, failure debugging, A/B comparison of prompt versions.

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
