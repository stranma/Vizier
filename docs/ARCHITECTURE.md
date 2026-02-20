# Vizier-on-OpenClaw Architecture

## 1. Overview

Vizier is an autonomous multi-agent work system using the Ottoman court metaphor. It receives high-level tasks from humans, decomposes them into actionable specs, executes them through specialized agents, and reports back.

**What changed:** Vizier's runtime is now **OpenClaw** -- an open-source gateway that provides multi-channel messaging (Telegram, WhatsApp, Discord, iMessage, Web UI, mobile apps), session management, tool infrastructure, and memory. Vizier's custom daemon, transport layer (aiogram/Telegram), and agent runtime are replaced by OpenClaw's battle-tested equivalents.

**What's preserved:** Vizier's domain intelligence -- spec lifecycle, agent orchestration, quality gates, Sentinel security -- lives on as a **FastMCP server** that OpenClaw agents call via tool use.

### v1 Scope (D75)

v1 delivers the first working end-to-end loop: Sultan gives task to Vizier, Vizier delegates to Pasha, Pasha assigns Worker, Worker implements, QG validates, result reported back. This requires **15 MCP tools** and **4 agent roles**.

**v1 boundary:** If it doesn't block the first spec going from DRAFT to DONE, it's v2.

**Ottoman court metaphor:**

| Role | Description | OpenClaw mapping | v1? |
|------|-------------|------------------|-----|
| **Sultan** | Human operator (CEO/CTO) | OpenClaw user (any channel) | YES |
| **Vizier** | Grand Vizier -- main agent, singleton | OpenClaw persistent session (Opus) | YES |
| **Pasha** | Per-project orchestrator | OpenClaw sub-session per project (Opus) | YES |
| **Worker** | Spec executor (fresh context per task) | OpenClaw spawned sub-session (Sonnet/Opus) | YES |
| **Quality Gate** | Work validator | OpenClaw spawned sub-session (Sonnet/Opus) | YES |
| **Sentinel** | Security enforcer (deterministic, not LLM) | MCP tools on Vizier MCP server | YES |
| **Scout** | Prior art researcher | OpenClaw spawned sub-session (Sonnet) | v2 |
| **Architect** | Task decomposer | OpenClaw spawned sub-session (Opus) | v2 |
| **Retrospective** | Failure analyzer, meta-improver | OpenClaw spawned sub-session (Opus) | v2 |

---

## 2. System Topology

```
Sultan (any channel: Telegram, WhatsApp, Discord, iMessage, Web UI, mobile)
  |
  OpenClaw Gateway (sessions, routing, tools, media, memory)
  |
  Vizier (main agent session, Opus, persistent)
    |
    +-- Pasha-{project} (sub-session per project, Opus, persistent)
    |     +-- Sentinel-{project} (MCP-enforced security per project)
    |     +-- Worker (sub-session, spawned per spec, fresh context)
    |     +-- Quality Gate (sub-session, spawned per review)
    |
    +-- Vizier MCP Server (Python, FastMCP)
          +-- Spec tools (CRUD, state machine, lifecycle)
          +-- Sentinel tools (write-set, command checking, web fetch)
          +-- Orchestration tools (scan, assign, ping)
          +-- DAG tool (check dependencies)
          +-- Config tool (project configuration)
```

**Key insight:** OpenClaw handles everything above the line (channels, sessions, routing, memory, tool infra). Vizier's MCP server handles everything below (domain logic, security, orchestration). The agents themselves are OpenClaw sessions with SOUL.md prompts that call MCP tools.

### v2 Additions

v2 adds to the topology: Scout (research sub-sessions), Architect (decomposition sub-sessions), Retrospective (periodic analysis sub-sessions), Budget tools, Evidence tools, Plugin framework, Verification tools, Research tool, Learnings injection tool.

---

## 3. Vizier MCP Server

All Vizier domain logic is exposed as MCP tools via a **FastMCP** Python server. OpenClaw agents call these tools to interact with the spec lifecycle, Sentinel, orchestration, and project configuration.

### 3.1 v1 Tool Groups (15 tools)

#### Spec Lifecycle (6 tools)

| Tool | Description | Inputs | Returns |
|------|-------------|--------|---------|
| `spec_create` | Create a new spec in DRAFT state | project_id, title, description, complexity, artifacts, criteria, depends_on | spec_id |
| `spec_read` | Read spec contents and metadata | spec_id | spec object (frontmatter + body) |
| `spec_list` | List specs with optional status filter | project_id, status_filter? | list of spec summaries |
| `spec_transition` | Transition spec to new state (validates state machine) | spec_id, new_status, agent_role | success/error with reason |
| `spec_update` | Update spec fields (retry count, assigned agent, etc.) | spec_id, fields | updated spec |
| `spec_write_feedback` | Write QG feedback or rejection reason | spec_id, verdict, feedback | feedback file path |

#### Sentinel + Execution (3 tools)

| Tool | Description | Inputs | Returns |
|------|-------------|--------|---------|
| `sentinel_check_write` | Validate file write against project write-set | project_id, file_path, agent_role | allow/deny with reason |
| `run_command_checked` | Execute shell command after Sentinel validation (D67) | project_id, command, agent_role | allow/deny + output + exit_code |
| `web_fetch_checked` | Fetch URL and scan content for injection (D67) | url, agent_role | safe/content or suspicious/reason |

#### Orchestration (4 tools)

| Tool | Description | Inputs | Returns |
|------|-------------|--------|---------|
| `orch_scan_specs` | Scan all specs and return actionable items | project_id | specs needing attention (by state) |
| `orch_check_ready` | Check if a spec's dependencies are satisfied | spec_id | ready/blocked with blocking spec IDs |
| `orch_assign_worker` | Claim a spec for a worker agent | spec_id, agent_session_id | assignment confirmation |
| `orch_write_ping` | Write a supervisor notification | spec_id, urgency, message | ping file path |

#### DAG + Config (2 tools)

| Tool | Description | Inputs | Returns |
|------|-------------|--------|---------|
| `dag_check_dependencies` | Check which specs are unblocked | project_id | list of unblocked spec IDs |
| `project_get_config` | Get project configuration (write-set, criteria, etc.) | project_id | config object |

### 3.2 v2 Tools (Deferred)

These tools are designed but not in v1 scope. See D75 for rationale.

| Group | Tool | Description |
|-------|------|-------------|
| Budget | `budget_track` | Record an agent invocation cost |
| Budget | `budget_check` | Check current spend against thresholds |
| Budget | `budget_get_summary` | Get cost breakdown by project/agent/model |
| Evidence | `evidence_check` | Check if all required evidence is present |
| Evidence | `evidence_write_verdict` | Write structured QG verdict with evidence links |
| Plugin | `plugin_get_write_set` | Get allowed write patterns for project |
| Plugin | `plugin_get_evidence_requirements` | Get required evidence types |
| Plugin | `plugin_get_system_prompt` | Get domain-specific prompt module for agent role |
| Plugin | `plugin_get_criteria` | Get criteria library entries |
| Plugin | `plugin_get_decomposition_guide` | Get Architect's decomposition patterns |
| Verification | `verify_tests` | Run plugin's test suite for spec artifacts |
| Verification | `verify_lint` | Run linter on spec's modified files |
| Verification | `verify_types` | Run type checker on spec's modified files |
| Research | `research_topic` | Lightweight research on a topic |
| Learnings | `get_relevant_learnings` | Get learnings relevant to a spec/role |
| Sentinel | `sentinel_check_command` | Validate shell command (subsumed by run_command_checked) |
| Sentinel | `sentinel_scan_content` | Scan untrusted content (folded into web_fetch_checked) |
| Sentinel | `sentinel_get_policy` | Get current project security policy |
| DAG | `dag_validate` | Validate dependency graph (cycles, missing refs) |
| DAG | `dag_get_order` | Get topological execution order |
| Orchestration | `orch_scan_pings` | Read pending supervisor notifications |

### 3.3 Server Configuration

The MCP server reads its configuration from `vizier-mcp/config.yaml`:

```yaml
vizier_root: /data/vizier
projects_dir: /data/vizier/projects
sentinel:
  default_policy: strict
  haiku_model: claude-haiku-4-5-20251001
  sentinel_learning: true           # Auto-promote after N Haiku approvals (D75)
  learning_threshold: 3
file_locking: true                   # fcntl/msvcrt locks on spec writes (D75)
```

### 3.4 Filesystem Layout (Managed by MCP Server)

```
/data/vizier/
  projects/
    {project-id}/
      config.yaml                    # Project config (write-set, criteria, etc.)
      sentinel.yaml                  # Sentinel policy (allowlist/denylist/roles)
      sentinel_learned.yaml          # Auto-promoted commands (D75)
      specs/
        001-feature-name/
          spec.md                    # Spec document (frontmatter + body)
          feedback/                  # QG feedback files
      reports/
        status.json                  # Current project status
      learnings.md                   # Learnings (v1: hand-maintained, v2: Retrospective-managed)
```

---

## 4. Agent Definitions

All agents are **OpenClaw sessions**. Their behavior is defined by SOUL.md files (system prompts), available tools (OpenClaw native + Vizier MCP), and session configuration (model tier, persistence, spawn rules).

### 4.1 Vizier (Main Agent)

**Role:** The Grand Vizier. Single entry point for the Sultan. Routes tasks to projects, manages commitments, provides briefings, handles cross-project coordination. **The only agent that communicates with the Sultan** (One Voice Policy, D75).

**OpenClaw session type:** Persistent (always available, maintains conversation history via OpenClaw memory)

**Model:** Opus

**Tools available:**
- OpenClaw native: web_search, browser, file tools, memory, sessions_spawn, sessions_send, sessions_list
- Vizier MCP: spec_create, spec_list, orch_scan_specs, project_get_config

**SOUL.md sketch:**
```markdown
You are the Grand Vizier -- the Sultan's most capable and trusted advisor.
You manage the Sultan's projects, commitments, and priorities.

## One Voice Policy
You are the ONLY agent that communicates with the Sultan. No other agent
messages the Sultan directly. All status updates, questions, and escalations
from Pashas and their agents flow through you. You decide what's worth
surfacing to the Sultan.

## Delegating to Pashas
When the Sultan gives you a task:
1. Create a spec via spec_create(project_id, title, description, ...)
2. Send a message to the project's Pasha via sessions_send telling them to handle it
3. Report back to the Sultan when Pasha reports completion

## Your Responsibilities
- Receive tasks from the Sultan and route them to the appropriate Pasha
- Create new projects and assign Pashas
- Provide status updates, morning briefings, and proactive alerts
- Track commitments and deadlines across all projects
- Handle cross-project coordination
- Answer direct questions using your knowledge and tools

## Memory Management
- Proactively write critical state to memory: active commitments, pending decisions, project priorities
- Don't rely on conversation history for important state -- write it to MEMORY.md or daily logs
- After receiving important updates, confirm key details are in memory

## Communication Style
- Concise, actionable, no fluff
- Proactive about risks and deadlines
- Always frame updates in terms of the Sultan's priorities
```

**Inputs:** Sultan messages via any OpenClaw channel
**Outputs:** Responses to Sultan, delegations to Pashas, status summaries

### 4.2 Pasha (Per-Project Orchestrator)

**Role:** Provincial governor. Owns a single project's lifecycle. Manages the inner loop: Worker -> Quality Gate -> Done.

**OpenClaw session type:** Persistent sub-session (one per project, long-lived)

**Model:** Opus

**Trigger model (D75):** Vizier-initiated. Pasha is activated by messages from Vizier, not by autonomous polling. When Vizier creates a spec and sends a message, Pasha scans specs and takes action.

**Tools available:**
- OpenClaw native: sessions_spawn, sessions_send, sessions_list
- Vizier MCP: spec_read, spec_list, spec_transition, spec_update, orch_scan_specs, orch_check_ready, orch_assign_worker, orch_write_ping, dag_check_dependencies, project_get_config

**SOUL.md sketch:**
```markdown
You are Pasha-{project_name}, the governor of the {project_name} project.
You report to the Grand Vizier and manage all work within your project.

## Trigger Model
You are activated by messages from the Vizier, not by polling.
When Vizier sends you a task:
1. Scan specs for actionable items (orch_scan_specs)
2. For DRAFT specs: review and promote to READY (spec_transition)
3. For READY specs: check dependencies (orch_check_ready), spawn Worker
4. For REVIEW specs: spawn Quality Gate
5. Handle rejections with graduated retry
6. Report results to the Vizier via sessions_send

## Graduated Retry
- Retry 1-3: Normal retry with QG feedback included in Worker spawn context
- Retry 4+: Mark STUCK (spec_transition), escalate to Vizier via sessions_send

## Reporting
Report all status changes to Vizier via sessions_send.
Never message the Sultan directly -- the Vizier handles all Sultan communication.

## Memory Management
- Write project status, active specs, and pending decisions to memory proactively
- After compaction, re-read project state via orch_scan_specs

## Sentinel
Your project has a dedicated Sentinel enforcing security policies.
All inner agents' commands go through run_command_checked.
```

**Inputs:** Messages from Vizier, spec state changes
**Outputs:** Agent spawn decisions, status reports to Vizier, escalations

### 4.3 Worker (Spec Executor)

**Role:** Executor. Takes a single READY spec and implements it. Fresh context, one spec, exit.

**OpenClaw session type:** Spawned sub-session (fresh context per spec, exits on completion)

**Model:** Sonnet

**Tools available:**
- OpenClaw native: file_read, file_write, edit_file, web_search
- Vizier MCP: spec_read, spec_transition, run_command_checked, web_fetch_checked, orch_write_ping, project_get_config

**SOUL.md sketch:**
```markdown
You are a Worker -- you implement exactly one spec, then exit.
You receive a spec ID. Read it, implement it, transition to REVIEW.

## Your Process
1. Read the spec (spec_read)
2. Read the project's learnings.md for any relevant lessons from past work
3. Read any QG feedback from previous attempts
4. Implement the artifacts listed in the spec
5. Before transitioning to REVIEW, run the project's test command, linter,
   and type checker via run_command_checked. Fix any failures.
6. When all checks pass, transition spec to REVIEW (spec_transition)

## Command Execution
All shell commands go through run_command_checked(project_id, command, "worker").
You cannot run commands directly -- Sentinel validates every command.

## Web Access
All URL fetches go through web_fetch_checked(url, "worker").
Content is scanned for prompt injection before you see it.

## Rules
- Write ONLY files listed in the spec's artifact list
- You may READ any file for context (bounded exploration)
- If blocked, ping your supervisor (orch_write_ping) with urgency QUESTION
- If fundamentally stuck, ping with urgency BLOCKER
- Do not loop on the same failing approach -- escalate
```

**Inputs:** READY spec ID, optional QG feedback from previous attempt
**Outputs:** Implemented artifacts, spec transitioned to REVIEW

### 4.4 Quality Gate (Work Validator)

**Role:** Validator. Reviews completed work against spec criteria using a structured multi-pass protocol.

**OpenClaw session type:** Spawned sub-session (fresh context per review)

**Model:** Sonnet (Opus for HIGH complexity specs, D49)

**Tools available:**
- OpenClaw native: file_read
- Vizier MCP: spec_read, spec_transition, spec_write_feedback, run_command_checked, project_get_config

**SOUL.md sketch:**
```markdown
You are a Quality Gate -- you validate completed work using a
structured multi-pass protocol. You are the last line of defense.

## Completion Protocol (4 passes)
Worker should have run tests, lint, and type checks before REVIEW.
Your role is semantic quality:

Pass 1 (Hygiene): Check for debug prints, breakpoints, TODOs, hardcoded values
Pass 2 (Mechanical): Verify tests pass, lint clean, types clean via run_command_checked
Pass 3 (Criteria): Evaluate each acceptance criterion from the spec
Pass 4 (Verdict): Write verdict with per-criterion PASS/FAIL

If Worker missed mechanical issues, that's a REJECT with feedback noting
the specific failures.

## Rules
- ACCEPT: all criteria pass, mechanical checks pass
- REJECT: write detailed feedback (spec_write_feedback) so Worker can fix
- Include test/lint/type output in your feedback
```

**Inputs:** REVIEW spec ID
**Outputs:** Verdict (ACCEPT/REJECT), spec DONE or REJECTED

---

## 5. Sentinel Architecture

Sentinel is a **deterministic security service**, not an LLM agent. It enforces per-project security policies via MCP tools that agents call before performing sensitive operations.

### 5.1 Per-Project Sentinels

Each project has a dedicated Sentinel configuration:

```yaml
# projects/{project-id}/sentinel.yaml
write_set:
  - "src/**/*.py"
  - "tests/**/*.py"
  - "docs/**/*.md"
  - "pyproject.toml"

command_allowlist:
  - "pytest"
  - "ruff check"
  - "ruff format"
  - "pyright"
  - "git status"
  - "git diff"
  - "git log"
  - "git add"
  - "git commit"

command_denylist:
  - "rm -rf"
  - "sudo"
  - "git push --force"
  - "git push -f"
  - "git reset --hard"
  - "git clean"
  - pattern: "printenv|^env$|os\\.environ|process\\.env"
    reason: "Environment exfiltration blocked"

role_permissions:
  worker:
    can_write: true       # Within write-set only
    can_bash: true        # Allowlisted commands only
    can_read: true        # Any file (bounded exploration)
  quality_gate:
    can_write: false      # Writes verdicts via MCP, not direct file writes
    can_bash: true        # Needs to run tests
    can_read: true
```

### 5.2 Three-Tier Enforcement (D24)

| Tier | Mechanism | Cost | Example |
|------|-----------|------|---------|
| **Allowlist** | Glob/regex match | Zero | `write src/auth.py` matches `src/**/*.py` |
| **Denylist** | Glob/regex match | Zero | `git push --force` matches denylist |
| **Ambiguous** | Haiku evaluation | ~$0.001 | Unfamiliar bash command, indirect invocation |

The MCP server handles all three tiers internally. `run_command_checked` combines Sentinel validation and command execution in a single call. `web_fetch_checked` combines content scanning and fetch. Both are enforced at the OpenClaw tool policy level (see section 5.4).

### 5.3 Haiku Fallback

For ambiguous cases (not in allowlist or denylist), the MCP server calls Haiku to evaluate intent:

```python
@mcp.tool()
async def run_command_checked(project_id: str, command: str, agent_role: str) -> dict:
    policy = load_policy(project_id)

    # Tier 1: Allowlist
    if policy.is_allowlisted(command):
        return execute_and_return(command)

    # Tier 2: Denylist
    if deny_reason := policy.is_denylisted(command):
        return {"allowed": False, "reason": deny_reason}

    # Tier 3: Haiku evaluation
    verdict = await haiku_evaluate(command, agent_role, policy)
    if verdict.decision == "allow":
        track_haiku_approval(project_id, command)  # For Sentinel Learning
        return execute_and_return(command)
    return {"allowed": False, "reason": verdict.reason}
```

### 5.4 Enforcement via Tool Policy (OpenClaw Integration)

Sentinel enforcement uses a combination of OpenClaw tool policy (mandatory)
and MCP tools (convenience):

| Operation | Enforcement | Mechanism |
|-----------|------------|-----------|
| Shell commands | MANDATORY | Native bash/exec blocked by tool policy. All commands via `run_command_checked` MCP tool. |
| File writes (in scope) | ALLOWED | OpenClaw native file_write within project workspace. No Sentinel check needed. |
| File writes (out of scope) | MANDATORY | `sentinel_check_write` MCP tool required. Tool policy restricts writes outside workspace. |
| Web fetch | MANDATORY | Native web fetch blocked. All fetches via `web_fetch_checked` MCP tool (content scanner). |
| File reads | ALLOWED | Any file readable (bounded exploration, D23). |

This means agents physically cannot bypass Sentinel for high-risk operations
(commands, out-of-scope writes, web access). Low-risk operations
(in-scope file writes, file reads) proceed without friction.

### 5.5 Sentinel Learning (D75)

For commands approved by Haiku evaluation, the MCP server tracks approval history per project. After a command pattern is approved 3 times for the same project, it is auto-promoted to the project's allowlist. This eliminates repeated Haiku latency for common build/test operations.

The learning state is stored in `projects/{project-id}/sentinel_learned.yaml`:

```yaml
learned_commands:
  - pattern: "npm run build"
    approved_count: 3
    first_approved: "2026-02-20T10:00:00Z"
    last_approved: "2026-02-20T14:30:00Z"
```

Auto-promoted commands can be manually removed by editing `sentinel_learned.yaml`.

---

## 6. Communication Model

### 6.1 Sultan <-> Vizier

Sultan communicates with the Vizier agent through **any OpenClaw channel** (Telegram, WhatsApp, Discord, iMessage, Web UI, mobile app). OpenClaw handles channel routing, message formatting, and session persistence.

The Vizier agent is a persistent OpenClaw session. It maintains conversation history via OpenClaw's built-in memory system.

### 6.2 Vizier <-> Pasha

Vizier delegates to Pashas via:
- **`spec_create`** (Vizier MCP): Create new specs in a project
- **`sessions_send`** (OpenClaw native): Tell Pasha to handle the new spec

Pashas report back to Vizier via:
- **`sessions_send`**: Completion notifications, escalations (STUCK specs)

**Trigger model (D75):** Pasha is activated by Vizier sending a message, not by autonomous polling. This eliminates the expensive Opus-as-doorbell-watcher anti-pattern.

### 6.3 Pasha <-> Inner Agents

Pasha spawns inner agents via **`sessions_spawn`** (OpenClaw native). Each spawned session receives:
- The spec ID to work on
- QG feedback from previous attempts (for retries)

Inner agents communicate back to Pasha via:
- **`orch_write_ping`** (Vizier MCP): For questions, blockers, and status pings
- **`spec_transition`** (Vizier MCP): State changes (REVIEW, DONE, etc.) that Pasha detects when triggered

### 6.4 All Agents <-> Domain Logic

All agents interact with Vizier's domain logic **exclusively through MCP tools**. No agent directly reads or writes spec files, state files, or configuration. The MCP server is the single point of control, using file locking to prevent race conditions (D75).

```
Agent decision: "I need to write src/auth.py"
  -> sentinel_check_write(project_id, "src/auth.py", "worker")
  -> MCP server checks write-set, returns allow
  -> Agent uses OpenClaw file_write tool

Agent decision: "I'm done with this spec"
  -> spec_transition(spec_id, "REVIEW", "worker")
  -> MCP server validates state machine, transitions spec
  -> Pasha picks up when Vizier triggers next scan
```

### 6.5 One Voice Policy (D75)

Only the Vizier agent communicates with the Sultan. This prevents notification overload from multiple agents competing for human attention.

| Agent | Can message Sultan? | Reports to |
|-------|---------------------|------------|
| Vizier | YES (sole communicator) | Sultan |
| Pasha | NO | Vizier (via sessions_send) |
| Worker | NO | Pasha (via orch_write_ping) |
| Quality Gate | NO | Pasha (via spec_write_feedback + spec_transition) |

Escalation path: Worker -> Pasha -> Vizier -> Sultan.
Urgent items (STUCK specs) flow up the chain, but only Vizier decides when to surface them to the Sultan.

---

## 7. Decision Map Update

Mapping old decisions (D1-D74) to the new architecture. Each is **KEPT**, **MODIFIED**, **REPLACED**, **REVERSED**, or **DROPPED**.

### KEPT (unchanged)

| Decision | Summary | Why kept |
|----------|---------|----------|
| D1 | Multi-agent over single-agent loop | Core architecture unchanged |
| D2 | Fresh context per task | Workers still spawn fresh per spec |
| D4 | Filesystem as message bus | MCP server still uses filesystem for specs |
| D7 | Architect must be exhaustively specific | Same decomposition philosophy (v2) |
| D8 | Retrospective as separate agent | Same role (v2) |
| D16 | Ottoman court naming | Preserved, "EA" renamed to "Vizier" |
| D18 | Least privilege per role | Now enforced via per-project Sentinel MCP |
| D19 | Sentinel -- deterministic + Haiku hybrid | Now exposed as MCP tools |
| D21 | Vizier stays monolithic and powerful | Same philosophy, OpenClaw session |
| D22 | Reconciliation -- events as optimization, disk as truth | MCP server scans filesystem |
| D23 | Workers get bounded read-only exploration | Unchanged |
| D24 | Permission enforcement: allowlist + denylist + Haiku | Now via MCP Sentinel tools |
| D26 | Retrospective always requires human approval | Unchanged (v2) |
| D29 | Completion signal, criteria versioning, graceful shutdown | Unchanged |
| D40 | Atomic writes via os.replace() | MCP server uses atomic writes |
| D44 | Progressive autonomy rollout | Unchanged |
| D46 | Agent System Reset | Already executed; this is the second reset |
| D49 | QG Model Tier Escalation | Opus for HIGH complexity unchanged |
| D50 | Synchronous supervisor notification (ping) | Now via MCP orch_write_ping |
| D52 | Spec Dependency DAG | Now via MCP DAG tools |
| D55 | Write-set via glob patterns | Now enforced via MCP sentinel_check_write |
| D67 | Sentinel enforcement via tool policy | Core security, v1 |
| D71 | Dynamic pipeline selection by Pasha | Simplified for v1 (Worker-only or escalate) |
| D73 | Context management for persistent agents | Compaction + memory still needed |

### MODIFIED

| Decision | Old | New | Why |
|----------|-----|-----|-----|
| D2 | Fresh LLM call per message/event | OpenClaw session management; sub-sessions spawned fresh per task | OpenClaw manages session lifecycle |
| D3 | Rules-based model router | Model tier specified per agent in OpenClaw config | OpenClaw handles model selection per session |
| D6 | Python plugin packages with entry points | v1: hardcoded config via project_get_config. v2: plugins as MCP tool providers | Plugin framework deferred (D75) |
| D9 | Hybrid deployment (package + daemon) | OpenClaw deployment + MCP server sidecar | OpenClaw replaces custom daemon |
| D20 | Three-layer use of claude-code-python-template | Layer 1 (build tooling) kept, Layer 2-3 reimagined | PCC still used for Vizier's own development |
| D25 | 5-level graduated retry (10 retries) | 2-level: retry 1-3 normal, retry 4+ STUCK | v1 simplification (D75) |
| D28 | Structured JSONL logging | OpenClaw transcripts | OpenClaw provides its own observability |
| D33 | Cost budget enforcement -- degrade + alert | Deferred to v2 | No usage data yet (D75) |
| D47 | Anthropic Python SDK with tool_use as agent foundation | OpenClaw manages LLM calls; MCP server uses SDK for Sentinel Haiku only | Agents are OpenClaw sessions |
| D48 | Scout Feedback Loop | Deferred to v2 with Scout | Scout not in v1 (D75) |
| D54 | Structured Message Schema | v1: spec model only. v2: full message/event types | Messages/events deferred (D75) |
| D56 | QG Structured Verdicts with evidence | v1: markdown via spec_write_feedback. v2: evidence tools | Evidence system deferred (D75) |
| D57 | Golden Trace per spec (trace.jsonl) | OpenClaw transcripts + MCP server trace logging | OpenClaw captures agent activity natively |
| D58 | Adaptive reconciliation interval | Pasha triggered by Vizier, not polling | Trigger model (D75) |
| D60 | Azure Key Vault as production secret store | Secrets managed by OpenClaw deployment | OpenClaw has its own secret management |
| D68 | verify_tests/lint/types MCP tools | Worker uses run_command_checked directly | Verification tools deferred to v2 (D75) |
| D69 | research_topic MCP tool | Worker/Architect use web_search directly | Research tool deferred to v2 (D75) |
| D70 | get_relevant_learnings MCP tool | Agents read learnings.md directly | Learnings tool deferred to v2 (D75) |
| D72 | Agent behavior eval suite | Deferred until agents exist | Eval suite deferred to v2 (D75) |
| D74 | Scope guidance for Architect | Deferred with Architect to v2 | Architect not in v1 (D75) |

### REPLACED

| Decision | Old | New replacement | Why |
|----------|-----|-----------------|-----|
| D42 | JIT prompt assembly for EA | SOUL.md + AGENTS.md + OpenClaw skills | OpenClaw's prompt system replaces JIT assembly |
| D51 | Loop Guardian -- behavioral checkpoint | OpenClaw's built-in loop detection | OpenClaw handles agent loop prevention natively |
| D59 | EA project capability summary | project_get_config MCP tool | MCP provides project metadata directly |

### REVERSED

| Decision | Old | Why reversed |
|----------|-----|--------------|
| D10 | EA is part of Vizier, not external | Vizier agent now runs ON OpenClaw. The tight integration argument is now served by MCP tools. |
| D14 | Own thin runtime over any agent framework | OpenClaw provides the UX ecosystem (Web UI, mobile, memory) that we'd otherwise build ourselves. Domain logic preserved in MCP server. |

### DROPPED (no longer applicable)

| Decision | Why dropped |
|----------|-------------|
| D5 | EA three communication layers -- OpenClaw handles multi-channel natively |
| D11 | EA tracks commitments/calendar/relationships -- will be reimagined using OpenClaw memory + MCP |
| D12 | Direct Pasha sessions -- OpenClaw sub-sessions replace this mechanism |
| D13 | Vizier as personal AI OS -- still the vision, but implementation details changed |
| D15 | EFM capabilities absorption -- no longer relevant to current architecture |
| D17 | Git-only sync with checkout/checkin -- OpenClaw handles file management |
| D27 | LiteLLM as library -- OpenClaw handles LLM routing |
| D30-D32 | Phase reordering, component eval, calendar -- old plan superseded |
| D34-D39 | Testing strategy, stub plugin, Telegram, asyncio, files-only, stub fixture -- all superseded |
| D41 | VCR/Record-Replay testing -- will be redesigned for MCP server tests |
| D43 | Plugin MCP exposure -- plugins are already MCP tools now |
| D45 | Langfuse observability -- OpenClaw provides its own observability |
| D53 | Integration tests from Phase 14 -- old phase structure superseded |
| D61 | Thread pool replaces subprocess -- OpenClaw handles agent execution |
| D62 | Model ID update -- OpenClaw config handles model selection |

---

## 8. What's Preserved from Old Codebase

The following domain logic will be **ported** from the old codebase (available in git history) to the MCP server:

| Component | Old location | New location | What to port | v1? |
|-----------|-------------|-------------|-------------|-----|
| Spec state machine | `libs/core/vizier/core/models/spec.py` | `vizier-mcp/vizier_mcp/tools/spec.py` | State enum, valid transitions, validation | YES |
| Spec I/O | `libs/core/vizier/core/file_protocol/spec_io.py` | `vizier-mcp/vizier_mcp/tools/spec.py` | CRUD, frontmatter parsing, atomic writes | YES |
| Sentinel policy engine | `libs/core/vizier/core/sentinel/` | `vizier-mcp/vizier_mcp/sentinel/` | Allowlist/denylist/Haiku, write-set matching | YES |
| Write-set glob matching | `libs/core/vizier/core/tools/domain/write_file.py` | `vizier-mcp/vizier_mcp/sentinel/write_set.py` | WriteSetChecker (glob pattern enforcement) | YES |
| Pydantic spec model | `libs/core/vizier/core/models/` | `vizier-mcp/vizier_mcp/models/spec.py` | Spec, SpecState, SpecMetadata | YES |
| DAG validator | `libs/core/vizier/core/tools/state/dag.py` | `vizier-mcp/vizier_mcp/tools/dag.py` | Dependency checking (partial) | YES |
| Evidence checker | `libs/core/vizier/core/tools/state/evidence.py` | `vizier-mcp/vizier_mcp/tools/evidence.py` | Completeness validation | v2 |
| Plugin base | `libs/core/vizier/core/plugins/` | `vizier-mcp/vizier_mcp/plugins/` | BasePlugin, criteria loader | v2 |
| Budget tracker | `libs/core/vizier/core/runtime/budget.py` | `vizier-mcp/vizier_mcp/tools/budget.py` | Cost tracking, threshold enforcement | v2 |
| Pydantic messages/events | `libs/core/vizier/core/models/` | `vizier-mcp/vizier_mcp/models/` | Message and event types | v2 |

---

## 9. Project Structure

```
vizier/
  vizier-mcp/                        # FastMCP server (Python package)
    vizier_mcp/
      __init__.py
      server.py                      # FastMCP app entry point
      config.py                      # Server configuration loader
      tools/
        __init__.py
        spec.py                      # Spec CRUD + state machine
        sentinel.py                  # run_command_checked, web_fetch_checked, sentinel_check_write
        orchestration.py             # Pasha support tools (scan, assign, ping)
        dag.py                       # dag_check_dependencies
        config_tool.py               # project_get_config
        evidence.py                  # [v2] Evidence checking
        budget.py                    # [v2] Cost tracking
      models/
        __init__.py
        spec.py                      # Spec, SpecState, SpecMetadata
        messages.py                  # [v2] Contract A message types
        events.py                    # [v2] Event types
      sentinel/                      # Policy engine (ported)
        __init__.py
        policy.py                    # Policy loading and evaluation
        write_set.py                 # WriteSetChecker (glob enforcement)
        haiku.py                     # Haiku evaluator for ambiguous cases
      plugins/                       # [v2] Plugin framework
        __init__.py
        base.py                      # [v2] BasePlugin
        software.py                  # [v2] Software development plugin
        documents.py                 # [v2] Document production plugin
        criteria.py                  # [v2] Criteria library loader
    tests/
      __init__.py
      test_spec_tools.py
      test_sentinel_tools.py
      test_orchestration_tools.py
      test_dag_tools.py
      test_config_tool.py
      test_models.py
      test_sentinel_policy.py
      test_write_set.py
      conftest.py
    pyproject.toml
  openclaw/                          # OpenClaw workspace configuration
    workspaces/
      vizier/                        # Main Vizier agent workspace
        SOUL.md
        AGENTS.md
        USER.md
        MEMORY.md
        skills/
      pasha-template/
        SOUL.md
        AGENTS.md
        skills/
      worker-template/
        SOUL.md
      quality-gate-template/
        SOUL.md
      v2-deferred/                   # v2 agent templates (preserved for future)
        scout-template/
          SOUL.md
        architect-template/
          SOUL.md
        retrospective-template/
          SOUL.md
    config/
      openclaw.json
      agents.json
  docs/
    ARCHITECTURE.md                  # This document
    DECISIONS.md                     # Historical + new decisions
    CHANGELOG.md                     # Project history
  .claude/                           # Claude Code development agents (PCC)
    agents/
    settings.json
  CLAUDE.md                          # Development instructions
  README.md                          # Project overview
  pyproject.toml                     # Root workspace config
```

---

## 10. Spec State Machine

### v1 State Machine (D75)

```
DRAFT --> READY --> IN_PROGRESS --> REVIEW --> DONE
                       |              |
                       v              |
                   INTERRUPTED        |
                       |              |
                       +----> READY   |
                                      |
                       REJECTED <-----+
                       |
                       +----> READY (retry 1-3)
                       +----> STUCK (retry 4+)
```

v1 valid transitions (enforced by MCP server):
- DRAFT -> READY (Pasha reviews and promotes)
- READY -> IN_PROGRESS (Worker claims)
- IN_PROGRESS -> REVIEW (Worker completes)
- IN_PROGRESS -> INTERRUPTED (graceful shutdown)
- INTERRUPTED -> READY (restart re-queues)
- REVIEW -> DONE (QG accepts)
- REVIEW -> REJECTED (QG rejects)
- REJECTED -> READY (retry)
- READY -> STUCK (retry 4+ exhausted)

### v2 State Machine

v2 adds SCOUTED and DECOMPOSED states for Scout and Architect agents:

```
DRAFT --> SCOUTED --> DECOMPOSED --> READY --> IN_PROGRESS --> REVIEW --> DONE
                                       |          |             |
                                       |          v             |
                                       |      INTERRUPTED       |
                                       |          |             |
                                       +<---------+             |
                                       |                        |
                                       +<--- REJECTED <---------+
                                       |
                                       +---> STUCK
```

Additional v2 transitions:
- DRAFT -> SCOUTED (Scout completes research)
- DRAFT -> DECOMPOSED (bypass Scout for simple specs)
- SCOUTED -> DECOMPOSED (Architect decomposes)
- DECOMPOSED -> READY (sub-specs created)

---

## 11. Testing Strategy

### MCP Server Tests

The MCP server is a standard Python package tested with pytest:

- **Unit tests**: Spec state machine, DAG dependency checker, write-set matcher, policy engine
- **Tool tests**: Each MCP tool tested with mock filesystem (no real projects)
- **Integration tests**: Full spec lifecycle through MCP tools (create -> transition -> validate)
- **Sentinel tests**: Allowlist/denylist/Haiku evaluation with mocked Haiku, Sentinel Learning

v1 test files:
- `test_spec_tools.py`, `test_sentinel_tools.py`, `test_orchestration_tools.py`
- `test_dag_tools.py`, `test_config_tool.py`, `test_models.py`
- `test_sentinel_policy.py`, `test_write_set.py`, `conftest.py`

### Agent Tests

Agent behavior is tested through OpenClaw's testing infrastructure. SOUL.md prompts are validated by running agents against mock MCP servers.

### No LLM Calls in CI

All automated tests mock LLM calls. The MCP server's Sentinel Haiku calls are mocked. Agent prompt quality is validated manually.

---

## 12. Future Enhancements

### 12.1 Lobster Workflow Runtime

[Lobster](https://docs.openclaw.ai/tools/lobster) is an OpenClaw plugin that provides a typed, deterministic workflow runtime with built-in approval gates. Instead of multiple LLM round-trips to orchestrate a sequence of tool calls, Lobster executes an entire pipeline in a single tool invocation -- pausing at explicit approval checkpoints and returning resume tokens.

**Why it matters for Vizier:**

| Workflow | Current (multi-call) | With Lobster (single pipeline) |
|----------|---------------------|-------------------------------|
| Worker verification | 3-4 LLM round-trips: run tests -> run lint -> run types -> spec_transition | One `lobster.run` with 4 chained steps, deterministic |
| Sentinel command execution | 2 calls: sentinel check + execute | One pipeline: validate then execute |
| Pasha agent spawn | 2-3 calls: read config -> enrich context -> sessions_spawn | One pipeline with config fetch piped into spawn |

**Status:** Not yet integrated. Adopt after core MCP tools are implemented and real usage patterns are established.

### 12.2 v2 Feature Roadmap

After v1 delivers a working end-to-end loop, these features can be added incrementally:

| Feature | Agent/Tool | Purpose |
|---------|-----------|---------|
| Scout agent | Scout + SCOUTED state | Prior art research before implementation |
| Architect agent | Architect + DECOMPOSED state | Task decomposition with dependency DAG |
| Retrospective agent | Retrospective + learnings.md | Failure analysis, meta-improvement |
| Budget tracking | budget_track, budget_check, budget_get_summary | Cost monitoring and enforcement |
| Evidence system | evidence_check, evidence_write_verdict | Structured QG verdicts with evidence links |
| Plugin framework | BasePlugin, plugin_get_* tools | Domain-specific configuration |
| Verification tools | verify_tests, verify_lint, verify_types | Worker self-verification as MCP tools |
| Research tool | research_topic | Lightweight on-demand research |
| Learnings injection | get_relevant_learnings | Keyword-matched learnings for agent spawn context |
| Agent behavior evals | test_agent_evals.py | SOUL.md behavioral contract tests |
| Graduated retry v2 | 5 levels (model bump, re-decompose) | Finer-grained retry strategy |

---

## v2 Agent Definitions

These agents are designed but not in v1 scope. SOUL.md files are preserved in `openclaw/workspaces/v2-deferred/`.

### Scout (Prior Art Researcher)

**Role:** Researcher. Investigates existing solutions before the Architect decomposes work.

**OpenClaw session type:** Spawned sub-session (fresh context, exits after research)

**Model:** Sonnet

**Tools available:**
- OpenClaw native: web_search, browser, file_read
- Vizier MCP: spec_read, spec_transition, plugin_get_system_prompt

**SOUL.md sketch:**
```markdown
You are a Scout -- a researcher who finds existing solutions before
new work is designed. You receive a DRAFT spec and investigate whether
existing libraries, tools, or patterns can solve the problem.

## Your Process
1. Read the spec (spec_read)
2. Search for existing solutions (web_search, browser)
3. Write a structured research report
4. Transition spec to SCOUTED (spec_transition)

## Output Format
Write a research.md report with:
- Existing solutions found (with links, pros/cons)
- Recommended approach (build vs. borrow)
- Key libraries/tools to use
- Confidence level (HIGH/MEDIUM/LOW)
```

### Architect (Task Decomposer)

**Role:** Decomposer. Takes a SCOUTED spec and breaks it into implementable sub-specs with a dependency DAG.

**OpenClaw session type:** Spawned sub-session (fresh context, exits after decomposition)

**Model:** Opus

**Tools available:**
- OpenClaw native: file_read, web_search
- Vizier MCP: spec_read, spec_create, spec_transition, dag_validate, plugin_get_decomposition_guide, plugin_get_criteria, plugin_get_write_set

**SOUL.md sketch:**
```markdown
You are an Architect -- you decompose high-level specs into
implementable sub-specs that a Worker can execute without exploration.

## Your Process
1. Read the parent spec and Scout's research report
2. Read the plugin's decomposition guide
3. Design sub-specs with clear artifacts, acceptance criteria, and dependencies
4. Validate the dependency DAG (dag_validate)
5. Create sub-specs (spec_create) in READY state
6. Transition parent to DECOMPOSED

## Sub-Spec Requirements
Each sub-spec MUST have:
- Clear title and description
- Explicit artifact list (files to create/modify)
- Acceptance criteria referencing @criteria/ library
- Complexity rating (LOW/MEDIUM/HIGH)
- depends_on list (other sub-spec IDs)

The Worker should NEVER need to explore. If they do, your spec was insufficient.

## Scope Guidelines
- Aim for 1-3 files per sub-spec. If a logical unit needs more than 5, split further.
```

### Retrospective (Meta-Improver)

**Role:** Analyst. Reviews completed and failed work to extract learnings and propose improvements.

**OpenClaw session type:** Spawned sub-session (periodic, triggered by Pasha)

**Model:** Opus

**Tools available:**
- OpenClaw native: file_read, file_write
- Vizier MCP: spec_list, spec_read, budget_get_summary, plugin_get_system_prompt

**SOUL.md sketch:**
```markdown
You are a Retrospective agent -- you analyze completed work to find
patterns, extract learnings, and propose improvements.

## Triggers
- End of a work cycle (batch of specs completed)
- A spec reaches STUCK state
- Periodic review (weekly)

## Analysis
1. Review completed specs: rejection rates, retry counts, time to completion
2. Review STUCK specs: root causes, common failure patterns
3. Analyze cost efficiency: cost per spec, model tier effectiveness
4. Check learnings.md for recurring issues

## Outputs
- Append learnings to project learnings.md (direct write)
- Write proposals to proposals/ directory (require Sultan approval)

## Learnings Format
Write learnings with clear keywords so retrieval matches correctly.
Structure: "When [context], [problem] because [root cause]. Fix: [solution]."

## Constraints
- You may update learnings and propose prompt/criteria changes
- You may NOT change architecture, code structure, or process rules
- ALL proposals require Sultan approval (always, no exceptions)
```
