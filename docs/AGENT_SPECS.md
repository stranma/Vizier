# Vizier Agent Specifications

## Agent Overview

| Agent | Scope | Model Tier | Trigger | Always Running? | Plugin-aware? |
|-------|-------|-----------|---------|-----------------|---------------|
| EA | Singleton (all projects) | Opus | Human message / calendar / report / schedule | Yes | No (reads project capability summary) |
| Pasha | Per-project | Opus | Spec lifecycle events / human session | Yes (event loop) | No (framework) |
| Scout | Per-project | Sonnet | DRAFT specs from Pasha | No (spawned) | Yes (reads plugin scout guide) |
| Architect | Per-project | Opus | SCOUTED specs from Pasha | No (spawned) | Yes (reads plugin guide + research report) |
| Worker | Per-project | Sonnet/Haiku | READY specs in queue | No (spawned per task) | Yes (plugin provides write-set + prompts) |
| Quality Gate | Per-project | Sonnet (Opus for HIGH) | REVIEW specs | No (spawned per review) | Yes (plugin provides criteria + evidence types) |
| Retrospective | Per-project | Opus | Cycle end / STUCK / pattern | No (spawned periodically) | No (framework) |

**Plugin-aware agents** use the project's plugin to determine their behavior: tools, prompts, criteria, restrictions. Framework agents are the same regardless of project type.

**All agents** are Claude API instances using `anthropic.Anthropic` with `client.messages.create(tools=...)`. Each agent runs as a fresh AgentRuntime instance in the daemon thread pool (D61). No shared memory between invocations -- each runtime gets a fresh message list. State is read from disk at start and written to disk at end (D47).

---

## EA (Executive Assistant)

### Role
The human's single interface to the entire system. Manages attention, tracks real-world commitments, routes tasks, and proactively surfaces what matters. Acts as a **traffic controller** -- creates minimal DRAFT spec seeds and routes them to the correct project, rather than writing detailed specs.

### Communication Modes

| Mode | Trigger | Behavior |
|------|---------|----------|
| **Delegation** | "Build auth for project-alpha" | Creates minimal DRAFT spec seed, routes to project, reports when done |
| **Status** | "How's everything?" or `/status` | Reads status.json + commitments, summarizes with risk assessment |
| **Control** | "Stop work on project-beta auth" | Direct spec status manipulation |
| **Session** | "Let's work on project-alpha" or `/session` | Opens direct Pasha session, holds non-urgent updates |
| **Briefing** | Scheduled / on-demand | Morning briefing: priorities, risks, reminders, calendar |
| **Check-in** | `/checkin` (periodic or on-demand) | Structured interview: new events, decisions, blockers, contacts |
| **Quick Query** | `/ask project-name question` | Routes to Pasha, relays answer without spec creation |
| **Focus** | `/focus Nh` | Holds non-emergency notifications for N hours |
| **Approval** | `/approve spec-id` | Approves pending operation in Sultan approval queue |
| **Budget** | `/budget` or `/budget project-name` | Shows cost summary from agent logs |
| **Priorities** | `/priorities` | View/edit Sultan's priorities.yaml |

### Tools (Contract B)

| Category | Tools |
|----------|-------|
| **Domain** | `read_file` |
| **State** | `create_spec`, `read_spec`, `list_specs` |
| **Communication** | `send_message`, `send_briefing` |

### Messages (Contract A)

| Sends | Receives |
|-------|----------|
| `TASK_ASSIGNMENT` (to Pasha) | `STATUS_UPDATE` (from Pasha) |
| `send_briefing` (to Sultan) | `ESCALATION` (from Pasha) |
| | `REQUEST_CLARIFICATION` (from Pasha, forwarded from agents) |

### Project Capability Summary (D59)

EA reads a per-project capability summary from the ProjectRegistry to make informed routing decisions without full plugin-awareness:

```yaml
project_alpha:
  plugin: software
  ci_signals: ["pytest", "ruff", "pyright"]
  done_definition: "All tests pass, lint clean, type check clean"
  critical_tools: ["bash", "git", "run_tests"]
  autonomy_stage: supervised
```

This enables EA to provide context when delegating (e.g., telling Sultan "this project uses pytest and ruff" or routing a task to the right project based on its capabilities).

### Inputs
- Human messages (Telegram / Slack / CLI)
- `reports/*/status.json` -- project status updates
- `reports/*/escalations/` -- blocker notifications
- Calendar events (via MCP: Google Calendar / Outlook)
- `ea/commitments/*.yaml` -- commitment state
- `ea/relationships/*.yaml` -- contact context
- Pasha session summaries (`ea/sessions/*.md`)
- ProjectRegistry capability summaries

### Outputs
- `.vizier/specs/NNN/spec.md` (status: DRAFT) -- minimal task seeds in target project
- Human messages (briefings, progress updates, escalation alerts, reminders)
- Updated commitments (new promises, status changes, completions)
- Updated relationships (new contacts, last interaction)
- Session summaries (after Pasha sessions end)

### Trigger
- Incoming human message
- Filesystem watch on `reports/` directory
- Calendar event approaching (meeting prep)
- Scheduled briefing time
- Commitment deadline approaching
- Commitment overdue threshold crossed

### Key Behaviors
- **Traffic controller**: creates minimal DRAFT spec seeds with goal + constraints, not detailed specs. Scout and Architect handle the details.
- **Gatekeeper of attention**: decides what's worth interrupting the human for
- Translates business language into structured spec seeds
- Filters noise: not every cycle report becomes a human message
- Escalates blockers and deadline risks immediately
- Tracks commitments vs. project progress: "Board deck due in 2 days, 60% done"
- Prepares meeting context: "Call with Novak in 1h -- you owe him partnership terms"
- Reminds about forgotten promises: "Response to Novak pending since Feb 10"
- Reads Pasha session summaries to maintain continuity
- During Pasha sessions: holds non-urgent updates, stays aware
- **JIT prompt assembly (D42)**: always-loaded core (~2,500 tokens) + conditional modules loaded by deterministic classifier
- **MCP plugin discovery (D43)**: at startup, discovers per-project plugin MCP tools
- **Behavioral anchor: priorities.yaml**: reads Sultan's current priorities on every LLM invocation

### Budget
- Opus tier (always)
- Per-invocation token limit: configurable, default 50,000
- Always-on: token usage tracked via `agent-log.jsonl`

### Proactive Behaviors

| Behavior | Trigger | Example |
|---|---|---|
| Morning briefing | Daily schedule | "Today: 2 meetings, 1 overdue commitment, 3 projects on track" |
| Deadline warning | Commitment + project behind | "Board deck due in 2 days, only 60% done" |
| Follow-up reminder | Promise past threshold | "You promised Novak a response 5 days ago" |
| Meeting prep | Calendar event approaching | "Call with Finesta in 1h. Here's their status + your open items" |
| Check-in | Periodic | "Weekly check-in: any new decisions, contacts, blockers?" |
| Completion notice | Spec DONE | "Auth feature shipped. Should I tell anyone?" |
| Risk escalation | STUCK or behind deadline | "Dashboard stuck after 5 retries. Blocking March 1 launch." |
| Session suggestion | Complex task or ambiguous request | "This needs a working session. Want me to connect you to Project Alpha's Pasha?" |
| Commit approval | Spec has `requires_approval: true` | Shows diff + summary in Telegram with Approve/Reject |

### Validated Scenarios

1. **Morning delegation** -- Sultan reads briefing, delegates "add dark mode to project-alpha", asks status. EA classifies intent, creates DRAFT spec, reads status.json.
2. **Deep Pasha session** -- Sultan says "let's work on project-alpha." EA opens Pasha session, holds non-urgent updates. After session, Pasha writes summary, EA reads it.
3. **Proactive crisis** -- Auth spec at 7/10 retries. EA correlates with commitment deadline. Proactively alerts Sultan with risk assessment.
4. **Cross-project coordination** -- Sultan needs board deck spanning multiple projects. EA reads status from all projects, creates linked DRAFT specs.

---

## Pasha

### Role
Owns the lifecycle of a single project. Orchestrates agents within the project. Writes progress reports for EA. Supports direct human working sessions for deep discussions. Enforces DAG scheduling (D52) and validates agent outputs deterministically.

### Operating Modes

| Mode | Trigger | Behavior |
|---|---|---|
| **Autonomous** | Normal operation | Event-driven loop, spawns agents, writes reports |
| **Session** | Human connects via EA | Deep back-and-forth discussion, spec design, architecture decisions |

When in session mode, the Pasha maintains full project context (constitution, specs, learnings, codebase) and engages in extended conversation. When the session ends, Pasha writes a summary to `ea/sessions/` so EA can maintain continuity.

### Tools (Contract B)

| Category | Tools |
|----------|-------|
| **Orchestration** | `delegate_to_scout`, `delegate_to_architect`, `delegate_to_worker`, `delegate_to_quality_gate`, `escalate_to_ea`, `spawn_agent`, `report_progress` |
| **State** | `read_spec`, `update_spec_status`, `list_specs` |
| **Communication** | `send_message` |

### Messages (Contract A)

| Sends | Receives |
|-------|----------|
| `TASK_ASSIGNMENT` (to agents) | `TASK_ASSIGNMENT` (from EA) |
| `STATUS_UPDATE` (to EA) | `STATUS_UPDATE` (from agents) |
| `ESCALATION` (to EA) | `PROPOSE_PLAN` (from Architect) |
| | `QUALITY_VERDICT` (from QG) |
| | `ESCALATION` (from agents) |
| | `REQUEST_CLARIFICATION` (from agents) |
| | `PING` (from agents) |

### Inputs
- `.vizier/specs/**` -- spec lifecycle events (filesystem watch)
- `.vizier/state.json` -- current project state
- `.vizier/constitution.md` -- project principles
- `.vizier/learnings.md` -- accumulated knowledge
- `.vizier/config.yaml` -- plugin selection and overrides

### Outputs
- Delegates to Scout, Architect, Worker, Quality Gate (creates specs or triggers agents)
- `reports/<project>/status.json` -- current status
- `reports/<project>/YYYY-MM-DD-cycle-NNN.md` -- cycle reports
- `reports/<project>/escalations/` -- blocker notifications

### Trigger
- New DRAFT spec arrives (from EA)
- Spec status changes (DONE, STUCK, REJECTED)
- PING messages from agents (via watchdog, D50)
- Periodic reconciliation (adaptive intervals, D58)

### Key Behaviors
- Maintains project state machine
- Loads the correct plugin for the project
- Spawns Scout, Architect, Worker, Quality Gate as needed
- **DAG-aware scheduling (D52)**: only assigns Workers to READY specs whose `depends_on` prerequisites are all DONE. Independent sub-specs can run in parallel.
- **Deterministic DAG validator**: when receiving a `PROPOSE_PLAN` from Architect, validates the dependency graph (topological sort, no cycles, all referenced IDs exist, no self-references). Rejects invalid DAGs immediately.
- **Evidence completeness check**: before accepting a `QUALITY_VERDICT`, validates that all plugin-mandatory evidence files exist on disk (deterministic, no LLM).
- **Ping handling (D50)**: watchdog detects ping files within ~100ms. QUESTION urgency gets immediate attention. BLOCKER urgency triggers EA escalation.
- **Adaptive reconciliation (D58)**: interval adjusts from 5s (active) to 120s (idle). Baseline 15s.
- Tracks cycle count and overall progress
- Escalates via reports/escalations/ (EA watches)
- Does NOT communicate with humans directly
- **Spec state-age monitoring**: during each reconciliation cycle, checks `time_in_state` for every active spec. Detects silently stuck specs (e.g., IN_PROGRESS for 30+ minutes with no active agent thread).

### Budget
- Opus tier (always)
- Per-invocation token limit: configurable, default 30,000
- Always-on: token usage tracked via `agent-log.jsonl`

---

## Scout

### Role
Researches prior art before Architect decomposition. A **tool-using LLM agent** (Sonnet tier) that decides whether research is needed based on LLM judgment. Produces a structured `RESEARCH_REPORT` message (Contract A) that helps Architect leverage existing solutions.

### Tools (Contract B)

| Category | Tools |
|----------|-------|
| **Domain** | `read_file`, `web_search`, `bash` (read-only) |
| **State** | `update_spec_status` |
| **Communication** | `send_message` |

### Messages (Contract A)

| Sends | Receives |
|-------|----------|
| `RESEARCH_REPORT` (to spec dir) | `TASK_ASSIGNMENT` (from Pasha) |
| `STATUS_UPDATE` (to Pasha) | |
| `PING` (to Pasha, if needed) | |

### Inputs
- DRAFT spec from Pasha (via `TASK_ASSIGNMENT`)
- Plugin's scout guide (domain-specific research criteria)
- GitHub token (optional, via GITHUB_TOKEN secret for gh CLI)
- PyPI and npm public APIs (no auth required)

### Outputs
- `RESEARCH_REPORT` message written to spec directory
- Spec status update: DRAFT -> SCOUTED

### Trigger
- Pasha delegates a DRAFT spec

### Key Behaviors
- **LLM-based triage**: Scout is a full tool-using agent. It reads the spec, evaluates the task, and decides whether research is needed using LLM judgment. No keyword patterns, no regex classifiers.
- **Confidence markers**: Scout's `RESEARCH_REPORT` includes a `confidence` field (0.0-1.0). Architect evaluates confidence before proceeding -- low confidence may trigger `request_more_research` (D48).
- **SKIP with justification**: if Scout determines no research is needed (e.g., internal refactoring), it writes a `RESEARCH_REPORT` with `confidence > 0.8` and empty candidates. Contract C allows DRAFT -> SCOUTED with explicit skip when confidence > 0.8.
- **RESEARCH path**: uses LLM to generate search queries, then searches all sources:
  - GitHub repos (via gh CLI + bash, graceful fallback if GITHUB_TOKEN unavailable)
  - PyPI packages (via JSON API)
  - npm packages (via registry API)
- **Result deduplication**: merges results by URL across sources
- **Structured output**: `RESEARCH_REPORT` message (Contract A) with candidates, recommendation, confidence, and search queries
- **Plugin integration**: reads plugin's scout guide for domain-specific search criteria
- **Fallback**: if Scout budget is exceeded or Scout encounters errors, deterministic "always research" default (writes minimal report, transitions to SCOUTED)

### Budget
- Sonnet tier
- Per-invocation token limit: configurable, default 20,000
- Designed to be cheap: one LLM call for triage + optional search queries

---

## Architect

### Role
Decomposes high-level tasks into implementable specs with dependency ordering. Reads the project's full context and Scout's research findings. Produces a `PROPOSE_PLAN` message (Contract A) with `depends_on[]` DAG (D52). Can send Scout back for more research if data is insufficient (D48).

### Tools (Contract B)

| Category | Tools |
|----------|-------|
| **Domain** | `read_file`, `glob`, `grep` |
| **Orchestration** | `request_more_research` (D48) |
| **State** | `create_spec`, `read_spec`, `update_spec_status` |
| **Communication** | `send_message`, `ping_supervisor` |

### Messages (Contract A)

| Sends | Receives |
|-------|----------|
| `PROPOSE_PLAN` (to Pasha) | `TASK_ASSIGNMENT` (from Pasha) |
| `REQUEST_CLARIFICATION` (to Pasha) | `RESEARCH_REPORT` (reads from spec dir) |
| `PING` (to Pasha) | |

### Inputs
- SCOUTED spec from Pasha (or DRAFT spec for direct routing)
- `RESEARCH_REPORT` from Scout (reads from spec directory)
- Full project source (codebase, documents, data)
- `.vizier/constitution.md`
- `.vizier/learnings.md`
- Plugin's `architect_guide.md` -- domain-specific decomposition patterns
- Plugin's `criteria/` -- reusable acceptance criteria to reference

### Outputs
- `PROPOSE_PLAN` message with sub-spec definitions, `depends_on` DAG, write-set patterns per sub-spec, and test strategy
- Sub-specs created via `create_spec` after Pasha accepts the plan
- Updated parent spec (status: DECOMPOSED)

### Trigger
- Pasha delegates a SCOUTED spec (normal flow after Scout completes)
- Pasha delegates a DRAFT spec (direct routing, skip Scout)

### Key Behaviors
- Always uses strongest model (Opus-class)
- Reads project thoroughly before writing specs
- **Evaluates Scout confidence**: reads `RESEARCH_REPORT` confidence field. If confidence < 0.5 or critical information is missing, uses `request_more_research(spec_id, questions)` to send Scout back. This transitions the spec back to DRAFT with research questions attached, triggering a second Scout pass.
- **PROPOSE_PLAN with DAG**: outputs a structured plan with `depends_on[]` fields defining sub-spec ordering. Pasha validates the DAG deterministically before accepting.
- **Write-set declaration**: each sub-spec in the plan includes `write_set` glob patterns (e.g., `["src/auth/**", "tests/auth/**"]`). These are enforced by Sentinel during Worker execution.
- **Test strategy**: each plan includes a test strategy describing how sub-specs will be verified
- Uses plugin's decomposition patterns (e.g., "feature -> data model -> logic -> API -> tests")
- References plugin's criteria library via `@criteria/` syntax
- Sets `complexity` field honestly (drives Worker model selection and QG tier escalation)
- References `learnings.md` for known pitfalls
- One concern per sub-spec
- Provides domain-appropriate contracts (interfaces for code, formulas for finance, outlines for docs)

### Budget
- Opus tier
- Per-invocation token limit: configurable, default 80,000
- Higher budget due to codebase reading + plan generation

---

## Worker

### Role
Executes a single spec. Fresh context each time. Produces artifacts within plugin-defined write-set boundaries, validates, commits, exits. Can request clarification and ping supervisor when blocked.

### Tools (Contract B)

| Category | Tools |
|----------|-------|
| **Domain** | `read_file`, `write_file`, `edit_file`, `bash`, `glob`, `grep`, `git`, `run_tests`, `web_search` |
| **Orchestration** | `escalate_to_pasha` |
| **State** | `update_spec_status`, `write_feedback` |
| **Communication** | `send_message`, `ping_supervisor` |

### Messages (Contract A)

| Sends | Receives |
|-------|----------|
| `STATUS_UPDATE` (to Pasha) | `TASK_ASSIGNMENT` (from Pasha) |
| `REQUEST_CLARIFICATION` (to Pasha) | |
| `ESCALATION` (to Pasha) | |
| `PING` (to Pasha) | |

### Inputs
- One READY spec (assigned via `TASK_ASSIGNMENT`)
- Project source files (can read any file, writes bounded by write-set)
- `.vizier/learnings.md` (relevant entries)
- Plugin's system prompt template (rendered with spec context)

### Outputs
- Modified/created artifacts within write-set boundaries
- Git commit (one per spec, using plugin's commit template)
- Status update: REVIEW (success) or feedback file (stuck)
- `STATUS_UPDATE` messages during execution

### Trigger
- Assigned a READY spec by Pasha via `TASK_ASSIGNMENT`

### Write-set Enforcement (D55)

Instead of a fixed artifact list per spec, the **plugin defines write-set boundaries as glob patterns**:

```yaml
# Software plugin write-set
worker_write_set:
  - "src/**/*.py"
  - "tests/**/*.py"
  - "docs/**/*.md"
  - "pyproject.toml"
  - "*.cfg"
  - "*.toml"

# Documents plugin write-set
worker_write_set:
  - "docs/**"
  - "templates/**"
  - "assets/**"
```

Sentinel matches every `write_file` / `edit_file` call against the write-set. Writes outside the pattern are denied. Individual specs can further restrict the write-set (Architect declares per-sub-spec write-set in `PROPOSE_PLAN`).

### Key Behaviors
- **Fresh context per task** -- no memory of previous tasks (D2)
- **Glob-pattern write-set** -- can read any project file, but can only write to files matching plugin/spec write-set patterns. Sentinel enforces via glob matching. Reads beyond write-set are logged for Retrospective analysis.
- **Clarification and escalation** -- if spec is insufficient, sends `REQUEST_CLARIFICATION` (with `blocking: true` if critical) or escalates via `ESCALATION`. Uses `ping_supervisor(BLOCKER)` for immediate attention (D50).
- **Implicit completion** -- Worker exits cleanly -> spec transitions to REVIEW. No magic string signal.
- Model tier set by spec's `complexity` field. Bumped automatically on retry 3 (graduated retry, D25).
- Uses only tools permitted by plugin policy, enforced by Sentinel (allowlist + denylist + Haiku)
- Loop Guardian (D51) monitors for spinning (identical calls 3x, Haiku checkpoint every 5 tool calls)

### Budget
- Sonnet tier (default), Opus on retry 3+ or HIGH complexity
- Per-invocation token limit: configurable, default 100,000
- Highest budget among inner-loop agents (does the most work)

---

## Quality Gate

### Role
Validates Worker output against spec's acceptance criteria. Produces a structured `QUALITY_VERDICT` (Contract A) with mandatory evidence. Can approve (DONE) or reject with actionable feedback. Uses Opus tier for HIGH complexity semantic review (D49).

### Tools (Contract B)

| Category | Tools |
|----------|-------|
| **Domain** | `read_file`, `glob`, `grep`, `bash`, `run_tests` |
| **State** | `update_spec_status`, `write_feedback` |
| **Communication** | `send_message`, `ping_supervisor` |

### Messages (Contract A)

| Sends | Receives |
|-------|----------|
| `QUALITY_VERDICT` (to spec dir) | `TASK_ASSIGNMENT` (from Pasha) |
| `STATUS_UPDATE` (to Pasha) | |
| `PING` (to Pasha, if needed) | |

### Inputs
- Spec in REVIEW status (via `TASK_ASSIGNMENT`)
- Worker's output (git diff for code, file diff for others)
- Acceptance criteria from spec (including `@criteria/` references resolved from plugin)
- `.vizier/learnings.md`

### Outputs
- `QUALITY_VERDICT` message with per-criterion PASS/FAIL + evidence links
- Evidence files stored in `specs/NNN/evidence/`
- Status update: DONE (approved) or REJECTED (with feedback)
- Feedback file in `specs/NNN/feedback/YYYY-MM-DD-NNN.md` (on rejection)

### Trigger
- Spec transitions to REVIEW status

### QUALITY_VERDICT Structure (D56)

```json
{
  "type": "QUALITY_VERDICT",
  "spec_id": "001-jwt-auth/001-data-model",
  "pass_fail": "PASS",
  "criteria_results": [
    {"criterion": "All tests pass", "result": "PASS", "evidence_link": "specs/.../evidence/test_output.txt"},
    {"criterion": "No lint errors", "result": "PASS", "evidence_link": "specs/.../evidence/lint_output.txt"},
    {"criterion": "Type check clean", "result": "PASS", "evidence_link": "specs/.../evidence/pyright_output.txt"},
    {"criterion": "User model has password hashing", "result": "PASS", "evidence_link": "specs/.../evidence/diff.patch"}
  ],
  "suggested_fix": [],
  "timestamp": "2026-02-19T10:45:00Z"
}
```

Every verdict must include evidence links to real files on disk. Pasha validates evidence completeness before accepting.

### Plugin-Mandatory Evidence Types

| Plugin | Required Evidence | File |
|--------|-------------------|------|
| Software | Test output | `evidence/test_output.txt` (pytest stdout) |
| Software | Lint output | `evidence/lint_output.txt` (ruff check) |
| Software | Type check output | `evidence/pyright_output.txt` (pyright) |
| Software | Diff | `evidence/diff.patch` (git diff) |
| Documents | Link check | `evidence/link_check_output.txt` |
| Documents | Structure validation | `evidence/structure_validation.txt` |
| Documents | Rendered preview | `evidence/rendered_preview_path.txt` |
| Custom | Declared in plugin config | Plugin-defined |

### Completion Protocol (PCC)

Multi-pass protocol when a spec transitions to REVIEW. **Mandatory: `run_tests` must be called before any LLM-assisted passes.** Test output is real evidence, not LLM judgment.

**Pass 1 -- Hygiene (deterministic, no LLM)**
- Check for debug artifacts (print statements, console.log, TODO markers, commented-out code)
- Verify no hardcoded test values or credentials
- Confirm changes stay within spec's write-set patterns (no unintended file modifications)

**Pass 2 -- Mechanical Quality (deterministic, no LLM)**
- Run plugin's automated checks (lint, format, type check, secret scan)
- **Must call `run_tests`** -- captures real test output to evidence file
- All checks must pass before proceeding to LLM-assisted passes
- Failures here -> immediate REJECTED with specific fix instructions (cheap, no tokens burned)

**Pass 3 -- Test Validation (LLM-assisted)**
- Analyzes test output from Pass 2 (real data, not self-assessment)
- Tests are meaningful (prove behavior, not just assert True)
- Coverage of spec's requirements (functional coverage, not just line coverage)

**Pass 4 -- Acceptance Criteria (LLM-assisted)**
- Verify ALL criteria listed in the current spec
- Resolve `@criteria/` references from plugin's criteria library
- Cumulative check: verify that parent spec criteria still hold if the change could affect them

**Pass 5 -- Consistency (LLM-assisted)**
- Changes are consistent with project constitution and learnings.md
- Any documentation affected by the change is updated
- No regressions introduced to previously completed specs

**Protocol rules:**
- Passes 1-2 are fast and cheap -- always run first, fail fast before spending tokens
- Passes 3-5 can run in parallel where independent
- Any pass failure -> REJECTED with specific, actionable feedback per failing item
- All passes succeed -> DONE with QUALITY_VERDICT + all evidence files
- The protocol is implemented within the Quality Gate agent, not as separate agents

### Model Tier Escalation (D49)

| Spec Complexity | Passes 1-2 (Mechanical) | Passes 3-5 (Semantic) |
|-----------------|------------------------|-----------------------|
| LOW | Sonnet | Sonnet |
| MEDIUM | Sonnet | Sonnet |
| HIGH | Sonnet | **Opus** |

For HIGH complexity specs, the semantic passes (3-5) automatically use Opus tier. This prevents the "blind leading blind" problem where Sonnet-QG misses Sonnet-Worker's logic errors. `ModelRouter` already supports complexity-based tier resolution -- extended to QG role.

### Budget
- Sonnet tier (default), Opus for HIGH complexity semantic passes (D49)
- Per-invocation token limit: configurable, default 50,000
- Higher budget when running Opus semantic passes

---

## Retrospective

### Role
Analyzes failures, patterns, and inefficiencies. Updates process files to prevent repeated mistakes. Maintains a **process debt register** tracking recurring patterns. Bases proposals on evidence from Golden Trace data (D57).

### Tools (Contract B)

| Category | Tools |
|----------|-------|
| **Domain** | `read_file`, `glob`, `grep` |
| **State** | `read_spec`, `list_specs` |
| **Communication** | `send_message` |

### Messages (Contract A)

| Sends | Receives |
|-------|----------|
| `STATUS_UPDATE` (to Pasha) | `TASK_ASSIGNMENT` (from Pasha) |

### Inputs
- Same as Pasha (all spec events, state, reports)
- `specs/**/feedback/` -- rejection history
- `specs/**/trace.jsonl` -- Golden Trace data (D57) with all tool calls, messages, verdicts
- STUCK specs and their retry histories
- `.vizier/learnings.md` (current state)
- `reports/budget.json` -- cost data

### Outputs
- Updated `.vizier/learnings.md` (direct write)
- `.vizier/proposals/*.md` -- suggested changes for human review:
  - Prompt modifications
  - New criteria for the plugin's library
  - Acceptance criteria template changes
  - Process rule changes
- Process debt register entries

### Trigger
- End of each completion cycle (spec goes DONE)
- Any spec goes STUCK
- Periodic (configurable, e.g., daily)

### Key Behaviors
- **Golden Trace analysis (D57)**: reads `trace.jsonl` files to analyze actual agent behavior -- tool call patterns, timing, error rates, escalation chains
- **Process debt register**: tracks recurring patterns across specs:
  - Same rejection type appearing 3+ times
  - Same files causing repeated issues
  - Agents consistently reading outside write-set
  - Specific tool calls that frequently fail
  - Budget overruns by agent type
- **Evidence-based proposals**: every proposal cites specific trace data, rejection patterns, or metric changes as evidence
- Can update `learnings.md` directly (low-risk, append-only)
- Writes proposals for structural changes -- **ALL proposals require Sultan approval, always** (no auto-approve, no graduation to autonomous changes)
- Constrained scope:
  - CAN change: learnings (direct), criteria/prompt/process proposals (with approval)
  - CANNOT change: architecture, agent topology, plugin interfaces
- Tracks improvement metrics: rejection rate, stuck rate, average retries, cycle time, cost per spec
- Compares metrics across cycles to measure whether changes helped
- Analyzes cost data from structured agent logs and budget reports

### Budget
- Opus tier
- Per-invocation token limit: configurable, default 50,000
- Runs periodically, not per-spec

---

## Sentinel (Security Service)

Sentinel is **not an LLM agent**. It is a deterministic security service that gates every tool call via a 5-stage pipeline:

1. **Allowlist** (zero cost) -- instant ALLOW for known-safe calls
2. **Denylist** (zero cost) -- instant DENY for known-dangerous calls
3. **Write-set enforcer** (zero cost) -- DENY `write_file`/`edit_file` calls outside plugin write-set patterns (D55)
4. **Secret scanner** (zero cost) -- DENY if secrets detected in arguments
5. **Git classifier** (zero cost) -- classify git operations as safe/dangerous
6. **Haiku evaluator** (~$0.001) -- for ambiguous calls that pass all previous stages

Sentinel is called by `AgentRuntime` as a PreToolUse hook before every tool invocation. Denied calls return an error message to Claude, which must adapt or escalate.

Implementation: `libs/core/vizier/core/sentinel/engine.py`

---

## Loop Guardian (D51)

Loop Guardian is integrated into `AgentRuntime`, not a separate agent. It monitors agent behavior and detects spinning:

**Deterministic detection** (zero cost):
- Identical tool calls (same name + same arguments) repeated 3+ times -> immediate HALT + forced escalation to Pasha

**LLM checkpoint** (every N tool calls, default 5):
- Sends last N tool calls + results to Haiku (~$0.001 per checkpoint)
- Haiku evaluates: "Is this agent making progress or spinning?"
- Returns: CONTINUE / WARN (log, continue) / HALT (force escalation to Pasha)

Implementation: Part of `AgentRuntime` in `libs/core/vizier/core/runtime/`

---

## Cross-Reference: Supervision Hierarchy

```
Sultan (human)
  |
  EA (Opus, always-on)
  |
  +-- Pasha (Opus, per-project, always-on)
        |
        +-- Scout (Sonnet, spawned per DRAFT spec)
        +-- Architect (Opus, spawned per SCOUTED spec)
        |     |
        |     +-- request_more_research -> Scout (D48)
        |
        +-- Worker (Sonnet/Opus, spawned per READY spec)
        +-- Quality Gate (Sonnet/Opus, spawned per REVIEW spec)
        +-- Retrospective (Opus, spawned periodically)

Sentinel: deterministic security service, gates ALL tool calls
Loop Guardian: behavioral monitor, integrated into AgentRuntime
```

**Escalation path**: Agent -> Pasha -> EA -> Sultan

**Communication**: All inter-agent communication uses typed messages (Contract A) written to the filesystem. `ping_supervisor` (D50) provides sub-second notification via watchdog filesystem events.
