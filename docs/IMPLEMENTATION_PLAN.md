# Vizier MCP Server -- Implementation Plan

## Status Summary

| Phase | Name | Status | Tools |
|-------|------|--------|-------|
| 1 | Spec Lifecycle | Complete | spec_create, spec_read, spec_list, spec_transition, spec_update, spec_write_feedback |
| 2 | Sentinel | Complete | sentinel_check_write, run_command_checked, web_fetch_checked |
| 3 | Orchestration | Complete | orch_write_ping, project_get_config |
| 4 | Integration | Complete | Wire FastMCP server, end-to-end test |
| 5 | OpenClaw Connection | Complete | SOUL.md tuning, OpenClaw config, setup guide |
| 6 | Deployment | Complete | Dockerfile, docker-compose, CI/CD, deployment guide |
| 7 | OpenClaw + Telegram Deployment | Complete | openclaw service, Telegram bot, dual health checks, setup script |
| 8 | Observability | Complete | system_get_logs, system_get_errors (+ bug fix: web_fetch_checked role enforcement, JSONL logging) |
| 9 | Self-Diagnosis | Complete | system_get_status, spec_analytics |

---

## Phase 1: Spec Lifecycle

**Goal:** Pydantic models for specs + 6 MCP tools implementing the spec state machine (8 states, all transitions).

**Deliverables:**
- [x] Pydantic models: Spec, SpecStatus, SpecSummary, SpecFeedback, SpecTransition
- [x] State machine: 8 states (DRAFT, READY, IN_PROGRESS, REVIEW, REJECTED, DONE, STUCK, INTERRUPTED), valid transitions
- [x] spec_create: create spec in DRAFT state
- [x] spec_read: read spec contents and metadata
- [x] spec_list: list specs with optional status filter
- [x] spec_transition: validate and execute state transitions
- [x] spec_update: update mutable spec fields (retry count, assigned agent, etc.)
- [x] spec_write_feedback: write QG feedback or rejection reason
- [x] Filesystem I/O: atomic writes (os.replace), spec directory layout
- [x] Unit tests for all tools and state machine
- [x] Integration test: spec DRAFT -> READY -> IN_PROGRESS -> REVIEW -> DONE

**Acceptance Criteria:**
- AC-1: spec_transition called with every valid transition from ARCHITECTURE.md section 10 returns {"success": true}. VALID_TRANSITIONS dict matches the 8-state diagram exactly.
- AC-2: spec_transition called with any invalid (from, to) pair returns {"success": false, "error": str} where the error contains the from_status and to_status values.
- AC-3: All spec file writes use write-then-rename (os.replace via tempfile). Verified by source inspection and tests confirming atomic behavior.
- AC-4: spec_list(project_id, status_filter="READY") returns only READY specs. status_filter=None returns all. No matching specs returns empty list (not error).
- AC-5: spec_write_feedback writes a JSON file to feedback/{timestamp}-{verdict}.json containing spec_id, verdict, feedback, reviewer, created_at. File is loadable by SpecFeedback model.
- AC-6: spec_create creates a spec in DRAFT state, assigns a unique spec_id (NNN-slug format), creates spec.md at the correct path, returns spec_id.
- AC-7: spec_read for existing spec returns Spec dict with correct metadata and body. Non-existent spec_id returns {"error": str} (not exception).
- AC-8: Integration happy path: DRAFT -> READY -> IN_PROGRESS -> REVIEW -> DONE using 6 tools in one test. Spec file on disk reflects status after each transition.
- AC-9: Integration rejection loop: REJECTED -> feedback -> READY -> IN_PROGRESS -> REVIEW -> DONE. Feedback file present on disk. retry_count incremented.
- AC-10: spec_update modifies mutable fields (retry_count, assigned_agent) and rejects immutable fields with error. Non-existent spec returns error.

**PIRR Acknowledgments (WARN items):**
- Spec-Plan Alignment WARN: All deliverables now have covering criteria (AC-1 through AC-10).
- Architectural Decision Coverage WARN: Spec ID format is NNN-slug (auto-incremented, 3-digit zero-padded). File locking deferred to Phase 4 server wiring. Feedback files are JSON with SpecFeedback schema. Spec files use YAML frontmatter between --- delimiters.

### Phase Completion Steps

> After this phase, execute the Phase Completion Checklist (steps -2 through 10 from CLAUDE.md): PIRR as pre-implementation gate, then sync remote, pre-commit hygiene, commit & push, parallel validation (code-quality-validator + test-coverage-validator + acceptance-criteria-validator), implementation plan check, docs-updater for documentation + changelog, create PR, verify CI, code review with code-reviewer agent, phase handoff note. Consult the Failure & Rollback Protocol if any step fails.

---

## Phase 2: Sentinel

**Goal:** Policy engine + 3 MCP tools for security enforcement (write-set validation, command checking, web fetch scanning).

**Deliverables:**
- [x] Pydantic models: SentinelPolicy, SentinelRule, WriteSetPattern, CommandCheckResult, WebFetchResult
- [x] Policy engine: load project sentinel.yaml, evaluate allowlist -> denylist -> Haiku
- [x] sentinel_check_write: validate file path against project write-set
- [x] run_command_checked: validate command, execute, return three-shape result (D78)
- [x] web_fetch_checked: fetch URL, scan content for injection, return result
- [x] Haiku evaluator: mock in tests, real Haiku call for ambiguous commands
- [x] Unit tests for all tools and policy evaluation tiers
- [x] Integration test: command allow/deny/Haiku flow

**Acceptance Criteria:**
- AC-S1: SentinelPolicy loads from a project's sentinel.yaml file. Missing file returns a sensible default policy (empty allowlist, empty denylist, empty write-set). Malformed YAML returns {"error": str} (not exception).
- AC-S2: sentinel_check_write with a path matching write-set glob returns {"allowed": true}. Path not matching returns {"allowed": false, "reason": str}. Glob patterns support `**`, `*`, and `?` wildcards. No `content` parameter -- write-set is path-only (matching ARCHITECTURE.md section 3.1).
- AC-S3: run_command_checked with an allowlisted command executes it and returns {"allowed": true, "exit_code": 0, "stdout": str, "stderr": str}. No LLM call made.
- AC-S4: run_command_checked with a denylisted command returns {"allowed": false, "reason": str}. No execution occurs. No LLM call made.
- AC-S5: run_command_checked with an ambiguous command (not in allowlist or denylist) calls the Haiku evaluator. If Haiku returns ALLOW, command executes. If DENY, returns {"allowed": false, "reason": str}.
- AC-S6: run_command_checked for a command that executes but fails returns {"allowed": true, "exit_code": N, "stdout": str, "stderr": str} where N != 0.
- AC-S7: web_fetch_checked fetches a URL and returns {"safe": true, "content": str, "status_code": 200} for clean content. Content containing prompt injection patterns (at minimum: "ignore previous instructions", "you are now", "disregard your system prompt", "SYSTEM:", "assistant:") returns {"safe": false, "reason": str}. HTTP 4xx/5xx responses are treated as fetch failures (see AC-S8).
- AC-S8: web_fetch_checked for a URL that fails to fetch (connection error, DNS failure, or HTTP status >= 400) returns {"safe": true, "content": "", "status_code": N, "error": str} where N is the HTTP status or 0 for connection errors.
- AC-S9: Haiku evaluator is mocked in all tests (no real API calls). Fail-closed: if Haiku call fails, command is denied.
- AC-S10: Integration test: command flows through allowlist -> execute, denylist -> deny, ambiguous -> Haiku -> execute/deny. All three paths verified in one test.
- AC-S11: Denylist entries support both simple strings and {pattern: regex, reason: str} objects.
- AC-S12: role_permissions from sentinel.yaml are checked: agent with can_bash=false gets denied for run_command_checked. Agent role absent from role_permissions defaults to deny (fail-closed).

**PIRR Acknowledgments (WARN items):**
- Deployment Readiness WARN: sentinel.yaml is a per-project config file loaded from disk. No deployment artifacts needed beyond the code. Production deployment is Phase 6.
- Architectural Decision Coverage WARN: web_fetch_checked uses regex-based prompt injection scanning (not Haiku). Haiku evaluator is only used for ambiguous commands. This matches ARCHITECTURE.md section 5.
- sentinel_check_write content parameter WARN: Stub had `content` parameter not in ARCHITECTURE.md section 3.1. Resolved by removing `content` -- write-set is path-only validation per architecture.
- httpx dependency WARN: Added `httpx>=0.27.0` to explicit dependencies. Previously only available as transitive dep of fastmcp.
- Malformed YAML error shape WARN: AC-S1 updated to specify {"error": str} return shape (matching Phase 1 convention).
- Missing role default WARN: AC-S12 updated to specify fail-closed default when agent_role absent from role_permissions.

### Phase Completion Steps

> After this phase, execute the Phase Completion Checklist (steps -2 through 10 from CLAUDE.md).

---

## Phase 3: Orchestration

**Goal:** 2 remaining MVP tools: supervisor pings and project configuration.

**Deliverables:**
- [x] orch_write_ping: write ping file with urgency (QUESTION, BLOCKER, IMPOSSIBLE)
- [x] project_get_config: load and return project config.yaml
- [x] Pydantic models: PingMessage, ProjectConfig
- [x] Unit tests for both tools
- [x] Integration test: Worker writes ping, ping file appears in correct location

**Acceptance Criteria:**
- AC-O1: orch_write_ping accepts config, project_id, spec_id, urgency, message. Valid urgencies are QUESTION, BLOCKER, IMPOSSIBLE. Returns {"written": true, "path": str} where path is the ping file location and matches the AC-O2 path formula.
- AC-O2: orch_write_ping writes a JSON file to {projects_dir}/{project_id}/specs/{spec_id}/pings/{timestamp}-{urgency}.json containing spec_id, urgency, message, created_at.
- AC-O3: orch_write_ping with invalid urgency returns {"error": str} without writing a file. Non-existent project or spec returns {"error": str}.
- AC-O4: project_get_config loads {projects_dir}/{project_id}/config.yaml and returns all fields as a dict. Missing config.yaml returns {"type": null, "settings": {}} (sensible default).
- AC-O5: project_get_config for non-existent project returns {"error": str}. Malformed YAML returns {"error": str}.
- AC-O6: PingMessage model validates urgency against allowed enum values. PingUrgency enum has exactly QUESTION, BLOCKER, IMPOSSIBLE.
- AC-O7: Integration test: orch_write_ping creates a file, file is valid JSON loadable as PingMessage model, urgency and message match inputs. Two pings for the same spec with different urgencies both produce files without collision.
- AC-O8: Cumulative: all Phase 1 (AC-1 through AC-10) and Phase 2 (AC-S1 through AC-S12) acceptance criteria still pass.

**PIRR Acknowledgments (WARN items):**
- AC-O4 default return shape WARN: Missing config.yaml returns `{"type": null, "settings": {}}` matching the stub's docstring return shape of `{"type": str, "settings": dict}` with null type.
- AC-O1 project_id input WARN: AC-O1 updated to include `config` and `project_id` as required parameters. ARCHITECTURE.md section 3.1 omitted project_id from the inputs table but AC-O2's path formula requires it. Phase 3 tools take `config: ServerConfig` as first parameter consistent with Phase 1/2 convention.
- D77 vs D80 IMPOSSIBLE conflict WARN: D77 takes precedence over D80's drop recommendation. IMPOSSIBLE is implemented as a distinct urgency value because ARCHITECTURE.md section 4.2 Pasha SOUL.md references IMPOSSIBLE with specific handling logic, and the semantic distinction between "I need help" (BLOCKER) and "the spec is defective" (IMPOSSIBLE) is worth the minimal implementation cost.
- Concurrent ping coverage WARN: AC-O7 updated to include two-ping collision test. Path-return verification is covered by AC-O1 requiring the path matches the AC-O2 formula.

### Phase Completion Steps

> After this phase, execute the Phase Completion Checklist (steps -2 through 10 from CLAUDE.md).

---

## Phase 4: Integration

**Goal:** Wire all 11 tools into FastMCP server. End-to-end test of full spec lifecycle.

**Deliverables:**
- [x] FastMCP server (server.py) registering all 11 tools
- [x] Server startup/shutdown lifecycle
- [x] End-to-end test: spec goes DRAFT -> READY -> IN_PROGRESS -> REVIEW -> DONE using all relevant tools
- [x] End-to-end test: spec goes through REJECTED -> retry -> DONE path
- [x] End-to-end test: spec reaches STUCK after max retries

**Acceptance Criteria:**
- AC-I1: create_server(config) returns a FastMCP instance with exactly 11 tools registered. list_tools() returns all 11 by name.
- AC-I2: Each of the 11 tools is callable via mcp.call_tool(name, args) and returns the expected result shape (not an error for valid inputs).
- AC-I3: End-to-end happy path: spec_create -> spec_transition DRAFT->READY -> spec_transition READY->IN_PROGRESS -> spec_transition IN_PROGRESS->REVIEW -> spec_write_feedback -> spec_transition REVIEW->DONE. All via call_tool.
- AC-I4: End-to-end rejection path: spec through REVIEW -> REJECTED -> spec_write_feedback -> spec_transition REJECTED->READY -> IN_PROGRESS -> REVIEW -> DONE. retry_count incremented.
- AC-I5: End-to-end STUCK path: spec_transition READY->STUCK returns success. Spec status is STUCK.
- AC-I6: Config injection: tools receive ServerConfig via closure. Tool functions that need config (spec_*, sentinel_*, orch_write_ping, project_get_config) work correctly with injected config.
- AC-I7: Async tools (run_command_checked, web_fetch_checked) are callable via call_tool and return correct shapes.
- AC-I8: Cumulative: all Phase 1-3 acceptance criteria still pass (AC-1 through AC-10, AC-S1 through AC-S12, AC-O1 through AC-O8).

### Phase Completion Steps

> After this phase, execute the Phase Completion Checklist (steps -2 through 10 from CLAUDE.md).

---

## Phase 5: OpenClaw Connection

**Goal:** Tune SOUL.md files for real OpenClaw agent usage. Validate with real LLM calls.

**Deliverables:**
- [x] SOUL.md updates reflecting MVP tool set (11 tools, not 15)
- [x] OpenClaw workspace config aligned with MVP
- [x] Manual smoke test procedure documented in docs/OPENCLAW_SETUP.md
- [x] Documentation: setup guide for connecting MCP server to OpenClaw (docs/OPENCLAW_SETUP.md)

**Acceptance Criteria:**
- AC-C1: SOUL.md files reference only MVP tools (no orch_check_ready, orch_scan_specs, or other Phase B tools)
- AC-C2: OpenClaw config matches MVP tool surface (mcp_servers section with vizier-mcp entry)
- AC-C3: Setup guide covers prerequisites, installation, project creation, agent-tool mapping, and manual smoke test

**Notes:**
- Real LLM round-trip smoke test deferred: requires ANTHROPIC_API_KEY and OpenClaw runtime (missing external dependencies)
- Pasha SOUL.md updated: replaced orch_check_ready reference with Phase B note, replaced orch_scan_specs with spec_list
- Manual smoke test procedure in docs/OPENCLAW_SETUP.md section 7 covers the full lifecycle

### Phase Completion Steps

> After this phase, execute the Phase Completion Checklist (steps -2 through 10 from CLAUDE.md).

---

## Phase 6: Deployment & Operations Guide

**Status: Complete** (2026-02-21)

**Goal:** Production-ready deployment artifacts and documentation for running the Vizier MCP server alongside OpenClaw.

**Deliverables:**
- [x] Dockerfile: multi-stage build for vizier-mcp (Python 3.11-slim + uv, FastMCP server as entrypoint)
- [x] docker-compose.yml: vizier-mcp service + volume mounts for projects/config. Langfuse optional via `observability` profile.
- [x] .env.example: local-dev-only variables (ANTHROPIC_API_KEY, VIZIER_ROOT). Production uses Azure Key Vault (D60).
- [x] Health endpoint: `/health` route on FastMCP server returning JSON (version, tool count, status). Deploy workflow expects `curl http://localhost:8080/health`.
- [x] Azure Key Vault integration: MCP server reads ANTHROPIC_API_KEY from `https://vizier.vault.azure.net/` in production. Managed identity or service principal auth. Falls back to env var for local dev.
- [x] .github/workflows/ updates: fix publish.yml for vizier-mcp/ package paths (deploy.yml not required; publish.yml updated to correctly reference vizier-mcp/ directory structure)
- [x] __main__.py entry point: `python -m vizier_mcp` starts MCP server with optional health endpoint (auto-enabled in Docker via /.dockerenv detection or HEALTH_PORT env var)
- [x] docs/DEPLOYMENT.md: setup guide covering prerequisites, local dev, Docker deployment, Azure Key Vault config, OpenClaw connection, health monitoring

**Acceptance Criteria:**
- [x] `docker compose up` starts MCP server and passes health check (Dockerfile HEALTHCHECK + docker-compose.yml healthcheck both use `curl -sf http://localhost:8080/health`)
- [x] Server reads secrets from Azure Key Vault in production, env vars in local dev (vizier_mcp/secrets.py: get_secret() checks AZURE_KEY_VAULT_URL first, falls back to os.environ)
- [x] CI/CD workflows reference correct paths (publish.yml updated to use vizier-mcp/ directory; path derivation from release tag e.g. vizier-mcp-v0.6.0)
- [x] DEPLOYMENT.md covers local dev, Docker, Azure Key Vault, and OpenClaw connection
- [x] Health endpoint returns JSON with server version and tool count (build_health_payload() returns {status, version, tool_count}; 6 tests in test_health.py)

### Phase Completion Steps

> After this phase, execute the Phase Completion Checklist (steps -2 through 10 from CLAUDE.md).

---

## Phase 7: OpenClaw + Telegram Deployment

**Status: Complete** (2026-02-21)

**Goal:** Extend the Docker deployment to include OpenClaw as a co-located service, enabling Sultan communication via a Telegram bot. The Vizier MCP server (Phase 6) becomes reachable through OpenClaw's Telegram channel so operators interact with Vizier by messaging a bot rather than making direct MCP calls.

**Deliverables:**
- [x] docker-compose.yml: added `openclaw` service depending on `vizier-mcp` health, mounting config and workspace volumes, exposing port 18789, named volume `openclaw-data`
- [x] openclaw/config/openclaw.json: production config -- Telegram channel (pairing DM policy), MCP server wired via `docker exec` stdio transport, session compaction settings, persistent Vizier + Pasha sessions, spawned Worker + QG sessions, one_voice_policy
- [x] ~~openclaw/config/agents.json~~: removed -- agent definitions consolidated into `openclaw.json` under `agents.list[]`; file was never read by OpenClaw
- [x] .env.example: added `TELEGRAM_BOT_TOKEN` as a required variable with instructions for obtaining it from @BotFather
- [x] .github/workflows/deploy.yml: SCP step now copies `openclaw/config/` and `openclaw/workspaces/` to server; deploy script pulls OpenClaw image, runs dual health checks (Vizier MCP gate + OpenClaw informational)
- [x] scripts/openclaw-setup.sh: first-time setup script with prerequisite checks, Telegram token validation, and pairing instructions
- [x] docs/DEPLOYMENT.md: Section 9 covering Telegram bot setup, OpenClaw deployment, pairing procedure, architecture diagram, Docker socket security, and troubleshooting

**Acceptance Criteria:**
- [x] `docker compose up -d` starts both `vizier-mcp` and `openclaw` services. OpenClaw depends on vizier-mcp being healthy before starting.
- [x] OpenClaw connects to Vizier MCP tools via `docker exec -i vizier-mcp uv run --directory vizier-mcp python -m vizier_mcp.server` (stdio transport).
- [x] Telegram bot token is injected via `.env` (`TELEGRAM_BOT_TOKEN`). The `.env.example` documents the variable.
- [x] CI/CD deploy workflow copies OpenClaw config files to the server and performs a health check for both services. OpenClaw health check failure is informational (non-blocking) to handle first-time deploys without a bot token.
- [x] `scripts/openclaw-setup.sh` guides operators through token verification and Telegram pairing on first deployment.
- [x] `docs/DEPLOYMENT.md` Section 9 covers the complete setup flow from bot creation to first message.

### Phase Completion Steps

> After this phase, execute the Phase Completion Checklist (steps -2 through 10 from CLAUDE.md).

---

## Phase 8: Observability

**Status: Complete** (2026-02-22)

**Version:** 0.8.0

**Goal:** Add structured logging, log query tools, and fix the web_fetch_checked role enforcement bug. Provides the foundation for system self-diagnosis by making all tool calls observable through JSONL logs and queryable through MCP tools.

**Deliverables:**
- [x] Bug fix: `web_fetch_checked` now accepts `config` and `project_id` parameters and checks `can_web_fetch` role permission via Sentinel policy (matching `run_command_checked` pattern)
- [x] `can_web_fetch` field added to `RolePermissions` model (default: `True`)
- [x] `StructuredLogger` class (`logging_structured.py`): JSONL writing, size-based rotation (configurable max size/files), thread-safe, `read_entries()` with filtering
- [x] Log config fields added to `ServerConfig`: `log_dir`, `log_max_size_mb`, `log_max_files`
- [x] All 12 existing tools instrumented with logging wrappers (`_logged_sync`, `_logged_async`) recording entry/exit/duration
- [x] `system_get_logs` MCP tool: query JSONL logs with filters (level, module, event, since_minutes, limit, spec_id)
- [x] `system_get_errors` MCP tool: convenience filter for ERROR-level entries
- [x] 16 tests for StructuredLogger, 8 tests for observability tools
- [x] Tool count: 12 -> 14

**Acceptance Criteria:**
- [x] AC-8.1: `web_fetch_checked` with `project_id` checks `can_web_fetch` role permission. Missing role -> deny.
- [x] AC-8.2: Every MCP tool call produces a JSONL log entry with timestamp, tool name, duration_ms.
- [x] AC-8.3: Log rotation at `log_max_size_mb`. Old files renamed with `.1`, `.2` suffixes.
- [x] AC-8.4: `system_get_logs(since_minutes=5)` returns recent entries. All filters work. Empty log -> empty list.
- [x] AC-8.5: `system_get_errors(since_minutes=60)` returns ERROR entries from last hour.
- [x] AC-8.6: `create_server()` returns FastMCP with 14 tools registered.
- [x] AC-8.7: Cumulative: all Phase 1-7 acceptance criteria still pass.

### Phase Completion Steps

> After this phase, execute the Phase Completion Checklist (steps -2 through 10 from CLAUDE.md).

---

## Phase 9: Self-Diagnosis Tools

**Status: Complete** (2026-02-22)

**Version:** 0.9.0

**Goal:** Add system status and spec analytics MCP tools, enabling agents and operators to query operational intelligence and per-project metrics without SSH access.

**Deliverables:**
- [x] `system_get_status` MCP tool (`tools/status.py`): returns server info (version, tool count, uptime), spec summary (counts by status, stuck specs with timing, in-progress specs with age), recent activity (transitions/errors/sentinel denials in last hour), optional `project_id` filter
- [x] `spec_analytics` MCP tool (`tools/analytics.py`): returns per-project throughput (completed, stuck, success rate), timing (avg time to done, avg time in review, slowest spec), quality (rejections, retries), sentinel stats (checks, denials)
- [x] 8 tests for status tool, 6 tests for analytics tool
- [x] Tool count: 14 -> 16
- [x] Version bumped to 0.9.0

**Acceptance Criteria:**
- [x] AC-9.1: `system_get_status()` returns correct spec counts by status. STUCK/IN_PROGRESS specs listed with timing.
- [x] AC-9.2: `system_get_status(project_id="X")` scopes to project X. Non-existent project -> zeroes.
- [x] AC-9.3: `spec_analytics(project_id="X")` returns throughput, timing, quality, sentinel metrics. No specs -> zeroes.
- [x] AC-9.4: `create_server()` returns FastMCP with 16 tools registered.
- [x] AC-9.5: Cumulative: all Phase 1-8 acceptance criteria still pass.

### Phase Completion Steps

> After this phase, execute the Phase Completion Checklist (steps -2 through 10 from CLAUDE.md).

---

## Phase B: Extended Tools (Build When Needed)

These 4 tools are designed (see D76, D79) but deferred until multi-spec projects require them:

| Tool | Trigger | Design Reference |
|------|---------|-----------------|
| orch_scan_specs | When `spec_list` with status filter becomes insufficient | ARCHITECTURE.md 3.1b |
| orch_check_ready | When specs have dependency relationships | D79 |
| orch_assign_worker | When concurrent workers need claim semantics | D76 |
| dag_check_dependencies | When specs have dependency graphs | D79 |
