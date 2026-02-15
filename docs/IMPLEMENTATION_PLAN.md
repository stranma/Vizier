# Vizier Implementation Plan

## Status Summary

| Phase | Name | Status | Branch |
|-------|------|--------|--------|
| 0 | Project Scaffold | Complete | `master` |
| 1 | Core Runtime + Plugin Framework + Sentinel | Pending | `feature/core-runtime` |
| 2 | Inner Loop (Worker + Quality Gate) | Pending | `feature/inner-loop` |
| 3 | Architect | Pending | `feature/architect` |
| 4 | Pasha + Orchestration | Pending | `feature/manager` |
| 5 | Retrospective | Pending | `feature/retrospective` |
| 6 | EA + Communication | Pending | `feature/ea` |
| 7 | Daemon + Multi-project | Pending | `feature/daemon` |
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
- [ ] File protocol implementation (spec CRUD, state management, file locking)
- [ ] Spec frontmatter parser (YAML frontmatter + markdown body, `@criteria/` snapshotting at creation)
- [ ] Model router (rules-based tier -> provider/model mapping via LiteLLM library, resolution order)
- [ ] Agent base class (fresh context pattern, spec reading, output writing, implicit completion on clean exit)
- [ ] Filesystem watcher (watchdog-based, event dispatch)
- [ ] Periodic reconciliation (scan all specs, verify/rebuild state from disk — events are optimization, disk is truth)
- [ ] Structured agent logging (`{agent, spec_id, model, tokens_in, tokens_out, duration_ms, cost_usd, result}` to `reports/<project>/agent-log.jsonl`)
- [ ] Sentinel policy engine (deterministic):
  - [ ] Allowlist (auto-approve known-safe tool calls, zero cost)
  - [ ] Denylist (auto-block known-dangerous tool calls, zero cost)
  - [ ] Haiku evaluator (assess ambiguous tool calls for safety, ~$0.001/call)
  - [ ] Secret pattern scanning (regex)
  - [ ] Git operation classification (safe/dangerous)
- [ ] Plugin framework:
  - [ ] `BasePlugin` abstract class
  - [ ] `BaseWorker` abstract class (allowed_tools, tool_restrictions, git_strategy)
  - [ ] `BaseQualityGate` abstract class (automated_checks, criteria library)
  - [ ] Plugin discovery via entry points
  - [ ] Prompt template renderer (Jinja2 with spec/context injection)
  - [ ] Criteria library loader (`@criteria/` reference resolution + snapshotting)
  - [ ] Tool registry with Sentinel enforcement integration

### Acceptance Criteria
- [ ] Can create, read, update spec files with correct frontmatter
- [ ] `@criteria/` references are resolved and snapshotted into spec at creation time
- [ ] State.json locking works under concurrent access
- [ ] Model router maps tiers to configured providers with correct resolution order (via `litellm.completion()`)
- [ ] Filesystem watcher detects spec file changes and dispatches events
- [ ] Reconciliation scan rebuilds correct state from disk (simulated missed events)
- [ ] Every agent invocation produces structured log entry with tokens and cost
- [ ] Sentinel allowlist auto-approves known-safe tool calls
- [ ] Sentinel denylist auto-blocks known-dangerous tool calls
- [ ] Sentinel Haiku evaluator correctly identifies bypass attempts (e.g., `python -c "import os; os.system('rm -rf /')"`)
- [ ] Agent base class enforces fresh-context pattern
- [ ] Worker completion is implicit (clean exit → REVIEW, no magic string)
- [ ] Plugin discovery finds installed plugins via entry points
- [ ] BaseWorker subclass can define tools and restrictions
- [ ] BaseQualityGate subclass can define automated checks
- [ ] Jinja2 prompt templates render with spec and context data

---

## Phase 2: Inner Loop (Worker + Quality Gate)

**Goal:** Build the Ralph-style execution loop. Worker picks a spec, produces artifacts, Quality Gate validates. Uses a stub plugin for testing. Includes CLI entry point for manual spec creation (bypass EA for testing).

### Components
- [ ] Worker agent runtime (loads plugin Worker class, runs fresh-context cycle)
- [ ] Worker bounded read-only exploration (can read any project file, must log reads beyond artifact list, cannot write beyond artifacts)
- [ ] Quality Gate agent runtime (loads plugin Quality Gate class, runs checks)
- [ ] Completion Protocol (PCC) implementation in Quality Gate (5-pass structured validation)
- [ ] Spec lifecycle state machine (READY -> IN_PROGRESS -> REVIEW -> DONE/REJECTED/INTERRUPTED)
- [ ] Graduated retry logic:
  - [ ] Retries 1-2: normal with Quality Gate feedback
  - [ ] Retry 3: bump Worker model tier
  - [ ] Retry 5: alert Pasha for spec review
  - [ ] Retry 7: Architect re-decomposes
  - [ ] Retry 10: STUCK
- [ ] INTERRUPTED state handling (daemon shutdown → IN_PROGRESS specs → INTERRUPTED → re-queued on restart)
- [ ] Tool sandbox (enforces plugin's allowed_tools via Sentinel integration)
- [ ] CLI entry point: `vizier spec create` and `vizier spec ready` for manual testing without EA
- [ ] Stub plugin `test-stub` for testing (D35): StubWorker (file_read + file_write, commit_to_main), StubQualityGate (check file exists), one criteria (`@criteria/file_exists`), prompt templates

### Acceptance Criteria
- [ ] Worker picks highest-priority READY spec
- [ ] Worker can read files beyond artifact list (read-only), logs what it read
- [ ] Worker cannot write files outside artifact list (Sentinel enforces)
- [ ] Worker creates git commit tied to spec using plugin's commit template
- [ ] Worker completion is implicit (clean exit → REVIEW transition)
- [ ] Quality Gate runs Completion Protocol: Pass 1-2 (deterministic) before Pass 3-5 (LLM-assisted)
- [ ] Quality Gate evaluates against snapshotted `@criteria/` from spec creation time
- [ ] Deterministic pass failures produce REJECTED without burning LLM tokens
- [ ] Cumulative criteria: parent spec criteria checked when relevant
- [ ] Graduated retry: model tier bumps at retry 3, Pasha alert at retry 5
- [ ] INTERRUPTED specs are re-queued as READY on daemon restart
- [ ] Rejected specs return to Worker with actionable feedback
- [ ] Spec goes STUCK after max_retries exceeded
- [ ] Fresh context: Worker has no memory of previous specs
- [ ] `vizier spec create "task description"` creates a DRAFT spec via CLI
- [ ] `vizier spec ready <spec-id>` transitions DRAFT to READY for manual testing

---

## Phase 3: Architect

**Goal:** Build the task decomposition agent that reads project context and writes detailed specs using plugin's decomposition patterns.

### Components
- [ ] Architect agent (reads project, writes sub-specs)
- [ ] Plugin decomposition pattern loading (reads plugin's architect_guide.md)
- [ ] Spec decomposition logic (parent -> children)
- [ ] `@criteria/` snapshotting (resolve and embed criteria at spec creation)
- [ ] Contract generation (domain-appropriate via plugin)
- [ ] Complexity estimation
- [ ] Criteria library integration (Architect references `@criteria/` in specs)

### Acceptance Criteria
- [ ] Architect reads DRAFT spec and produces READY sub-specs
- [ ] Sub-specs include: artifacts, contracts, acceptance criteria with snapshotted `@criteria/`
- [ ] Architect uses plugin's decomposition patterns
- [ ] Parent spec transitions to DECOMPOSED when children are created
- [ ] Complexity field is set and used by model router for Worker

---

## Phase 4: Pasha + Orchestration

**Goal:** Build the per-project orchestrator that manages agent lifecycle and reports progress.

### Components
- [ ] Pasha agent (event-driven loop + periodic reconciliation)
- [ ] Plugin loading on project startup (reads config.yaml, loads correct plugin)
- [ ] Agent spawning and lifecycle management (plugin-aware)
- [ ] Progress reporting (status.json, cycle reports)
- [ ] Escalation logic (blockers -> reports/escalations/)
- [ ] Worker/Quality Gate pipeline (Worker finishes -> Quality Gate starts)
- [ ] Graduated retry orchestration (model bumping, Pasha review, Architect re-decomposition at thresholds)
- [ ] Graceful shutdown (IN_PROGRESS specs → INTERRUPTED)

### Acceptance Criteria
- [ ] Pasha loads correct plugin based on project config
- [ ] Pasha reacts to spec lifecycle events (new DRAFT, DONE, STUCK)
- [ ] Reconciliation catches missed filesystem events
- [ ] Pasha spawns Architect for DRAFT specs
- [ ] Pasha spawns plugin's Worker for READY specs
- [ ] Pasha spawns plugin's Quality Gate for REVIEW specs
- [ ] Graduated retry: Pasha reviews at retry 5, triggers Architect re-decomposition at retry 7
- [ ] Progress reports written to reports/ directory
- [ ] Blockers escalated to escalations/ directory
- [ ] Graceful shutdown transitions IN_PROGRESS specs to INTERRUPTED

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
- [ ] EA agent (monolithic, powerful, Opus-tier — Claude Code pattern: Python event loop + fresh LLM call per message)
- [ ] Telegram bot integration (aiogram 3.x)
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
- [ ] Focus mode (`/focus Nh` — hold non-emergency notifications)
- [ ] Commit approval UI (requires_approval specs -> Telegram Approve/Reject)
- [ ] Sentinel content scanner (Haiku-tier, on-demand for untrusted web/file content)
- [ ] Sultan approval queue (dangerous ops -> EA -> Sultan -> decision)

### Acceptance Criteria
- [ ] EA receives Telegram messages and creates DRAFT specs in correct project
- [ ] EA handles all message types without architectural routing split
- [ ] EA watches reports/ and sends relevant updates to Sultan
- [ ] Escalations trigger immediate Sultan notification
- [ ] Status queries answered from status.json files across all projects
- [ ] Session mode connects Sultan directly to project Pasha
- [ ] Quick queries (`/ask`) route to Pasha and relay response
- [ ] Commitments tracked with deadlines, linked to projects and contacts
- [ ] Check-in flow creates relationships and commitments from conversation
- [ ] File checkout/checkin works via Telegram file transfer
- [ ] Cross-project tasks create DRAFT specs in multiple projects
- [ ] Focus mode holds notifications, allows emergencies through
- [ ] Inbound files from Sultan relayed to target project as spec context
- [ ] Content scanner evaluates untrusted web content for prompt injection
- [ ] GitHub Actions changes require Sultan approval via EA
- [ ] Cost summary from agent logs included in morning briefing

---

## Phase 7: Daemon + Multi-project

**Goal:** Build the server daemon that manages multiple projects.

### Components
- [ ] Daemon process (systemd-compatible)
- [ ] Project registration (`vizier register <repo-url>`)
- [ ] Per-project workspace management (clone, venv setup, plugin installation)
- [ ] Resource management (concurrent agent limits)
- [ ] CLI commands (init, register, start, stop, status)

### Acceptance Criteria
- [ ] `vizier register` clones repo, reads .vizier/config.yaml, installs plugin
- [ ] `vizier start` launches daemon with all registered projects
- [ ] Multiple projects run concurrently without interference
- [ ] Resource limits prevent server overload
- [ ] `vizier status` shows all projects and their state

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
