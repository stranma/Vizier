# Vizier MCP Server -- Implementation Plan

## Status Summary

| Phase | Name | Status | Tools |
|-------|------|--------|-------|
| 1 | Spec Lifecycle | Not Started | spec_create, spec_read, spec_list, spec_transition, spec_update, spec_write_feedback |
| 2 | Sentinel | Not Started | sentinel_check_write, run_command_checked, web_fetch_checked |
| 3 | Orchestration | Not Started | orch_write_ping, project_get_config |
| 4 | Integration | Not Started | Wire FastMCP server, end-to-end test |
| 5 | OpenClaw Connection | Not Started | SOUL.md tuning, real agent test |

---

## Phase 1: Spec Lifecycle

**Goal:** Pydantic models for specs + 6 MCP tools implementing the spec state machine (8 states, all transitions).

**Deliverables:**
- [ ] Pydantic models: Spec, SpecStatus, SpecSummary, SpecFeedback, SpecTransition
- [ ] State machine: 8 states (DRAFT, READY, IN_PROGRESS, REVIEW, REJECTED, DONE, STUCK, INTERRUPTED), valid transitions
- [ ] spec_create: create spec in DRAFT state
- [ ] spec_read: read spec contents and metadata
- [ ] spec_list: list specs with optional status filter
- [ ] spec_transition: validate and execute state transitions
- [ ] spec_update: update mutable spec fields (retry count, assigned agent, etc.)
- [ ] spec_write_feedback: write QG feedback or rejection reason
- [ ] Filesystem I/O: atomic writes (os.replace), spec directory layout
- [ ] Unit tests for all tools and state machine
- [ ] Integration test: spec DRAFT -> READY -> IN_PROGRESS -> REVIEW -> DONE

**Acceptance Criteria:**
- All 8 states and valid transitions enforced
- Invalid transitions return clear error messages
- Atomic writes prevent corruption on crash
- spec_list filters by status correctly
- spec_write_feedback creates structured feedback files

### Phase Completion Steps

> After this phase, execute the Phase Completion Checklist (steps -2 through 10 from CLAUDE.md): PIRR as pre-implementation gate, then sync remote, pre-commit hygiene, commit & push, parallel validation (code-quality-validator + test-coverage-validator + acceptance-criteria-validator), implementation plan check, docs-updater for documentation + changelog, create PR, verify CI, code review with code-reviewer agent, phase handoff note. Consult the Failure & Rollback Protocol if any step fails.

---

## Phase 2: Sentinel

**Goal:** Policy engine + 3 MCP tools for security enforcement (write-set validation, command checking, web fetch scanning).

**Deliverables:**
- [ ] Pydantic models: SentinelPolicy, SentinelRule, WriteSetPattern, CommandCheckResult, WebFetchResult
- [ ] Policy engine: load project sentinel.yaml, evaluate allowlist -> denylist -> Haiku
- [ ] sentinel_check_write: validate file path against project write-set
- [ ] run_command_checked: validate command, execute, return three-shape result (D78)
- [ ] web_fetch_checked: fetch URL, scan content for injection, return result
- [ ] Haiku evaluator: mock in tests, real Haiku call for ambiguous commands
- [ ] Unit tests for all tools and policy evaluation tiers
- [ ] Integration test: command allow/deny/Haiku flow

**Acceptance Criteria:**
- Allowlist commands approved with zero LLM cost
- Denylist commands blocked with zero LLM cost
- Ambiguous commands evaluated by Haiku (mocked in tests)
- run_command_checked returns correct three-shape responses (D78)
- web_fetch_checked scans content for prompt injection patterns
- Write-set enforcement uses glob patterns

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

## Phase B: Extended Tools (Build When Needed)

These 4 tools are designed (see D76, D79) but deferred until multi-spec projects require them:

| Tool | Trigger | Design Reference |
|------|---------|-----------------|
| orch_scan_specs | When `spec_list` with status filter becomes insufficient | ARCHITECTURE.md 3.1b |
| orch_check_ready | When specs have dependency relationships | D79 |
| orch_assign_worker | When concurrent workers need claim semantics | D76 |
| dag_check_dependencies | When specs have dependency graphs | D79 |
