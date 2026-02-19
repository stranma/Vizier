# Phase 13: Agent Protocol Design & Use Case Specification

## Context

After the Agent System Reset (D46), the rigid prompt-in/response-out agent layer was deleted. Infrastructure remains intact (409 tests, file protocol, Sentinel, watcher, secrets, LLM factory, plugins). The goal is to redesign agents as tool-using, interactive Claude instances that can reason, call tools, escalate to supervisors, and request clarifications dynamically.

This phase produces **specification documents only** -- no code implementation. The documents define the communication protocol and testable use cases that will drive all subsequent implementation phases.

### Key Decisions (from brainstorming)

| Decision | Choice | Supersedes |
|----------|--------|------------|
| Agent communication | Tool-mediated handoffs (independent agents, custom tools) | -- |
| LLM provider | Claude only (Anthropic API) | D27 (litellm multi-provider) |
| SDK foundation | Anthropic Python SDK with tool_use (direct API, no subprocess) | D14 (own thin runtime) |
| State management | Keep filesystem state machine as-is | -- |
| Document format | Design Doc + BDD Scenarios | -- |
| Testing | Mocked LLM for CI + real LLM for golden paths | D34 (extends) |

### Consistency Check: Conflicts with Prior Decisions

| Prior Decision | Conflict | Resolution |
|---|---|---|
| **D14**: Own thin runtime over Claude Agent SDK | User now wants SDK as foundation | Deliberate reversal. D46 already marked D14 as "partially obsolete." New D47 will document the switch. |
| **D27**: LiteLLM as library (multi-provider) | User chose Claude-only | Deliberate simplification. Multi-provider adds complexity without current benefit. Re-evaluate when needed. |
| **D4**: Filesystem as message bus | No conflict | Keeping filesystem. Agents use tools to read/write specs. |
| **D2**: Fresh context per task | No conflict | Each agent still starts clean, reads state from disk, executes, exits. |
| **D37**: asyncio daemon + subprocess per agent | No conflict | Agent subprocess pattern remains. SDK may change what runs inside the subprocess. |

### SDK Choice: D47 -- Anthropic Python SDK with tool_use

**Decision**: Use the `anthropic` Python package with `client.messages.create(tools=...)` for the agent loop. Do not use the Claude Agent SDK (`claude-agent-sdk` package).

**Why**:
- Direct API calls -- no subprocess overhead, no ~12s startup, no 55MB binary
- Full control over the agent loop: Sentinel PreToolUse hooks, budget enforcement, structured logging
- Stable, production-ready package (not pre-1.0 alpha)
- Windows-friendly (no CLI binary initialization issues)
- Custom tools are needed anyway (spec CRUD, delegation, escalation) -- the built-in tools from the Agent SDK don't cover our use cases

**What we build**: ~500 lines of agent loop + tool definitions that wrap existing infrastructure (ToolExecutor, spec_io, SentinelEngine).

**Supersedes**: D14 (own thin runtime -- now we use Anthropic SDK directly instead of litellm), D27 (litellm multi-provider -- now Claude-only).

### Design Critique Resolutions (D48-D53)

Six architectural issues identified during review. All will be documented as decisions in AGENT_PROTOCOL.md:

**D48: Scout Feedback Loop**
- **Problem**: Scout is a one-shot bottleneck. If Scout hallucinates a wrong library or declares "no research needed" for a complex task, Architect works from poisoned data.
- **Resolution**: Architect gets a `request_more_research(spec_id, questions)` tool. This transitions the spec back to DRAFT with research questions attached, triggering a second Scout pass. Scout's output includes confidence markers; Architect must evaluate them before proceeding.

**D49: QG Model Tier Escalation ("Blind leading blind")**
- **Problem**: Sonnet-Worker and Sonnet-QG share the same model capabilities. If Worker makes a subtle logic error, QG with the same "brain" has a high probability of missing it.
- **Resolution**: Two-pronged fix:
  1. QG **must run real tests** (not just review code). The `run_tests` tool is mandatory for the mechanical pass -- QG validates against actual test output, not its own judgment.
  2. For HIGH complexity specs, QG automatically escalates to Opus tier for the semantic/logic passes. ModelRouter already supports complexity-based tier resolution -- extend it to QG role.

**D50: Synchronous Supervisor Notification ("ping_supervisor")**
- **Problem**: Filesystem-mediated handoffs have 0-15s latency (reconciliation interval). For "extensive communication" between agents, this is too slow. A Worker blocked on a question shouldn't wait 15 seconds.
- **Resolution**: Add `ping_supervisor(spec_id, urgency, message)` tool. Implementation:
  - Writes the message file (filesystem remains source of truth)
  - AND triggers immediate Pasha attention via IPC
  - Three urgency levels: INFO (next reconciliation), QUESTION (immediate ping), BLOCKER (immediate + EA escalation)
  - Falls back to reconciliation if Pasha is busy (filesystem still authoritative)
- **IPC mechanism (watch-out #1)**: Since Pasha and Worker are separate processes (D37), `asyncio.Event` won't cross the process boundary. Options:
  - **Recommended: watchdog filesystem event** -- Worker writes the ping file, Pasha's existing watchdog detects it near-instantly (sub-second on all platforms). No new IPC mechanism needed. The existing watcher infrastructure already handles this.
  - Alternative: Named pipe / Unix socket. More complex, harder on Windows.
  - Alternative: Shared memory / mmap. Overkill for a notification signal.
  - **Decision**: Use watchdog. The file write IS the signal. Watchdog events fire within ~100ms. Reconciliation is the backup, not the primary path. This means ping_supervisor is just `write_ping_file()` -- Pasha's watcher does the rest.

**D51: Active Oversight ("Supervisor Hook")**
- **Problem**: Sentinel only gates individual tool calls (is this call allowed?). It doesn't detect behavioral patterns like an agent looping 10x on the same failing bash command, burning tokens without progress.
- **Resolution**: Add a **Loop Guardian** to AgentRuntime:
  - Every N tool calls (configurable, default 5), a Haiku-tier checkpoint evaluates: "Is this agent making progress or spinning?"
  - Input: last N tool calls + results (compact summary)
  - Output: CONTINUE / WARN (log, continue) / HALT (force escalation to Pasha)
  - Cost: ~$0.001 per checkpoint (Haiku), triggered every 5 tool calls
  - Also detects: identical tool calls repeated 3+ times (deterministic, no LLM needed)

**D52: Spec Dependency DAG**
- **Problem**: Architect creates sub-specs but doesn't express dependencies. If sub-spec-2 (API endpoint) depends on sub-spec-1 (data model), Pasha might assign them in parallel or in wrong order.
- **Resolution**: Extend spec frontmatter with `depends_on: [spec-id-1, spec-id-2]` field. Architect uses `create_spec(..., depends_on=[...])` to define the DAG. Pasha's scheduling:
  - Only transitions a spec to READY when all `depends_on` specs are DONE
  - **Deterministic DAG validator in Pasha (watch-out #2)**: When Pasha receives a PROPOSE_PLAN, it runs a strict graph validator BEFORE accepting the plan. Checks: no cycles (topological sort), all referenced spec IDs exist, no self-references. Rejects invalid DAGs immediately -- Architect must fix and resubmit. This is deterministic (no LLM needed), runs in Pasha's event loop.
  - Enables parallelism for independent sub-specs
  - Extends existing `VALID_TRANSITIONS` -- a spec with unmet dependencies stays in DECOMPOSED until prerequisites complete

**D53: Integration Tests in Phase 14 (not Phase 22)**
- **Problem**: If integration tests are deferred to Phase 22, we build 8 phases of tools and agents before discovering that the AgentRuntime can't properly route messages between simulated agents.
- **Resolution**: Phase 14 (Agent Runtime Foundation) includes mocked integration tests from day one. The AgentRuntime test suite verifies:
  - Simulated Worker -> Pasha handoff (via filesystem + ping_supervisor)
  - Simulated Pasha -> Worker delegation (spawn + spec state transition)
  - Loop Guardian checkpoint triggering
  - Sentinel PreToolUse hook blocking
  - Budget threshold enforcement
  - Phase 22 becomes "Golden Path + Real LLM" only (the expensive stuff)

---

## Deliverables

### 1. `docs/AGENT_PROTOCOL.md` -- Communication Protocol Design Document

Restructured around **3 machine-verifiable contracts** (per external review). This ensures the protocol is testable, not just prose.

**Sections:**

1. **Overview & Philosophy** (~300 words)
   - Why: Agent System Reset, rebuilding with tool use
   - Core principle: Each agent = Claude instance + system prompt + tools + model tier
   - Agent loop: gather context -> act -> verify -> repeat (or escalate)
   - **Key insight**: Protocol = 3 contracts (message schema, tool policy, state invariants), not text agreements

2. **Contract A: Message Schema** (~800 words + JSON/YAML examples)
   All inter-agent communication uses typed, structured messages. Free text can be a field within a message, but never the canonical format. This eliminates the regex parsing that failed before.
   - `TASK_ASSIGNMENT(spec_id, goal, constraints, budgets, allowed_tools)` -- EA->Pasha, Pasha->Agent
   - `STATUS_UPDATE(spec_id, state, progress, blockers, next_step, confidence)` -- Any agent -> supervisor
   - `REQUEST_CLARIFICATION(spec_id, question, options[], blocking: bool, deadline)` -- Any agent -> supervisor
   - `PROPOSE_PLAN(spec_id, steps[], risks[], expected_artifacts[], depends_on[])` -- Architect -> Pasha
   - `ESCALATION(spec_id, severity, reason, attempted[], needed_from_supervisor)` -- Any agent -> supervisor
   - `QUALITY_VERDICT(spec_id, pass_fail, criteria_results[{criterion, result, evidence_link}], suggested_fix[])` -- QG -> Pasha
   - `RESEARCH_REPORT(spec_id, candidates[], recommendation, confidence, search_queries[])` -- Scout -> Architect (via filesystem)
   - `PING(spec_id, urgency: INFO|QUESTION|BLOCKER, message)` -- Any agent -> supervisor (D50)
   - Each message type has a JSON Schema definition, stored in `libs/core/vizier/core/models/messages.py` as Pydantic models
   - Messages are written as YAML/JSON files to the spec directory (filesystem remains source of truth)
   - **Golden Trace**: Every message appended to `specs/NNN/trace.jsonl` -- per-spec timeline of all actions, tool calls, verdicts, state transitions

3. **Contract B: Tool-use Policy** (~1000 words + capabilities matrix)
   Defines what each agent CAN do, enforced by Sentinel + plugin. Replaces implicit restrictions with explicit capability matrix.
   - **Domain tools**: `read_file`, `write_file`, `edit_file`, `bash`, `glob`, `grep`, `git`, `run_tests`, `web_search`
   - **Orchestration tools**: `delegate_to_scout`, `delegate_to_architect`, `delegate_to_worker`, `delegate_to_quality_gate`, `escalate_to_pasha`, `escalate_to_ea`, `report_progress`, `spawn_agent`, `request_more_research` (D48)
   - **State tools**: `create_spec`, `update_spec_status`, `read_spec`, `list_specs`, `read_state`, `write_feedback` (wrapping `spec_io` in `libs/core/vizier/core/file_protocol/spec_io.py`)
   - **Communication tools**: `send_message` (emits typed message from Contract A), `ping_supervisor` (D50), `send_briefing`
   - **Security tools**: `check_permission`, `log_action` (wrapping `SentinelEngine` in `libs/core/vizier/core/sentinel/engine.py`)
   - **Tool Access Matrix**: Role -> allowed tool categories -> guardrails -> budget
   - **Write-set via glob patterns**: Instead of fixed artifact list, plugin defines write-set as glob patterns (e.g., `src/**/*.py`, `tests/**`, `docs/**`, `pyproject.toml`). Worker can write to anything matching the patterns. Sentinel enforces. Replaces the overly restrictive "only artifacts listed in spec" rule.
   - **EA project capability summary**: EA reads a per-project capability summary from ProjectRegistry (plugin type, available CI signals, definition of "done", critical tools). Enables informed routing without full plugin-awareness.

4. **Contract C: State Machine Invariants** (~600 words + formal conditions)
   Machine-verifiable conditions for every state transition. These become test assertions.
   - DRAFT -> SCOUTED: only if research.md exists (or explicit skip with confidence > 0.8)
   - SCOUTED -> DECOMPOSED: only if sub-specs created with PROPOSE_PLAN message
   - READY: only if `depends_on` specs are all DONE (D52: DAG enforcement)
   - READY -> IN_PROGRESS: only if Worker subprocess alive AND budget available
   - IN_PROGRESS -> REVIEW: only if commit hash exists AND artifacts match write-set patterns
   - REVIEW -> DONE: only if QUALITY_VERDICT.json saved with all criteria PASS + evidence links
   - REVIEW -> REJECTED: only if QUALITY_VERDICT.json saved with failure reasons + suggested fixes
   - Clarification with `blocking: true` halts work; if deadline expires -> auto-escalation
   - **Evidence requirement**: Every QUALITY_VERDICT must include evidence links (test output files, lint logs, grep results). No LLM-only verdicts.
   - **Mandatory evidence types by plugin (watch-out #3)**: Plugin defines which evidence types are required for DONE transition. QG cannot mark DONE without producing them.
     - Software plugin: `test_output` (pytest stdout), `lint_output` (ruff check), `type_check_output` (pyright), `diff` (git diff of changes)
     - Documents plugin: `link_check_output`, `structure_validation`, `rendered_preview_path`
     - Custom plugins declare their own required evidence types in plugin config
     - Pasha validates evidence completeness before accepting QUALITY_VERDICT (deterministic check, not LLM)

5. **SDK Integration Architecture** (~500 words + code examples)
   - D47: Anthropic Python SDK with `client.messages.create(tools=...)` -- direct API, no subprocess
   - `AgentRuntime` wrapper: wraps Anthropic client, adds Sentinel PreToolUse hook, budget tracking, Loop Guardian (D51), structured logging, Golden Trace
   - Model resolution via existing `ModelRouter` (`libs/core/vizier/core/model_router/router.py`)
   - API key resolution via existing `SecretStore` (`libs/core/vizier/core/secrets/`)

6. **Agent Lifecycle** (~500 words)
   - Spawning: Pasha creates subprocess, subprocess loads spec + plugin, creates AgentRuntime
   - Running: Tool loop until completion, escalation, or budget limit
   - Termination: Clean exit (spec transitions), error exit (feedback written), crash (Pasha detects)
   - Fresh context guarantee: new subprocess, no shared memory, state from disk

7. **Supervision & Monitoring** (~600 words)
   - Sentinel as PreToolUse hook (existing `SentinelEngine`)
   - **Loop Guardian** (D51): Haiku checkpoint every N tool calls. Deterministic repeat detection (identical calls 3x). Configurable threshold.
   - Budget monitoring (token usage tracking, threshold alerts from D33)
   - **QG tier escalation** (D49): Automatic Opus upgrade for HIGH complexity semantic passes + mandatory real test execution
   - **Adaptive reconciliation**: Backoff when idle (30s, 60s, 120s), accelerate when busy (5s, 10s). Default 15s baseline.
   - Structured JSONL logging (existing agent log format from D28)
   - Golden Trace per spec (all tool calls, messages, state transitions in `specs/NNN/trace.jsonl`)

8. **Error Handling** (~400 words)
   - Tool execution errors (Claude receives error, adapts or escalates)
   - Sentinel blocks (permission denied, agent finds alternative)
   - Budget exhaustion (graceful handoff at 80%/100% thresholds)
   - Agent crash recovery (Pasha detects, retries per D25, reconciliation catches missed events per D22)

9. **Integration with Existing Infrastructure** (~600 words)
   - File Protocol: tool implementations wrap `spec_io` functions
   - Plugin System: BasePlugin extended to provide ToolSets, write-set patterns, system prompt templates
   - Sentinel: PreToolUse hook wraps existing SentinelEngine
   - Watcher/Reconciler: adaptive intervals, drives Pasha event loop
   - ModelRouter: resolves role + complexity -> model string for Anthropic API

10. **Architectural Alternatives** (~300 words)
    - **Scout + Architect merge** ("Planner"): Document as future simplification if Scout proves low-value. Keep separate for now (better testability, clear responsibility).
    - **Event log vs filesystem bus**: Append-only event log with materialized state would improve concurrency and replay. Note for future if FS watcher limitations emerge.
    - **Overseer as full agent**: Loop Guardian (D51) + Sentinel is sufficient for now. Full Overseer agent if incident patterns emerge.

### 2. `docs/USE_CASES.md` -- BDD Scenarios

15 scenarios in Gherkin-like format (Given/When/Then):

| # | Scenario | Tests | New Decision |
|---|----------|-------|--------------|
| 1 | Happy path: full task lifecycle (Sultan -> EA -> Pasha -> Scout -> Architect -> Worker -> QG -> Done) | End-to-end delegation, all state transitions | -- |
| 2 | Escalation: Worker stuck, graduates through retry thresholds to Sultan | Graduated retry (D25), escalation files | -- |
| 3 | Rejection loop: QG rejects, Worker retries with feedback | REVIEW -> REJECTED -> IN_PROGRESS -> REVIEW cycle | -- |
| 4 | Clarification: Worker needs info, chain to Sultan and back | Async clarification via filesystem | -- |
| 5 | Decomposition: Architect splits task into DAG of sub-specs with dependencies | Parent DECOMPOSED, children ordered by DAG, Pasha respects prerequisites | **D52** |
| 6 | Multi-project: EA manages multiple Pashas, cross-project coordination | Multiple projects, linked specs | -- |
| 7 | Security gating: Sentinel blocks dangerous tool call, agent adapts | Sentinel denylist, agent recovery | -- |
| 8 | Budget enforcement: Agent approaching token limit, graceful degradation | 80%/100% thresholds, tier downgrade | -- |
| 9 | Recovery: Agent crashes mid-task, system recovers via reconciliation | INTERRUPTED -> READY, reconciler scan | -- |
| 10 | Retrospective: System learns from failure patterns, proposes improvements | Feedback analysis, learnings update | -- |
| 11 | Scout feedback: Architect finds Scout research insufficient, requests re-research | `request_more_research` tool, Scout re-invocation, enriched research output | **D48** |
| 12 | QG Opus escalation: HIGH complexity spec gets Opus-tier semantic review | ModelRouter escalation, real test execution mandatory, logic error caught | **D49** |
| 13 | Synchronous ping: Worker hits blocker, pings Pasha immediately (no 15s wait) | `ping_supervisor` with BLOCKER urgency, Pasha responds < 1s | **D50** |
| 14 | Loop Guardian: Worker spins on same failing command 5x, checkpoint halts it | Haiku checkpoint triggers, HALT decision, forced escalation to Pasha | **D51** |
| 15 | DAG scheduling: Pasha holds spec-2 until spec-1 completes, then releases | `depends_on` field, DECOMPOSED -> READY transition gated by prerequisites | **D52** |

Each scenario includes:
- **Given**: Preconditions (filesystem state, config, active agents)
- **When**: Trigger (message, event, timer, crash)
- **Then**: Expected outcomes (tool calls made, state transitions, files created/modified)
- **Notes**: Which existing infrastructure is exercised, which new components are needed

### 3. Updated `docs/AGENT_SPECS.md`

Major revisions based on external review:

**EA**:
- Add "Project Capability Summary" -- EA reads plugin type, CI signals, definition of "done" from ProjectRegistry
- EA becomes "traffic controller" (minimal DRAFT seeds), not "spec writer" (detailed DRAFTs)
- Add tool list from Contract B

**Scout**:
- **Delete regex/keyword triage** (lines 169-172 of current spec). This is the same rigidity that failed before.
- Scout is now a tool-using LLM agent (Sonnet) that decides whether research is needed based on LLM judgment, not keyword patterns
- Fallback: if Scout budget is exceeded or Scout is uncertain, deterministic "always research" default
- Output: structured `RESEARCH_REPORT` message (Contract A), not free-text research.md

**Architect**:
- Add `request_more_research` tool (D48) -- can send Scout back if data is insufficient
- Must output `PROPOSE_PLAN` message (Contract A) with `depends_on[]` DAG (D52)
- Must declare write-set patterns + test strategy for each sub-spec

**Worker**:
- **Replace fixed artifact list with glob-pattern write-set** from plugin policy
- Write-set is categorical: `src/**/*.py`, `tests/**`, `docs/**`, `pyproject.toml`, etc.
- Sentinel enforces write-set boundaries via glob matching
- Add `send_message(REQUEST_CLARIFICATION)` and `ping_supervisor` tools

**Quality Gate**:
- Must produce `QUALITY_VERDICT` (Contract A) -- structured JSON with evidence links
- **Mandatory `run_tests` before any LLM-assisted passes** -- QG validates against real test output, not just code review
- Opus escalation for HIGH complexity specs (D49)
- Evidence artifacts stored alongside verdict (test output, lint logs, grep results)

**Retrospective**:
- Add "process debt register" -- tracks recurring patterns (repeated rejection types, stuck patterns)
- Proposals include evidence from Golden Trace data

All agents:
- Add tool list from Contract B capabilities matrix
- Add message types they can send/receive (Contract A)
- Add budget limits per invocation

### 4. Updated `docs/IMPLEMENTATION_PLAN.md`

Append new phases:

| Phase | Name | Summary |
|-------|------|---------|
| 13 | Agent Protocol Design | This phase (documentation only): 3 contracts, 15 BDD scenarios, agent specs |
| 14 | Message Schema + Agent Runtime | Contract A Pydantic models (D54), AgentRuntime wrapper, Sentinel hook, Loop Guardian (D51), Golden Trace (D57), **mocked integration tests from day one (D53)** |
| 15 | Domain Tools | read_file, write_file (glob write-set D55), edit_file, bash, glob, grep, git, run_tests |
| 16 | State + Communication Tools | spec CRUD (Contract C invariants), delegation, escalation, `ping_supervisor` (D50), `request_more_research` (D48), DAG scheduling (D52), adaptive reconciliation (D58) |
| 17 | EA Agent | Tool-based EA with project capability summary (D59), Telegram integration |
| 18 | Pasha Orchestrator | Event-driven loop, agent spawning, DAG-aware scheduling (D52), ping handling, adaptive reconciliation (D58) |
| 19 | Inner Loop Agents | Scout (LLM triage, no regex), Architect (PROPOSE_PLAN + DAG), Worker (glob write-set), QG (structured verdicts D56, Opus escalation D49) |
| 20 | Plugin Rebuild | Software + Documents plugins: write-set patterns, criteria, system prompts |
| 21 | Retrospective Agent | Failure analysis, process debt register, learnings, proposals based on Golden Trace data |
| 22 | Golden Path Validation | Real LLM end-to-end tests (expensive, manual) -- mocked integration already in Phase 14 |

### 5. Decision Records D47-D59

Add to `docs/DECISIONS.md`:
- **D47**: Anthropic Python SDK with tool_use as agent foundation. Supersedes D14, D27.
- **D48**: Scout Feedback Loop -- Architect can send Scout back for more research via `request_more_research`.
- **D49**: QG Model Tier Escalation -- Opus for HIGH complexity semantic passes + mandatory real test execution.
- **D50**: Synchronous Supervisor Notification -- `ping_supervisor` tool with urgency levels (file write + asyncio event).
- **D51**: Loop Guardian -- Haiku checkpoint every N tool calls to detect agent spinning. Deterministic repeat detection.
- **D52**: Spec Dependency DAG -- `depends_on` frontmatter field, Pasha gates scheduling on prerequisites.
- **D53**: Integration Tests from Phase 14 -- mocked integration tests in AgentRuntime, not deferred to Phase 22.
- **D54**: Structured Message Schema -- all inter-agent communication uses typed Pydantic messages (Contract A). No free-text as canonical format. Eliminates regex parsing.
- **D55**: Write-set via glob patterns -- replaces fixed artifact list. Plugin defines categorical write-set (e.g., `src/**/*.py`, `tests/**`). Sentinel enforces via glob matching.
- **D56**: QG Structured Verdicts with evidence -- QUALITY_VERDICT is a JSON object with per-criterion PASS/FAIL + evidence links (test output, lint logs, file+line). Required for DONE/REJECTED transitions (Contract C invariant).
- **D57**: Golden Trace per spec -- `specs/NNN/trace.jsonl` captures all tool calls, messages, state transitions, verdicts. Enables debugging and Retrospective analysis.
- **D58**: Adaptive reconciliation interval -- backoff when idle (30s -> 60s -> 120s), accelerate when busy (5s -> 10s). Default 15s baseline. Reduces IO noise in multi-project scenarios.
- **D59**: EA project capability summary -- EA reads per-project capability data from ProjectRegistry (plugin type, CI signals, definition of "done"). Enables informed routing without full plugin-awareness.

---

## Order of Work

1. Write `docs/AGENT_PROTOCOL.md` (Sections 1-10: overview, 3 contracts, SDK, lifecycle, supervision, errors, integration, alternatives)
2. Write `docs/USE_CASES.md` (Scenarios 1-15)
3. Update `docs/AGENT_SPECS.md` (major revisions: delete Scout regex, add tools, message types, write-set patterns, structured verdicts)
4. Update `docs/IMPLEMENTATION_PLAN.md` (append Phases 13-22)
5. Add D47-D59 to `docs/DECISIONS.md`

## Existing Files to Modify

| File | Action |
|------|--------|
| `docs/AGENT_SPECS.md` | Major revisions: delete Scout regex triage, add tool lists, message types, write-set patterns, structured verdicts, project capability summary |
| `docs/IMPLEMENTATION_PLAN.md` | Append Phases 13-22 |
| `docs/DECISIONS.md` | Add D47-D59 (13 new decisions) |

## New Files to Create

| File | Purpose |
|------|---------|
| `docs/AGENT_PROTOCOL.md` | Communication protocol design document |
| `docs/USE_CASES.md` | BDD-style use case scenarios |

## Key Existing Infrastructure Referenced

| Component | Path | How Used |
|-----------|------|----------|
| Spec I/O | `libs/core/vizier/core/file_protocol/spec_io.py` | State tools wrap these functions |
| State Manager | `libs/core/vizier/core/file_protocol/state_manager.py` | State tools use for state.json |
| Sentinel Engine | `libs/core/vizier/core/sentinel/engine.py` | PreToolUse hook for all tool calls |
| Model Router | `libs/core/vizier/core/model_router/router.py` | Resolves agent role -> model string |
| Tool Executor | `libs/core/vizier/core/tools/executor.py` | Domain tools (bash) wrap this |
| Secret Store | `libs/core/vizier/core/secrets/` | API key resolution for Claude client |
| Plugin Base | `libs/core/vizier/core/plugins/base_plugin.py` | Extended to provide ToolSets |
| Tool Registry | `libs/core/vizier/core/plugins/tool_registry.py` | Sentinel enforcement per tool |
| Watcher | `libs/core/vizier/core/watcher/fs_watcher.py` | Drives Pasha event loop |
| Reconciler | `libs/core/vizier/core/watcher/reconciler.py` | Filesystem truth recovery |

## Verification

Since this phase is documentation-only:
- All documents reviewed for internal consistency
- BDD scenarios cover all agent pairs (EA<->Pasha, Pasha<->Architect, Architect<->Scout, Pasha<->Worker, Worker<->QG, Pasha<->EA)
- BDD scenarios 11-15 specifically validate the new mechanisms (D48-D52)
- Tool catalog references only existing infrastructure or clearly marks new components
- Spec frontmatter extension (`depends_on`) is documented with validation rules (no cycles, DONE prerequisite)
- Implementation plan phases are sequentially buildable (each phase depends only on prior phases)
- Phase 14 explicitly includes mocked integration tests (D53)
- Decisions D47-D59 are consistent with D46 and explicitly note what they supersede
- Contract A message types have JSON Schema / Pydantic model definitions
- Contract C invariants are testable as assertions (each invariant maps to a test case)

## Phase Completion Steps

After this phase, execute the Phase Completion Checklist (steps -2 through 10 from CLAUDE.md): PIRR, sync remote, pre-commit hygiene, commit & push, parallel validation, implementation check, documentation verification, create PR, verify CI, code review, phase handoff note.
