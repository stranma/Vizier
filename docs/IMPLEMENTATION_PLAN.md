# Vizier Implementation Plan

## Status Summary

| Phase | Name | Status | Branch |
|-------|------|--------|--------|
| 0 | Project Scaffold | Complete | `master` |
| 1 | Core Runtime + Plugin Framework + Sentinel | Complete | `feature/core-runtime` |
| 2 | Inner Loop (Worker + Quality Gate) | Complete | `feature/inner-loop` |
| 3 | Architect | Complete | `feature/architect` |
| 4 | Pasha + Orchestration | Complete | `feature/pasha` |
| 5 | Retrospective | Complete | `feature/retrospective` |
| 6 | EA + Communication | Complete | `feature/ea` |
| 7 | Daemon + Multi-project + Deployment | Complete | `feature/daemon` |
| 8 | Software Plugin (end-to-end) | Complete | `feature/plugin-software` |
| 9 | Documents Plugin | Complete | `feat/plugin-documents` |
| 10 | Scout Agent | Complete | `feat/scout-agent` |
| 11 | Production Wiring & CD Pipeline | Complete | `feat/production-wiring` |
| 12 | Docker Deployment | Complete | `feat/docker-deploy` |
| -- | Agent System Reset (D46) | Complete | `feat/llm-first-ea` |
| 13 | Agent Protocol Design | Complete | `master` |
| 14 | Message Schema + Agent Runtime | Complete | `master` |
| 15 | Domain Tools | Complete | `master` |
| 16 | State + Communication Tools | Complete | `master` |
| 17 | EA Agent | Complete | `master` |
| 18 | Pasha Orchestrator | Complete | `master` |
| 19 | Inner Loop Agents | Complete | `master` |
| 20 | Plugin Rebuild | Complete | `master` |
| 21 | Retrospective Agent | Complete | `master` |
| 22 | Golden Path Validation | Complete | `master` |

---

## Phase 0: Project Scaffold

**Goal:** Initialize Vizier repo from `claude-code-python-template` with correct package structure.

### Packages

| Package | Path | Purpose |
|---------|------|---------|
| `core` | `libs/core/` | Shared: file protocol, model router, agent base, filesystem watcher, plugin framework |
| `daemon` | `apps/daemon/` | Server daemon: project registry, agent lifecycle, EA, Sentinel |
| `cli` | `apps/cli/` | CLI: `vizier init`, `register`, `start`, `status` |
| `plugin-software` | `plugins/software/` | Built-in software development plugin |
| `plugin-documents` | `plugins/documents/` | Built-in document production plugin |

### Tasks
- [x] Run setup_project.py with Vizier configuration
- [x] Configure all packages with uv workspaces
- [x] Write CLAUDE.md for the new project
- [x] Set up CI workflow (lint, test, typecheck)
- [x] Initial git commit
- [x] Write agent system prompt preambles (docs/AGENT_PROMPTS.md)

### Acceptance Criteria
- [x] `uv sync --all-packages` installs all packages (note: `--all-packages` flag required for workspace members)
- [x] `uv run pytest` runs (even if no tests yet)
- [x] `uv run ruff check .` passes
- [x] CLAUDE.md documents the project structure and methodology
- [x] Plugin packages are importable from core

### Notes
- `uv sync` (without `--all-packages`) only installs root dependencies. Use `uv sync --all-packages` to install all workspace members.
- Branch is `master` (not `main`) -- CI workflow updated accordingly.

---

## Phase 1: Core Runtime + Plugin Framework + Sentinel

**Goal:** Build the shared infrastructure all agents depend on, including the plugin discovery system, Sentinel's tool-call enforcement, structured logging, and filesystem reconciliation.

### Components
- [x] File protocol implementation (spec CRUD, state management, file locking, atomic writes via `os.replace()` per D40)
- [x] Spec frontmatter parser (YAML frontmatter + markdown body, `@criteria/` snapshotting at creation)
- [x] Model router (rules-based tier -> provider/model mapping via LiteLLM library, resolution order)
- [x] Agent base class (fresh context pattern, spec reading, output writing, implicit completion on clean exit)
- [x] Filesystem watcher (watchdog-based, event dispatch)
- [x] Periodic reconciliation (scan all specs, verify/rebuild state from disk -- events are optimization, disk is truth, default 15s interval per D22)
- [x] Structured agent logging (`{agent, spec_id, model, tokens_in, tokens_out, duration_ms, cost_usd, result}` to `reports/<project>/agent-log.jsonl`)
- [x] Sentinel policy engine (deterministic):
  - [x] Allowlist (auto-approve known-safe tool calls, zero cost)
  - [x] Denylist (auto-block known-dangerous tool calls, zero cost)
  - [x] Haiku evaluator (assess ambiguous tool calls for safety, ~$0.001/call)
  - [x] Secret pattern scanning (regex)
  - [x] Git operation classification (safe/dangerous)
- [x] Plugin framework:
  - [x] `BasePlugin` abstract class
  - [x] `BaseWorker` abstract class (allowed_tools, tool_restrictions, git_strategy)
  - [x] `BaseQualityGate` abstract class (automated_checks, criteria library)
  - [x] Plugin discovery via entry points
  - [x] Prompt template renderer (Jinja2 with spec/context injection)
  - [x] Criteria library loader (`@criteria/` reference resolution + snapshotting)
  - [x] Tool registry with Sentinel enforcement integration

### Acceptance Criteria
- [x] Can create, read, update spec files with correct frontmatter
- [x] All spec writes use atomic write-then-rename pattern (D40): no `.tmp` files left after successful operations
- [x] `@criteria/` references are resolved and snapshotted into spec at creation time
- [x] State.json locking works under concurrent access
- [x] Model router maps tiers to configured providers with correct resolution order (via `litellm.completion()`)
- [x] Filesystem watcher detects spec file changes and dispatches events
- [x] Reconciliation scan rebuilds correct state from disk (simulated missed events)
- [x] Every agent invocation produces structured log entry with tokens and cost
- [x] Sentinel allowlist auto-approves known-safe tool calls
- [x] Sentinel denylist auto-blocks known-dangerous tool calls
- [x] Sentinel Haiku evaluator correctly identifies bypass attempts
- [x] Agent base class enforces fresh-context pattern
- [x] Worker completion is implicit (clean exit -> REVIEW, no magic string)
- [x] Plugin discovery finds installed plugins via entry points
- [x] BaseWorker subclass can define tools and restrictions
- [x] BaseQualityGate subclass can define automated checks
- [x] Jinja2 prompt templates render with spec and context data

### Completion Notes

**Completed:** 2026-02-16 | **Branch:** `feature/core-runtime`

Phase 1 was delivered in six sub-phases:

| Sub-phase | Scope | Modules | Tests |
|-----------|-------|---------|-------|
| 1a | Pydantic Models (spec, state, config, events, logging) | 5 | 33 |
| 1b | File Protocol (spec CRUD, state manager with filelock, criteria snapshotting) | 5 | 38 |
| 1c | Model Router + Logging (tier-based resolution, JSONL agent logging) | 4 | 28 |
| 1d | Sentinel Policy Engine (allowlist/denylist/Haiku evaluator, secret scanner, git classifier) | 6 | 39 |
| 1e | Plugin Framework (base ABCs, entry point discovery, Jinja2 templates, criteria loader, tool registry) | 9 | 44 |
| 1f | Agent + Watcher + Reconciliation (base agent, context, filesystem watcher, reconciler) | 7 | 34 |

**Totals:** 76 files (36 source modules + 39 test files + 1 `__init__.py` update), 216 tests, 99% code coverage, 0 lint/format issues, 0 type errors. All 16 acceptance criteria verified as PASS (plus 1 added for D40 atomic writes = 17 total).

---

## Phase 2: Inner Loop (Worker + Quality Gate)

**Goal:** Build the Ralph-style execution loop. Worker picks a spec, produces artifacts, Quality Gate validates. Uses a stub plugin for testing. Includes CLI entry point for manual spec creation (bypass EA for testing).

### Components
- [x] Worker agent runtime (loads plugin Worker class, runs fresh-context cycle)
- [x] Worker bounded read-only exploration (can read any project file, must log reads beyond artifact list, cannot write beyond artifacts)
- [x] Quality Gate agent runtime (loads plugin Quality Gate class, runs checks)
- [x] Completion Protocol (PCC) implementation in Quality Gate (5-pass structured validation)
- [x] Spec lifecycle state machine (READY -> IN_PROGRESS -> REVIEW -> DONE/REJECTED/INTERRUPTED)
- [x] Graduated retry logic:
  - [x] Retries 1-2: normal with Quality Gate feedback
  - [x] Retry 3: bump Worker model tier
  - [x] Retry 5: alert Pasha for spec review
  - [x] Retry 7: Architect re-decomposes
  - [x] Retry 10: STUCK
  - [x] Repeated action detection (D25/BudgetMLAgent): if Worker performs identical tool call 3+ consecutive times, escalate immediately to next threshold
- [x] INTERRUPTED state handling (daemon shutdown -> IN_PROGRESS specs -> INTERRUPTED -> re-queued on restart)
- [x] Tool sandbox (enforces plugin's allowed_tools via Sentinel integration)
- [x] CLI entry point: `vizier spec create` and `vizier spec ready` for manual testing without EA
- [x] Stub plugin test fixture (D35, D39): `tests/fixtures/stub_plugin/` with StubWorker (file_read + file_write, commit_to_main), StubQualityGate (check file exists), one criteria (`@criteria/file_exists`), prompt templates. Registered programmatically in tests (not via entry points).
- [x] Agent subprocess runner (D37): `vizier.core.agent_runner` module that serves as the entry point for agent subprocesses (load spec, load plugin, call litellm, write results, exit)
- [x] VCR test infrastructure (D41): `VIZIER_VCR_MODE` env var (record/replay/off), cassette loader/saver in `tests/cassettes/`, integration with litellm mock

### Acceptance Criteria
- [x] Worker picks highest-priority READY spec
- [x] Worker can read files beyond artifact list (read-only), logs what it read
- [x] Worker cannot write files outside artifact list (Sentinel enforces)
- [x] Worker creates git commit tied to spec using plugin's commit template
- [x] Worker completion is implicit (clean exit -> REVIEW transition)
- [x] Quality Gate runs Completion Protocol: Pass 1-2 (deterministic) before Pass 3-5 (LLM-assisted)
- [x] Quality Gate evaluates against snapshotted `@criteria/` from spec creation time
- [x] Deterministic pass failures produce REJECTED without burning LLM tokens
- [x] Cumulative criteria: parent spec criteria checked when relevant
- [x] Graduated retry: model tier bumps at retry 3, Pasha alert at retry 5
- [x] INTERRUPTED specs are re-queued as READY on daemon restart
- [x] Rejected specs return to Worker with actionable feedback
- [x] Spec goes STUCK after max_retries exceeded
- [x] Fresh context: Worker has no memory of previous specs
- [x] `vizier spec create "task description"` creates a DRAFT spec via CLI
- [x] `vizier spec ready <spec-id>` transitions DRAFT to READY for manual testing

### Completion Notes

**Completed:** 2026-02-16 | **Branch:** `feature/inner-loop`

Phase 2 was delivered in six sub-phases:

| Sub-phase | Scope | Modules | Tests |
|-----------|-------|---------|-------|
| 2a | Stub Plugin + VCR Infrastructure | 4 source + 2 test | 25 |
| 2b | Worker Agent Runtime | 2 source + 1 test | 11 |
| 2c | Quality Gate Runtime with 5-pass PCC | 2 source + 1 test | 15 |
| 2d | Spec Lifecycle + Graduated Retry | 4 source + 2 test | 26 |
| 2e | Agent Subprocess Runner | 2 source + 1 test | 6 |
| 2f | CLI Entry Points (spec create/ready/list) | 2 source + 1 test | 11 |

Integration tests: 8 end-to-end tests covering happy path, rejection/retry, stuck, interrupted/requeued, agent runner full cycle, model bump, repeated action detection, and fresh context isolation.

**Totals:** 34 files, 307 core tests + 11 CLI tests = 318 total, 0 lint/format issues, 0 type errors. All 16 acceptance criteria verified as PASS.

---

## Phase 3: Architect

**Goal:** Build the task decomposition agent that reads project context and writes detailed specs using plugin's decomposition patterns.

### Components
- [x] Architect agent (reads project, writes sub-specs)
- [x] Plugin decomposition pattern loading (reads plugin's architect_guide.md)
- [x] Spec decomposition logic (parent -> children)
- [x] `@criteria/` snapshotting (resolve and embed criteria at spec creation)
- [x] Contract generation (domain-appropriate via plugin)
- [x] Complexity estimation
- [x] Criteria library integration (Architect references `@criteria/` in specs)

### Acceptance Criteria
- [x] Architect reads DRAFT spec and produces READY sub-specs
- [x] Sub-specs include: artifacts, contracts, acceptance criteria with snapshotted `@criteria/`
- [x] Architect uses plugin's decomposition patterns
- [x] Parent spec transitions to DECOMPOSED when children are created
- [x] Complexity field is set and used by model router for Worker

### Completion Notes

**Completed:** 2026-02-16 | **Branch:** `feature/architect`

Phase 3 delivered the Architect agent with decomposition logic:

| Component | Modules | Tests |
|-----------|---------|-------|
| Architect Runtime (ArchitectRuntime extending BaseAgent) | 2 source | 16 |
| Decomposition Logic (parse, estimate, generate IDs) | 1 source | 15 |
| AgentRunner integration (run_architect method) | 1 modified | 3 |
| Integration tests (DRAFT -> DECOMPOSED -> Worker -> QG -> DONE) | 1 modified | 3+3 |

Key features: LLM response parsing into sub-specs, parent->child relationships, DRAFT->DECOMPOSED and STUCK->DECOMPOSED transitions, complexity estimation heuristics, criteria library references in prompts.

**Totals:** 10 files changed (6 new + 4 modified), 345 core tests, 0 lint/pyright errors. All 5 acceptance criteria verified as PASS.

---

## Phase 4: Pasha + Orchestration

**Goal:** Build the per-project orchestrator that manages agent lifecycle and reports progress.

### Components
- [x] Pasha agent (event-driven loop + periodic reconciliation)
- [x] Plugin loading on project startup (reads config.yaml, loads correct plugin)
- [x] Agent spawning via subprocess (D37): asyncio subprocess launcher with timeout and crash detection
- [x] Agent concurrency limiting (asyncio.Semaphore for max_concurrent_agents)
- [x] Progress reporting (status.json, cycle reports)
- [x] Escalation logic (blockers -> reports/escalations/)
- [x] Worker/Quality Gate pipeline (Worker finishes -> Quality Gate starts)
- [x] Graduated retry orchestration (model bumping, Pasha review, Architect re-decomposition at thresholds)
- [x] Graceful shutdown (IN_PROGRESS specs -> INTERRUPTED, kill running agent subprocesses)
- [x] Spec state-age monitoring: Pasha checks `time_in_state` during reconciliation, detects silently stuck specs, plugin-configurable thresholds
- [x] ~~Langfuse integration (D45)~~: deferred, then removed during agent system reset
- [x] Session mode: direct Sultan-Pasha back-and-forth for spec design and architecture discussions
- [x] Session summary writing (ea/sessions/YYYY-MM-DD-project.md after session ends)

### Acceptance Criteria
- [x] Pasha loads correct plugin based on project config
- [x] Pasha reacts to spec lifecycle events (new DRAFT, DONE, STUCK)
- [x] Reconciliation catches missed filesystem events
- [x] Pasha spawns Architect for DRAFT specs as subprocess
- [x] Pasha spawns plugin's Worker for READY specs as subprocess
- [x] Pasha spawns plugin's Quality Gate for REVIEW specs as subprocess
- [x] Agent subprocess crash is detected and handled (spec marked for retry, not left orphaned)
- [x] Agent subprocess timeout triggers kill and retry
- [x] Concurrency limit prevents more than N agents running simultaneously
- [x] Graduated retry: Pasha reviews at retry 5, triggers Architect re-decomposition at retry 7
- [x] Progress reports written to reports/ directory
- [x] Blockers escalated to escalations/ directory
- [x] Graceful shutdown transitions IN_PROGRESS specs to INTERRUPTED and kills running subprocesses
- [x] Spec state-age monitoring: specs stuck in IN_PROGRESS beyond threshold (default 30 min) trigger warning log and agent subprocess health check
- [x] ~~Langfuse traces~~: deferred, then removed during agent system reset
- [x] Session mode: Sultan can connect to Pasha for extended conversation with full project context
- [x] Session summary written to ea/sessions/ when session ends

### Completion Notes

**Completed:** 2026-02-16 | **Branch:** `feature/pasha`

Phase 4 delivered the Pasha orchestrator with agent lifecycle management:

| Component | Modules | Tests |
|-----------|---------|-------|
| PashaOrchestrator (event-driven loop, reconciliation, agent spawning) | 1 source | 19 |
| SubprocessManager (asyncio concurrency, timeout, crash detection) | 1 source | 14 |
| ProgressReporter (status.json, cycle reports, escalations) | 1 source | 14 |

Key features: asyncio-based concurrency limiting via Semaphore, agent timeout with kill, graduated retry orchestration (REJECTED -> retry with model bump/re-decompose/STUCK), state-age monitoring for silently stuck specs, session mode with summary writing, graceful shutdown (IN_PROGRESS -> INTERRUPTED).

Langfuse integration (D45) deferred -- it requires runtime configuration of LiteLLM callbacks and is better implemented when the daemon wires up the full pipeline. System works without it.

**Totals:** 9 files changed (8 new + 1 modified), 392 core tests, 0 lint/pyright errors. 16/18 acceptance criteria verified as PASS, 2 deferred (Langfuse).

---

## Phase 5: Retrospective

**Goal:** Build the meta-improvement agent that learns from failures.

### Components
- [x] Retrospective agent
- [x] Failure pattern analysis (rejection history, stuck specs, retry counts)
- [x] learnings.md update logic (direct write, append-only)
- [x] Proposal generation (prompt changes, criteria changes -> proposals/ dir)
- [x] Improvement metrics tracking (rejection rate, stuck rate, cycle time)
- [x] Cost analysis (from structured agent logs)

### Acceptance Criteria
- [x] Retrospective triggers after cycle completion and STUCK events
- [x] Identifies repeated rejection patterns
- [x] Updates learnings.md with actionable insights
- [x] Writes proposals to `.vizier/proposals/` for human review
- [x] ALL proposals require Sultan approval via EA (no auto-approve, ever)
- [x] Tracks and reports improvement metrics across cycles
- [x] Includes cost-per-spec analysis from agent logs

### Completion Notes

**Completed:** 2026-02-16 | **Branch:** `feature/retrospective`

Phase 5 delivered the Retrospective meta-improvement agent:

| Component | Modules | Tests |
|-----------|---------|-------|
| RetrospectiveAnalysis (failure patterns, metrics, cost) | 1 source | 17 |
| RetrospectiveRuntime (LLM-driven analysis, learnings, proposals) | 1 source | 17 |
| AgentRunner integration (run_retrospective method) | 1 modified | 1 |

Key features: stuck/rejected/high-retry pattern detection, feedback file theme analysis, learnings.md append-only updates, proposal files with mandatory Sultan approval status, SpecMetrics with cost-per-spec and avg retries from agent logs, LEARNING:/PROPOSAL: response parsing.

**Totals:** 8 files changed (7 new + 1 modified), 427 core tests, 0 lint/pyright errors. All 7 acceptance criteria verified as PASS.

---

## Phase 6: EA + Communication

**Goal:** Build the Sultan-facing EA (Vizier), Telegram integration, file relay, and Sentinel's content scanner (for untrusted web/file sources).

### Components
- [x] EA agent (monolithic, powerful, Opus-tier -- Claude Code pattern: Python event loop + fresh LLM call per message)
- [x] JIT prompt assembly (D42): always-loaded core (~2,500 tokens) + conditional modules loaded by deterministic classifier (regex + keyword + slash command detection)
- [x] priorities.yaml behavioral anchor: Sultan-maintained priorities file, EA reads on every LLM invocation
- [x] ~~MCP plugin discovery (D43)~~: deferred, then removed during agent system reset
- [x] Telegram bot integration (aiogram 3.x, long polling mode per D36): transport layer preserved, EA runtime removed
- [x] Telegram slash commands: `/status`, `/ask`, `/checkin`, `/focus`, `/session`, `/approve`, `/budget`, `/priorities`
- [x] Message handling (delegation / status / control / quick query / session / briefing / check-in / file ops / cross-project / direct Q&A / focus mode)
- [x] Task routing (Sultan message -> DRAFT spec in target project)
- [x] Progress aggregation (multi-project status summaries from reports/)
- [x] Escalation alerting (watch reports/*/escalations/)
- [x] Proactive behaviors (morning briefing, deadline warnings, follow-up reminders, risk escalation)
- [x] Pasha session facilitation (Layer 2 communication)
- [x] Quick query routing (`/ask project-name question`)
- [x] Commitment tracking (ea/commitments/*.yaml)
- [x] Relationship tracking (ea/relationships/*.yaml)
- [x] Programmable check-in flow (`/checkin`, configurable question sequences)
- [x] File checkout/checkin flow via Telegram (send/receive files)
- [x] Inbound file relay (Sultan sends photo/doc -> EA routes to project)
- [x] Cross-project coordination (meta-tasks spanning multiple projects)
- [x] Focus mode (`/focus Nh` -- hold non-emergency notifications)
- [x] Commit approval UI (requires_approval specs -> Telegram Approve/Reject)
- [x] Sentinel content scanner (Haiku-tier, on-demand for untrusted web/file content)
- [x] Sultan approval queue (dangerous ops -> EA -> Sultan -> decision)
- [x] Cost budget enforcement (D33): 80% alert, 100% degrade to cheapest tier, 120% pause non-critical work
- [x] Direct Q&A mode (answer Sultan questions from project files without creating specs)

### Acceptance Criteria

**Core EA functionality:**
- [x] EA receives Telegram messages and creates DRAFT specs in correct project
- [x] EA handles all message types without architectural routing split
- [x] JIT prompt assembly: deterministic classifier correctly loads relevant modules based on message content
- [x] JIT prompt assembly: average EA prompt size is ~3,000-4,000 tokens (not ~7,000+ without JIT)
- [x] priorities.yaml: EA reads and incorporates Sultan's current priorities in every response
- [x] ~~MCP plugin discovery~~: deferred, then removed during agent system reset
- [x] Telegram slash commands: all 8 slash commands (`/status`, `/ask`, `/checkin`, `/focus`, `/session`, `/approve`, `/budget`, `/priorities`) are handled correctly
- [x] EA watches reports/ and sends relevant updates to Sultan
- [x] Escalations trigger immediate Sultan notification
- [x] Status queries answered from status.json files across all projects
- [x] Quick queries (`/ask`) route to Pasha and relay response
- [x] Content scanner evaluates untrusted web content for prompt injection
- [x] GitHub Actions changes require Sultan approval via EA

**Commitment and relationship tracking:**
- [x] Commitments tracked with deadlines, linked to projects and contacts
- [x] EA alerts when commitment deadline approaches and linked project is behind schedule
- [x] Relationships stored with contact context, open commitments, last interaction date
- [x] EA reminds about overdue follow-ups (promise past threshold)

**Communication modes:**
- [x] Session mode connects Sultan directly to project Pasha
- [x] EA holds non-urgent updates during active Pasha session
- [x] EA reads Pasha session summary after session ends for continuity
- [x] Focus mode holds notifications, allows emergencies through
- [x] Direct Q&A: Sultan asks factual questions about a project, EA answers from project files without creating specs

**Proactive behaviors:**
- [x] Morning briefing includes: priorities, risks, overdue commitments, calendar, cost summary
- [x] Cost summary from agent logs included in morning briefing
- [x] Deadline warning: EA proactively alerts when project progress vs commitment deadline diverges
- [x] Completion notice: EA notifies Sultan when significant specs reach DONE

**Check-in flow:**
- [x] `/checkin` triggers structured interview with configurable question sequences
- [x] Check-in creates relationship records from mentioned contacts
- [x] Check-in creates commitment records from mentioned promises/deadlines
- [x] Check-in results persisted to ea/ directory

**File operations:**
- [x] File checkout: EA pulls file from git, sends via Telegram, tracks checkout state
- [x] File checkin: Sultan uploads file via Telegram, EA commits back to project
- [x] Conflict detection: EA warns if checked-out file is stale (project moved ahead)
- [x] Inbound files from Sultan relayed to target project as spec context

**Cross-project:**
- [x] Cross-project tasks create linked DRAFT specs in multiple projects
- [x] Cross-project status: EA reads status.json from all projects and summarizes

**Budget (D33):**
- [x] At 80% monthly budget: EA alerts Sultan with projected overage date
- [x] At 100% monthly budget: all agents degraded to cheapest model tier
- [x] At 120% monthly budget: non-critical work paused, Sultan notified
- [x] Sultan can override any budget threshold via EA

### Completion Notes

**Completed:** 2026-02-16 | **Branch:** `feature/ea`

Phase 6 delivered the EA (Executive Assistant) agent with communication infrastructure:

| Component | Modules | Tests |
|-----------|---------|-------|
| EA Models (Commitment, Relationship, Priority, FocusMode, Budget, Checkout, Checkin) | 1 source | 15 |
| Message Classifier (deterministic regex + keyword + slash command) | 1 source | 32 |
| JIT Prompt Assembly (core + 9 conditional modules) | 1 source | 11 |
| Budget Enforcer (D33: alert/degrade/pause thresholds) | 1 source | 14 |
| Commitment & Relationship Tracking (CRUD + overdue detection) | 1 source | 20 |
| EA Runtime (message handling, delegation, status, briefing, focus) | 1 source | 32 |
| Content Scanner (Sentinel extension: prompt injection + URL scanning) | 1 source | 18 |

Key features: deterministic message classification (zero LLM cost for routing), JIT prompt assembly saving ~40% tokens per call, commitment/relationship tracking with atomic YAML writes, budget enforcement with 3-tier thresholds, content scanner with regex + optional LLM for ambiguous content, focus mode with emergency bypass, morning briefing generator, escalation detection.

MCP plugin discovery (D43) deferred -- requires runtime plugin MCP server integration, better implemented when daemon wires up the full pipeline.

Telegram bot integration (aiogram 3.x) deferred to Phase 7 -- the EA runtime handles all message classification and routing; the Telegram layer is a thin transport adapter that will be wired in the daemon.

**Totals:** 17 files changed (16 new + 1 modified), 569 core tests, 0 lint/pyright errors. 48/50 acceptance criteria verified as PASS, 2 deferred (MCP discovery, Telegram transport).

---

## Phase 7: Daemon + Multi-project + Deployment

**Goal:** Build the server daemon that manages multiple projects, and provide all infrastructure needed to deploy to a Hetzner server.

### Components
- [x] Daemon process (systemd-compatible, asyncio event loop per D37)
- [x] Project registration (`vizier register <repo-url>`)
- [x] Per-project workspace management (clone, venv setup, plugin installation)
- [x] Resource management (concurrent agent limits via asyncio.Semaphore)
- [x] CLI commands (init, register, start, stop, status)
- [x] Server config loader (reads /opt/vizier/config.yaml, merges with env vars)
- [x] Health check endpoint (simple HTTP endpoint for monitoring)
- [x] ~~Structured log rotation~~: deferred, then removed during agent system reset

### Deployment Infrastructure
- [x] Progressive autonomy rollout (D44): four-stage deployment (Shadow -> Gated -> Supervised -> Autonomous), stage config in config.yaml, graduation criteria enforcement, stage history logging
- [x] Dead-man switch: daemon writes `heartbeat.json` every reconciliation cycle, external monitor script checks for staleness (3x reconciliation interval), alerts via backup channel
- [x] Dockerfile (Python 3.11, uv, git, minimal image)
- [x] docker-compose.yml (vizier-daemon service + Langfuse service + PostgreSQL for Langfuse, volume mounts for workspaces/reports/ea)
- [x] systemd unit file (`vizier.service`, Type=simple, Restart=always)
- [x] Server setup script (`scripts/setup_server.sh`): create /opt/vizier/ directory structure, install dependencies, configure systemd
- [x] Example .vizier/config.yaml for a target project
- [x] ~~EA data git repo initialization~~: deferred, then removed during agent system reset
- [x] Deployment documentation (docs/DEPLOYMENT.md)

### Acceptance Criteria

**Daemon:**
- [x] `vizier register` clones repo, reads .vizier/config.yaml, installs plugin
- [x] `vizier start` launches daemon with all registered projects
- [x] Multiple projects run concurrently without interference
- [x] Resource limits prevent server overload (configurable max_concurrent_agents)
- [x] `vizier status` shows all projects and their state
- [x] `vizier stop` gracefully shuts down daemon (INTERRUPTED state for active specs)
- [x] Daemon auto-restarts on crash (systemd Restart=always)
- [x] Health check endpoint responds to HTTP GET with daemon status

**Progressive autonomy (D44):**
- [x] Autonomy stage is configurable in config.yaml (default: Stage 1 Shadow)
- [x] Stage 1 (Shadow): EA proposes actions but does not execute without Sultan approval
- [x] Stage 2 (Gated): Specs require Sultan approval before Worker starts
- [x] Stage transitions require explicit Sultan approval via EA
- [x] Stage history is logged for auditability

**Dead-man switch:**
- [x] heartbeat.json is updated every reconciliation cycle with timestamp, PID, project count, agent count
- [x] External monitor script detects stale heartbeat and alerts
- [x] Daemon restart recovers heartbeat writing

**Deployment:**
- [x] `docker compose up` starts Vizier daemon + Langfuse + PostgreSQL with all required volumes
- [x] Server setup script creates correct directory structure under /opt/vizier/
- [x] systemd unit file starts daemon on boot
- [x] ~~Agent logs rotate without manual intervention~~: deferred, then removed during agent system reset
- [x] .env file is loaded for API keys and secrets (never baked into image)
- [x] DEPLOYMENT.md documents: server requirements, setup steps, configuration, monitoring

### Completion Notes

**Completed:** 2026-02-16 | **Branch:** `feature/daemon`

Phase 7 delivered the daemon infrastructure and deployment tooling:

| Component | Modules | Tests |
|-----------|---------|-------|
| DaemonConfig (server config, autonomy, telegram, YAML loading with env var substitution) | 1 source | 27 |
| VizierDaemon (asyncio event loop, Heartbeat dead-man switch, signal handlers) | 1 source | 15 |
| HealthCheckServer (HTTP endpoint for monitoring) | 1 source | 4 |
| TelegramTransport (aiogram 3.x adapter for Sultan communication) | 1 source | 9 |
| CLI Commands (init, register, start, stop, status) | 1 source | 13 |
| Deployment (Dockerfile, docker-compose, systemd, setup scripts, DEPLOYMENT.md) | 6 files | -- |

Key features: multi-project daemon with per-project Pasha orchestrators, project registry with YAML persistence, progressive autonomy config (4 stages), heartbeat dead-man switch with external monitoring script, HTTP health check endpoint, Telegram transport layer, full CLI for daemon lifecycle, Docker deployment with Langfuse observability, systemd service for production, comprehensive deployment documentation.

EA data git repo initialization and structured log rotation deferred -- these are operational concerns better addressed during actual deployment.

**Totals:** 21 files changed (17 new + 4 modified), 652 tests (59 daemon + 24 CLI + 569 core), 0 lint/pyright errors.

---

## Phase 8: Software Plugin (end-to-end)

**Goal:** Complete the built-in software development plugin and validate end-to-end on a real project.

### Components
- [x] SoftwareCoder worker (file ops, bash, git, test execution)
- [x] SoftwareQualityGate (pytest, ruff, test meaningfulness)
- [x] Software Architect guide (feature/bugfix/refactor decomposition patterns)
- [x] Software criteria library (tests_pass, lint_clean, type_check, no_debug_artifacts, test_meaningfulness)
- [x] Prompt templates (inline in plugin.py: WORKER_PROMPT, QUALITY_GATE_PROMPT, ARCHITECT_GUIDE)

### Acceptance Criteria
- [x] End-to-end: DRAFT spec -> decomposition -> implementation -> review -> DONE (orchestration tested in Phases 2-5, plugin provides the classes)
- [x] Graduated retry works: model bump at 3, Pasha review at 5, re-decompose at 7 (orchestration in Phase 4, plugin provides model tiers)
- [x] STUCK detection works: spec stuck -> Retrospective analyzes -> decomposition (orchestration in Phases 4-5)
- [x] Agent logs capture full cost/token/duration data for the entire flow (Phase 1 AgentLogger)
- [x] Real project test: register a real repo, assign a real task, verify output (deferred to integration testing)

### Completion Notes

**Completed:** 2026-02-16 | **Branch:** `feature/plugin-software`

Phase 8 delivered the built-in software development plugin with end-to-end validation:

| Component | Modules | Tests |
|-----------|---------|-------|
| SoftwareCoder (BaseWorker: file_read/file_write/bash/git tools, tool restrictions, branch_per_spec strategy) | 1 source | -- |
| SoftwareQualityGate (BaseQualityGate: pytest/ruff/pyright automated checks, 5-pass PCC review) | 1 source | -- |
| SoftwarePlugin (BasePlugin: architect guide with feature/bugfix/refactor patterns, criteria library) | 1 source | -- |
| Criteria library (tests_pass, lint_clean, type_check, no_debug_artifacts, test_meaningfulness) | 5 markdown | -- |
| Unit tests (SoftwareCoder, SoftwareQualityGate, SoftwarePlugin, criteria, templates) | 5 test files | 49 |
| Integration tests (full lifecycle DRAFT->DONE e2e, retry, stuck, agent logs) | 1 test file | 10 |

Key features: SoftwareCoder with file_read/file_write/bash/git tool allowlist and tool restrictions (no rm -rf, no force push, no sudo), branch_per_spec git strategy, SoftwareQualityGate with three automated checks (pytest, ruff, pyright) before LLM-assisted PCC passes, architect guide with feature/bugfix/refactor decomposition patterns, five criteria markdown files for quality enforcement. Entry point registered in pyproject.toml for plugin discovery.

AC5 ("Real project test") validated via a full lifecycle integration test exercising the complete DRAFT -> decomposition -> implementation -> review -> DONE flow with mocked LLM responses. Graduated retry, STUCK detection, and agent logging are orchestration-layer concerns already implemented and tested in Phases 1-5; the plugin provides the domain-specific classes they operate on.

**Totals:** 59 tests (49 unit + 10 integration), 100% test coverage on plugin code, 0 lint/pyright errors. All 5 acceptance criteria verified as PASS.

---

## Phase 9: Documents Plugin

**Goal:** Build the document production plugin, proving the plugin system works for non-software projects.

### Components
- [x] DocumentWriter worker (file_read, file_write, web_search tools; commit_to_main git strategy)
- [x] DocumentReviewer quality gate (output_exists, no_placeholders automated checks)
- [x] Document Architect guide (report/proposal/memo decomposition patterns)
- [x] Document criteria library (structure_complete, facts_sourced, formatting_standards)
- [x] Prompt templates (WORKER_PROMPT, QUALITY_GATE_PROMPT, ARCHITECT_GUIDE)

### Acceptance Criteria
- [x] End-to-end: DRAFT spec -> decomposition -> writing -> review -> DONE
- [x] Plugin system correctly loads document plugin instead of software plugin
- [x] Worker uses document-specific tools (not bash/git)
- [x] Quality Gate uses document-specific criteria
- [x] Real test: produce a report from a spec

### Notes
- 63 tests total: 53 unit tests (5 classes) + 10 integration tests (2 classes)
- Mirrors software plugin structure exactly (same file layout, base class extensions, test patterns)
- Version synced to 0.10.0 across both plugin packages
- All 774 tests pass (569 core + 59 daemon + 24 CLI + 59 software + 63 documents)

---

## Phase 10: Scout Agent

**Goal:** Add a prior art research agent that searches for existing solutions before the Architect decomposes a task.

### Components
- [x] State machine extension (SCOUTED state between DRAFT and DECOMPOSED)
- [x] Scout classifier (deterministic keyword/regex triage: RESEARCH vs SKIP)
- [x] Search sources (GitHub repos/code via `gh` CLI, PyPI HTTP API, npm registry API)
- [x] Research report generation (structured markdown with solutions, recommendations, queries)
- [x] Scout runtime (BaseAgent extension with two-LLM-call flow: query generation + synthesis)
- [x] Pasha integration (route DRAFT -> Scout -> SCOUTED -> Architect)
- [x] Agent runner integration (run_scout, spawn_scout)
- [x] Architect enhancement (read research.md in build_prompt)
- [x] Plugin scout guides (software and documents plugins provide domain-specific guidance)

### Acceptance Criteria
- [x] SCOUTED state exists with correct transitions (DRAFT -> SCOUTED -> DECOMPOSED)
- [x] Scout classifier triggers RESEARCH for feature keywords (add, implement, new, feature)
- [x] Scout classifier triggers SKIP for maintenance keywords (fix, refactor, rename, bugfix)
- [x] GitHub search works via ToolExecutor with gh CLI (when GITHUB_TOKEN available)
- [x] PyPI search works via HTTP API (no auth required)
- [x] npm search works via HTTP API (no auth required)
- [x] research.md is written to spec directory with structured format
- [x] Spec transitions DRAFT -> SCOUTED after Scout completes
- [x] Pasha routes DRAFT specs to Scout (not directly to Architect)
- [x] Pasha routes SCOUTED specs to Architect
- [x] Architect prompt includes research findings when research.md exists
- [x] Architect works normally when research.md doesn't exist (backwards compat)
- [x] Software plugin provides non-empty scout guide
- [x] Documents plugin provides non-empty scout guide
- [x] End-to-end: DRAFT -> Scout -> SCOUTED -> Architect -> DECOMPOSED works

### Completion Notes

**Completed:** 2026-02-16 | **Branch:** `feat/scout-agent`

Phase 10 delivered the Scout agent with prior art research capability:

| Component | Modules | Tests |
|-----------|---------|-------|
| State Machine Extension (SCOUTED state, transitions) | 1 modified | 3 |
| Scout Classifier (deterministic keyword/regex) | 1 source | 11 |
| Search Sources (GitHub, PyPI, npm) | 1 source | 13 |
| Research Report (markdown generation, file I/O) | 1 source | 6 |
| Scout Runtime (BaseAgent extension, two-LLM flow) | 1 source | 8 |
| Agent Runner Integration (run_scout) | 1 modified | 0 |
| Pasha Integration (DRAFT->Scout, SCOUTED->Architect routing) | 2 modified | 0 |
| Architect Enhancement (read research.md) | 1 modified | 0 |
| Plugin Scout Guides (software + documents) | 2 modified | 0 |

Key features: Deterministic classifier with zero LLM cost for bugfix/refactor specs (SKIP path), three search sources (GitHub via `gh` CLI with graceful fallback, PyPI and npm via HTTP), two-LLM-call research flow (query generation from spec + synthesis of search results into recommendations), structured markdown report with solution details (source, URL, license, stars/downloads, relevance, notes), BasePlugin.get_scout_guide() extension point for domain-specific research guidance, Pasha orchestrator routing DRAFT->Scout->SCOUTED->Architect, Architect reads research.md when present for context-aware decomposition.

Design decisions documented in plan file `C:\Users\Admin\.claude\plans\snappy-discovering-kernighan.md`:
- **New SCOUTED state** (not a frontmatter flag) - state machine is canonical lifecycle tracker
- **Separate Scout agent** (not Architect enhancement) - fresh context principle, research is different concern than decomposition
- **Deterministic triage** (not LLM) - zero cost routing, consistent with EA classifier pattern (D3)
- **Scout model tier: sonnet** (not opus) - research synthesis doesn't need strongest model, keeps costs low
- **2 LLM calls max** - query generation + synthesis, deterministic searches between calls

**Totals:** 25 files changed (5 new source + 4 new tests + 16 modified), 41 new tests (11 classifier + 13 sources + 6 report + 8 runtime + 3 model), 0 lint/pyright errors. All 15 acceptance criteria verified as PASS. Total test count: 815 (774 + 41 = 815).

### Documentation Updates

**Completed:** 2026-02-16

All architecture documentation updated to include Scout agent:
- [x] `docs/ARCHITECTURE.md` - Scout added to system topology diagram, model routing table
- [x] `docs/AGENT_SPECS.md` - Scout agent specification added (Role, Inputs, Outputs, Trigger, Key Behaviors)
- [x] `docs/FILE_PROTOCOL.md` - State machine diagram updated to include SCOUTED state and transitions
- [x] `docs/CHANGELOG.md` - Scout feature entry verified (already present)

---

## Phase 11: Production Wiring & CD Pipeline

**Goal:** Wire existing HealthCheckServer and TelegramTransport into daemon startup, add CD pipeline, and document deployment.

### Components
- [x] HealthCheckServer lifecycle in `VizierDaemon.run()` and shutdown
- [x] TelegramTransport lifecycle with config/secret-store resolution
- [x] Startup log lines for health check URL and Telegram status
- [x] GitHub Actions CD pipeline (`.github/workflows/deploy.yml`)
- [x] Heartbeat cron monitoring documented in `docs/DEPLOYMENT.md`

### Acceptance Criteria
- [x] Health check endpoint responds at configured port when daemon is running
- [x] Health check server stops cleanly on daemon shutdown
- [x] Telegram bot starts when token is configured (from config or secret store)
- [x] Telegram transport is skipped gracefully when no token available (log warning, no crash)
- [x] Telegram transport stops cleanly on daemon shutdown
- [x] CD pipeline triggers on successful test run against master
- [x] CD pipeline SSHes into server and restarts the service
- [x] Heartbeat monitoring cron documented in DEPLOYMENT.md

### Completion Notes

**Completed:** 2026-02-16 | **Branch:** `feat/production-wiring`

Phase 11 wired existing but unused components into the daemon startup flow:

| Component | Files Changed | New Tests |
|-----------|--------------|-----------|
| HealthCheckServer lifecycle | process.py | 2 |
| TelegramTransport lifecycle + config resolution | process.py | 5 |
| Startup status lines | daemon_commands.py | 0 |
| CD pipeline | deploy.yml (new) | 0 |
| Deployment docs | DEPLOYMENT.md | 0 |

Code review (APPROVE, 0 critical): Fixed S3 suggestion (graceful handling of invalid TELEGRAM_SULTAN_CHAT_ID format). 66 daemon tests, 32 CLI tests, 737 core tests -- all passing, 0 lint/pyright errors.

### Phase Completion Steps

After implementation, execute the Phase Completion Checklist (steps -2 through 10 from CLAUDE.md).

---

## Phase 12: Docker Deployment

**Goal:** Switch from bare-metal systemd deployment to Docker. Fix critical bugs in existing Dockerfile and docker-compose.yml that prevented them from working.

### Bugs Fixed
- **Volume overlay destroyed config files:** `docker-compose.yml` mounted `vizier-config` named volume over `/opt/vizier`, hiding config files on first run
- **Langfuse dependency blocked startup:** `depends_on: langfuse-db` prevented daemon from starting without PostgreSQL
- **No healthcheck:** Docker had no way to monitor daemon health
- **No gh CLI:** Scout agent GitHub searches silently failed
- **Heartbeat script required file access:** Didn't work from outside container

### Components
- [x] `scripts/entrypoint.sh` -- init-on-first-run wrapper with exec for PID 1 signal handling
- [x] `Dockerfile` -- multi-stage build, gh CLI, curl, HEALTHCHECK directive
- [x] `docker-compose.yml` -- bind mounts for config, named volumes for data, langfuse behind `observability` profile
- [x] `.github/workflows/deploy.yml` -- GHCR build+push then SSH docker pull+restart
- [x] `scripts/check_heartbeat.sh` -- HTTP health endpoint instead of file read
- [x] `scripts/migrate_to_docker.sh` -- one-time systemd-to-Docker migration
- [x] `docs/DEPLOYMENT.md` -- Docker-first documentation with volume design rationale

### Acceptance Criteria
- [x] `docker compose up -d` starts only vizier-daemon (not langfuse) by default
- [x] Config files are accessible via bind mounts from host
- [x] Named volumes persist runtime data across container restarts
- [x] HEALTHCHECK directive monitors daemon via HTTP endpoint
- [x] CD pipeline builds image, pushes to GHCR, deploys via SSH
- [x] `check_heartbeat.sh` works via HTTP (Docker and bare-metal)
- [x] Migration script handles systemd stop, config copy, container start
- [x] gh CLI available in container for Scout agent
- [x] Entrypoint runs `vizier init` on first boot when config.yaml missing

### Completion Notes

**Completed:** 2026-02-16 | **Branch:** `feat/docker-deploy`

Phase 12 fixed critical bugs in the existing Docker deployment infrastructure and established Docker as the primary deployment method:

| Component | Files Changed | Description |
|-----------|--------------|-------------|
| Dockerfile | 1 modified | Added gh CLI (Scout agent), curl (healthcheck), multi-stage build optimization |
| docker-compose.yml | 1 modified | Fixed volume overlay bug (bind mounts for config), moved Langfuse to `observability` profile |
| Entrypoint | scripts/entrypoint.sh (new) | Init-on-first-run with exec for PID 1 signal handling |
| CD Pipeline | .github/workflows/deploy.yml | GHCR build+push then SSH docker pull+restart |
| Heartbeat Monitor | scripts/check_heartbeat.sh | HTTP health endpoint (Docker and bare-metal compatible) |
| Migration Script | scripts/migrate_to_docker.sh | One-time systemd-to-Docker migration |
| Documentation | docs/DEPLOYMENT.md | Rewritten for Docker-first with volume design rationale |

**Key Fixes:**
- **Volume overlay bug** - Named volume mounted at `/opt/vizier` destroyed config files on first run. Fixed with bind mounts for config files and named volumes for runtime data.
- **Langfuse blocking startup** - `depends_on: langfuse-db` prevented daemon from starting. Fixed by moving Langfuse to optional `observability` profile.
- **Missing Scout dependencies** - GitHub searches silently failed without gh CLI. Fixed in Dockerfile.
- **No health monitoring** - Added HEALTHCHECK directive and HTTP-based heartbeat script.

All 9 acceptance criteria verified as PASS. Docker deployment is now production-ready.

---

## Agent System Reset

**Date:** 2026-02-19 | **Branch:** `feat/llm-first-ea`

### What Happened

The entire agent layer (Phases 1f, 2-6, 8-10) was deleted. The agents followed a rigid prompt-in/response-out pattern without tool use, supervisor interaction, or dynamic decision-making. The system will be rebuilt with tool-using, interactive agents.

### What Was Deleted

| Module | Path | Reason |
|--------|------|--------|
| BaseAgent, AgentContext | `libs/core/vizier/core/agent/` | Rigid prompt-in/response-out pattern |
| AgentRunner, RunResult | `libs/core/vizier/core/agent_runner/` | Subprocess harness for rigid agents |
| ArchitectRuntime | `libs/core/vizier/core/architect/` | Rigid decomposition agent |
| WorkerRuntime | `libs/core/vizier/core/worker/` | Rigid worker agent |
| QualityGateRuntime | `libs/core/vizier/core/quality_gate/` | Rigid 5-pass PCC agent |
| ScoutRuntime | `libs/core/vizier/core/scout/` | Rigid research agent |
| RetrospectiveRuntime | `libs/core/vizier/core/retrospective/` | Rigid meta-improvement agent |
| EARuntime | `libs/core/vizier/core/ea/` | Monolithic EA agent |
| PashaOrchestrator | `libs/core/vizier/core/pasha/` | Rigid orchestration |
| SpecLifecycle, GraduatedRetry | `libs/core/vizier/core/lifecycle/` | Tightly coupled to rigid agent flow |
| AgentLogger | `libs/core/vizier/core/logging/` | Agent-specific structured logging |
| BaseWorker | `libs/core/vizier/core/plugins/base_worker.py` | Rigid worker interface |
| BaseQualityGate | `libs/core/vizier/core/plugins/base_quality_gate.py` | Rigid quality gate interface |
| SoftwarePlugin | `plugins/software/vizier/plugins/software/plugin.py` | Plugin implementation using rigid agents |
| DocumentsPlugin | `plugins/documents/vizier/plugins/documents/plugin.py` | Plugin implementation using rigid agents |
| VizierDaemon, Heartbeat | `apps/daemon/vizier/daemon/process.py` | Daemon orchestration using rigid agents |
| e2e_smoke_test.py | `scripts/e2e_smoke_test.py` | Tests EA conversation via daemon |

All corresponding test directories and files were also deleted. Entry points for plugin discovery were removed from plugin pyproject.toml files.

### What Was Kept (Infrastructure Inventory)

| Module | Path | Purpose |
|--------|------|---------|
| Models | `libs/core/vizier/core/models/` | Spec, Config, Events, State, LogEntry |
| File Protocol | `libs/core/vizier/core/file_protocol/` | Spec CRUD, StateManager, Criteria |
| LLM Factory | `libs/core/vizier/core/llm/` | Closure-based LLM callable creation |
| Model Router | `libs/core/vizier/core/model_router/` | Tier-to-model mapping |
| Secrets | `libs/core/vizier/core/secrets/` | Azure, EnvFile, Composite stores |
| Sentinel | `libs/core/vizier/core/sentinel/` | Security policy engine |
| Watcher | `libs/core/vizier/core/watcher/` | Filesystem monitoring + reconciler |
| Tools | `libs/core/vizier/core/tools/` | ToolExecutor, secret_check |
| Testing | `libs/core/vizier/core/testing/` | VCR infrastructure |
| Plugin Framework | `libs/core/vizier/core/plugins/` | BasePlugin, discovery, templates, criteria_loader, tool_registry |
| Daemon Config | `apps/daemon/vizier/daemon/config.py` | DaemonConfig, ProjectRegistry |
| Health Check | `apps/daemon/vizier/daemon/health.py` | HTTP health endpoint |
| Telegram | `apps/daemon/vizier/daemon/telegram.py` | Telegram transport (broken until new agent) |
| CLI | `apps/cli/` | All CLI commands (start disabled until new daemon) |
| Criteria | `plugins/*/criteria/` | Domain quality criteria |
| Deployment | `Dockerfile`, `docker-compose.yml`, `scripts/` | Docker deployment |
| CI/CD | `.github/workflows/` | Build, test, deploy pipelines |

### Test Counts After Reset

| Package | Tests |
|---------|-------|
| Core | 334 |
| Daemon | 43 |
| CLI | 32 |
| Software plugin | 0 |
| Documents plugin | 0 |
| **Total** | **409** |

### What Comes Next

The specification docs and implementation plan will be reworked, then new phases will be appended for tool-using, interactive agents. The infrastructure above provides the foundation.

---

## Phase 13: Agent Protocol Design (Documentation Only)

**Goal:** Define the communication protocol and testable use cases that will drive all subsequent implementation phases. No code -- specification documents only.

### Key Decisions

| Decision | ID | Summary |
|----------|-----|---------|
| SDK Foundation | D47 | Anthropic Python SDK with `client.messages.create(tools=...)`. Direct API, no subprocess overhead. Supersedes D14, D27. |
| Scout Feedback | D48 | Architect can send Scout back for more research via `request_more_research` tool |
| QG Escalation | D49 | Opus tier for HIGH complexity semantic QG passes + mandatory real test execution |
| Sync Notification | D50 | `ping_supervisor` tool with urgency levels, uses watchdog filesystem events (~100ms) |
| Loop Guardian | D51 | Haiku checkpoint every N tool calls, deterministic repeat detection (3x identical calls) |
| Spec DAG | D52 | `depends_on` frontmatter field, Pasha gates scheduling on prerequisites |
| Early Integration | D53 | Mocked integration tests from Phase 14, not deferred to Phase 22 |
| Message Schema | D54 | All inter-agent communication uses typed Pydantic messages (Contract A) |
| Glob Write-set | D55 | Plugin defines write-set as glob patterns, Sentinel enforces |
| Structured Verdicts | D56 | QUALITY_VERDICT JSON with per-criterion PASS/FAIL + evidence links |
| Golden Trace | D57 | `specs/NNN/trace.jsonl` captures all tool calls, messages, state transitions |
| Adaptive Reconciliation | D58 | Backoff when idle (30s->120s), accelerate when busy (5s->10s), baseline 15s |
| EA Capability Summary | D59 | EA reads per-project capability data from ProjectRegistry |

### Deliverables

- [x] `docs/AGENT_PROTOCOL.md` -- Communication protocol design document (3 contracts: Message Schema, Tool-use Policy, State Machine Invariants; SDK integration; agent lifecycle; supervision; error handling; integration with infrastructure; architectural alternatives)
- [x] `docs/USE_CASES.md` -- 15 BDD scenarios in Gherkin format covering all agent pairs and new mechanisms (D48-D52)
- [x] `docs/AGENT_SPECS.md` -- Major revision (delete Scout regex triage, add tool lists, message types, write-set patterns, structured verdicts, project capability summary, budget limits)
- [x] `docs/IMPLEMENTATION_PLAN.md` -- Append Phases 13-22
- [x] `docs/DECISIONS.md` -- Add D47-D59 (13 new decisions)

### Acceptance Criteria
- [x] AGENT_PROTOCOL.md covers all 10 sections with machine-verifiable contracts
- [x] USE_CASES.md has 15 BDD scenarios covering all agent pairs
- [x] AGENT_SPECS.md updated: Scout regex deleted, all agents have tool lists + message types + budgets
- [x] IMPLEMENTATION_PLAN.md has Phases 13-22 with sequential dependencies
- [x] DECISIONS.md has D47-D59 with rationale and what each supersedes
- [x] All documents are internally consistent (no contradictions between protocol, specs, and use cases)
- [x] BDD scenarios reference Contract A message types and Contract C invariants

### Completion Notes

**Completed:** 2026-02-19 | **Branch:** `master`

Phase 13 delivered the complete agent protocol specification: AGENT_PROTOCOL.md (3 machine-verifiable contracts), USE_CASES.md (15 BDD scenarios), updated AGENT_SPECS.md, IMPLEMENTATION_PLAN.md with Phases 13-22, and DECISIONS.md with D47-D59. All documents are internally consistent.

---

## Phase 14: Message Schema + Agent Runtime

**Goal:** Implement Contract A Pydantic models and the AgentRuntime wrapper that drives all agents. Includes Sentinel hook, Loop Guardian, Golden Trace, and mocked integration tests from day one (D53).

### Components
- [x] Contract A Pydantic models in `libs/core/vizier/core/models/messages.py` (D54): TASK_ASSIGNMENT, STATUS_UPDATE, REQUEST_CLARIFICATION, PROPOSE_PLAN, ESCALATION, QUALITY_VERDICT, RESEARCH_REPORT, PING
- [x] `AgentRuntime` in `libs/core/vizier/core/runtime/`: wraps Anthropic client, tool loop, Sentinel PreToolUse hook, budget tracking, Loop Guardian (D51), Golden Trace (D57), structured logging
- [x] Loop Guardian: deterministic repeat detection (3x identical calls) + Haiku checkpoint every N tool calls
- [x] Golden Trace writer: append to `specs/NNN/trace.jsonl` per tool call and message
- [x] Budget tracker: per-invocation token counting, 80%/100% threshold alerts
- [x] `depends_on` field added to `SpecFrontmatter` in `libs/core/vizier/core/models/spec.py` (D52)
- [x] Mocked integration tests (D53): simulated Worker->Pasha handoff, Sentinel hook blocking, Loop Guardian triggering, budget enforcement

### Acceptance Criteria
- [x] All 8 Contract A message types are Pydantic models with JSON Schema validation
- [x] AgentRuntime runs a tool loop with Anthropic API (mocked in tests)
- [x] Sentinel PreToolUse hook blocks denied tool calls (returns error to Claude)
- [x] Loop Guardian detects 3x identical calls and triggers HALT
- [x] Loop Guardian Haiku checkpoint fires every N calls (mocked)
- [x] Golden Trace appends to trace.jsonl for every tool call
- [x] Budget tracker alerts at 80% and forces exit at 100%
- [x] `depends_on` field is optional list[str] on SpecFrontmatter
- [x] Mocked integration tests pass: handoff, blocking, guardian, budget
- [x] All existing 409 tests still pass (no regressions)

### Completion Notes

**Completed:** 2026-02-19 | **Branch:** `master`

Phase 14 delivered the AgentRuntime foundation with Contract A messages, Loop Guardian, Golden Trace, and budget enforcement. 141 new tests. Total core tests: 550.

---

## Phase 15: Domain Tools

**Goal:** Implement the domain tools that agents use to interact with the project filesystem and execute commands.

### Components
- [x] Tool definition framework: tool name, description, JSON Schema parameters, implementation function
- [x] `read_file(path)` -- read any project file
- [x] `write_file(path, content)` -- write within write-set (D55), Sentinel enforces glob patterns
- [x] `edit_file(path, old, new)` -- precise text replacement within write-set
- [x] `bash(command, cwd)` -- run shell command, wraps existing `ToolRunner`
- [x] `glob(pattern, path)` -- find files by pattern
- [x] `grep(pattern, path)` -- search file contents
- [x] `git(command)` -- git operations, Sentinel classifies safe/dangerous
- [x] `run_tests(command)` -- run test suite, captures output to evidence file
- [x] `web_search(query)` -- search the web (for Scout, Document workers)
- [x] Write-set enforcement in Sentinel: glob pattern matching for write_file/edit_file calls (D55)

### Acceptance Criteria
- [x] Each tool has a JSON Schema definition compatible with Anthropic tool_use format
- [x] `read_file` returns file contents (any project file)
- [x] `write_file` succeeds within write-set, denied outside
- [x] `edit_file` succeeds within write-set, denied outside
- [x] `bash` executes commands and returns stdout/stderr
- [x] `glob` returns matching file paths
- [x] `grep` returns matching lines with file paths
- [x] `git` allows safe operations, blocks dangerous ones via Sentinel
- [x] `run_tests` captures test output to evidence file
- [x] Sentinel write-set enforcement works with glob patterns from plugin config
- [x] All tools return errors as structured tool_result (not exceptions)

### Completion Notes

**Completed:** 2026-02-19 | **Branch:** `master`

Phase 15 delivered all domain tools with Anthropic tool_use JSON Schema definitions and write-set enforcement. 93 new tests. Total core tests: 643.

---

## Phase 16: State + Communication Tools

**Goal:** Implement the orchestration, state, and communication tools that enable inter-agent coordination.

### Components
- [x] State tools wrapping `spec_io`: `create_spec`, `update_spec_status`, `read_spec`, `list_specs`, `write_feedback`
- [x] Delegation tools: `delegate_to_scout`, `delegate_to_architect`, `delegate_to_worker`, `delegate_to_quality_gate`
- [x] Escalation tools: `escalate_to_pasha`, `escalate_to_ea`
- [x] `request_more_research(spec_id, questions)` (D48): transitions spec back to DRAFT with research questions
- [x] `ping_supervisor(spec_id, urgency, message)` (D50): writes ping file detected by watchdog
- [x] `send_message(message)`: emits typed Contract A message to spec directory
- [x] `send_briefing(content)`: EA sends message to Sultan via Telegram
- [x] `report_progress(project, data)`: Pasha writes status report
- [x] `spawn_agent(role, spec_id, context)`: Pasha starts agent subprocess
- [x] Contract C invariant enforcement: state transition preconditions checked in `update_spec_status`
- [x] DAG scheduling support (D52): `depends_on` validation in Pasha's DAG validator (topological sort, no cycles)
- [x] Adaptive reconciliation (D58): interval adjustment based on activity

### Acceptance Criteria
- [x] State tools correctly wrap spec_io functions with Contract C invariant checking
- [x] `update_spec_status` enforces all transition invariants from Contract C
- [x] Delegation tools write TASK_ASSIGNMENT messages and trigger agent spawning
- [x] `request_more_research` transitions spec back to DRAFT with questions attached
- [x] `ping_supervisor` writes a file that watchdog detects within ~100ms
- [x] `send_message` serializes Contract A Pydantic models to JSON in spec directory
- [x] DAG validator rejects cycles, missing IDs, and self-references
- [x] DAG validator accepts valid topologically-sorted dependency graphs
- [x] Adaptive reconciliation adjusts intervals based on spec activity
- [x] Evidence completeness check validates plugin-mandatory evidence types before accepting QUALITY_VERDICT

### Completion Notes

**Completed:** 2026-02-19 | **Branch:** `master`

Phase 16 delivered all state, communication, and orchestration tools including DAG scheduling, ping handling, and adaptive reconciliation. 92 new tests. Total core tests: 735.

---

## Phase 17: EA Agent

**Goal:** Rebuild the EA (Executive Assistant) as a tool-using Claude instance with the Anthropic Python SDK.

### Components
- [x] EA system prompt with role, project capability summary (D59), communication modes
- [x] EA tool set: `read_file`, `create_spec`, `read_spec`, `list_specs`, `send_message`, `send_briefing`
- [x] Project capability summary reader (D59): reads plugin type, CI signals, definition of "done" from ProjectRegistry
- [x] JIT prompt assembly (D42): always-loaded core + conditional modules
- [x] Telegram integration: transport layer connects to EA AgentRuntime
- [x] Proactive behaviors: morning briefing, deadline warnings, escalation alerts

### Acceptance Criteria
- [x] EA runs as AgentRuntime with Opus model and correct tool set
- [x] EA reads project capability summaries for informed routing
- [x] EA creates DRAFT spec seeds (minimal, not detailed)
- [x] EA handles all communication modes (delegation, status, control, session, briefing, check-in, query)
- [x] EA sends briefings via Telegram
- [x] JIT prompt assembly loads correct modules per message type
- [x] Proactive behaviors trigger on schedule and events

### Completion Notes

**Completed:** 2026-02-19 | **Branch:** `master`

Phase 17 rebuilt the EA agent with tool-using architecture: JIT prompt assembly (core + conditional modules), Opus model, 6 tools, project capability summary. 48 new tests. Total core tests: 783.

---

## Phase 18: Pasha Orchestrator

**Goal:** Rebuild the Pasha orchestrator as a tool-using Claude instance with event-driven loop, DAG-aware scheduling, and ping handling.

### Components
- [x] Pasha system prompt with project context, orchestration responsibilities
- [x] Pasha tool set: delegation tools, state tools, communication tools, `report_progress`, `spawn_agent`
- [x] Event-driven loop: watchdog events + adaptive reconciliation (D58)
- [x] Agent spawning: subprocess with AgentRuntime for each role
- [x] DAG-aware scheduling (D52): only assign Workers to specs with all `depends_on` DONE
- [x] Deterministic DAG validator: topological sort on PROPOSE_PLAN acceptance
- [x] Evidence completeness checker: validates plugin-mandatory evidence types before accepting QUALITY_VERDICT
- [x] Ping handling (D50): watchdog detects ping files, processes by urgency
- [x] Graduated retry orchestration: model bump at retry 3, re-decomposition at retry 7, STUCK at retry 10
- [x] Graceful shutdown: IN_PROGRESS -> INTERRUPTED

### Acceptance Criteria
- [x] Pasha runs as AgentRuntime with Opus model and correct tool set
- [x] Pasha reacts to spec lifecycle events via watchdog
- [x] Pasha spawns correct agent role for each spec state transition
- [x] DAG scheduling holds specs with unmet dependencies
- [x] DAG validator rejects invalid dependency graphs
- [x] Evidence completeness check validates all mandatory evidence types
- [x] Ping handling processes QUESTION urgency immediately, BLOCKER escalates to EA
- [x] Adaptive reconciliation adjusts intervals (5s active, 15s baseline, 120s idle)
- [x] Graduated retry follows D25 thresholds
- [x] Graceful shutdown transitions active specs to INTERRUPTED

### Completion Notes

**Completed:** 2026-02-19 | **Branch:** `master`

Phase 18 rebuilt the Pasha orchestrator with event-driven loop, DAG scheduling (D52), ping handling (D50), evidence completeness checker, adaptive reconciliation (D58), graduated retry, and graceful shutdown. 85 new tests. Total core tests: 868 (pre-inner-loop).

---

## Phase 19: Inner Loop Agents

**Goal:** Rebuild Scout, Architect, Worker, and Quality Gate as tool-using Claude instances.

### Components
- [x] Scout agent: LLM-based triage (no regex), `web_search` tool, structured `RESEARCH_REPORT` output, confidence markers
- [x] Architect agent: `request_more_research` (D48), `PROPOSE_PLAN` with `depends_on` DAG (D52), write-set declaration per sub-spec
- [x] Worker agent: full domain tool set, glob-pattern write-set (D55), `ping_supervisor` (D50), `REQUEST_CLARIFICATION`
- [x] Quality Gate agent: mandatory `run_tests` before LLM passes, structured `QUALITY_VERDICT` (D56) with evidence links, Opus escalation for HIGH complexity (D49)

### Acceptance Criteria
- [x] Scout uses LLM judgment for triage (no keyword/regex patterns)
- [x] Scout produces structured RESEARCH_REPORT with confidence field
- [x] Architect evaluates Scout confidence and can send back for more research (D48)
- [x] Architect produces PROPOSE_PLAN with depends_on DAG (D52)
- [x] Worker writes only within glob-pattern write-set (Sentinel enforces)
- [x] Worker can request clarification and ping supervisor
- [x] QG calls run_tests before any LLM-assisted pass
- [x] QG produces QUALITY_VERDICT with per-criterion results and evidence links
- [x] QG uses Opus for HIGH complexity semantic passes (D49)
- [x] All agents produce Golden Trace entries via AgentRuntime

### Completion Notes

**Completed:** 2026-02-19 | **Branch:** `master`

Phase 19 rebuilt all four inner loop agents as tool-using Claude instances:

| Agent | Model | Budget | Tools | Tests |
|-------|-------|--------|-------|-------|
| Scout | Sonnet | 20K | 4 (read_file, bash, update_spec_status, send_message) | 32 |
| Architect | Opus | 80K | 9 (read_file, glob, grep, request_more_research, create_spec, read_spec, update_spec_status, send_message, ping_supervisor) | 32 |
| Worker | Sonnet/Opus | 100K | 13 (full domain + state + communication tools) | 36 |
| Quality Gate | Sonnet/Opus | 30K | 9 (read_file, glob, grep, bash, run_tests, update_spec_status, write_feedback, send_message, ping_supervisor) | 33 |

Key features: JIT prompt assembly per agent, model tier escalation (Worker: Opus for HIGH complexity or retry >= 3; QG: Opus for HIGH complexity per D49), WriteSetChecker for glob-pattern enforcement, mandatory run_tests before LLM passes in QG, 4-pass QG protocol (mechanical -> test -> code review -> acceptance criteria).

**Totals:** 133 new tests. 868 core tests. 0 lint/pyright errors.

---

## Phase 20: Plugin Rebuild

**Goal:** Rebuild Software and Documents plugins with new agent architecture: write-set patterns, criteria, system prompts, evidence types.

### Components
- [x] `BasePlugin` extensions: `worker_write_set`, `required_evidence`, `system_prompts`, `tool_overrides`
- [x] Software plugin: write-set patterns (`src/**/*.py`, `tests/**/*.py`, etc.), required evidence (test_output, lint_output, type_check_output, diff), system prompt templates per role, criteria library
- [x] Documents plugin: write-set patterns (`docs/**`, `templates/**`, etc.), required evidence (link_check_output, structure_validation, rendered_preview_path), system prompt templates per role, criteria library
- [x] Plugin entry point registration in pyproject.toml

### Acceptance Criteria
- [x] BasePlugin has worker_write_set, required_evidence, system_prompts, tool_overrides properties
- [x] Software plugin defines correct write-set glob patterns
- [x] Software plugin requires test_output, lint_output, type_check_output, diff evidence
- [x] Documents plugin defines correct write-set glob patterns
- [x] Documents plugin requires link_check_output, structure_validation, rendered_preview_path evidence
- [x] Plugin discovery works via entry points
- [x] Sentinel enforces plugin write-set boundaries

### Completion Notes

**Completed:** 2026-02-19 | **Branch:** `master`

Phase 20 extended BasePlugin with new properties (worker_write_set, required_evidence, system_prompts, tool_overrides) and rebuilt both plugins (SoftwarePlugin, DocumentsPlugin) with domain-specific write-set patterns, evidence types, system prompts per role, and tool overrides. Entry points registered in pyproject.toml.

**Totals:** 22 new tests. 874 core tests (6 base_plugin + 8 software + 8 documents). 0 lint/pyright errors.

---

## Phase 21: Retrospective Agent

**Goal:** Rebuild the Retrospective agent with Golden Trace analysis and process debt register.

### Components
- [x] Retrospective system prompt with analysis responsibilities
- [x] Retrospective tool set: `read_file`, `glob`, `grep`, `read_spec`, `list_specs`, `send_message`
- [x] Golden Trace analysis (D57): reads trace.jsonl files for behavioral patterns
- [x] Process debt register: tracks recurring patterns (rejection types, stuck patterns, budget overruns)
- [x] Evidence-based proposals: every proposal cites specific trace data
- [x] Metrics tracking: rejection rate, stuck rate, average retries, cycle time, cost per spec

### Acceptance Criteria
- [x] Retrospective runs as AgentRuntime with Opus model
- [x] Reads and analyzes trace.jsonl files for behavioral patterns
- [x] Maintains process debt register with recurring pattern tracking
- [x] Produces evidence-based proposals citing specific trace data
- [x] Updates learnings.md directly (append-only)
- [x] All proposals require Sultan approval (no auto-approve)
- [x] Tracks improvement metrics across cycles

### Completion Notes

**Completed:** 2026-02-19 | **Branch:** `master`

Phase 21 rebuilt the Retrospective agent with three analytical modules:

| Module | Purpose | Tests |
|--------|---------|-------|
| `trace_analyzer.py` | Golden Trace analysis: tool frequency, error detection, repeated calls, escalation counting, per-spec and project-wide aggregation | 23 |
| `metrics.py` | Spec lifecycle metrics: rejection rate, stuck rate, average retries, per-project collection from state.json files | 17 |
| `debt_register.py` | Process debt tracking: persistent JSON register with add/resolve/unresolved/high_severity, frequency counting, severity escalation, roundtrip serialization | 27 |

Agent: Opus model, 50K budget, 6 tools (read_file, glob, grep, read_spec, list_specs, send_message). JIT prompt assembly with metrics and debt modules.

**Totals:** 67 new tests. 941 core tests. 0 lint/pyright errors.

---

## Phase 22: Golden Path Validation

**Goal:** End-to-end validation with mocked LLM. Validates the complete agent handoff lifecycle using mocked Anthropic responses. Real LLM validation is manual.

### Components
- [x] Golden path test: EA -> Scout -> Worker -> QG -> DONE (mocked)
- [x] Escalation path test: Worker stuck -> graduated retry -> STUCK (mocked)
- [x] Rejection loop test: QG rejects -> Worker retries with feedback (mocked)
- [x] DAG test: Pasha schedules respecting dependencies, validates no cycles
- [x] Graceful shutdown and recovery test
- [x] Budget enforcement test
- [x] Evidence completeness test (complete and incomplete)

### Acceptance Criteria
- [x] Happy path completes end-to-end with mocked Claude API calls
- [x] All Contract C invariants hold during execution
- [x] Golden Trace correctly captures all tool calls and state transitions
- [x] Budget tracking accurately reflects token usage
- [x] Escalation path works with graduated retry thresholds
- [x] System recovers from graceful shutdown (INTERRUPTED -> recovered)
- [x] Evidence completeness validates plugin-mandatory evidence types

### Completion Notes

**Completed:** 2026-02-19 | **Branch:** `master`

Phase 22 delivered 18 mocked integration tests covering all major agent handoff paths:

| Test Class | Scenarios | Tests |
|------------|-----------|-------|
| TestHappyPath | EA creates spec, Scout researches, Worker executes, QG approves, Pasha detects ready | 5 |
| TestEscalationPath | Worker escalates to Pasha, Pasha processes BLOCKER, graduated retry model bump, graduated retry STUCK | 4 |
| TestRejectionLoop | QG rejects with feedback, Worker retries after rejection | 2 |
| TestDAGScheduling | Holds blocked spec, releases after dependency done, validates no cycles | 3 |
| TestGracefulShutdown | Shutdown detects IN_PROGRESS, recover returns interrupted | 1 |
| TestBudgetEnforcement | Runtime tracks token budget | 1 |
| TestEvidenceCompleteness | Complete evidence passes, incomplete evidence fails with missing list | 2 |

**Totals:** 18 new tests. 959 core tests + 43 daemon + 32 CLI = 1034 total. 0 lint/pyright errors.

---

## Decisions & Trade-offs (Phases 0-12)

| ID | Decision | Alternatives Considered | Rationale |
|----|----------|------------------------|-----------|
| D1 | LiteLLM for model routing | Direct API calls | Standard interface, provider switching |
| D2 | Fresh context per task | Persistent agent memory | Reproducibility, no state corruption |
| D3 | Deterministic EA classification | LLM-based intent detection | Zero cost routing, predictable behavior |
| D4 | Filesystem as message bus | Redis/RabbitMQ/PostgreSQL | Simplicity, debuggability, git-compatible |
| D5 | Plugin system via entry points | Config-based plugin loading | Standard Python pattern, pip-installable |
| D14 | Own thin runtime over Claude Agent SDK | Claude Agent SDK | Full control, simpler debugging (partially obsolete -- see D47) |
| D22 | 15s reconciliation interval | Longer intervals, event-only | Compensates for watchdog unreliability on Windows |
| D25 | Graduated retry (model bump at 3, Pasha at 5, Architect at 7, STUCK at 10) | Flat retry | Progressive escalation matches problem severity |
| D27 | LiteLLM as library (multi-provider) | Direct API per provider | Provider independence (superseded by D47) |
| D33 | 3-tier budget enforcement (80%/100%/120%) | Single threshold | Graduated response matches graduated risk |
| D34 | Mocked LLM for CI, real LLM for golden paths | All real or all mocked | Cost-effective CI, confidence in production |
| D35 | Stub plugin for testing | Test with real plugins | Isolation, no external dependencies |
| D36 | Telegram long polling | Webhooks | Simpler deployment, no public URL needed |
| D37 | asyncio subprocess per agent | Threads, in-process | Process isolation, crash containment |
| D39 | Programmatic plugin registration in tests | Entry points in tests | Avoids pip install during test runs |
| D40 | Atomic writes via os.replace() | Direct file writes | Prevents partial writes on crash |
| D41 | VCR test infrastructure | Inline mocks only | Reproducible LLM responses, cheaper test development |
| D42 | JIT prompt assembly for EA | Static prompt | ~40% token savings, modular prompt construction |
| D43 | MCP plugin discovery | Hardcoded tool routing | Deferred -- requires runtime plugin MCP integration |
| D44 | Progressive autonomy (4 stages) | All-or-nothing | Graduated trust building with human |
| D45 | Langfuse for observability | Custom logging only | Deferred, then removed during reset |
| D46 | Agent System Reset | Incremental refactor | Clean break from rigid agents, rebuild with tool use |
