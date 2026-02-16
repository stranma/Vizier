# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- **D40: Atomic writes via os.replace()** -- All spec file writes now use write-then-rename pattern for crash safety. Prevents half-written files on crash or power loss. Implemented in `spec_io.py` with tests.
- **D41: VCR/Record-Replay testing** -- Cassette-based record/replay for LLM responses. `VIZIER_VCR_MODE` env var (record/replay/off). Extends D34 mock strategy with realistic test data. Cassettes stored in `tests/cassettes/`.
- **D42: JIT prompt assembly for EA** -- Dynamic prompt composition: always-loaded core (~2,500 tokens) plus conditional modules loaded by deterministic classifier. Saves ~40% on EA input tokens per call.
- **D43: Plugin MCP exposure** -- Plugins can optionally expose capabilities as MCP tools via FastMCP. EA discovers per-project tools at startup. Quick queries bypass the spec lifecycle.
- **D44: Progressive autonomy rollout** -- Four-stage deployment: Shadow (propose only) -> Gated (per-spec approval) -> Supervised (autonomous + surface all) -> Autonomous (EA filters). Measurable graduation criteria per stage.
- **D45: Langfuse observability** -- Self-hosted Langfuse for agent tracing. Native LiteLLM callback integration. Docker Compose deployment alongside daemon. Complements D28 JSONL logs.
- **Spec state-age monitoring** -- Pasha checks `time_in_state` during reconciliation to detect silently stuck specs. Plugin-configurable thresholds.
- **Dead-man switch** -- Daemon writes `heartbeat.json` every reconciliation cycle. External monitor detects stale heartbeat and alerts via backup channel.
- **Telegram slash commands** -- `/status`, `/ask`, `/checkin`, `/focus`, `/session`, `/approve`, `/budget`, `/priorities` for structured EA interactions.
- **priorities.yaml behavioral anchor** -- Sultan-maintained priorities file that EA reads on every LLM invocation for stable decision context.

### Changed

- **D22: Reconciliation interval** -- Default changed from 60 seconds to 15 seconds (recommended 10-30s). Shorter intervals compensate for ReadDirectoryChangesW unreliability on Windows.
- **D25: Repeated action detection** -- If Worker performs identical tool call 3+ consecutive times, escalate immediately to next retry threshold. Catches stuck loops that diverse-failure retry logic misses.

## [0.5.0] - 2026-02-16

Phase 4: Pasha + Orchestration. Per-project agent lifecycle management.

### Added

- **PashaOrchestrator** -- Event-driven per-project orchestrator with periodic reconciliation. Manages full spec lifecycle: DRAFT specs trigger Architect, READY specs trigger Worker, REVIEW specs trigger Quality Gate. Supports session mode for direct Sultan interaction with summary writing to `ea/sessions/`.
- **SubprocessManager** -- Asyncio-based agent subprocess management with `Semaphore` concurrency limiting, configurable per-agent timeout, crash detection, and graceful shutdown. Tracks active and completed agent processes.
- **ProgressReporter** -- Writes `status.json` (project overview), cycle reports (`YYYY-MM-DD-cycle-NNN.md`), and escalation files (`escalations/YYYY-MM-DD-spec-id.md`). All writes use atomic write-then-rename pattern.
- **Graduated retry orchestration** -- PashaOrchestrator processes REJECTED specs through graduated retry: normal retry, model bump (retry 3), Pasha alert (retry 5), Architect re-decomposition (retry 7), STUCK (retry 10). STUCK specs generate escalation files.
- **State-age monitoring** -- Detects specs stuck IN_PROGRESS beyond configurable threshold (default 30 min) with no active agent subprocess. Generates escalation files for EA pickup.
- **Graceful shutdown** -- Transitions IN_PROGRESS specs to INTERRUPTED, signals subprocess manager to reject new spawns. INTERRUPTED specs re-queued as READY on restart.

## [0.4.0] - 2026-02-16

Phase 3: Architect. Task decomposition agent with sub-spec generation.

### Added

- **Architect agent runtime** -- ArchitectRuntime extends BaseAgent to decompose DRAFT specs into READY sub-specs. Reads plugin's decomposition guide, criteria library, project constitution, and learnings. Parses structured LLM responses into sub-spec definitions.
- **Decomposition logic** -- LLM response parser extracts sub-specs with title, complexity, priority, artifacts, and @criteria/ references. Includes complexity estimation heuristic and sub-spec ID generator.
- **Re-decomposition support** -- STUCK specs (retry 7+) can be re-decomposed via the same Architect flow (STUCK -> DECOMPOSED).
- **AgentRunner.run_architect()** -- Entry point for spawning Architect as a subprocess, completing the Worker/QualityGate/Architect trinity.
- **Full lifecycle integration test** -- DRAFT -> Architect -> DECOMPOSED parent + READY children -> Worker -> QG -> DONE.

## [0.3.0] - 2026-02-16

Phase 2: Inner Loop (Worker + Quality Gate). Delivered in 6 sub-phases (2a-2f), 34 files, 318 tests.

### Added

- **Worker agent runtime** -- Fresh-context Worker that picks highest-priority READY spec, claims it (READY -> IN_PROGRESS), runs LLM completion, and transitions to REVIEW on clean exit. Supports bounded read-only exploration with logging.
- **Quality Gate runtime** -- 5-pass Completion Protocol: Pass 1 (hygiene -- debug prints, breakpoints), Pass 2 (mechanical -- plugin automated checks), Pass 3-5 (LLM-assisted review, criteria evaluation, final verdict). Deterministic failures skip LLM passes to save tokens. Writes structured feedback files on rejection.
- **Graduated retry** -- Configurable retry escalation: retries 1-2 normal with feedback, retry 3 bumps model tier (haiku -> sonnet -> opus), retry 5 alerts Pasha, retry 7 triggers re-decomposition, retry 10 marks STUCK. Repeated action detection (3+ identical calls) triggers immediate escalation.
- **Spec lifecycle management** -- INTERRUPTED state handling for graceful daemon shutdown (IN_PROGRESS -> INTERRUPTED -> READY on restart). Rejection handling with retry counter and status transitions.
- **Agent subprocess runner** -- Entry point for agent subprocesses (D37). Loads spec, plugin, creates tool registry with Sentinel, runs Worker or Quality Gate, returns structured RunResult.
- **VCR test infrastructure** -- Cassette-based record/replay for LLM calls (D41). SHA256 request hashing, JSON cassette storage, `VIZIER_VCR_MODE` env var control.
- **Stub plugin** -- Test fixture (D35/D39) with StubWorker, StubQualityGate, prompt templates, and `@criteria/file_exists`. Registered programmatically in tests.
- **CLI spec commands** -- `vizier spec create`, `vizier spec ready`, `vizier spec list` for manual spec management without EA. Auto-generates sequential spec IDs.

## [0.2.0] - 2026-02-16

Phase 1: Core Runtime + Plugin Framework + Sentinel. Delivered in 6 sub-phases (1a-1f), 76 files, 216 tests, 99% coverage.

### Added

- **Pydantic models** -- Spec, state, config, events, and logging models with strict validation and serialization. All models use frozen dataclasses or Pydantic BaseModel with type annotations.
- **File protocol** -- Spec CRUD operations (`spec_io.py`), state manager with filelock-based concurrent access (`state_manager.py`), and `@criteria/` reference resolution with snapshotting at spec creation time. All writes use atomic write-then-rename pattern (D40).
- **Model router** -- Tier-based model resolution (quick/standard/advanced/flagship) mapping to provider/model pairs via LiteLLM. Supports config-driven overrides with correct resolution order.
- **Structured agent logging** -- JSONL agent log writer producing `{agent, spec_id, model, tokens_in, tokens_out, duration_ms, cost_usd, result}` entries to `reports/<project>/agent-log.jsonl`.
- **Sentinel policy engine** -- Deterministic tool-call enforcement with three evaluation tiers: allowlist (auto-approve, zero cost), denylist (auto-block, zero cost), and Haiku evaluator for ambiguous calls. Includes secret pattern scanning (regex-based) and git operation classification (safe/dangerous).
- **Plugin framework** -- `BasePlugin`, `BaseWorker`, and `BaseQualityGate` abstract base classes. Plugin discovery via entry points (`vizier.plugins` group). Jinja2 prompt template renderer with spec/context injection. Criteria library loader for `@criteria/` reference resolution. Tool registry with Sentinel enforcement integration.
- **Agent base class** -- Fresh-context agent pattern with spec reading and output writing. Implicit completion on clean exit (no magic strings). Agent context object for runtime state.
- **Filesystem watcher** -- Watchdog-based file monitoring with event dispatch for spec file changes.
- **Periodic reconciliation** -- Full disk scan rebuilding state from filesystem truth (events are optimization, disk is truth). Default 15-second interval (D22).
