# Vizier MCP Server -- Implementation Plan

## Status Summary

| Phase | Name | Status | Tools |
|-------|------|--------|-------|
| 1 | Spec Lifecycle | Complete | spec_create, spec_read, spec_list, spec_transition, spec_update, spec_write_feedback |
| 2 | Sentinel | Complete | sentinel_check_write, run_command_checked, web_fetch_checked |
| 3 | Orchestration | Not Started | orch_write_ping, project_get_config |
| 4 | Integration | Not Started | Wire FastMCP server, end-to-end test |
| 5 | OpenClaw Connection | Not Started | SOUL.md tuning, real agent test |
| 6 | Deployment | Not Started | Dockerfile, docker-compose, CI/CD, deployment guide |

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
- [ ] orch_write_ping: write ping file with urgency (QUESTION, BLOCKER, IMPOSSIBLE)
- [ ] project_get_config: load and return project config.yaml
- [ ] Pydantic models: PingMessage, ProjectConfig
- [ ] Unit tests for both tools
- [ ] Integration test: Worker writes ping, ping file appears in correct location

**Acceptance Criteria:**
- Ping files written to correct directory with urgency level
- project_get_config returns complete project configuration
- Invalid urgency values rejected

### Phase Completion Steps

> After this phase, execute the Phase Completion Checklist (steps -2 through 10 from CLAUDE.md).

---

## Phase 4: Integration

**Goal:** Wire all 11 tools into FastMCP server. End-to-end test of full spec lifecycle.

**Deliverables:**
- [ ] FastMCP server (server.py) registering all 11 tools
- [ ] Server startup/shutdown lifecycle
- [ ] End-to-end test: spec goes DRAFT -> READY -> IN_PROGRESS -> REVIEW -> DONE using all relevant tools
- [ ] End-to-end test: spec goes through REJECTED -> retry -> DONE path
- [ ] End-to-end test: spec reaches STUCK after max retries

**Acceptance Criteria:**
- All 11 tools callable via MCP protocol
- Full happy path works end-to-end
- Rejection/retry path works end-to-end
- STUCK escalation path works end-to-end

### Phase Completion Steps

> After this phase, execute the Phase Completion Checklist (steps -2 through 10 from CLAUDE.md).

---

## Phase 5: OpenClaw Connection

**Goal:** Tune SOUL.md files for real OpenClaw agent usage. Validate with real LLM calls.

**Deliverables:**
- [ ] SOUL.md updates reflecting MVP tool set (11 tools, not 15)
- [ ] OpenClaw workspace config aligned with MVP
- [ ] Real LLM smoke test: Vizier creates spec, Pasha promotes, Worker implements (mocked artifacts)
- [ ] Documentation: setup guide for connecting MCP server to OpenClaw

**Acceptance Criteria:**
- SOUL.md files reference only MVP tools
- OpenClaw config matches MVP tool surface
- At least one real LLM round-trip validates the tool contract

### Phase Completion Steps

> After this phase, execute the Phase Completion Checklist (steps -2 through 10 from CLAUDE.md).

---

## Phase 6: Deployment & Operations Guide

**Goal:** Production-ready deployment artifacts and documentation for running the Vizier MCP server alongside OpenClaw.

**Deliverables:**
- [ ] Dockerfile: multi-stage build for vizier-mcp (Python 3.11-slim + uv, FastMCP server as entrypoint)
- [ ] docker-compose.yml: vizier-mcp service + volume mounts for projects/config. Langfuse optional via `observability` profile.
- [ ] .env.example: local-dev-only variables (ANTHROPIC_API_KEY, VIZIER_ROOT). Production uses Azure Key Vault (D60).
- [ ] Health endpoint: `/health` route on FastMCP server returning JSON (version, tool count, status). Deploy workflow expects `curl http://localhost:8080/health`.
- [ ] Azure Key Vault integration: MCP server reads ANTHROPIC_API_KEY from `https://vizier.vault.azure.net/` in production. Managed identity or service principal auth. Falls back to env var for local dev.
- [ ] .github/workflows/ updates: fix deploy.yml (Docker build + GHCR push + SSH deploy) and tests.yml (lint/type/test) for vizier-mcp/ package structure
- [ ] docs/DEPLOYMENT.md: setup guide covering prerequisites, local dev, Docker deployment, Azure Key Vault config, OpenClaw connection, health monitoring

**Acceptance Criteria:**
- `docker compose up` starts MCP server and passes health check
- Server reads secrets from Azure Key Vault in production, env vars in local dev
- CI/CD workflows reference correct paths (vizier-mcp/, not libs/core/)
- DEPLOYMENT.md covers local dev, Docker, Azure Key Vault, and OpenClaw connection
- Health endpoint returns JSON with server version and tool count

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
