# Vizier Implementation Plan

## Status Summary

| Phase | Name | Status | Branch |
|-------|------|--------|--------|
| 0 | Project Scaffold | Complete | `master` |
| 1 | Core Runtime + Plugin Framework + Sentinel | Complete | `feature/core-runtime` |
| 2 | Inner Loop (Worker + Quality Gate) | Complete | `feature/inner-loop` |
| 3 | Architect | Complete | `feature/architect` |
| 4 | Pasha + Orchestration | Complete | `feature/pasha` |
| 5 | Retrospective | Pending | `feature/retrospective` |
| 6 | EA + Communication | Pending | `feature/ea` |
| 7 | Daemon + Multi-project + Deployment | Pending | `feature/daemon` |
| 8 | Software Plugin (end-to-end) | Pending | `feature/plugin-software` |
| 9 | Documents Plugin | Pending | `feature/plugin-documents` |

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
- Branch is `master` (not `main`) — CI workflow updated accordingly.

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
- [ ] Langfuse integration (D45): configure LiteLLM success/failure callbacks, optional self-hosted Langfuse for trace-level agent debugging
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
- [ ] Langfuse traces appear for agent invocations when Langfuse is configured (optional, system works without it)
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
- [ ] Retrospective agent
- [ ] Failure pattern analysis (rejection history, stuck specs, retry counts)
- [ ] learnings.md update logic (direct write, append-only)
- [ ] Proposal generation (prompt changes, criteria changes -> proposals/ dir)
- [ ] Improvement metrics tracking (rejection rate, stuck rate, cycle time)
- [ ] Cost analysis (from structured agent logs)

### Acceptance Criteria
- [ ] Retrospective triggers after cycle completion and STUCK events
- [ ] Identifies repeated rejection patterns
- [ ] Updates learnings.md with actionable insights
- [ ] Writes proposals to `.vizier/proposals/` for human review
- [ ] ALL proposals require Sultan approval via EA (no auto-approve, ever)
- [ ] Tracks and reports improvement metrics across cycles
- [ ] Includes cost-per-spec analysis from agent logs

---

## Phase 6: EA + Communication

**Goal:** Build the Sultan-facing EA (Vizier), Telegram integration, file relay, and Sentinel's content scanner (for untrusted web/file sources).

### Components
- [ ] EA agent (monolithic, powerful, Opus-tier -- Claude Code pattern: Python event loop + fresh LLM call per message)
- [ ] JIT prompt assembly (D42): always-loaded core (~2,500 tokens) + conditional modules loaded by deterministic classifier (regex + keyword + slash command detection)
- [ ] priorities.yaml behavioral anchor: Sultan-maintained priorities file, EA reads on every LLM invocation
- [ ] MCP plugin discovery (D43): EA discovers per-project plugin MCP tools at startup, routes quick queries to plugin tools without spec creation
- [ ] Telegram bot integration (aiogram 3.x, long polling mode per D36)
- [ ] Telegram slash commands: `/status`, `/ask`, `/checkin`, `/focus`, `/session`, `/approve`, `/budget`, `/priorities`
- [ ] Message handling (delegation / status / control / quick query / session / briefing / check-in / file ops / cross-project / direct Q&A / focus mode)
- [ ] Task routing (Sultan message -> DRAFT spec in target project)
- [ ] Progress aggregation (multi-project status summaries from reports/)
- [ ] Escalation alerting (watch reports/*/escalations/)
- [ ] Proactive behaviors (morning briefing, deadline warnings, follow-up reminders, risk escalation)
- [ ] Pasha session facilitation (Layer 2 communication)
- [ ] Quick query routing (`/ask project-name question`)
- [ ] Commitment tracking (ea/commitments/*.yaml)
- [ ] Relationship tracking (ea/relationships/*.yaml)
- [ ] Programmable check-in flow (`/checkin`, configurable question sequences)
- [ ] File checkout/checkin flow via Telegram (send/receive files)
- [ ] Inbound file relay (Sultan sends photo/doc -> EA routes to project)
- [ ] Cross-project coordination (meta-tasks spanning multiple projects)
- [ ] Focus mode (`/focus Nh` -- hold non-emergency notifications)
- [ ] Commit approval UI (requires_approval specs -> Telegram Approve/Reject)
- [ ] Sentinel content scanner (Haiku-tier, on-demand for untrusted web/file content)
- [ ] Sultan approval queue (dangerous ops -> EA -> Sultan -> decision)
- [ ] Cost budget enforcement (D33): 80% alert, 100% degrade to cheapest tier, 120% pause non-critical work
- [ ] Direct Q&A mode (answer Sultan questions from project files without creating specs)

### Acceptance Criteria

**Core EA functionality:**
- [ ] EA receives Telegram messages and creates DRAFT specs in correct project
- [ ] EA handles all message types without architectural routing split
- [ ] JIT prompt assembly: deterministic classifier correctly loads relevant modules based on message content
- [ ] JIT prompt assembly: average EA prompt size is ~3,000-4,000 tokens (not ~7,000+ without JIT)
- [ ] priorities.yaml: EA reads and incorporates Sultan's current priorities in every response
- [ ] MCP plugin discovery: EA can invoke plugin MCP tools for quick queries without creating specs
- [ ] Telegram slash commands: all 8 slash commands (`/status`, `/ask`, `/checkin`, `/focus`, `/session`, `/approve`, `/budget`, `/priorities`) are handled correctly
- [ ] EA watches reports/ and sends relevant updates to Sultan
- [ ] Escalations trigger immediate Sultan notification
- [ ] Status queries answered from status.json files across all projects
- [ ] Quick queries (`/ask`) route to Pasha and relay response
- [ ] Content scanner evaluates untrusted web content for prompt injection
- [ ] GitHub Actions changes require Sultan approval via EA

**Commitment and relationship tracking:**
- [ ] Commitments tracked with deadlines, linked to projects and contacts
- [ ] EA alerts when commitment deadline approaches and linked project is behind schedule
- [ ] Relationships stored with contact context, open commitments, last interaction date
- [ ] EA reminds about overdue follow-ups (promise past threshold)

**Communication modes:**
- [ ] Session mode connects Sultan directly to project Pasha
- [ ] EA holds non-urgent updates during active Pasha session
- [ ] EA reads Pasha session summary after session ends for continuity
- [ ] Focus mode holds notifications, allows emergencies through
- [ ] Direct Q&A: Sultan asks factual questions about a project, EA answers from project files without creating specs

**Proactive behaviors:**
- [ ] Morning briefing includes: priorities, risks, overdue commitments, calendar, cost summary
- [ ] Cost summary from agent logs included in morning briefing
- [ ] Deadline warning: EA proactively alerts when project progress vs commitment deadline diverges
- [ ] Completion notice: EA notifies Sultan when significant specs reach DONE

**Check-in flow:**
- [ ] `/checkin` triggers structured interview with configurable question sequences
- [ ] Check-in creates relationship records from mentioned contacts
- [ ] Check-in creates commitment records from mentioned promises/deadlines
- [ ] Check-in results persisted to ea/ directory

**File operations:**
- [ ] File checkout: EA pulls file from git, sends via Telegram, tracks checkout state
- [ ] File checkin: Sultan uploads file via Telegram, EA commits back to project
- [ ] Conflict detection: EA warns if checked-out file is stale (project moved ahead)
- [ ] Inbound files from Sultan relayed to target project as spec context

**Cross-project:**
- [ ] Cross-project tasks create linked DRAFT specs in multiple projects
- [ ] Cross-project status: EA reads status.json from all projects and summarizes

**Budget (D33):**
- [ ] At 80% monthly budget: EA alerts Sultan with projected overage date
- [ ] At 100% monthly budget: all agents degraded to cheapest model tier
- [ ] At 120% monthly budget: non-critical work paused, Sultan notified
- [ ] Sultan can override any budget threshold via EA

---

## Phase 7: Daemon + Multi-project + Deployment

**Goal:** Build the server daemon that manages multiple projects, and provide all infrastructure needed to deploy to a Hetzner server.

### Components
- [ ] Daemon process (systemd-compatible, asyncio event loop per D37)
- [ ] Project registration (`vizier register <repo-url>`)
- [ ] Per-project workspace management (clone, venv setup, plugin installation)
- [ ] Resource management (concurrent agent limits via asyncio.Semaphore)
- [ ] CLI commands (init, register, start, stop, status)
- [ ] Server config loader (reads /opt/vizier/config.yaml, merges with env vars)
- [ ] Health check endpoint (simple HTTP endpoint for monitoring)
- [ ] Structured log rotation (agent-log.jsonl rotation by size/date)

### Deployment Infrastructure
- [ ] Progressive autonomy rollout (D44): four-stage deployment (Shadow -> Gated -> Supervised -> Autonomous), stage config in config.yaml, graduation criteria enforcement, stage history logging
- [ ] Dead-man switch: daemon writes `heartbeat.json` every reconciliation cycle, external monitor script checks for staleness (3x reconciliation interval), alerts via backup channel
- [ ] Dockerfile (Python 3.11, uv, git, minimal image)
- [ ] docker-compose.yml (vizier-daemon service + Langfuse service + PostgreSQL for Langfuse, volume mounts for workspaces/reports/ea)
- [ ] systemd unit file (`vizier.service`, Type=simple, Restart=always)
- [ ] Server setup script (`scripts/setup_server.sh`): create /opt/vizier/ directory structure, install dependencies, configure systemd
- [ ] Example .vizier/config.yaml for a target project
- [ ] EA data git repo initialization (ea/ directory as its own git repo)
- [ ] Deployment documentation (docs/DEPLOYMENT.md)

### Acceptance Criteria

**Daemon:**
- [ ] `vizier register` clones repo, reads .vizier/config.yaml, installs plugin
- [ ] `vizier start` launches daemon with all registered projects
- [ ] Multiple projects run concurrently without interference
- [ ] Resource limits prevent server overload (configurable max_concurrent_agents)
- [ ] `vizier status` shows all projects and their state
- [ ] `vizier stop` gracefully shuts down daemon (INTERRUPTED state for active specs)
- [ ] Daemon auto-restarts on crash (systemd Restart=always)
- [ ] Health check endpoint responds to HTTP GET with daemon status

**Progressive autonomy (D44):**
- [ ] Autonomy stage is configurable in config.yaml (default: Stage 1 Shadow)
- [ ] Stage 1 (Shadow): EA proposes actions but does not execute without Sultan approval
- [ ] Stage 2 (Gated): Specs require Sultan approval before Worker starts
- [ ] Stage transitions require explicit Sultan approval via EA
- [ ] Stage history is logged for auditability

**Dead-man switch:**
- [ ] heartbeat.json is updated every reconciliation cycle with timestamp, PID, project count, agent count
- [ ] External monitor script detects stale heartbeat and alerts
- [ ] Daemon restart recovers heartbeat writing

**Deployment:**
- [ ] `docker compose up` starts Vizier daemon + Langfuse + PostgreSQL with all required volumes
- [ ] Server setup script creates correct directory structure under /opt/vizier/
- [ ] systemd unit file starts daemon on boot
- [ ] Agent logs rotate without manual intervention
- [ ] .env file is loaded for API keys and secrets (never baked into image)
- [ ] DEPLOYMENT.md documents: server requirements, setup steps, configuration, monitoring

---

## Phase 8: Software Plugin (end-to-end)

**Goal:** Complete the built-in software development plugin and validate end-to-end on a real project.

### Components
- [ ] SoftwareCoder worker (file ops, bash, git, test execution)
- [ ] SoftwareQualityGate (pytest, ruff, test meaningfulness)
- [ ] Software Architect guide (feature/bugfix/refactor decomposition patterns)
- [ ] Software criteria library (tests_pass, lint_clean, type_check, no_debug_artifacts, test_meaningfulness)
- [ ] Prompt templates (worker.md, quality_gate.md, architect_guide.md)

### Acceptance Criteria
- [ ] End-to-end: DRAFT spec -> decomposition -> implementation -> review -> DONE
- [ ] Graduated retry works: model bump at 3, Pasha review at 5, re-decompose at 7
- [ ] STUCK detection works: spec stuck -> Retrospective analyzes -> decomposition
- [ ] Agent logs capture full cost/token/duration data for the entire flow
- [ ] Real project test: register a real repo, assign a real task, verify output

---

## Phase 9: Documents Plugin

**Goal:** Build the document production plugin, proving the plugin system works for non-software projects.

### Components
- [ ] DocumentWriter worker (file ops, web search, pandoc/python-docx)
- [ ] DocumentReviewer quality gate (structure validation, link checking)
- [ ] Document Architect guide (report/proposal/memo decomposition patterns)
- [ ] Document criteria library (structure_complete, facts_sourced, formatting_standards)
- [ ] Prompt templates

### Acceptance Criteria
- [ ] End-to-end: DRAFT spec -> decomposition -> writing -> review -> DONE
- [ ] Plugin system correctly loads document plugin instead of software plugin
- [ ] Worker uses document-specific tools (not bash/git)
- [ ] Quality Gate uses document-specific criteria
- [ ] Real test: produce a report from a spec
