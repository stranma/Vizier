# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

## [0.1.0] - 2026-02-20

Phase 1: Spec Lifecycle. First functional delivery of the vizier-mcp MCP server: Pydantic models, 8-state spec state machine, and 6 MCP tools covering the full spec lifecycle from creation to completion.

### Added

- **Spec lifecycle tools** -- Six MCP tools allow agents to manage specs end-to-end without direct filesystem access: `spec_create` (create a spec in DRAFT), `spec_read` (retrieve spec contents and metadata), `spec_list` (list specs with optional status filter -- returns empty list, not error, when no matches), `spec_transition` (validate and execute a state change, returning `{"success": true}` on success or `{"success": false, "error": str}` with the invalid transition described), `spec_update` (modify mutable fields such as retry_count and assigned_agent while rejecting immutable fields with an error), and `spec_write_feedback` (write a JSON feedback file to `feedback/{timestamp}-{verdict}.json` for Quality Gate verdicts and rejection reasons).
- **Pydantic models** -- `Spec`, `SpecStatus`, `SpecMetadata`, `SpecSummary`, `SpecFeedback`, `SpecTransitionRequest`, `SpecCreateRequest`, and `SpecUpdateRequest` provide strict validated types for all spec data. Serialisation uses `model_dump(mode="json")` so all values are JSON-safe.
- **8-state spec state machine** -- States DRAFT, READY, IN_PROGRESS, REVIEW, REJECTED, DONE, STUCK, and INTERRUPTED with a `VALID_TRANSITIONS` dict that encodes every legal edge. Invalid transitions return a structured error naming both the current and target state. The `is_valid_transition` helper function is publicly importable for use in other tools.
- **Atomic filesystem writes** -- All spec file writes and feedback file writes use a write-then-rename pattern (`tempfile.mkstemp` + `os.replace`) so a crash or power loss mid-write never leaves a partial file on disk. The temp file is cleaned up on error.
- **YAML frontmatter spec format** -- Spec files are stored as `spec.md` with YAML frontmatter between `---` delimiters followed by optional Artifacts and Acceptance Criteria sections and a free-form body. Fully round-trips through parse and serialize without data loss.
- **Spec ID format** -- Spec IDs are auto-assigned as `NNN-slug` (3-digit zero-padded sequential counter, hyphen, lower-cased title slug truncated to 40 characters). IDs are stable and unique within a project.
- **ServerConfig** -- Pydantic model for MCP server configuration loaded via `load_config(path)`. Configures `vizier_root`, `projects_dir`, sentinel settings, file locking, startup recovery, and claim timeout. Falls back to defaults when no config file is present, reading `VIZIER_ROOT` from the environment.
- **Unit and integration tests** -- Full test coverage of all six tools and all state machine transitions, including the happy path (DRAFT -> READY -> IN_PROGRESS -> REVIEW -> DONE), rejection loop (REJECTED -> READY -> IN_PROGRESS -> REVIEW -> DONE with retry_count increment), and error paths (non-existent spec, invalid transition, immutable field update).

---

- **Deployment phase added to implementation plan** -- Phase 6 covers Dockerfile, docker-compose.yml, CI/CD workflow updates, Azure Key Vault integration (D60), health endpoint, and docs/DEPLOYMENT.md setup guide.
- **MVP Build Priority** (D80) -- Split 15 v1 tools into 11 MVP (Phase A) and 4 deferred-to-need (Phase B). Phase A: minimum to get first spec from DRAFT to DONE. Phase B: orch_scan_specs, orch_check_ready, orch_assign_worker, dag_check_dependencies -- build when multi-spec projects start. All 8 states preserved. D76-D79 decisions kept as design docs. Sentinel auto-promote set to false (Haiku 3-tier eval unchanged).
- **Architecture simplification for v1** (D75) -- Reduced tool surface from 35+ to 15 tools across 5 groups, agent roles from 7 to 4 (Vizier, Pasha, Worker, QG). Scout, Architect, and Retrospective deferred to v2.
- **One Voice Policy** (D75) -- Only Vizier communicates with the Sultan. Escalation chain: Worker -> Pasha -> Vizier -> Sultan. Prevents notification overload.
- **Pasha trigger model** (D75) -- Vizier-initiated activation replaces autonomous polling. Eliminates expensive Opus-as-doorbell-watcher pattern.
- **Sentinel Learning** (D75) -- After 3 Haiku approvals for the same command pattern in a project, auto-promote to allowlist. Stored in sentinel_learned.yaml.
- **project_get_config tool** (D75) -- Single config tool replaces 5 plugin_get_* tools. Returns project type, language, test/lint commands.
- **Crash recovery & zombie detection** (D76) -- MCP startup scan transitions orphaned IN_PROGRESS specs to INTERRUPTED. Claim timeout (default 30min) detects zombie Workers. Zombie recovery counts as retry.
- **Worker IMPOSSIBLE signal** (D77) -- New ping urgency for defective specs. Worker signals "spec is wrong" without entering retry loop. Pasha escalates to Vizier as spec_defect.
- **Sentinel error contract** (D78) -- run_command_checked returns three shapes: denied, succeeded (exit_code 0), failed (exit_code N). stdout/stderr split. Worker owns cleanup. QG does not rollback.
- **Dependency stall prevention** (D79) -- orch_check_ready returns stall_reason when dependency is STUCK. orch_assign_worker guards against unsatisfied dependencies. Pasha escalates stalls to Vizier.
- **vizier-status command spec** -- CLI command reading vizier_root for human-readable court health summary. Documented for implementation during coding phase.

### Changed

- **Graduated retry simplified** (D75) -- From 5 levels (10 retries) to 2 levels: retry 1-3 normal, retry 4+ STUCK.
- **Spec state machine simplified** (D75) -- v1 removes SCOUTED and DECOMPOSED states. DRAFT transitions directly to READY. Full state machine preserved for v2.
- **Worker self-verification** (D75) -- Uses run_command_checked directly instead of dedicated verify_tests/verify_lint/verify_types tools. Workers read learnings.md at task start.
- **Quality Gate simplified** (D75) -- Verdicts via spec_write_feedback only. Evidence system deferred to v2.
- **SOUL.md files updated** -- Vizier (One Voice + delegation), Pasha (trigger model + 2-level retry + zombie detection + IMPOSSIBLE handling + dependency stalls + QG/Worker arbitration), Worker (run_command_checked error handling + IMPOSSIBLE signal + context bridge), QG (inline verdicts + no-rollback policy)
- **openclaw.json updated** -- Pasha trigger config, spawned agent templates (worker/QG with Sonnet), one_voice_policy section

### Removed

- **v2 agent templates moved** -- Scout, Architect, Retrospective SOUL.md files moved to openclaw/workspaces/v2-deferred/
- **v2 tool stubs deleted** -- verification.py (verify_tests/verify_lint/verify_types) and research.py (research_topic) removed
- **get_relevant_learnings removed** -- Workers read learnings.md directly instead of using MCP tool
- **plugin.py renamed** -- Renamed to config_tool.py with project_get_config stub

### Deferred to v2

- Budget system (budget_track, budget_check, budget_get_summary)
- Evidence system (evidence_check, evidence_write_verdict)
- Plugin framework (5 plugin_get_* tools, BasePlugin, SoftwarePlugin, DocumentsPlugin)
- Agent behavior eval suite (D72)
- Sentinel additional tools (sentinel_check_command, sentinel_scan_content, sentinel_get_policy)
- DAG additional tools (dag_validate, dag_get_order)
- Orchestration pings (orch_scan_pings)

---

- **Ottoman Empire architecture improvements** (D67-D74) -- Eight new decisions addressing real-world weaknesses found via claude-code-ultimate-guide analysis:
  - **Sentinel enforcement via tool policy** (D67) -- Native bash/exec and web_fetch blocked by OpenClaw tool policy; agents forced through `run_command_checked` and `web_fetch_checked` MCP tools
  - **Worker mandatory self-verification** (D68) -- Workers must pass `verify_tests`, `verify_lint`, `verify_types` before REVIEW; QG reduced from 5 to 4 passes
  - **Lightweight research tool** (D69) -- `research_topic(query, depth)` for quick lookups during decomposition without spawning full Scout pipeline
  - **Learnings injection** (D70) -- `get_relevant_learnings` MCP tool; Pasha injects relevant learnings into agent spawn context
  - **Dynamic pipeline selection** (D71) -- Pasha decides which agents to spawn per spec (bugfix skips Scout/Architect, research skips Worker, etc.)
  - **Agent behavior eval suite** (D72) -- Mocked scenarios testing SOUL.md behavioral contracts (tool call sequences, decision patterns)
  - **Context management for persistent agents** (D73) -- SOUL.md memory management guidance + OpenClaw compaction settings
  - **Scope guidance for Architect** (D74) -- Soft guidance for 1-3 files per sub-spec
- **Verification tool scaffolds** -- `vizier-mcp/vizier_mcp/tools/verification.py` (verify_tests, verify_lint, verify_types)
- **Research tool scaffold** -- `vizier-mcp/vizier_mcp/tools/research.py` (research_topic)
- **Sentinel-wrapped execution tools** -- `run_command_checked` and `web_fetch_checked` added to sentinel.py
- **Learnings injection tool** -- `get_relevant_learnings` added to orchestration.py
- **OpenClaw compaction settings** -- `openclaw/config/openclaw.json` configured for persistent agent sessions
- **Lobster workflow runtime** -- Documented as future enhancement (ARCHITECTURE.md section 12.1). Lobster is an OpenClaw plugin for deterministic multi-step pipelines with approval gates. Identified fit for Worker self-verification, Sentinel command execution, Pasha agent spawn, and Retrospective approval flows. Adopt after core MCP tools are implemented.

### Changed

- **SOUL.md updates** -- Vizier (memory management), Pasha (pipeline flexibility, learnings injection, memory), Architect (scope guidelines, research_topic), Worker (mandatory self-verification, run_command_checked, web_fetch_checked), Quality Gate (4-pass protocol), Retrospective (data sources, learnings format)
- **ARCHITECTURE.md expanded** -- New tool groups (verification, sentinel-wrapped, research, learnings), updated SOUL.md sketches, sentinel enforcement model (5.4), state machine shortcut annotations, agent behavior eval section

- **Vizier-on-OpenClaw architecture spec** (D63) -- Complete architecture document (`docs/ARCHITECTURE.md`) specifying the new system: OpenClaw as runtime, Vizier MCP server for domain logic, all agents as OpenClaw sessions, per-project Sentinels via MCP tools
- **Vizier MCP server scaffold** -- `vizier-mcp/` package with module structure for tools (spec, sentinel, orchestration, DAG, evidence, plugin, budget), models, sentinel policy engine, and plugins
- **OpenClaw workspace templates** -- SOUL.md files for all 7 agent roles (Vizier, Pasha, Scout, Architect, Worker, Quality Gate, Retrospective) plus agent and config scaffolds
- **New decisions D63-D66** -- OpenClaw architectural reset, EA renamed to Vizier, all inner agents as OpenClaw sub-sessions, per-Pasha Sentinels via MCP tools

### Changed

- **CLAUDE.md updated** for new project structure -- repository layout, development commands, testing paths, context recovery, and consistency check sections updated for vizier-mcp; PCC workflow and development methodology preserved
- **README.md rewritten** for Vizier-on-OpenClaw architecture
- **pyproject.toml rewritten** -- workspace now points to `vizier-mcp/`; old workspace members (`libs/*`, `apps/*`, `plugins/*`) removed

### Removed

- **Full codebase removal** (D63) -- Removed `libs/core/`, `apps/daemon/`, `apps/cli/`, `plugins/software/`, `plugins/documents/`, `tests/`, `scripts/`, `src/`. All domain logic will be ported to the MCP server from git history. Old architecture docs removed (AGENT_PROTOCOL.md, AGENT_SPECS.md, FILE_PROTOCOL.md, TECH_STACK.md, IMPLEMENTATION_PLAN.md, SPEC_FORMAT.md, AGENT_PROMPTS.md, USE_CASES.md, DEPLOYMENT.md). Docker/systemd deployment files removed (replaced by OpenClaw deployment).
- **Agent system reset (D46)** -- Deleted the entire first-generation agent layer: BaseAgent, AgentRunner, all agent runtimes (Architect, Worker, QualityGate, Scout, Retrospective, EA), Pasha orchestrator, lifecycle management (SpecLifecycle, GraduatedRetry), AgentLogger, BaseWorker, BaseQualityGate, plugin implementations (SoftwarePlugin, DocumentsPlugin), VizierDaemon, and Heartbeat. The rigid prompt-in/response-out pattern could not support tool use, supervisor interaction, or dynamic decision-making. Infrastructure preserved: models, file protocol, LLM factory, model router, secrets, Sentinel, watcher, tools, plugin framework, daemon config/health/telegram, CLI, deployment. System will be rebuilt with tool-using, interactive agents.

### Added

- **Agent Protocol Design (Phase 13)** -- Complete specification for the rebuilt agent system: AGENT_PROTOCOL.md with 3 machine-verifiable contracts (Message Schema, Tool-use Policy, State Machine Invariants), USE_CASES.md with 15 BDD scenarios, updated AGENT_SPECS.md, and 13 new decisions (D47-D59).
- **AgentRuntime (Phase 14)** -- Tool-using agent runtime wrapping the Anthropic Python SDK (`client.messages.create(tools=...)`). Includes Sentinel PreToolUse hook, Loop Guardian (deterministic repeat detection + Haiku checkpoint), Golden Trace writer (trace.jsonl per spec), budget tracker (80%/100% thresholds), and 8 Contract A Pydantic message types (D54).
- **Domain Tools (Phase 15)** -- 10 tools with Anthropic tool_use JSON Schema definitions: read_file, write_file (with WriteSetChecker glob enforcement per D55), edit_file, bash, glob, grep, git, run_tests, web_search. All return structured tool_result on errors.
- **State + Communication Tools (Phase 16)** -- Orchestration tools: create_spec, update_spec_status (with Contract C invariant enforcement), read_spec, list_specs, write_feedback, delegation tools, escalation tools, request_more_research (D48), ping_supervisor (D50), send_message, send_briefing, spawn_agent. DAG validator with topological sort (D52). Adaptive reconciliation (D58). Evidence completeness checker.
- **EA Agent (Phase 17)** -- Rebuilt EA as tool-using Claude instance (Opus, 6 tools). JIT prompt assembly with core + conditional modules. Project capability summary reader (D59). Telegram integration.
- **Pasha Orchestrator (Phase 18)** -- Rebuilt Pasha as tool-using Claude instance with event-driven loop, DAG-aware scheduling (D52), ping handling (D50), evidence completeness validation, adaptive reconciliation (D58), graduated retry orchestration, and graceful shutdown.
- **Inner Loop Agents (Phase 19)** -- Four tool-using agents: Scout (Sonnet, 20K budget, 4 tools, LLM-based triage), Architect (Opus, 80K budget, 9 tools, PROPOSE_PLAN with DAG), Worker (Sonnet/Opus, 100K budget, 13 tools, glob write-set enforcement), Quality Gate (Sonnet/Opus, 30K budget, 9 tools, mandatory run_tests before LLM passes, Opus escalation for HIGH complexity per D49).
- **Plugin Rebuild (Phase 20)** -- Extended BasePlugin with worker_write_set, required_evidence, system_prompts, tool_overrides properties. SoftwarePlugin: write-set (`src/**/*.py`, `tests/**/*.py`, etc.), evidence (test_output, lint_output, type_check_output, diff). DocumentsPlugin: write-set (`docs/**`, `templates/**`, etc.), evidence (link_check_output, structure_validation, rendered_preview_path). Entry points registered.
- **Retrospective Agent (Phase 21)** -- Rebuilt Retrospective with three analytical modules: trace_analyzer (Golden Trace analysis, tool frequency, error/escalation detection), metrics (rejection rate, stuck rate, average retries), debt_register (persistent JSON tracking with add/resolve/severity escalation). Opus model, 50K budget, 6 tools.
- **Golden Path Integration Tests (Phase 22)** -- 18 mocked end-to-end tests covering: happy path (EA->Scout->Worker->QG->DONE), escalation path (Worker stuck, graduated retry, STUCK), rejection loop (QG rejects, Worker retries), DAG scheduling (dependency gating, cycle detection), graceful shutdown/recovery, budget enforcement, evidence completeness.

- **EA conversation history** -- The EA now maintains persistent, multi-turn conversation history across messages and bot restarts. User and assistant turns are stored in `ea/sessions/conversation.jsonl` (append-only JSONL). The last 10 turns are included in every LLM call for general messages, enabling the EA to reference earlier context in the same conversation.
- **ConversationLog** -- New `ConversationLog` class with append-only JSONL storage, configurable recent-turn retrieval, and automatic rotation at 1000 lines (previous log renamed to `conversation.jsonl.1`). Corrupt lines are skipped with a warning instead of failing.
- **ConversationTurn** -- New Pydantic model recording timestamp, role (user/assistant), content, message category, and arbitrary metadata per turn.
- **Telegram reply context forwarding** -- When Sultan replies to a previous bot message in Telegram, the quoted text (up to 200 chars) is prepended as `[Replying to: ...]` so the EA sees the referenced context without requiring the user to repeat it.
- **E2E smoke test script** -- `scripts/e2e_smoke_test.py` tests a live deployment via the Telegram Bot API. Verifies status responses, general greetings, and conversation continuity (bot remembers a "secret word" from a prior message). Marked `@pytest.mark.production` so it is excluded from CI runs.
- **EA stateless gap postmortem** -- `docs/postmortem/2026-02-17-ea-stateless-gap.md` documents the root cause (no conversation log despite `sessions/` directory existing in code), impact (no cross-message context), resolution, and process improvements for future phases.

- **Docker deployment** -- Docker is now the primary deployment method. Multi-stage Dockerfile with gh CLI (for Scout agent), curl (for healthcheck), and entrypoint script that runs `vizier init` on first boot.
- **Docker Compose rewrite** -- Fixed critical volume overlay bug where `vizier-config` named volume destroyed config files on first run. Config files now use bind mounts from `/opt/vizier/config/`; runtime data uses named volumes. Langfuse services moved behind `observability` profile so `docker compose up -d` starts only the daemon.
- **CD pipeline with GHCR** -- Deploy workflow now builds Docker image, pushes to GitHub Container Registry with SHA and `latest` tags, then SSHes to server to pull and restart via `docker compose up -d`.
- **HTTP-based heartbeat monitor** -- `check_heartbeat.sh` now queries the health endpoint via HTTP instead of reading `heartbeat.json` from the filesystem, making it work in both Docker and bare-metal deployments.
- **Migration script** -- `scripts/migrate_to_docker.sh` handles one-time migration from systemd bare-metal to Docker: stops systemd service, copies config files, pulls image, starts container, verifies health.
- **Docker entrypoint** -- `scripts/entrypoint.sh` initializes the Vizier directory on first boot and exec's the daemon as PID 1 for proper signal handling.

- **Health check server wired into daemon startup** -- HealthCheckServer is now created and started during `VizierDaemon.run()`, responding at the configured port (default 8080). Stops cleanly on daemon shutdown.
- **Telegram transport wired into daemon startup** -- TelegramTransport is now created during `VizierDaemon.run()` when a bot token is available (from `config.yaml` or secret store). Skips gracefully with a warning log when no token is configured.
- **Startup status lines** -- `vizier start` now prints health check URL and Telegram configuration status.

- **Scout agent for prior art research** -- New agent that runs on DRAFT specs before the Architect. Searches GitHub repos, PyPI, and npm for existing solutions, then writes a structured `research.md` report. Deterministic keyword classifier triages specs into RESEARCH or SKIP paths (zero LLM cost for bug fixes and refactors). Architect reads the report during decomposition, enabling sub-specs that leverage existing libraries instead of building from scratch.
- **SCOUTED spec state** -- New lifecycle state between DRAFT and DECOMPOSED. DRAFT specs now route to Scout (not directly to Architect). Specs can still bypass Scout via direct DRAFT -> DECOMPOSED transition for backwards compatibility.
- **Plugin scout guides** -- Software and Documents plugins provide domain-specific research guidance to the Scout agent (library evaluation criteria, template sources, etc.).
- **Secret management system** -- SecretStore protocol with pluggable backends: Azure Key Vault (production) and .env file (dev/CI fallback). Composite store chains multiple backends with priority ordering. Daemon initializes the secret store at startup and sanitizes os.environ so agent subprocesses cannot read API keys from the environment.
- **LLM callable factory** -- Creates closure-captured LLM callables where the API key lives in the closure scope, never in os.environ or agent context. Supports Anthropic, OpenAI, and Azure providers via `PROVIDER_KEY_MAP`.
- **Secret check tool for agents** -- Agents can verify whether required secrets (e.g., GITHUB_TOKEN) are configured without ever seeing the actual value. Returns metadata only (exists, has_value).
- **Tool executor with scoped secret injection** -- Subprocess execution that injects only the secrets explicitly allowed for each tool type (e.g., git gets GITHUB_TOKEN but not ANTHROPIC_API_KEY). Secrets exist only for the lifetime of the subprocess.
- **Sentinel denylist: environment exfiltration patterns** -- Blocks `printenv`, `env`, `env |`, `env >`, `os.environ`, `process.env`, and shell variable expansion of sensitive key names (KEY, TOKEN, SECRET, PASSWORD, CREDENTIAL). Prevents agents from reading secrets via command execution.
- **CLI secret commands** -- `vizier secret list` (show configured secret names with status), `vizier secret check <key>` (verify a specific secret), `vizier secret set <key>` (securely set a value in .env with hidden input prompt).
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

- **CD pipeline switched to Docker** -- Deploy workflow no longer SSHes to run `git pull` and `systemctl restart`. Instead builds a Docker image, pushes to GHCR, and restarts the container on the server.
- **Deployment docs rewritten for Docker** -- Docker is now the primary deployment method. Bare-metal instructions replaced with Docker quick start, volume design rationale, and migration guide.
- **Heartbeat monitor uses HTTP** -- `check_heartbeat.sh` parameters changed from `(vizier_root, max_age)` to `(health_url, max_age)`.

- **Sentinel permissions alignment** -- Broadened denylist to block `git clean` (all variants), `git config`, `git init`, `git restore`, `git worktree`, and `sudo`. Added read-only git commands (`blame`, `reflog`, `describe`, `shortlog`, `rev-list`, `stash`, `fetch`, `pull`, `add`, `remote`, `tag`) to allowlist for zero-cost approval. Aligned git classifier safe/dangerous patterns. Expanded SoftwareCoder `tool_restrictions` to cover `push -f`, `reset --hard`, `clean`, `config`, `init`, `restore`, `rebase -i`, `branch -D`, `checkout .`. Autonomous agents now deny commands that require human confirmation in the IDE.
- **D22: Reconciliation interval** -- Default changed from 60 seconds to 15 seconds (recommended 10-30s). Shorter intervals compensate for ReadDirectoryChangesW unreliability on Windows.
- **D25: Repeated action detection** -- If Worker performs identical tool call 3+ consecutive times, escalate immediately to next retry threshold. Catches stuck loops that diverse-failure retry logic misses.
- **Daemon config: Azure Key Vault URL** -- Added `azure_vault_url` field to DaemonConfig for configuring the secret store backend at server level.

### Fixed

- **Sentinel allowlist: `git push -f` bypass** -- The allowlist pattern for `git push` was incorrectly matching `push -f` and `push --force` as safe, bypassing the denylist. Force-push commands now correctly fall through to denylist evaluation.
- **CompositeSecretStore.is_non_empty() consistency** -- Method now returns `True` only when at least one backend store is non-empty, consistent with `SecretStore` protocol semantics.

## [0.10.0] - 2026-02-16

Phase 9: Documents Plugin.

### Added

- **DocumentsPlugin** -- Document production plugin proving plugin system works for non-software domains. Registers as `documents` plugin via entry points.
- **DocumentWriter** -- Worker agent with file_read, file_write, and web_search tools (no bash or git). Uses commit_to_main git strategy. Document-focused prompt with structure planning, source citation, and formatting instructions.
- **DocumentReviewer** -- Quality gate with output_exists and no_placeholders automated checks. Evaluates structure, content completeness, factual accuracy, and formatting consistency.
- **Document Architect Guide** -- Decomposition patterns for Report, Proposal, and Memo document types with complexity guidelines (Low/Medium/High).
- **Document criteria library** -- Three criteria files: structure_complete (section presence and order), facts_sourced (citation and attribution), formatting_standards (consistent headings, lists, tables).
- **63 new tests** -- 53 unit tests across 5 test classes + 10 integration tests across 2 test classes. Full lifecycle coverage: DRAFT -> decompose -> write -> review -> DONE.

### Changed

- **Version sync** -- All plugin packages bumped to 0.10.0 (software and documents).

## [0.8.0] - 2026-02-16

Phase 7: Daemon + Multi-project + Deployment. Phase 8: Software Plugin (end-to-end).

### Added

- **VizierDaemon** -- Asyncio event loop managing multiple project Pasha orchestrators. Per-project workspace management with concurrent agent limits. Heartbeat dead-man switch writes heartbeat.json every reconciliation cycle. Graceful shutdown via SIGINT/SIGTERM signal handlers. Single reconciliation cycle mode for testing.
- **DaemonConfig** -- Server-wide configuration with YAML loading and environment variable substitution (`${VAR}` syntax). Configurable: vizier_root, max_concurrent_agents, reconciliation_interval, monthly_budget, health_check_port, log rotation, progressive autonomy stage.
- **ProjectRegistry** -- YAML-persisted project registration with add/remove/get/active_projects operations. Atomic writes via os.replace(). Per-project plugin and active/inactive status.
- **TelegramTransport** -- Thin aiogram 3.x adapter connecting Sultan's Telegram messages to EA runtime. User ID allowlist for authorization. Message splitting for Telegram's 4096-char limit. Document handling with captions.
- **HealthCheckServer** -- Minimal asyncio HTTP server returning daemon status as JSON on GET /health. Configurable port and host.
- **CLI daemon commands** -- `vizier init` (create directory structure), `vizier register` (add project), `vizier start` (launch daemon), `vizier stop` (graceful shutdown via PID), `vizier status` (show daemon and project state).
- **Deployment infrastructure** -- Dockerfile (Python 3.11 + uv + git), docker-compose.yml (vizier-daemon + Langfuse + PostgreSQL), systemd unit file (Type=simple, Restart=always), server setup script, heartbeat monitoring script, deployment documentation.
- **Progressive autonomy config (D44)** -- Four-stage configuration (Shadow/Gated/Supervised/Autonomous) with stage history logging. Default Stage 1 (Shadow).
- **SoftwareCoder** -- Worker agent for software development tasks. Allowed tools: file_read, file_write, bash, git. Security restrictions block destructive commands (rm -rf, sudo, pipe-to-shell, push --force, reset --hard). Uses branch_per_spec git strategy.
- **SoftwareQualityGate** -- Quality gate with three automated checks: pytest (tests_pass), ruff check (lint_clean), pyright (type_check). LLM-based review validates correctness, test coverage, code quality, and edge cases.
- **SoftwarePlugin** -- BasePlugin implementation registering SoftwareCoder and SoftwareQualityGate. Default model tiers: sonnet for worker/quality_gate, opus for architect.
- **Architect guide** -- Software-specific decomposition patterns for feature implementation, bug fixes, and refactoring. Complexity guidelines (low/medium/high) with file count heuristics.
- **Criteria library** -- Five criteria loaded from markdown files via CriteriaLibraryLoader: tests_pass, lint_clean, type_check, no_debug_artifacts, test_meaningfulness.
- **Plugin entry point** -- Registered via `[project.entry-points."vizier.plugins"]` for automatic discovery.

## [0.7.0] - 2026-02-16

Phase 6: EA + Communication. Sultan-facing Executive Assistant with full communication infrastructure.

### Added

- **EARuntime** -- Monolithic, Opus-tier Executive Assistant agent. Handles all Sultan communication: delegation, status queries, quick queries, control commands, focus mode, briefings, and general LLM-backed conversation. Uses JIT prompt assembly (D42) for efficient context window usage.
- **MessageClassifier** -- Deterministic message classifier using regex, keyword matching, and slash command detection. Zero LLM cost for routing. Classifies into 15 message categories: delegation, status, control, session, briefing, checkin, quick_query, focus, approval, budget, priorities, file_ops, cross_project, direct_qa, general.
- **PromptAssembler** -- JIT prompt assembly (D42). Always-loaded core module (~2,500 tokens) plus 9 conditional modules (checkin, file_ops, calendar, cross_project, budget, briefing, session, approval, proactive) loaded based on message classification. Reads priorities.yaml on every invocation.
- **BudgetEnforcer** -- Cost budget enforcement (D33). Three-tier thresholds: alert at 80%, degrade to cheapest model at 100%, pause non-critical work at 120%. Reads agent-log.jsonl to compute spending. Sultan can override any threshold.
- **CommitmentTracker** -- CRUD operations for Sultan's commitments with deadlines, project links, and status tracking. Atomic YAML writes via os.replace(). Lists active and overdue commitments.
- **RelationshipTracker** -- CRUD operations for contacts with role, open commitments, and last interaction date. Finds overdue follow-ups by days threshold. Case-insensitive name search.
- **ContentScanner** -- Sentinel extension for untrusted content. Deterministic regex patterns detect prompt injection attempts (6 patterns). URL scanning flags URL shorteners and data/javascript URIs. Optional Haiku-tier LLM for ambiguous content analysis. Fail-cautious: marks suspicious on LLM failure.
- **EA data models** -- Commitment, Relationship, Priority, PrioritiesConfig, BriefingConfig, CheckoutRecord, CheckinRecord, FocusMode, BudgetConfig. All with Pydantic validation and JSON serialization.
- **Focus mode** -- Hold non-emergency notifications for configurable duration. Control and approval commands bypass focus. Release returns held messages.
- **Morning briefing generator** -- Structured briefing with priorities, overdue commitments, active commitments, escalations, and cost summary from agent logs.

## [0.6.0] - 2026-02-16

Phase 5: Retrospective. Meta-improvement agent that learns from failures.

### Added

- **RetrospectiveAnalysis** -- Analyzes project specs for failure patterns: stuck specs (exhausted retries), high retry counts (3+), rejected specs, and feedback file themes (test failures, code quality, type errors). Computes aggregate SpecMetrics including cost-per-spec from agent logs.
- **RetrospectiveRuntime** -- LLM-driven analysis agent extending BaseAgent. Parses LEARNING:/PROPOSAL: markers from LLM response. Appends learnings to `.vizier/learnings.md` (append-only, never overwrites). Writes proposals to `.vizier/proposals/` with mandatory PENDING status requiring Sultan approval.
- **AgentRunner.run_retrospective()** -- Entry point for spawning Retrospective as a subprocess, completing the full agent set (Worker, QualityGate, Architect, Retrospective).
- **Cost analysis** -- SpecMetrics includes total_cost_usd, cost_per_spec, avg_duration_ms, and total_agent_calls computed from agent-log.jsonl entries.

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
