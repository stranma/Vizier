# Vizier-on-OpenClaw Architecture

## 1. Overview

Vizier is an autonomous multi-agent work system using the Ottoman court metaphor. It receives high-level tasks from humans, decomposes them into actionable specs, executes them through specialized agents, and reports back.

**What changed:** Vizier's runtime is now **OpenClaw** -- an open-source gateway that provides multi-channel messaging (Telegram, WhatsApp, Discord, iMessage, Web UI, mobile apps), session management, tool infrastructure, and memory. Vizier's custom daemon, transport layer (aiogram/Telegram), and agent runtime are replaced by OpenClaw's battle-tested equivalents.

**What's preserved:** Vizier's domain intelligence -- spec lifecycle, agent orchestration, quality gates, Sentinel security, DAG scheduling, plugin extensibility -- lives on as a **FastMCP server** that OpenClaw agents call via tool use.

**Ottoman court metaphor (preserved):**

| Role | Description | OpenClaw mapping |
|------|-------------|------------------|
| **Sultan** | Human operator (CEO/CTO) | OpenClaw user (any channel) |
| **Vizier** | Grand Vizier -- main agent, singleton | OpenClaw persistent session (Opus) |
| **Pasha** | Per-project orchestrator | OpenClaw sub-session per project (Opus) |
| **Scout** | Prior art researcher | OpenClaw spawned sub-session (Sonnet) |
| **Architect** | Task decomposer | OpenClaw spawned sub-session (Opus) |
| **Worker** | Spec executor (fresh context per task) | OpenClaw spawned sub-session (Sonnet/Opus) |
| **Quality Gate** | Work validator | OpenClaw spawned sub-session (Sonnet/Opus) |
| **Retrospective** | Failure analyzer, meta-improver | OpenClaw spawned sub-session (Opus) |
| **Sentinel** | Security enforcer (deterministic, not LLM) | MCP tools on Vizier MCP server |

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
    |     +-- Scout (sub-session, spawned per research task)
    |     +-- Architect (sub-session, spawned per decomposition)
    |     +-- Worker (sub-session, spawned per spec, fresh context)
    |     +-- Quality Gate (sub-session, spawned per review)
    |     +-- Retrospective (sub-session, periodic)
    |
    +-- Vizier MCP Server (Python, FastMCP)
          +-- Spec tools (CRUD, state machine, lifecycle)
          +-- Sentinel tools (write-set enforcement, policy engine)
          +-- Sentinel-wrapped tools (run_command_checked, web_fetch_checked)
          +-- Orchestration tools (scan, assign, schedule)
          +-- DAG tools (validate, check dependencies)
          +-- Evidence tools (check completeness, write verdict)
          +-- Plugin tools (domain-specific operations)
          +-- Budget tools (track costs, check thresholds)
          +-- Verification tools (verify_tests, verify_lint, verify_types)
          +-- Research tool (research_topic)
          +-- Learnings tool (get_relevant_learnings)
```

**Key insight:** OpenClaw handles everything above the line (channels, sessions, routing, memory, tool infra). Vizier's MCP server handles everything below (domain logic, security, orchestration). The agents themselves are OpenClaw sessions with SOUL.md prompts that call MCP tools.

---

## 3. Vizier MCP Server

All Vizier domain logic is exposed as MCP tools via a **FastMCP** Python server. OpenClaw agents call these tools to interact with the spec lifecycle, Sentinel, orchestration, and plugins.

### 3.1 Tool Groups

#### Spec Lifecycle

| Tool | Description | Inputs | Returns |
|------|-------------|--------|---------|
| `spec_create` | Create a new spec in DRAFT state | project_id, title, description, complexity, artifacts, criteria, depends_on | spec_id |
| `spec_read` | Read spec contents and metadata | spec_id | spec object (frontmatter + body) |
| `spec_list` | List specs with optional status filter | project_id, status_filter? | list of spec summaries |
| `spec_transition` | Transition spec to new state (validates state machine) | spec_id, new_status, agent_role | success/error with reason |
| `spec_update` | Update spec fields (retry count, assigned agent, etc.) | spec_id, fields | updated spec |
| `spec_write_feedback` | Write QG feedback or rejection reason | spec_id, verdict, feedback, evidence | feedback file path |

#### Sentinel

| Tool | Description | Inputs | Returns |
|------|-------------|--------|---------|
| `sentinel_check_write` | Validate file write against project write-set | project_id, file_path, agent_role | allow/deny with reason |
| `sentinel_check_command` | Validate shell command against policy | project_id, command, agent_role | allow/deny with reason |
| `sentinel_scan_content` | Scan untrusted content for injection | content, source_url? | safe/suspicious with details |
| `sentinel_get_policy` | Get current project security policy | project_id | policy object |

#### Orchestration

| Tool | Description | Inputs | Returns |
|------|-------------|--------|---------|
| `orch_scan_specs` | Scan all specs and return actionable items | project_id | specs needing attention (by state) |
| `orch_check_ready` | Check if a spec's dependencies are satisfied | spec_id | ready/blocked with blocking spec IDs |
| `orch_assign_worker` | Claim a spec for a worker agent | spec_id, agent_session_id | assignment confirmation |
| `orch_scan_pings` | Read pending supervisor notifications | project_id | list of pings with urgency |
| `orch_write_ping` | Write a supervisor notification | spec_id, urgency, message | ping file path |

#### DAG

| Tool | Description | Inputs | Returns |
|------|-------------|--------|---------|
| `dag_validate` | Validate dependency graph (cycles, missing refs) | project_id | valid/invalid with errors |
| `dag_check_dependencies` | Check which specs are unblocked | project_id | list of unblocked spec IDs |
| `dag_get_order` | Get topological execution order | project_id | ordered list of spec IDs |

#### Evidence

| Tool | Description | Inputs | Returns |
|------|-------------|--------|---------|
| `evidence_check` | Check if all required evidence is present for a spec | spec_id | complete/incomplete with missing items |
| `evidence_write_verdict` | Write a structured QG verdict with evidence links | spec_id, verdict, per_criterion_results | verdict file path |

#### Plugin

| Tool | Description | Inputs | Returns |
|------|-------------|--------|---------|
| `plugin_get_write_set` | Get allowed write patterns for project | project_id | list of glob patterns |
| `plugin_get_evidence_requirements` | Get required evidence types | project_id | list of evidence types |
| `plugin_get_system_prompt` | Get domain-specific prompt module for agent role | project_id, agent_role | prompt text |
| `plugin_get_criteria` | Get criteria library entries | project_id, criteria_refs | resolved criteria text |
| `plugin_get_decomposition_guide` | Get Architect's decomposition patterns | project_id | guide text |

#### Budget

| Tool | Description | Inputs | Returns |
|------|-------------|--------|---------|
| `budget_track` | Record an agent invocation cost | project_id, agent_role, model, tokens_in, tokens_out, cost_usd | updated totals |
| `budget_check` | Check current spend against thresholds | project_id? | spend summary + threshold status |
| `budget_get_summary` | Get cost breakdown by project/agent/model | period? | detailed cost report |

#### Verification (D68)

| Tool | Description | Inputs | Returns |
|------|-------------|--------|---------|
| `verify_tests` | Run plugin's test suite for spec artifacts | project_id, spec_id | pass/fail + test output |
| `verify_lint` | Run linter on spec's modified files | project_id, spec_id | pass/fail + lint output |
| `verify_types` | Run type checker on spec's modified files | project_id, spec_id | pass/fail + type errors |

#### Sentinel-Wrapped Execution (D67)

| Tool | Description | Inputs | Returns |
|------|-------------|--------|---------|
| `run_command_checked` | Execute shell command after Sentinel validation | project_id, command, agent_role | allow/deny + command output |
| `web_fetch_checked` | Fetch URL and scan content for injection | url, agent_role | safe/suspicious + content |

Note: `write_file_checked` is not needed for in-scope writes. Standard in-scope writes go through OpenClaw native file_write (allowed by tool policy within workspace). The existing `sentinel_check_write` handles out-of-scope write validation.

#### Research (D69)

| Tool | Description | Inputs | Returns |
|------|-------------|--------|---------|
| `research_topic` | Lightweight research on a topic (web search + analysis) | query, depth (shallow/deep) | structured findings |

#### Learnings (D70)

| Tool | Description | Inputs | Returns |
|------|-------------|--------|---------|
| `get_relevant_learnings` | Get learnings relevant to a spec/role | project_id, spec_id?, agent_role? | list of relevant learning entries |

### 3.2 Server Configuration

The MCP server reads its configuration from `vizier-mcp/config.yaml`:

```yaml
vizier_root: /data/vizier          # Root directory for all project data
projects_dir: /data/vizier/projects  # Per-project spec/state storage
sentinel:
  default_policy: strict            # strict | permissive
  haiku_model: claude-haiku-4-5-20251001  # For ambiguous Sentinel calls
budget:
  monthly_limit_usd: 500
  alert_threshold: 0.8              # 80%
  degrade_threshold: 1.0            # 100%
  pause_threshold: 1.2              # 120%
plugins:
  - software
  - documents
```

### 3.3 Filesystem Layout (Managed by MCP Server)

```
/data/vizier/
  projects/
    {project-id}/
      config.yaml                    # Project config (plugin, autonomy stage, etc.)
      specs/
        001-feature-name/
          spec.md                    # Spec document (frontmatter + body)
          trace.jsonl                # Golden Trace (tool calls, transitions)
          feedback/                  # QG feedback files
          research/                  # Scout output
          evidence/                  # Test output, lint output, etc.
      reports/
        status.json                  # Current project status
        agent-log.jsonl              # Cost/performance tracking
      learnings.md                   # Retrospective learnings (append-only)
      proposals/                     # Retrospective proposals (pending approval)
  budget/
    spending.jsonl                   # Cross-project cost tracking
```

---

## 4. Agent Definitions

All agents are **OpenClaw sessions**. Their behavior is defined by SOUL.md files (system prompts), available tools (OpenClaw native + Vizier MCP), and session configuration (model tier, persistence, spawn rules).

### 4.1 Vizier (Main Agent)

**Role:** The Grand Vizier. Single entry point for the Sultan. Routes tasks to projects, manages commitments, provides briefings, handles cross-project coordination.

**OpenClaw session type:** Persistent (always available, maintains conversation history via OpenClaw memory)

**Model:** Opus

**Tools available:**
- OpenClaw native: web_search, browser, file tools, memory, sessions_spawn, sessions_send, sessions_list
- Vizier MCP: spec_create, spec_list, orch_scan_specs, budget_check, budget_get_summary, plugin_get_write_set

**SOUL.md sketch:**
```markdown
You are the Grand Vizier -- the Sultan's most capable and trusted advisor.
You manage the Sultan's projects, commitments, and priorities.

## Your Responsibilities
- Receive tasks from the Sultan and route them to the appropriate Pasha
- Create new projects and assign Pashas
- Provide status updates, morning briefings, and proactive alerts
- Track commitments and deadlines across all projects
- Handle cross-project coordination
- Answer direct questions using your knowledge and tools

## Your Pashas
Each project has a dedicated Pasha (sub-session). You communicate with
Pashas via sessions_send for async updates and spec_create for new work.
Never do a Pasha's job -- delegate and coordinate.

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

**Role:** Provincial governor. Owns a single project's lifecycle. Manages the inner loop: Scout -> Architect -> Worker -> Quality Gate -> Done.

**OpenClaw session type:** Persistent sub-session (one per project, long-lived)

**Model:** Opus

**Tools available:**
- OpenClaw native: sessions_spawn, sessions_send, sessions_list
- Vizier MCP: spec_read, spec_list, spec_transition, spec_update, orch_scan_specs, orch_check_ready, orch_assign_worker, orch_scan_pings, dag_validate, dag_check_dependencies, dag_get_order, evidence_check, budget_track, budget_check, sentinel_get_policy, plugin_get_write_set, plugin_get_evidence_requirements

**SOUL.md sketch:**
```markdown
You are Pasha-{project_name}, the governor of the {project_name} project.
You report to the Grand Vizier and manage all work within your project.

## Your Loop
1. Check for new specs (orch_scan_specs)
2. For DRAFT specs: spawn Scout for research, then Architect for decomposition
3. For READY specs: check dependencies (orch_check_ready), spawn Worker
4. For REVIEW specs: spawn Quality Gate
5. Handle pings from inner agents (orch_scan_pings)
6. Handle rejections with graduated retry
7. Report status to the Vizier

## Graduated Retry
- Retry 1-2: Normal retry with QG feedback
- Retry 3: Bump Worker model tier
- Retry 5: Review spec yourself, consider re-scoping
- Retry 7: Spawn Architect for re-decomposition
- Retry 10: Mark STUCK, escalate to Vizier

## Pipeline Flexibility
You decide which agents to spawn based on the spec's nature:
- Simple bugfix: skip Scout and Architect, assign Worker directly (DRAFT -> READY)
- Documentation task: skip Scout, lighter QG (no test passes)
- Research-only task: spawn Scout, mark spec DONE when research complete
- Complex feature: full pipeline (Scout -> Architect -> Worker -> QG)

## Learnings Injection
Before spawning any agent, call get_relevant_learnings(project_id, spec_id, agent_role).
Include relevant learnings in the agent's spawn context.

## Memory Management
- Write project status, active specs, and pending decisions to memory proactively
- After compaction, re-read project state via orch_scan_specs

## Sentinel
Your project has a dedicated Sentinel enforcing security policies.
All inner agents' file writes are validated via sentinel_check_write.
```

**Inputs:** Specs from Vizier, pings from inner agents, QG verdicts
**Outputs:** Agent spawn decisions, status reports, escalations

### 4.3 Scout (Prior Art Researcher)

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

**Inputs:** DRAFT spec ID
**Outputs:** research.md file, spec transitioned to SCOUTED

### 4.4 Architect (Task Decomposer)

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
- Use research_topic(query, depth) for quick lookups during decomposition.
  Reserve request_more_research for cases requiring deep multi-source investigation.
```

**Inputs:** SCOUTED spec ID, research report
**Outputs:** Sub-specs created in READY state, parent spec DECOMPOSED

### 4.5 Worker (Spec Executor)

**Role:** Executor. Takes a single READY spec and implements it. Fresh context, one spec, exit.

**OpenClaw session type:** Spawned sub-session (fresh context per spec, exits on completion)

**Model:** Sonnet (bumped to Opus on retry 3)

**Tools available:**
- OpenClaw native: file_read, file_write, edit_file, bash, web_search
- Vizier MCP: spec_read, spec_transition, sentinel_check_write, sentinel_check_command, orch_write_ping, plugin_get_system_prompt, budget_track

**SOUL.md sketch:**
```markdown
You are a Worker -- you implement exactly one spec, then exit.
You receive a spec ID. Read it, implement it, transition to REVIEW.

## Your Process
1. Read the spec (spec_read)
2. Read any QG feedback from previous attempts
3. Implement the artifacts listed in the spec
4. All file writes are validated by Sentinel (sentinel_check_write)
5. Run mandatory self-verification (see below)
6. When all checks pass, transition spec to REVIEW (spec_transition)

## Mandatory Self-Verification
Before transitioning to REVIEW, you MUST:
1. Run verify_tests(project_id, spec_id) -- fix failures
2. Run verify_lint(project_id, spec_id) -- fix violations
3. Run verify_types(project_id, spec_id) -- fix type errors
Iterate until all three PASS. Only then call spec_transition(spec_id, "REVIEW").

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

### 4.6 Quality Gate (Work Validator)

**Role:** Validator. Reviews completed work against spec criteria using a structured multi-pass protocol.

**OpenClaw session type:** Spawned sub-session (fresh context per review)

**Model:** Sonnet (Opus for HIGH complexity specs)

**Tools available:**
- OpenClaw native: file_read, bash
- Vizier MCP: spec_read, spec_transition, spec_write_feedback, evidence_check, evidence_write_verdict, plugin_get_criteria, plugin_get_evidence_requirements, budget_track

**SOUL.md sketch:**
```markdown
You are a Quality Gate -- you validate completed work using a
structured multi-pass protocol. You are the last line of defense.

## Completion Protocol (4 passes)
Worker now handles mechanical verification (tests, lint, types) before REVIEW.
Your role shifts to semantic quality:

Pass 1 (Hygiene): Check for debug prints, breakpoints, TODOs, hardcoded values
Pass 2 (Criteria): Evaluate each acceptance criterion from the spec
Pass 3 (Consistency): Check for regressions against related specs
Pass 4 (Verdict): Write structured verdict with per-criterion PASS/FAIL + evidence

If Worker missed mechanical issues (tests failing, lint errors), that's a REJECT
with feedback noting Worker's self-verification was insufficient.

## Rules
- You MUST check all required evidence is present (evidence_check)
- ACCEPT: all criteria pass, all evidence present
- REJECT: write detailed feedback (spec_write_feedback) so Worker can fix

## Evidence
Every verdict must include evidence links (test output, lint output, etc.).
Verdicts without evidence are invalid.
```

**Inputs:** REVIEW spec ID
**Outputs:** QUALITY_VERDICT with per-criterion results, spec DONE or REJECTED

### 4.7 Retrospective (Meta-Improver)

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

## Data Sources
- Per-spec traces (trace.jsonl) -- tool calls, transitions, decisions
- OpenClaw session transcripts -- full agent conversations
- learnings.md -- previously captured learnings
- Agent logs -- cost, duration, model tier per invocation

## Analysis
1. Review completed specs: rejection rates, retry counts, time to completion
2. Review STUCK specs: root causes, common failure patterns
3. Analyze cost efficiency: cost per spec, model tier effectiveness
4. Check learnings.md for recurring issues

## Outputs
- Append learnings to project learnings.md (direct write)
- Write proposals to proposals/ directory (require Sultan approval)

## Learnings Retrieval
Your learnings are served to agents via get_relevant_learnings.
Write learnings with clear keywords so the retrieval matches correctly.
Structure: "When [context], [problem] because [root cause]. Fix: [solution]."

## Constraints
- You may update learnings and propose prompt/criteria changes
- You may NOT change architecture, code structure, or process rules
- ALL proposals require Sultan approval (always, no exceptions)
```

**Inputs:** Project state, spec history, cost data
**Outputs:** Learnings (append-only), proposals (pending approval)

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
  scout:
    can_write: false
    can_bash: false
    can_read: true
  architect:
    can_write: false      # Creates specs via MCP, not direct file writes
    can_bash: false
    can_read: true
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

The MCP server handles all three tiers internally. Agents call `sentinel_check_write` or `sentinel_check_command` and get allow/deny. For command execution and web fetches, the Sentinel-wrapped tools (`run_command_checked`, `web_fetch_checked`) combine validation and execution in a single call, enforced at the OpenClaw tool policy level (see section 5.4).

### 5.3 Haiku Fallback

For ambiguous cases (not in allowlist or denylist), the MCP server calls Haiku to evaluate intent:

```python
@mcp.tool()
async def sentinel_check_command(project_id: str, command: str, agent_role: str) -> dict:
    policy = load_policy(project_id)

    # Tier 1: Allowlist
    if policy.is_allowlisted(command):
        return {"decision": "allow", "tier": "allowlist"}

    # Tier 2: Denylist
    if deny_reason := policy.is_denylisted(command):
        return {"decision": "deny", "tier": "denylist", "reason": deny_reason}

    # Tier 3: Haiku evaluation
    verdict = await haiku_evaluate(command, agent_role, policy)
    return {"decision": verdict.decision, "tier": "haiku", "reason": verdict.reason}
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

---

## 6. Communication Model

### 6.1 Sultan <-> Vizier

Sultan communicates with the Vizier agent through **any OpenClaw channel** (Telegram, WhatsApp, Discord, iMessage, Web UI, mobile app). OpenClaw handles channel routing, message formatting, and session persistence.

The Vizier agent is a persistent OpenClaw session. It maintains conversation history via OpenClaw's built-in memory system.

### 6.2 Vizier <-> Pasha

Vizier communicates with Pashas via:
- **`sessions_send`** (OpenClaw native): Direct messages for status requests, urgent directives
- **`spec_create`** (Vizier MCP): Create new specs in a project (Pasha picks them up)

Pashas report back to Vizier via:
- **`sessions_send`**: Status updates, escalations, completion notifications
- Status data in MCP (Vizier can call `orch_scan_specs` for any project)

### 6.3 Pasha <-> Inner Agents

Pasha spawns inner agents via **`sessions_spawn`** (OpenClaw native). Each spawned session receives:
- The spec ID to work on
- Any relevant context (QG feedback for retries, research report for Architect)

Pasha enriches spawn context with:
- Relevant learnings (via `get_relevant_learnings` MCP tool)
- QG feedback from previous attempts (for retries)
- Research report (for Architect)

Inner agents communicate back to Pasha via:
- **`orch_write_ping`** (Vizier MCP): For questions, blockers, and status pings
- **`spec_transition`** (Vizier MCP): State changes (REVIEW, DONE, etc.) that Pasha detects on next scan

### 6.4 All Agents <-> Domain Logic

All agents interact with Vizier's domain logic **exclusively through MCP tools**. No agent directly reads or writes spec files, state files, or configuration. The MCP server is the single point of control.

```
Agent decision: "I need to write src/auth.py"
  -> sentinel_check_write(project_id, "src/auth.py", "worker")
  -> MCP server checks write-set, returns allow
  -> Agent uses OpenClaw file_write tool

Agent decision: "I'm done with this spec"
  -> spec_transition(spec_id, "REVIEW", "worker")
  -> MCP server validates state machine, transitions spec
  -> Pasha picks up on next orch_scan_specs call
```

---

## 7. Decision Map Update

Mapping old decisions (D1-D62) to the new architecture. Each is **KEPT**, **MODIFIED**, **REPLACED**, **REVERSED**, or **DROPPED**.

### KEPT (unchanged)

| Decision | Summary | Why kept |
|----------|---------|----------|
| D1 | Multi-agent over single-agent loop | Core architecture unchanged |
| D2 | Fresh context per task | Workers still spawn fresh per spec |
| D4 | Filesystem as message bus | MCP server still uses filesystem for specs |
| D7 | Architect must be exhaustively specific | Same decomposition philosophy |
| D8 | Retrospective as separate agent | Same role, now an OpenClaw sub-session |
| D16 | Ottoman court naming | Preserved, "EA" renamed to "Vizier" |
| D18 | Least privilege per role | Now enforced via per-project Sentinel MCP |
| D19 | Sentinel -- deterministic + Haiku hybrid | Now exposed as MCP tools |
| D21 | Vizier stays monolithic and powerful | Same philosophy, OpenClaw session |
| D22 | Reconciliation -- events as optimization, disk as truth | MCP server scans filesystem |
| D23 | Workers get bounded read-only exploration | Unchanged |
| D24 | Permission enforcement: allowlist + denylist + Haiku | Now via MCP Sentinel tools |
| D25 | Graduated retry strategy | Pasha still manages graduated retry |
| D26 | Retrospective always requires human approval | Unchanged |
| D29 | Completion signal, criteria versioning, graceful shutdown | Unchanged |
| D33 | Cost budget enforcement -- degrade + alert | Now via MCP budget tools |
| D40 | Atomic writes via os.replace() | MCP server uses atomic writes |
| D44 | Progressive autonomy rollout | Unchanged |
| D46 | Agent System Reset | Already executed; this is the second reset |
| D48 | Scout Feedback Loop | Architect can still request more research |
| D49 | QG Model Tier Escalation | Opus for HIGH complexity unchanged |
| D50 | Synchronous supervisor notification (ping) | Now via MCP orch_write_ping |
| D52 | Spec Dependency DAG | Now via MCP DAG tools |
| D54 | Structured Message Schema | Pydantic models ported to MCP server |
| D55 | Write-set via glob patterns | Now enforced via MCP sentinel_check_write |
| D56 | QG Structured Verdicts with evidence | Now via MCP evidence tools |

### MODIFIED

| Decision | Old | New | Why |
|----------|-----|-----|-----|
| D2 | Fresh LLM call per message/event | OpenClaw session management; sub-sessions spawned fresh per task | OpenClaw manages session lifecycle |
| D3 | Rules-based model router | Model tier specified per agent in OpenClaw config | OpenClaw handles model selection per session |
| D6 | Python plugin packages with entry points | Plugins as MCP tool providers within vizier-mcp | Simpler, no entry point discovery needed |
| D9 | Hybrid deployment (package + daemon) | OpenClaw deployment + MCP server sidecar | OpenClaw replaces custom daemon |
| D20 | Three-layer use of claude-code-python-template | Layer 1 (build tooling) kept, Layer 2-3 reimagined | PCC still used for Vizier's own development |
| D28 | Structured JSONL logging | MCP budget tools + OpenClaw transcripts | OpenClaw provides its own observability |
| D47 | Anthropic Python SDK with tool_use as agent foundation | OpenClaw manages LLM calls for agents; MCP server uses Anthropic SDK for Sentinel Haiku only | Agents are OpenClaw sessions, not direct API calls |
| D57 | Golden Trace per spec (trace.jsonl) | OpenClaw transcripts + MCP server trace logging | OpenClaw captures agent activity natively |
| D58 | Adaptive reconciliation interval | MCP server periodic scan (Pasha calls orch_scan_specs on heartbeat) | No watchdog; Pasha polls MCP on schedule |
| D60 | Azure Key Vault as production secret store | Secrets managed by OpenClaw deployment | OpenClaw has its own secret management |

### REPLACED

| Decision | Old | New replacement | Why |
|----------|-----|-----------------|-----|
| D42 | JIT prompt assembly for EA | SOUL.md + AGENTS.md + OpenClaw skills | OpenClaw's prompt system replaces JIT assembly |
| D51 | Loop Guardian -- behavioral checkpoint | OpenClaw's built-in loop detection | OpenClaw handles agent loop prevention natively |
| D59 | EA project capability summary | Vizier reads project config via MCP tools | MCP provides project metadata directly |

### REVERSED

| Decision | Old | Why reversed |
|----------|-----|--------------|
| D10 | EA is part of Vizier, not external | Vizier agent now runs ON OpenClaw. OpenClaw is the runtime. The tight integration argument is now served by MCP tools. |
| D14 | Own thin runtime over any agent framework | OpenClaw is not "any framework" -- it provides the UX ecosystem (Web UI, mobile, memory) that we'd otherwise build ourselves. Domain logic preserved in MCP server. |

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
| D30 | Phase reordering -- old implementation plan superseded |
| D31 | Component replacement evaluation -- landscape changed with OpenClaw adoption |
| D32 | Calendar integration dual provider -- will be reimagined |
| D34 | Testing strategy mock litellm -- MCP server tests mock at different layer |
| D35 | Stub plugin for testing -- will be redesigned |
| D36 | Telegram long polling first -- OpenClaw handles transport |
| D37 | asyncio daemon + subprocess per agent -- OpenClaw handles agent lifecycle |
| D38 | Files only for queryable data -- OpenClaw memory replaces some of this |
| D39 | Stub plugin as test fixture -- will be redesigned |
| D41 | VCR/Record-Replay testing -- will be redesigned for MCP server tests |
| D43 | Plugin MCP exposure -- plugins are already MCP tools now |
| D45 | Langfuse observability -- OpenClaw provides its own observability |
| D53 | Integration tests from Phase 14 -- old phase structure superseded |
| D61 | Thread pool replaces subprocess -- OpenClaw handles agent execution |
| D62 | Model ID update -- OpenClaw config handles model selection |

---

## 8. What's Preserved from Old Codebase

The following domain logic will be **ported** from the old codebase (available in git history) to the MCP server:

| Component | Old location | New location | What to port |
|-----------|-------------|-------------|-------------|
| Spec state machine | `libs/core/vizier/core/models/spec.py` | `vizier-mcp/vizier_mcp/tools/spec.py` | State enum, valid transitions, validation |
| Spec I/O | `libs/core/vizier/core/file_protocol/spec_io.py` | `vizier-mcp/vizier_mcp/tools/spec.py` | CRUD, frontmatter parsing, atomic writes |
| DAG validator | `libs/core/vizier/core/tools/state/dag.py` | `vizier-mcp/vizier_mcp/tools/dag.py` | Topological sort, cycle detection |
| Evidence checker | `libs/core/vizier/core/tools/state/evidence.py` | `vizier-mcp/vizier_mcp/tools/evidence.py` | Completeness validation |
| Sentinel policy engine | `libs/core/vizier/core/sentinel/` | `vizier-mcp/vizier_mcp/sentinel/` | Allowlist/denylist/Haiku, write-set matching |
| Pydantic models | `libs/core/vizier/core/models/` | `vizier-mcp/vizier_mcp/models/` | Spec, state, messages, events |
| Write-set glob matching | `libs/core/vizier/core/tools/domain/write_file.py` | `vizier-mcp/vizier_mcp/sentinel/write_set.py` | WriteSetChecker (glob pattern enforcement) |
| Plugin base | `libs/core/vizier/core/plugins/` | `vizier-mcp/vizier_mcp/plugins/` | BasePlugin, criteria loader, template renderer |
| Budget tracker | `libs/core/vizier/core/runtime/budget.py` | `vizier-mcp/vizier_mcp/tools/budget.py` | Cost tracking, threshold enforcement |
| Verification wrappers | NEW | `vizier-mcp/vizier_mcp/tools/verification.py` | Plugin-aware test/lint/type runners |

---

## 9. New Project Structure

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
        sentinel.py                  # Security enforcement tools
        orchestration.py             # Pasha support tools
        dag.py                       # DAG validation
        evidence.py                  # Evidence checking
        plugin.py                    # Plugin tool exposure
        budget.py                    # Cost tracking
        verification.py              # Worker self-verification (tests, lint, types)
        research.py                  # Lightweight on-demand research
      models/                        # Pydantic models (ported from old core)
        __init__.py
        spec.py                      # Spec, SpecState, SpecMetadata
        messages.py                  # Contract A message types
        events.py                    # Event types
      sentinel/                      # Policy engine (ported)
        __init__.py
        policy.py                    # Policy loading and evaluation
        write_set.py                 # WriteSetChecker (glob enforcement)
        haiku.py                     # Haiku evaluator for ambiguous cases
      plugins/                       # Plugin framework
        __init__.py
        base.py                      # BasePlugin
        software.py                  # Software development plugin
        documents.py                 # Document production plugin
        criteria.py                  # Criteria library loader
    tests/
      __init__.py
      test_spec_tools.py
      test_sentinel_tools.py
      test_orchestration_tools.py
      test_dag_tools.py
      test_evidence_tools.py
      test_budget_tools.py
      test_models.py
      test_sentinel_policy.py
      test_write_set.py
      test_verification_tools.py
      test_research_tools.py
      test_agent_evals.py            # SOUL.md behavioral contract tests
      conftest.py
    pyproject.toml                   # Package config (fastmcp, anthropic, pydantic)
  openclaw/                          # OpenClaw workspace configuration
    workspaces/
      vizier/                        # Main Vizier agent workspace
        SOUL.md                      # Vizier system prompt
        AGENTS.md                    # Inner agent definitions
        USER.md                      # Sultan preferences
        MEMORY.md                    # Persistent memory
        skills/
          project-management/        # Project CRUD, status
          spec-lifecycle/            # Spec creation, delegation
          delegation/                # Task routing to Pashas
      pasha-template/                # Template for per-project Pashas
        SOUL.md                      # Pasha system prompt
        AGENTS.md                    # Inner agent definitions
        skills/
          orchestration/             # Spec scanning, agent spawning
          retry-management/          # Graduated retry logic
      scout-template/
        SOUL.md
      architect-template/
        SOUL.md
      worker-template/
        SOUL.md
      quality-gate-template/
        SOUL.md
      retrospective-template/
        SOUL.md
    config/
      openclaw.json                  # Gateway configuration
      agents.json                    # Agent definitions + routing
  docs/
    ARCHITECTURE.md                  # This document
    DECISIONS.md                     # Historical + new decisions
    CHANGELOG.md                     # Project history
  .claude/                           # Claude Code development agents (PCC)
    agents/                          # PCC workflow agents
    settings.json
  .github/                           # CI/CD
    workflows/
  CLAUDE.md                          # Development instructions
  README.md                          # Project overview
  pyproject.toml                     # Root workspace config
  .gitignore
  LICENSE
```

---

## 10. Spec State Machine (Preserved)

The spec lifecycle state machine is unchanged:

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
                                       +---> STUCK (retry 10)
```

Valid transitions (enforced by MCP server):
- DRAFT -> SCOUTED (Scout completes research)
- DRAFT -> DECOMPOSED (bypass Scout for simple specs)
- SCOUTED -> DECOMPOSED (Architect decomposes)
- DECOMPOSED -> READY (sub-specs created)
- READY -> IN_PROGRESS (Worker claims)
- IN_PROGRESS -> REVIEW (Worker completes)
- IN_PROGRESS -> INTERRUPTED (graceful shutdown)
- INTERRUPTED -> READY (restart re-queues)
- REVIEW -> DONE (QG accepts)
- REVIEW -> REJECTED (QG rejects)
- REJECTED -> READY (retry)
- READY -> STUCK (retry 10 exhausted)

Note: Pasha dynamically decides which transitions to use based on spec nature (D71).
- Bugfix: DRAFT -> READY (skip Scout, Architect)
- Research: DRAFT -> SCOUTED -> DONE (no Worker)
- Documentation: DRAFT -> DECOMPOSED -> READY -> IN_PROGRESS -> REVIEW -> DONE (lighter QG)

---

## 11. Testing Strategy

### MCP Server Tests

The MCP server is a standard Python package tested with pytest:

- **Unit tests**: Spec state machine, DAG validator, write-set matcher, policy engine, budget tracker
- **Tool tests**: Each MCP tool tested with mock filesystem (no real projects)
- **Integration tests**: Full spec lifecycle through MCP tools (create -> transition -> validate)
- **Sentinel tests**: Allowlist/denylist/Haiku evaluation with mocked Haiku

### Agent Tests

Agent behavior is tested through OpenClaw's testing infrastructure. SOUL.md prompts are validated by running agents against mock MCP servers.

### Agent Behavior Evals (D72)

`tests/test_agent_evals.py` tests SOUL.md behavioral contracts:

- Worker calls `run_command_checked` (not native bash)
- Worker calls `verify_tests`/`verify_lint`/`verify_types` before transitioning to REVIEW
- Worker calls `web_fetch_checked` for URLs
- Architect decomposes to sub-specs with <=5 artifacts each
- QG rejects when mandatory evidence is missing
- Pasha calls `get_relevant_learnings` before spawning agents
- Pasha skips Scout for simple bugfix specs

These are mocked scenarios testing the expected tool call sequences,
not the quality of LLM output. They validate that SOUL.md instructions
produce the correct behavioral patterns.

### No LLM Calls in CI

Same principle as D34: all automated tests mock LLM calls. The MCP server's Sentinel Haiku calls are mocked. Agent prompt quality is validated manually.
