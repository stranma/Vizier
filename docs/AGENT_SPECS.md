# Vizier Agent Specifications

## Agent Overview

| Agent | Scope | Model Tier | Trigger | Always Running? | Plugin-aware? |
|-------|-------|-----------|---------|-----------------|---------------|
| EA | Singleton (all projects) | Opus | Human message / calendar / report / schedule | Yes | No (framework) |
| Pasha | Per-project | Opus | Spec lifecycle events / human session | Yes (event loop) | No (framework) |
| Architect | Per-project | Opus | DRAFT specs from Pasha | No (spawned) | Yes (reads plugin guide) |
| Worker | Per-project | Sonnet/Haiku | READY specs in queue | No (spawned per task) | Yes (plugin provides class) |
| Quality Gate | Per-project | Sonnet | REVIEW specs | No (spawned per review) | Yes (plugin provides class) |
| Retrospective | Per-project | Opus | Cycle end / STUCK / pattern | No (spawned periodically) | No (framework) |

**Plugin-aware agents** use the project's plugin to determine their behavior: tools, prompts, criteria, restrictions. Framework agents are the same regardless of project type.

---

## EA (Executive Assistant)

### Role
The human's single interface to the entire system. Manages attention, tracks real-world commitments, routes tasks, and proactively surfaces what matters. Replaces the original "Secretary" role with full executive assistant capabilities.

### Communication Modes

| Mode | Trigger | Behavior |
|------|---------|----------|
| **Delegation** | "Build auth for project-alpha" | Creates DRAFT spec, routes to project, reports when done |
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

### Inputs
- Human messages (Telegram / Slack / CLI)
- `reports/*/status.json` — project status updates
- `reports/*/escalations/` — blocker notifications
- Calendar events (via MCP: Google Calendar / Outlook)
- `ea/commitments/*.yaml` — commitment state
- `ea/relationships/*.yaml` — contact context
- Pasha session summaries (`ea/sessions/*.md`)

### Outputs
- `.vizier/specs/NNN/spec.md` (status: DRAFT) — new task seeds in target project
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
- **Gatekeeper of attention**: decides what's worth interrupting the human for
- Translates business language into structured spec seeds
- Filters noise: not every cycle report becomes a human message
- Escalates blockers and deadline risks immediately
- Tracks commitments vs. project progress: "Board deck due in 2 days, 60% done"
- Prepares meeting context: "Call with Novak in 1h -- you owe him partnership terms"
- Reminds about forgotten promises: "Response to Novak pending since Feb 10"
- Reads Pasha session summaries to maintain continuity
- During Pasha sessions: holds non-urgent updates, stays aware
- **JIT prompt assembly (D42)**: always-loaded core (~2,500 tokens) + conditional modules loaded by deterministic classifier. Keeps context window efficient without splitting EA into separate agents.
- **MCP plugin discovery (D43)**: at startup, discovers per-project plugin MCP tools. Routes quick queries (e.g., "are the tests passing?") to plugin tools without creating specs.
- **Behavioral anchor: priorities.yaml**: reads Sultan's current priorities on every LLM invocation. Provides stable decision context across fresh calls.

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
| Commit approval | Spec has `requires_approval: true` | Shows diff + summary in Telegram with Approve/Reject. Gates the commit until Sultan responds. |

### Validated Scenarios

These scenarios confirmed the monolithic EA design (D21):

1. **Morning delegation** — Sultan reads briefing, delegates "add dark mode to project-alpha", asks status. EA classifies intent, creates DRAFT spec, reads status.json.
2. **Deep Pasha session** — Sultan says "let's work on project-alpha." EA opens Pasha session, holds non-urgent updates. After session, Pasha writes summary, EA reads it. EA surfaces held notifications.
3. **Proactive crisis** — Auth spec at 7/10 retries. EA correlates with commitment deadline (API docs for Novak, due Friday). Proactively alerts Sultan with risk assessment. Sultan bumps Worker to Opus.
4. **File checkout/checkin** — Sultan requests file via Telegram. EA pulls from git, sends file. Sultan edits, uploads back. EA commits. Handles conflicts if project moved ahead.
5. **Programmable check-in** — Sultan runs `/checkin`. EA conducts structured interview: new contacts, commitments, decisions, blockers. Creates relationship and commitment records from conversation.
6. **Cross-project coordination** — Sultan needs board deck spanning multiple projects. EA reads status from all projects, creates linked DRAFT specs. Tracks completion across projects.
7. **Direct Q&A** — Sultan asks "what framework does project-alpha use?" EA reads project files and answers directly. Simple questions don't need spec routing.

---

## Pasha

### Role
Owns the lifecycle of a single project. Orchestrates agents within the project. Writes progress reports for EA. Supports direct human working sessions for deep discussions.

### Operating Modes

| Mode | Trigger | Behavior |
|---|---|---|
| **Autonomous** | Normal operation | Event-driven loop, spawns agents, writes reports |
| **Session** | Human connects via EA | Deep back-and-forth discussion, spec design, architecture decisions |

When in session mode, the Pasha maintains full project context (constitution, specs, learnings, codebase) and engages in extended conversation. When the session ends, Pasha writes a summary to `ea/sessions/` so EA can maintain continuity.

### Inputs
- `.vizier/specs/**` — spec lifecycle events (filesystem watch)
- `.vizier/state.json` — current project state
- `.vizier/constitution.md` — project principles
- `.vizier/learnings.md` — accumulated knowledge
- `.vizier/config.yaml` — plugin selection and overrides

### Outputs
- Delegates to Architect (creates DRAFT specs or triggers Architect)
- `reports/<project>/status.json` — current status
- `reports/<project>/YYYY-MM-DD-cycle-NNN.md` — cycle reports
- `reports/<project>/escalations/` — blocker notifications

### Trigger
- New DRAFT spec arrives (from EA)
- Spec status changes (DONE, STUCK, REJECTED)
- Periodic reconciliation (configurable, default 15 seconds)

### Key Behaviors
- Maintains project state machine
- Loads the correct plugin for the project
- Spawns Architect, Worker (from plugin), Quality Gate (from plugin) as needed
- Tracks cycle count and overall progress
- Escalates via reports/escalations/ (EA watches)
- Does NOT communicate with humans directly
- **Spec state-age monitoring**: during each reconciliation cycle, checks `time_in_state` for every active spec. Detects silently stuck specs (e.g., IN_PROGRESS for 30+ minutes with no agent subprocess alive). Thresholds are plugin-configurable.
- **Reconciliation at 15s default** (D22): short intervals compensate for watchdog unreliability on Windows. Reconciliation is cheap (reading file metadata and frontmatter).

---

## Architect

### Role
Decomposes high-level tasks into implementable specs. Reads the project's full context. Writes specs detailed enough that Workers don't need to explore.

### Inputs
- DRAFT spec from Pasha
- Full project source (codebase, documents, data)
- `.vizier/constitution.md`
- `.vizier/learnings.md`
- Plugin's `architect_guide.md` — domain-specific decomposition patterns
- Plugin's `criteria/` — reusable acceptance criteria to reference

### Outputs
- Sub-specs in `specs/NNN-parent/NNN-subtask.md` (status: READY)
- Updated parent spec (status: DECOMPOSED if split)

### Trigger
- Pasha delegates a DRAFT spec

### Key Behaviors
- Always uses strongest model (Opus-class)
- Reads project thoroughly before writing specs
- Uses plugin's decomposition patterns (e.g., "feature -> data model -> logic -> API -> tests")
- References plugin's criteria library via `@criteria/` syntax
- Sets `complexity` field honestly (drives Worker model selection)
- References `learnings.md` for known pitfalls
- One concern per sub-spec
- Provides domain-appropriate contracts (interfaces for code, formulas for finance, outlines for docs)

---

## Worker

### Role
Executes a single spec. Fresh context each time. Produces artifacts, validates, commits, exits.

### Plugin Provides
- **Python class** extending `BaseWorker` — defines tools, restrictions, git strategy
- **Prompt template** (Jinja2) — rendered with spec + context
- **Tool restrictions** — which tools are available and what commands are allowed

### Inputs
- One READY spec (assigned via state.json)
- Project source files (only those listed in spec)
- `.vizier/learnings.md` (relevant entries)
- Plugin's prompt template (rendered)

### Outputs
- Modified/created artifacts as specified
- Git commit (one per spec, using plugin's commit template)
- Status update: REVIEW (success) or feedback file (stuck)

### Trigger
- Assigned a READY spec by Pasha

### Key Behaviors
- **Fresh context per task** — no memory of previous tasks
- **Bounded read-only exploration** — can read any project file, but can only write to artifacts listed in spec. Reads beyond artifact list are logged for Retrospective analysis.
- If spec is fundamentally insufficient, writes feedback and exits (does NOT guess)
- **Implicit completion** — Worker exits cleanly → spec transitions to REVIEW. No magic string signal.
- Model tier set by spec's `complexity` field via plugin's model tier config. Bumped automatically on retry 3 (graduated retry).
- Uses only tools permitted by plugin's `allowed_tools`, enforced by Sentinel (allowlist + denylist + Haiku)

### Built-in Implementations

| Plugin | Worker Class | Tools | Git Strategy |
|--------|-------------|-------|-------------|
| `software` | `SoftwareCoder` | file ops, bash, git, glob, grep | branch_per_spec |
| `documents` | `DocumentWriter` | file ops, web_search, python_exec (pandoc) | commit_to_main |

---

## Quality Gate

### Role
Validates Worker output against spec's acceptance criteria. Can approve (DONE) or reject with feedback.

### Plugin Provides
- **Python class** extending `BaseQualityGate` — defines automated checks
- **Prompt template** (Jinja2) — for non-automatable evaluation
- **Criteria library** — reusable criteria definitions

### Inputs
- Spec in REVIEW status
- Worker's output (git diff for code, file diff for others)
- Acceptance criteria from spec (including `@criteria/` references resolved from plugin)
- `.vizier/learnings.md`

### Outputs
- Status update: DONE (approved) or REJECTED (with feedback)
- Feedback file in `specs/NNN/feedback/YYYY-MM-DD-NNN.md`

### Trigger
- Spec transitions to REVIEW status

### Key Behaviors
- Runs every automated check defined by the plugin
- Resolves `@criteria/` references from plugin's criteria library
- Evaluates non-automatable criteria with honest assessment
- For software: checks test meaningfulness (not just "tests pass" but "tests prove something")
- Feedback must be specific and actionable
- Does NOT fix issues — only identifies them
- Follows the Completion Protocol (see below)

### Completion Protocol (PCC)

Inspired by claude-code-python-template's Phase Completion Checklist, adapted to Vizier's event-driven model. When a spec transitions to REVIEW, the Quality Gate executes this structured multi-pass protocol.

**Pass 1 — Hygiene (deterministic, no LLM)**
- Check for debug artifacts (print statements, console.log, TODO markers, commented-out code)
- Verify no hardcoded test values or credentials
- Confirm changes stay within spec's artifact list (no unintended file modifications)

**Pass 2 — Mechanical Quality (deterministic, no LLM)**
- Run plugin's automated checks (lint, format, type check, secret scan)
- All checks must pass before proceeding to LLM-assisted passes
- Failures here → immediate REJECTED with specific fix instructions (cheap, no tokens burned)

**Pass 3 — Test Validation (LLM-assisted)**
- All tests pass
- Tests are meaningful (prove behavior, not just assert True)
- Coverage of spec's requirements (functional coverage, not just line coverage)

**Pass 4 — Acceptance Criteria (LLM-assisted)**
- Verify ALL criteria listed in the current spec
- Resolve `@criteria/` references from plugin's criteria library
- Cumulative check: verify that parent spec criteria still hold if the change could affect them

**Pass 5 — Consistency (LLM-assisted)**
- Changes are consistent with project constitution and learnings.md
- Any documentation affected by the change is updated
- No regressions introduced to previously completed specs

**Protocol rules:**
- Passes 1-2 are fast and cheap — always run first, fail fast before spending tokens
- Passes 3-5 can run in parallel where independent
- Any pass failure → REJECTED with specific, actionable feedback per failing item
- All passes succeed → DONE
- The protocol is implemented within the Quality Gate class, not as separate agents

### Built-in Implementations

| Plugin | Quality Gate Class | Automated Checks |
|--------|-------------------|-----------------|
| `software` | `SoftwareQualityGate` | pytest, ruff check, ruff format |
| `documents` | `DocumentReviewer` | structure validation, link checking |

---

## Retrospective

### Role
Analyzes failures, patterns, and inefficiencies. Updates process files to prevent repeated mistakes. This is the meta-improvement engine.

### Inputs
- Same as Pasha (all spec events, state, reports)
- `specs/**/feedback/` — rejection history
- STUCK specs and their retry histories
- `.vizier/learnings.md` (current state)

### Outputs
- Updated `.vizier/learnings.md` (direct write)
- `.vizier/proposals/*.md` — suggested changes for human review:
  - Prompt modifications
  - New criteria for the plugin's library
  - Acceptance criteria template changes
  - Process rule changes

### Trigger
- End of each completion cycle (spec goes DONE)
- Any spec goes STUCK
- Periodic (configurable, e.g., daily)

### Key Behaviors
- Looks for patterns: same type of rejection repeated? Same files causing issues? Workers consistently reading files not in artifact list?
- Can update `learnings.md` directly (low-risk, append-only)
- Writes proposals for structural changes — **ALL proposals require Sultan approval, always** (no auto-approve, no graduation to autonomous changes)
- Constrained scope:
  - CAN change: learnings (direct), criteria/prompt/process proposals (with approval)
  - CANNOT change: architecture, agent topology, plugin interfaces
- Tracks improvement metrics: rejection rate, stuck rate, average retries, cycle time, cost per spec
- Compares metrics across cycles to measure whether changes helped
- Analyzes cost data from structured agent logs
