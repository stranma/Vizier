# Vizier Decision Map

## Mindmap

```mermaid
mindmap
  root((Vizier))
    Architecture
      Multi-agent orchestra
        Why: different cognitive tasks need different capabilities
        Why: parallelism between Worker and Quality Gate
        Alt rejected: single agent loop - too limited for complex orchestration
      Ralph Wiggum pattern
        Fresh context per task
        Why: prevents context drift and hallucinated state
        Why: forces agents to verify from disk, not memory
        Alt rejected: persistent sessions - context degrades over long sessions
      Event-driven, not polling
        Filesystem watch via watchdog
        Why: saves API tokens vs polling loops
        Why: instant pickup on state changes
        Reconciliation: periodic scan verifies state from disk
          Events are optimization, disk is truth
          Why: watchdog can miss events under load
        Alt rejected: polling loop - wasteful, burns tokens on idle checks
        Alt rejected: message queue Redis/NATS - unnecessary infrastructure
      Filesystem as message bus
        Why: zero infrastructure dependency
        Why: state survives restarts
        Why: every agent naturally has access
        Why: git-trackable history
        Alt rejected: Redis pub/sub - adds ops complexity for no benefit at this scale
    Agent Roles
      EA - Executive Assistant singleton
        Replaces Secretary - much broader scope
        Why: single human interface to everything
        Why: gatekeeper of human attention
        Monolithic and powerful - Claude Code pattern
          Why: Grand Vizier was the most capable person, not a receptionist
          Why: fresh LLM call per message, no accumulated state
          Why: internal modularity via handler functions, not agent split
          Alt rejected: thin router + handler agents - makes EA dumb
        Owns: commitments, calendar, relationships, priorities
        Proactive: briefings, deadline warnings, meeting prep, reminders
        Three layers: async Telegram, direct Pasha session, autonomous
        Alt rejected: simple Secretary routing agent - too narrow
        Alt rejected: two bots EA + dispatcher - dispatcher is just a function
      Pasha - per project, two modes
        Autonomous mode: event-driven loop, spawns agents, writes reports
        Session mode: deep back-and-forth with human for spec design
        Why: owns project lifecycle
        Why: isolates project concerns
        Reports to EA, supports direct human sessions
      Architect - per project, Opus
        Why: decomposition is the hardest cognitive task
        Why: must understand full project context
        Writes specs specific enough that Worker does not explore
        Alt rejected: Worker explores and plans - wrong model tier for exploration
      Worker - per project, plugin-provided
        Fresh context, one spec, exit
        Model tier set by spec complexity, bumped on retry 3
        Bounded read-only exploration beyond artifact list
        Graduated retry: bump model 3, alert Pasha 5, re-decompose 7, STUCK 10
        Completion: clean exit = REVIEW, no magic string
        Alt rejected: persistent Worker with memory - context drift
      Quality Gate - per project, plugin-provided
        Completion Protocol PCC: 5-pass structured validation
          Pass 1-2: deterministic, no LLM - hygiene, lint, format, types
          Pass 3-5: LLM-assisted - tests, acceptance criteria, consistency
          Inspired by claude-code-python-template PCC
          Alt rejected: separate reviewer + test agent - protocol subsumes both
        Can reject back to Worker
      Retrospective - per project
        Same inputs as Pasha, different goals
        Why: meta-improvement without blocking critical path
        Can update learnings directly
        Proposes structural changes for human approval
        Alt rejected: bake into Pasha - overloads Pasha, different concern
    Model Routing
      Rules-based router
        Why: don't burn tokens deciding which model to use
        20 lines of code, not an agent
        Resolution: spec complexity then project config then plugin default then framework default
        Alt rejected: dedicated Scheduler agent - over-engineered
      Multi-provider support
        Anthropic, OpenAI, pluggable
        Why: cost optimization, availability, capability matching
        Abstract tiers: opus, sonnet, haiku
    Framework Independence
      Own thin runtime over any agent framework
        ~1500 lines of Python, not 10k+ framework abstractions
        Why: event-driven orchestration is the product differentiator
        Why: no framework supports filesystem-as-bus natively
        Alt rejected: Claude Agent SDK - LLM-driven, Anthropic-only, alpha, 12s overhead
        Alt rejected: LangGraph - graph-driven, stateful, heavy
        Alt rejected: CrewAI - shared context, moving to paid
        Agent SDK as future optional Worker backend
          When: 1.0 release, daemon mode, stable multi-agent
          Where: software plugin SoftwareCoder only
          Why: built-in file ops save ~500 lines
    Plugin System
      Python packages with entry points
        Why: full flexibility for custom tools and validation logic
        Why: type-safe, testable, debuggable
        Why: standard Python packaging and distribution
        Alt rejected: YAML-only profiles - cannot add custom capabilities
        Alt rejected: prompt-only profiles - no tool restriction enforcement
      Plugins provide Worker + Quality Gate classes
        Tools and restrictions per plugin
        Prompt templates Jinja2
        Criteria library with @criteria/ references
        Decomposition patterns for Architect
      Plugin discovery via entry points
        Why: standard Python mechanism
        Why: supports both built-in and third-party plugins
        Why: no central registry needed
      Built-in plugins
        software - first, validates the system
        documents - second, proves plugin system works for non-code
    Deployment
      Hybrid: package + daemon
        Why: framework code shared, config per-project
        Why: single server manages multiple projects
        Alt rejected: per-project standalone - duplicated infrastructure
        Alt rejected: server-only - no project-specific tuning
      Per-project .vizier/ in git
        constitution, config, specs, learnings committed
        state.json gitignored
        Why: project knowledge travels with the project
        Why: work history is valuable
      Reports outside project repos
        Why: transient, server-specific
        Why: cross-project aggregation by EA
      EA as singleton in daemon
        Per-project agents instantiated per workspace
    Communication
      Three layers
        Layer 1: EA on Telegram - async, mobile
          Delegation, status, briefings, commitments, calendar
          Why: quick interactions, always available
        Layer 2: Direct Pasha session - sync, focused
          Deep project discussions, spec design, architecture
          EA facilitates connection, holds updates, reads summary after
          Why: creative/technical work needs extended back-and-forth
        Layer 3: Autonomous - no human
          Agents execute specs, EA surfaces only what matters
          Why: human attention is the scarcest resource
      Telegram first
        Why: mobile, always available
        Why: user already has Telegram bot experience from EFM
        Slack/CLI as future channels
    Real-World Awareness
      Commitments tracking
        Promises with deadlines, linked to projects or standalone
        EA correlates project progress with deadlines
        Why: the real question is not spec status but will I keep my promises
      Calendar integration
        Google Calendar / Outlook via MCP
        Meeting prep, deadline awareness, schedule context
        Why: meetings are where commitments are made and checked
      Relationships
        Contacts with context, open commitments, last interaction
        Generalized from EFM relationships.md
        Why: people are the other side of every commitment
      Proactive behaviors
        Morning briefings, deadline warnings, follow-up reminders
        Meeting prep, completion notices, risk escalation
        Why: EA manages attention, not just routes tasks
    Meta-improvement
      Retrospective agent
        Triggers on: cycle end, STUCK, periodic
        Analyzes: rejection patterns, stuck specs, retry counts
        Outputs: learnings.md updates, proposals for human review
        Constrained scope: prompts and rules only, not architecture
        Why: prevent same mistakes from repeating
        Why: system gets better over time
        Risk: can degrade prompts if unconstrained
        Mitigation: proposals require human approval initially
      Learnings.md
        Append-only, machine and human readable
        All agents read on startup
        Why: institutional memory persisted to disk
    claude-code-python-template - three layers
      Layer 1: scaffold Vizier itself
        Monorepo, TDD, CI/CD, 7 dev agents
        Why: same toolchain, saves setup time
      Layer 2: project type for Vizier-managed Python projects
        Software plugin offers as scaffolding
        Why: no-brainer, template is what Vizier manages
      Layer 3: selective inspiration for Vizier agents
        PCC adopted as Completion Protocol in Quality Gate
        Deterministic-first, cumulative criteria, parallel checks
        Agent architecture NOT adopted - different execution model
        Why: concepts transfer, implementation model does not
    EFM Lineage
      Check-in bot absorbed into EA + plugins
        Telegram interface -> EA channel
        Structured check-in -> EA check-in mode
        MCP safety tiers -> plugin tool restrictions
        Lane 1/2 git -> plugin git strategies
        ops/ docs -> documents/operations plugin
        relationships.md -> EA relationships/*.yaml
        open-items.md -> EA commitments/*.yaml
        Diff approval -> EA approval UI for sensitive specs
      Gaps filled by Vizier
        Commitment tracking with deadlines
        Calendar integration and meeting prep
        Cross-project visibility
        Meta-improvement via Retrospective
        Plugin extensibility to any domain
    Naming - Ottoman Court
      Sultan - the human owner
        Why: Vizier serves the Sultan, not the other way around
        All dangerous operations require Sultan approval
      Vizier - EA, the chief minister
        Why: historically ran the empire so the Sultan could focus
      Pasha - project governor, one per project
        Why: Pashas governed provinces autonomously, reported upward
        Replaces generic Manager - more evocative and consistent
      Sentinel - Security, guarding the gates
        Why: guards the gates, deterministic + Haiku hybrid
      Architect, Worker, Quality Gate, Retrospective - functional names
        Why: Ottoman equivalents (Kadi, Scribe) too obscure for code
    Sync and Permissions
      Git-only sync
        All edits through agents or file checkout/checkin
        Why: atomic, history, conflict resolution, works everywhere
        Alt rejected: OneDrive/cloud sync - latency, conflicts, flaky mounts
        Alt rejected: Syncthing - another daemon, basic conflict resolution
      File checkout for direct Sultan edits
        EA copies file to checkout/, Sultan edits, EA copies back and commits
        Why: Sultan sometimes needs Excel or direct file editing
      Permission model
        EA reads everything, writes only ea/ data + DRAFT specs
        Pasha reads/writes own project only
        Worker reads any file, writes only spec artifacts
        Enforcement: allowlist + denylist + Haiku via Sentinel
          Allowlist: auto-approve common safe ops, zero cost
          Denylist: auto-block dangerous ops, zero cost
          Ambiguous: Haiku evaluates intent, ~$0.001/call
          Why: regex-only is bypassable, Haiku understands intent
        Why: principle of least privilege per role
      Pasha to EA via filesystem
        Pasha writes reports/ -> watchdog -> EA reads
        EA writes specs/ -> watchdog -> Pasha reads
        Why: consistent with filesystem-as-bus principle
        Alt rejected: direct calls between agents - breaks isolation
    Security - Sentinel
      Deterministic service, not an LLM agent
        Whitelist/blocklist, regex patterns, permission enforcement
        Why: 95% of security checks are deterministic, no tokens needed
      Haiku Content Scanner for untrusted sources
        Evaluates web content for prompt injection
        Scans inbound files from unknown sources
        Why: need intelligence for novel threats, Haiku is cheap enough
      Sultan approval queue via EA
        GitHub Actions changes, force push, new dependencies
        Sentinel blocks -> EA asks Sultan -> decision flows back
        Why: dangerous operations need human judgment
      Pre-commit secret scanning
        Block API keys, tokens, passwords, private keys
        Why: defense in depth, learned from EFM safety server
    Infrastructure
      Telegram long polling first
        Why: zero infrastructure, no domain or TLS needed
        Webhook later when latency or multi-channel matters
      asyncio daemon + subprocess per agent
        Daemon: asyncio event loop for aiogram, watchdog, orchestration
        Agents: separate Python process per invocation
        Why: crash isolation, resource limits, true fresh context
        Concurrency: asyncio.Semaphore gates max concurrent agents
        Alt rejected: pure asyncio tasks - no crash isolation
        Alt rejected: ProcessPoolExecutor - over-engineered, agents are I/O-bound
      Files only for queryable data
        YAML for commitments, relationships
        JSONL for agent logs
        Why: single-user scale, git-trackable, human-readable
        Alt rejected: SQLite - breaks git-trackability for no benefit at this scale
      Stub plugin as test fixture
        tests/fixtures/stub_plugin/
        Why: test-only code, not a real plugin
        Plugin discovery tested separately with mocks
    Spec Contract
      Architect writes, Worker consumes
        Worker has bounded read-only exploration
          Can read any project file, must log reads beyond artifact list
          Cannot write beyond artifact list
          Why: Architect is 90% right, remaining 10% shouldnt require re-decomposition
        Why: keeps Worker simple and cheap
        Why: Architect already paid Opus-tier cost for understanding
      One spec, one concern, one commit
        Why: atomic changes, easy rollback, clear history
      Acceptance criteria must be automatable
        @criteria/ references from plugin library
        Why: Quality Gate can verify mechanically
        Why: prevents subjective pass/fail judgment
```

## Decision Log (Chronological)

### D1: Multi-agent over single-agent loop
**Context:** Ralph Wiggum uses a single agent in a bash loop. We considered the same.
**Decision:** Multi-agent with specialized roles (Pasha, Architect, Worker, Quality Gate, Retrospective, EA).
**Why:** Different cognitive tasks (decomposition vs implementation vs review) need different model tiers and different tool access. A single agent doing everything requires the strongest model for every step, wasting budget on simple implementation tasks.
**Trade-off:** More complex orchestration, but better cost efficiency and quality.

### D2: Fresh context per task (from Ralph Wiggum)
**Context:** Agents could maintain persistent sessions or start fresh each time.
**Decision:** Fresh context per task for Workers. Pasha and EA maintain lightweight Python event loops (no LLM in the loop — fresh LLM call per message/event).
**Why:** Long sessions accumulate stale context and hallucinated state. Fresh starts force agents to verify reality from disk.

### D3: Rules-based model routing, not a Scheduler agent
**Context:** Original proposal had a dedicated Scheduler agent deciding which model to use.
**Decision:** Replace with a 20-line rules-based router. Resolution order: spec complexity > project config > plugin default > framework default.
**Why:** Using an LLM to decide which LLM to call is wasteful meta-reasoning.

### D4: Filesystem as message bus, not Redis/NATS
**Context:** Agents need to communicate state changes (new spec, spec done, etc.).
**Decision:** Filesystem with watchdog-based event detection. No message queue.
**Why:** Zero infrastructure dependency. State survives restarts. Git-trackable. Every agent naturally has access. At single-server scale, filesystem watch is fast enough.

### D5: EA replaces Secretary — three communication layers
**Context:** Originally had a "Secretary" that routed tasks. Evolved through: Secretary with two modes -> Secretary as EA -> EA with direct Pasha sessions.
**Decision:** Executive Assistant (EA) replaces Secretary. Three layers: (1) EA on Telegram for async/mobile (delegation, status, briefings, commitments), (2) Direct Pasha sessions for deep project discussions, (3) Autonomous operation with no human. EA is the gatekeeper of human attention.
**Why:** A CEO doesn't just delegate — they need proactive briefings, commitment tracking, calendar awareness, and the ability to drop into deep working sessions when needed. A "Secretary" was too narrow.

### D6: Plugin system (Python packages) over YAML profiles or prompt-only
**Context:** Need to support different project types (software, finance, documents). Three approaches considered.
**Decision:** Python plugin packages with entry point discovery. Plugins provide Worker class, Quality Gate class, prompt templates, criteria library, tool restrictions.
**Why:** YAML profiles can't add custom validation logic or tools. Prompt-only profiles can't enforce tool restrictions. Python packages give full flexibility while remaining testable and type-safe.

### D7: Architect must be exhaustively specific
**Context:** Should Workers plan and explore, or should Architect provide complete specs?
**Decision:** Architect (Opus-tier) writes specs specific enough that Worker (Sonnet/Haiku-tier) never needs to explore. If Worker can't proceed without exploring, the spec was insufficient.
**Why:** Exploration is expensive and requires strong models. Workers run cheap. Moving cognitive load to Architect is more cost-effective.

### D8: Retrospective as separate agent, not part of Pasha
**Context:** Meta-improvement could be baked into Pasha or split into its own agent.
**Decision:** Separate Retrospective agent with same inputs as Pasha but different goals. Constrained to changing prompts/rules/criteria, not architecture.
**Why:** Separates concerns. Pasha is on the critical path (orchestration); Retrospective is off the critical path (analysis). Different goals from the same data.

### D9: Hybrid deployment (package + daemon)
**Context:** Two models: per-project standalone installation, or server-based agents working on anything.
**Decision:** Framework is a Python package. Runtime is a server daemon. Per-project `.vizier/` config lives in git. Daemon manages workspaces and agent lifecycle.
**Why:** Framework code should be shared (DRY). Project config should travel with the project (portability). Server resources should be managed centrally (efficiency).

### D10: EA is part of Vizier, not external
**Context:** EA could be a separate system (e.g., OpenClaw, custom Telegram bot).
**Decision:** EA is a built-in component of the Vizier daemon.
**Why:** EA needs deep integration with the project registry, status files, spec creation, and commitment tracking. External systems would need adapters for all of this. Building it in ensures tight integration.

### D11: EA tracks real-world state (commitments, calendar, relationships)
**Context:** Projects exist because of real-world promises and deadlines. Internal spec status alone doesn't answer "Am I going to keep my promises?"
**Decision:** EA maintains a real-world model: commitments (promises + deadlines), relationships (people + context), calendar integration (via MCP). EA correlates project progress with real-world deadlines and proactively alerts on risks.
**Why:** The unique value is a system that not only does the work but knows whether the work will meet real-world obligations. No existing tool combines autonomous execution with commitment tracking.
**Trade-off:** More state to manage, calendar integration adds external dependency. But without this, the system is just a fancy task runner.

### D12: Direct Pasha sessions for deep project work
**Context:** EA handles quick delegation, but some tasks need extended back-and-forth: spec design, architecture, project kickoff.
**Decision:** Human can "enter" a direct session with a project's Pasha (or Architect). EA facilitates the connection, holds non-urgent updates during the session, and reads the session summary afterward for continuity.
**Why:** Deep creative/technical work can't be mediated through a routing layer. Like a CEO sitting down with a VP for a working session — the EA steps back but stays aware.

### D13: Vizier as a personal AI operating system, not just coding
**Context:** Started as "autonomous coding system." Evolved as we recognized the same orchestration serves any knowledge work.
**Decision:** Vizier is a personal AI operating system for knowledge workers. EA = interface to everything. Project teams = autonomous agents for any domain. Plugin system = extensible to any structured work.
**Why:** The orchestration (Pasha -> Architect -> Worker -> Quality Gate) is domain-agnostic. The plugin system already supports non-code work. Adding EA's real-world awareness makes it a complete system for anyone who works with information.

### D14: Own thin runtime over Claude Agent SDK (or any framework)
**Context:** Evaluated 8 agent frameworks (Claude Agent SDK, LangGraph, CrewAI, AutoGen/Microsoft Agent Framework, Smolagents, OpenAI Agents SDK, Google ADK, Agno). Claude Agent SDK was the strongest candidate — it provides built-in file ops, bash, search, editing, subagent spawning, and context compaction for free.
**Decision:** Build our own thin runtime (~1500 lines). Do not adopt any framework as foundation. Keep Claude Agent SDK as a future optional backend for the `software` plugin's Worker.
**Why:**
- **Orchestration mismatch**: Every framework assumes either LLM-driven orchestration (Claude SDK, CrewAI, OpenAI SDK) or graph-driven orchestration (LangGraph, Microsoft Agent Framework). Our event-driven, code-driven filesystem orchestration is the product differentiator — adopting someone else's orchestration means giving it away.
- **Claude Agent SDK specifics**: It wraps the entire CLI binary as a subprocess (~55-73 MB). Each `query()` call has ~12s startup overhead (no daemon mode). Alpha status (v0.1.36, pre-1.0) with known issues: multi-agent OOM kills, lock file corruption, Windows initialization hangs. Anthropic-only — breaks our LiteLLM multi-provider strategy.
- **Cost of independence**: ~500 lines of custom tool implementation (file ops + bash + search) is cheap insurance against depending on alpha software for the core product.
- **Re-evaluation trigger**: When Agent SDK reaches 1.0, adds daemon mode (eliminating 12s overhead), and fixes multi-agent stability, consider it as optional backend for `SoftwareCoder`. The plugin system supports this swap without changing orchestration code.
**Trade-off:** We implement tools ourselves (~500 lines) that the SDK provides for free. But we gain: full control, lower latency, multi-provider support, production stability, and no 55MB binary dependency.
**Alt rejected:** Claude Agent SDK as foundation — LLM-driven loop, Anthropic-only, alpha stability.
**Alt rejected:** LangGraph — graph-driven, stateful by design (opposite of fresh-context), heavy LangChain abstractions.
**Alt rejected:** CrewAI — agents share context (opposite of fresh-context), moving toward paid platform.
**Alt rejected:** Smolagents — minimal and fast, but no orchestration layer, code-agent paradigm doesn't match tool-restriction model. Worth reading for patterns.

### D15: EFM check-in bot capabilities absorbed into EA + plugins
**Context:** EFM's Telegram check-in bot handles structured founder check-ins, document updates, git automation, and approval workflows for a single project. Vizier's design should subsume all of this.
**Decision:** EFM's capabilities map cleanly onto Vizier components:

| EFM Function | Vizier Equivalent |
|---|---|
| Telegram bot interface | EA's Telegram channel (aiogram) |
| Structured check-in flow (5 phases) | EA's check-in mode (scheduled/on-demand) |
| Multi-turn Claude conversation | Worker's agentic loop (fresh context per spec) |
| MCP safety tiers (read/write/approve) | Plugin tool restrictions (allowed_tools, tool_restrictions) |
| Lane 1 direct commits | Plugin git strategy: `commit_to_main` |
| Lane 2 branch + PR + CI | Plugin git strategy: `branch_per_spec` |
| ops/ document updates | "documents" or "operations" plugin Worker |
| relationships.md | EA's `relationships/*.yaml` (structured, queryable) |
| open-items.md | EA's `commitments/*.yaml` (deadlines, linked contacts) |
| Telegram diff approval | EA approval UI for `requires_approval: true` specs |

**Gaps identified in Vizier that EFM has:** Pre-commit approval UI (human reviews diff before commit). Addressable by adding `requires_approval` flag to specs — EA shows diff in Telegram, gates the commit.
**Gaps in EFM that Vizier covers:** Commitment tracking with deadlines, calendar integration, proactive briefings, cross-project visibility, meta-improvement (Retrospective), multi-project support, plugin extensibility.
**Why:** EFM's bot is a "single-threaded operations assistant" for one project. Vizier generalizes this into a multi-project autonomous work system while preserving all of EFM's operational capabilities.

### D16: Ottoman court naming — Sultan, Vizier, Pasha, Sentinel
**Context:** System needed clear role names. "TeamCoder" was too narrow (coding only). "User" and "admin" are bland.
**Decision:** Adopt Ottoman court metaphor selectively. Human = Sultan. EA = Vizier. Per-project orchestrator = Pasha (replaces "Manager"). Security = Sentinel. The product itself = Vizier. Architect, Worker, Quality Gate, Retrospective keep functional names — Ottoman equivalents (Kadi, Scribe, Nişancı) are too obscure.
**Why:** Sultan, Vizier, Pasha, and Sentinel are widely recognized words that create instant mental models. Pashas governed provinces (projects) autonomously but reported upward to the Vizier — exactly the per-project orchestrator role. Names should clarify, not require a history lesson.

### D17: Git-only sync with file checkout/checkin for direct edits
**Context:** Need to sync project files between Sultan's machine and Vizier server. Options: git only, git + OneDrive/rclone, git + Syncthing.
**Decision:** Git-only. All agent edits go through git. When Sultan needs to edit files directly (e.g., Excel), EA manages a checkout/checkin flow: copy file to `checkout/` folder, Sultan edits, EA copies back and commits.
**Why:** Git provides atomic operations, history, and conflict resolution. Cloud sync (OneDrive, Syncthing) adds infrastructure, latency, and conflict issues. Since Sultan primarily interacts through agents (Telegram, CLI), git covers 95% of cases. The checkout/checkin pattern handles the remaining 5% (direct file editing) cleanly.
**Trade-off:** Binary files (Excel) don't diff well in git. Acceptable — these files are edited infrequently and the checkout flow provides the safety net.

### D18: Permission model — least privilege per role
**Context:** Need to define what each agent can read and write. Agents should not have unrestricted access.
**Decision:** Role-based permissions: EA reads everything but writes only to ea/ data and DRAFT specs. Pasha reads/writes own project only. Worker reads/writes only files listed in its spec. Sentinel reads all outbound requests and can block operations.
**Why:** Principle of least privilege. Workers that can read the whole filesystem are a security risk. Pashas that can modify other projects break isolation. EA needs broad read access to correlate across projects but doesn't need write access to source code.
**Key design:** EA→Pasha communication is through specs/ (EA writes DRAFT) and reports/ (Pasha writes status). No direct calls. Consistent with filesystem-as-bus.

### D21: EA stays monolithic and powerful — rejected "god object" critique

**Context:** Design review raised concern that EA has 13+ responsibilities (routing, status, briefings, commitments, calendar, file relay, sessions, check-ins, cross-project coordination, direct Q&A, focus mode, proactive alerts) and violates the fresh-context principle by being "always-on." Proposed splitting EA into thin router + specialized handler agents.

**Decision:** Reject the critique. EA stays as a single, powerful Opus-tier agent. No architectural split.

**Why (three arguments):**

1. **Ottoman metaphor is correct.** The historical Grand Vizier wasn't a receptionist — he was the most capable, most trusted person in the empire. He handled everything *because* he understood the full picture. Splitting the Vizier into router + specialists is like replacing the Grand Vizier with a helpdesk. That's the opposite of the metaphor's intent.

2. **Claude Code pattern.** Claude Code is a "god object" by software engineering definitions: it reads files, writes code, runs tests, does git, searches the web, creates PRs. And it works brilliantly because the user talks to ONE capable agent. EA should follow this pattern: one capable agent that handles anything the Sultan throws at it. Making it "dumb" by splitting would be like replacing Claude Code with a menu system.

3. **The anti-pattern doesn't apply.** Software god objects fail because they accumulate mutable state. EA doesn't — each incoming message spawns a fresh LLM call with relevant state loaded from disk. The "always-on" part is a Python event loop (no LLM), not an LLM sitting in memory. Internal modularity (separate handler functions for delegation, status, check-in, file ops) provides testability without architectural splitting.

**Internal structure:** Python event loop (always-on, deterministic) receives messages. Each message triggers a fresh Opus-tier LLM call with only the relevant state loaded (commitments, status files, relationships, etc.). Handler functions are separate Python code units, testable in isolation, but orchestrated by a single agent prompt.

**EA scenarios validated:** 7 distinct usage scenarios confirmed this design — morning briefing, delegation, deep sessions, proactive crisis management, file checkout/checkin, structured check-ins, cross-project coordination, and direct Q&A. All work naturally with a single powerful agent.

---

### D22: Filesystem reconciliation — events as optimization, disk as truth

**Context:** Design review identified that watchdog can miss filesystem events (inotify overflow, crash during processing, no ordering guarantees, Windows falls back to polling). No acknowledgment or replay mechanism exists.

**Decision:** Add periodic reconciliation. On daemon start and periodically (configurable, e.g., every 60 seconds), scan all spec files and rebuild/verify state from disk. Filesystem events are an optimization (instant notification), not the source of truth. If an event is missed, reconciliation catches it on the next cycle.

**Why:** This turns a fragile event-notification system into a robust state-reconciliation system. The fresh-context pattern already assumes agents read from disk — reconciliation just ensures the Pasha's view of spec states is always consistent with reality.

**Trade-off:** Reconciliation adds a periodic scan (cheap — just reading file metadata and frontmatter). Worst case latency for a missed event is one reconciliation cycle.

---

### D23: Workers get bounded read-only exploration

**Context:** Design review challenged "if Worker needs to explore, Architect failed" as too rigid. Workers encounter runtime errors, missing transitive dependencies, and undiscovered config files that the Architect couldn't predict.

**Decision:** Allow Workers bounded read-only exploration beyond the artifact list. Workers can read (but NOT write) any file in the project. They must log what files they read beyond the artifact list. Write access stays restricted to spec artifacts only.

**Why:** In practice, Architects are 90% right about artifacts. The remaining 10% (runtime import errors, config files, test fixtures) shouldn't require a full re-decomposition cycle (Worker exits → Pasha → Architect → new spec → Worker retries). Bounded read access handles the 80% of these edge cases cheaply.

**Constraints:** Workers still cannot write beyond the artifact list. Any file reads beyond the artifact list are logged for Retrospective analysis (if Workers consistently read files not in specs, it indicates Architect prompt needs improvement).

---

### D24: Permission enforcement via allowlist + denylist + Haiku

**Context:** Design review noted that regex-based tool restrictions are bypassable (`rm -rf` blocked but `python -c "import os; os.system('rm -rf /')"` passes). Permissions are aspirational, not enforced.

**Decision:** Replace regex-only tool restrictions with a three-tier enforcement model via Sentinel:

| Tier | Mechanism | Cost | Example |
|---|---|---|---|
| **Allowlist** | Deterministic pattern match | Zero | `read_file`, `write_file` to spec artifacts, `pytest`, `ruff` |
| **Denylist** | Deterministic pattern match | Zero | `rm -rf`, `force push`, secret patterns |
| **Ambiguous** | Haiku evaluates intent | ~$0.001/call | `python -c "..."`, unfamiliar bash commands |

Sentinel intercepts every tool call. Allowlisted calls pass through instantly. Denylisted calls are blocked instantly. Anything else gets a Haiku evaluation of whether the call is safe given the agent's role and current spec.

**Why:** Haiku can understand that `python -c "import os; os.system('rm -rf /')"` is a destructive command even though it doesn't match a string pattern. The allowlist ensures 90%+ of calls (common operations) have zero latency/cost overhead. Only unusual calls hit the LLM.

**Trade-off:** Every tool call goes through Sentinel, adding a function call overhead. But allowlist/denylist checks are microseconds, and Haiku calls (~$0.001 each) only trigger for ambiguous cases. This is much cheaper than recovering from a destructive action.

---

### D25: Graduated retry strategy

**Context:** Design review noted that flat retry up to `max_retries: 10` wastes budget on fundamentally unimplementable specs. 10 retries at Sonnet-tier could cost $50-100 with no progressive response.

**Decision:** Implement graduated retry with escalating interventions:

| Retry | Action |
|---|---|
| 1-2 | Normal retry with feedback from Quality Gate |
| 3 | Bump Worker model tier (Haiku → Sonnet → Opus) |
| 5 | Alert Pasha for spec review |
| 7 | Architect re-decomposes the spec |
| 10 | STUCK |

**Why:** Progressive response catches different failure modes at appropriate cost. Model bumping solves capability issues cheaply. Pasha review catches spec ambiguity. Re-decomposition handles over-scoped specs. Each threshold is a circuit breaker.

**Trade-off:** More complex retry logic (~50 lines vs ~10). But prevents the worst case: spending $100 on a spec that needed re-decomposition at retry 3.

---

### D26: Retrospective always requires human approval

**Context:** Design review asked when "initially" ends for Retrospective proposals requiring human approval. Auto-approval risks silent system degradation (e.g., Retrospective learns "be lenient on tests" from rejection patterns).

**Decision:** All Retrospective proposals require human approval. Always. No auto-approve, no graduation to autonomous changes. Learnings.md remains direct-write (append-only, low-risk observations). But any change to prompts, criteria, or process rules requires Sultan approval via EA.

**Why:** The cost of human review is one Telegram message per proposal. The cost of a bad auto-approved prompt change is cascading quality degradation across all future specs. The asymmetry strongly favors mandatory approval.

---

### D27: LiteLLM as library, not proxy

**Context:** Original design specified LiteLLM in proxy mode (Docker container). Design review noted Vizier is 100% Python — running a separate Docker proxy adds infrastructure, latency, and complexity for no benefit.

**Decision:** Use `litellm.completion()` as a Python library call. No Docker container. No network hop.

**Why:** Proxy mode is useful when multiple non-Python services need LLM access. Vizier is a single Python application. Library mode gives the same functionality (model routing, cost tracking, tier aliases) without the operational overhead.

**Reconsider when:** Vizier adds non-Python components that need LLM access, or when running multiple Vizier instances that should share a cost budget.

---

### D28: Structured logging from Phase 1

**Context:** Design review noted no observability story — no logging, metrics, tracing, or cost tracking. For a system that runs autonomously and burns API budget, this is unacceptable.

**Decision:** Every agent invocation produces a structured log entry:

```json
{
  "timestamp": "2026-02-15T10:05:00Z",
  "agent": "worker",
  "spec_id": "001-auth/002-jwt",
  "model": "sonnet",
  "tokens_in": 4200,
  "tokens_out": 1800,
  "duration_ms": 12500,
  "cost_usd": 0.042,
  "result": "REVIEW",
  "project": "project-alpha"
}
```

Log destination: append to `reports/<project>/agent-log.jsonl` (per-project, EA-readable). EA includes cost summaries in morning briefings.

**Why:** Trivial to implement (~20 lines wrapping LiteLLM calls). Invaluable for debugging, cost tracking, and Retrospective analysis. LiteLLM already provides token counts and cost estimates.

---

### D29: Completion signal, criteria versioning, graceful shutdown

**Context:** Design review identified three smaller issues.

**Decision (completion signal):** Remove `<promise>DONE</promise>` magic string. Worker completion is implicit: Worker exits cleanly → spec transitions to REVIEW. If Worker exits with an error or writes feedback, spec stays IN_PROGRESS or gets feedback file.

**Why:** LLMs can hallucinate the signal early. Implicit completion (clean exit = done) is more reliable and doesn't depend on the LLM outputting a specific string.

**Decision (criteria versioning):** When Architect creates a spec, `@criteria/` references are resolved and snapshotted into the spec file at creation time. Quality Gate evaluates against the snapshotted criteria, not the current plugin library version.

**Why:** If `@criteria/tests_pass` changes between spec creation and quality gate evaluation, the Worker implemented against the old criteria but gets judged by the new ones. Snapshotting prevents this version mismatch.

**Decision (graceful shutdown):** Add INTERRUPTED state to the spec lifecycle. When daemon stops, any IN_PROGRESS specs transition to INTERRUPTED. On restart, INTERRUPTED specs are treated as READY (re-queued, Worker gets fresh context).

**Why:** Without this, daemon restart leaves specs permanently IN_PROGRESS with no agent working on them. Reconciliation (D22) would eventually catch this, but an explicit state is cleaner.

---

### D30: Phase reordering — Sentinel to Phase 1, CLI entry point in Phase 2

**Context:** Design review noted Sentinel is bundled with EA in Phase 6, but it's a deterministic Python service that enforces tool-call permissions (D24) — foundational infrastructure, not an afterthought. Also, Phases 2-4 can't be tested end-to-end without a way to create specs (EA is Phase 6).

**Decision:**
- Move Sentinel (deterministic policy engine, allowlist/denylist/Haiku tool enforcement) from Phase 6 to Phase 1.
- Add a minimal CLI entry point in Phase 2 that creates DRAFT/READY specs manually, bypassing EA for testing.
- Phase 6 retains EA + Telegram + communication (Sentinel's LLM content scanner moves here since it depends on EA for approvals).

**Why:** Sentinel's tool-call enforcement (D24) must exist before Workers run in Phase 2. Building Workers without permission enforcement means testing against an unrealistic environment. The CLI entry point enables end-to-end testing of the inner loop (Phase 2) without waiting for EA (Phase 6).

---

### D20: Three-layer use of claude-code-python-template

**Context:** `claude-code-python-template` provides project scaffolding (uv monorepo, ruff/pyright/pytest), TDD methodology, 7 Claude Code quality-gate agents, an 11-step Phase Completion Checklist (PCC), and CI/CD setup. Vizier needs development infrastructure, will manage Python projects, and needs its own validation protocol for completed specs.

**Decision:** Use the template in three distinct layers:

**Layer 1 — Template for building Vizier (adopted)**
Use the template to scaffold Vizier's own monorepo, development methodology, and CI/CD. The template's 7 Claude Code agents serve as quality gates during Vizier's own development. CLAUDE.md customized for Vizier-specific conventions.

**Layer 2 — Template as a Vizier project type (adopted)**
The software plugin offers claude-code-python-template as a scaffolding option for Python projects that Vizier manages. The Architect knows the template's conventions; the Worker knows its toolchain; the Quality Gate validates against its standards.

**Layer 3 — Selective inspiration for Vizier's agents (partially adopted)**

Adopted:
- **PCC as Completion Protocol** — After any spec enters REVIEW, Quality Gate runs a structured multi-pass validation protocol inspired by the template's 11-step PCC. Adapted from interactive checklist to event-driven protocol.
- **Deterministic checks first** — Fast mechanical checks (lint, format, type check, secret scan) run before any LLM-based review. Fail fast, fail cheap.
- **Cumulative acceptance criteria** — Validate not just current spec criteria but relevant parent/sibling spec criteria that could be affected by the change.
- **Parallel validation** — Independent checks run concurrently where possible (e.g., lint + type check + format in parallel).

Not adopted:
- Template's agent architecture — Claude Code subagents (run in IDE session, use Claude Code tools) are fundamentally different from Vizier's agents (event-driven, filesystem-based, fresh-context, LiteLLM-backed).
- 1:1 mapping of template's 7 agents to Vizier roles — Vizier's Quality Gate subsumes code-quality-validator + test-coverage-validator + acceptance-criteria-validator + code-reviewer into a single structured protocol.
- Linear checklist model — Vizier uses state machines, not step-by-step interactive checklists.
- Template's implementation-tracker and docs-updater as separate concerns — in Vizier, the Pasha handles plan tracking and the Retrospective handles documentation of learnings.

**Why:** The template excels as development tooling (Layer 1) and as a project type offering (Layer 2). Its validation concepts (PCC, deterministic-first, cumulative criteria) are universally valuable and transfer cleanly to Vizier's architecture. Its agent implementation model doesn't transfer — Vizier's fresh-context, filesystem-based, event-driven design is fundamentally different and deliberately so (see D14).

**Trade-off:** Layer 1 means we depend on the template's CLAUDE.md conventions during development, which is a process dependency. But since we control both projects, this is manageable. Layer 3's selective adoption means we don't get the template's agents "for free" — we implement PCC natively in the Quality Gate. But this is the right cost: Vizier's Quality Gate needs to work for any domain (documents, finance), not just Claude Code sessions.

---

### D31: Component replacement evaluation — build vs. borrow

**Context:** Evaluated whether existing tools could replace any Vizier component, based on competitive landscape analysis (CrewAI, LangGraph, AutoGen, OpenAI Agents SDK, Claude Agent SDK, Temporal, Prefect, Qodo, CodeRabbit, Invariant, Lakera Guard, EvoAgentX).

**Decision:** No component replacements. Vizier's core value (EA + Plugin System + File Protocol) has no external equivalent. Proposed replacements either break core architectural principles or provide marginal benefit over the current design.

**Evaluated and rejected:**

| Component | Proposed replacement | Why rejected |
|---|---|---|
| Sentinel | Invariant/Snyk Guardrails + Lakera Guard | Sentinel's allowlist/denylist/Haiku model (D24) is simpler, more integrated, and purpose-built for Vizier's tool-call enforcement. Bolting on 2-3 external tools adds complexity. |
| Quality Gate | Qodo + CodeRabbit | PR-level tools for software only. Vizier's Quality Gate works across domains (docs, finance) via plugin system + PCC (D20). |
| Architect | LangGraph Deep Agents | Graph-driven orchestration — explicitly rejected in D14. Opposite of Vizier's event-driven model. |
| Orchestration | Temporal / Prefect | Would replace filesystem-as-message-bus — a core principle (D4). Reconciliation (D22) addresses the reliability concern without adding infrastructure. |

**Monitor for future consideration:**

| Tool | Potential use | When to revisit |
|---|---|---|
| Lakera Guard | Prompt injection detection on inbound Telegram messages | Phase 6 (EA) — could complement Sentinel's content scanner for untrusted inbound messages |
| EvoAgentX | Automatic prompt optimization for Retrospective | Phase 5+ — academic (EMNLP 2025), needs maturity. Could help Retrospective propose better prompt changes. |

**Already adopted (confirmed):** LiteLLM (library, D27), aiogram 3.x, watchdog + reconciliation (D22), Jinja2, Pydantic, uv, ruff, pyright, pytest.

**Why no framework adoption:** Every evaluated framework (8 total) assumes either LLM-driven or graph-driven orchestration. Vizier's event-driven, filesystem-based, code-driven orchestration is the product differentiator (D14). Adopting a framework means giving away the core design.

---

### D32: Calendar integration — dual provider (Google + Microsoft 365)

**Context:** Sultan uses personal Google account and company Microsoft 365 (algoenergy.cz, Outlook). Need calendar access for EA's meeting prep, deadline awareness, and scheduling.

**Decision:** Use both MCP servers: workspace-mcp for Google Calendar (personal), Microsoft 365 MCP Server for Outlook (company). EA reads from both and presents a unified calendar view. MCP protocol makes multi-provider clean — EA has two calendar tool sources.

**Why:** Real executive assistants check all their boss's calendars, not just one. Sultan's meetings span personal and company contexts. EA must see both to correlate commitments with calendar events accurately.

---

### D33: Cost budget enforcement — degrade + alert

**Context:** Vizier runs autonomously and burns real API budget. Structured logging (D28) tracks costs, but what happens when the budget is exceeded?

**Decision:** Three thresholds with escalating response:

| Threshold | Action |
|---|---|
| 80% of monthly budget | Alert Sultan via EA: "Budget at 80%. Projected to exceed by [date]." |
| 100% of monthly budget | Degrade all agents to cheapest available tier. Alert Sultan. |
| 120% of monthly budget | Pause non-critical work (only process STUCK escalations and Sultan-initiated tasks). Alert Sultan. |

Sultan can override any threshold via EA. Budget tracked in structured agent logs (D28), aggregated by EA.

**Why:** Alert-only means the Sultan might not see the message in time. Degrade + alert preserves system function at reduced quality while ensuring the human knows. Auto-pause at 120% prevents runaway costs from an overnight loop.

---

### D34: Testing strategy — mock litellm, no API credits in CI

**Context:** Vizier makes LLM calls via `litellm.completion()`. Tests need to verify agent behavior without burning API credits on every test run.

**Decision:** Mock `litellm.completion()` in all automated tests. Return canned responses that exercise the code paths being tested. No real LLM calls in CI, ever.

**Test layers:**
- **Unit tests**: Pure Python logic (file protocol, state machine, model router, Sentinel allowlist/denylist, plugin loader, reconciliation). No mocking needed — these don't touch LLM.
- **Agent tests**: Mock `litellm.completion()`, test that agent runtime correctly handles responses (spec transitions, file writes, git commits, feedback generation).
- **Sentinel Haiku tests**: Mock `litellm.completion()` for Haiku evaluator, test classification of safe/dangerous tool calls.
- **Integration tests**: Run full Worker → Quality Gate loop with mocked LLM. Verify spec lifecycle from READY → REVIEW → DONE/REJECTED.
- **Manual validation**: Real LLM calls during development only. Used to validate prompt quality, not code correctness.

**Why:** 90%+ of Vizier's code is pure Python that never touches an LLM. The remaining code calls `litellm.completion()` at a single point, trivially mockable. Prompt quality is a manual concern, not a CI concern.

---

### D35: Stub plugin for Phase 2 testing

**Context:** Phase 2 (Inner Loop) needs a plugin to test Worker and Quality Gate. The real software plugin isn't built until Phase 8. A stub plugin is needed.

**Decision:** Build a minimal `test-stub` plugin that exercises all base class features:

```python
class StubPlugin(BasePlugin):
    name = "test-stub"
    worker_class = StubWorker
    quality_gate_class = StubQualityGate
    default_model_tiers = {"worker": "haiku", "quality_gate": "haiku"}

class StubWorker(BaseWorker):
    allowed_tools = ["file_read", "file_write"]
    tool_restrictions = {}
    git_strategy = "commit_to_main"

    # Worker creates/modifies a simple text file per spec

class StubQualityGate(BaseQualityGate):
    automated_checks = [
        {"name": "file_exists", "command": "test -f {artifact}"}
    ]

    # Quality Gate checks that the artifact file exists and is non-empty
```

The stub plugin is minimal but complete: it has a Worker that writes files, a Quality Gate that checks files exist, prompt templates, and one criteria (`@criteria/file_exists`). This exercises the full Worker → Quality Gate → DONE/REJECTED flow without needing real code generation.

**Why:** A stub plugin that's too simple (no tools, no checks) doesn't test the real code paths. A stub that's too complex delays Phase 2. This design hits the sweet spot: exercises all base class methods while being trivial to implement.

---

### D19: Sentinel — deterministic security service with Haiku content scanner
**Context:** Agents that web search, fetch URLs, receive files, and modify CI pipelines need security guardrails. Options: full LLM agent, deterministic service, hybrid.
**Decision:** Sentinel is a deterministic Python service for 95% of operations (whitelists, regex secret scanning, permission enforcement, git operation classification). Spawns a Haiku-tier LLM call only for evaluating untrusted web content and inbound files from unknown sources.
**Why:** Security checks should be fast, deterministic, and cheap. LLM-based security would burn tokens on every operation. But novel threats (prompt injection in fetched content) need intelligence — Haiku is cheap enough for on-demand scanning.
**Dangerous operations requiring Sultan approval:** GitHub Actions changes, force push, branch delete, history rewrite, new dependencies. Sentinel blocks → EA asks Sultan → decision flows back.
**Lineage:** Directly inspired by EFM's MCP safety server (Tier 1/2/3 system), generalized to cover web access, file relay, and CI/CD.

---

### D36: Telegram long polling first, webhook later

**Context:** aiogram supports both long polling (simpler) and webhook (lower latency, more production-grade). Webhook requires HTTPS endpoint on Hetzner (domain + TLS cert). Long polling works immediately.

**Decision:** Start with long polling. Migrate to webhook when multi-channel or latency requirements justify the infrastructure.

**Why:** Long polling needs zero infrastructure beyond the running daemon. No domain name, no TLS certificate, no reverse proxy. For a single-user system (Sultan), the ~1-2 second latency difference is irrelevant. Webhook can be added later as a config option without architectural changes -- aiogram supports both modes with the same handler code.

**Reconsider when:** Latency becomes noticeable, or when adding webhook-dependent features (e.g., Telegram payment processing, inline mode).

---

### D37: asyncio daemon + subprocess per agent invocation

**Context:** The daemon needs to manage agent lifecycle (Worker, Quality Gate, Architect). Options: (A) all agents as asyncio tasks in one process, (B) subprocess per agent, (C) asyncio + ProcessPoolExecutor.

**Decision:** Daemon runs an asyncio event loop (for aiogram, watchdog, orchestration). Each agent invocation is launched as a **separate Python process** via `asyncio.create_subprocess_exec()`. Communication between daemon and agents is through the filesystem (already the design).

**Why:**
- **Crash isolation**: If a Worker process crashes, segfaults, or OOMs, the daemon is unaffected. With pure asyncio, a misbehaving agent could bring down the entire daemon (blocking event loop, memory leak, unhandled exception escaping TaskGroup).
- **Resource limits**: OS-level process boundaries enable per-agent memory limits and timeouts. The daemon kills hung agents after configurable timeout.
- **True fresh context**: A separate process is the most literal implementation of the Ralph Wiggum pattern -- literally a fresh Python interpreter with zero state from previous invocations.
- **No external deps**: `asyncio.create_subprocess_exec()` is stdlib. No Celery, no Redis, no task queue infrastructure.
- **Negligible overhead**: Python startup (~0.5s) is trivial compared to LLM API call duration (seconds to minutes).

**Concurrency limit:** `asyncio.Semaphore(max_concurrent_agents)` gates how many agent subprocesses run simultaneously.

**Trade-off:** Slightly more complex than pure asyncio (~100 lines vs ~50). But the isolation guarantee is worth it for an autonomous system that runs unattended.

---

### D38: Files only for queryable data (commitments, relationships, agent logs)

**Context:** EA maintains commitments, relationships, and agent logs. These need querying (overdue commitments, cost by project, contacts with open items). Options: YAML/JSONL files (current design), SQLite for queryable data, or decide later.

**Decision:** Keep files only. YAML for structured records (commitments, relationships). JSONL for append-only logs (agent invocations). No database.

**Why:** Vizier is a single-user system (one Sultan). The data volumes are small: dozens of commitments, dozens of relationships, thousands of agent log entries per month. Python can load and filter these in milliseconds. Files are git-trackable (EA data lives in its own git repo per ARCHITECTURE.md), human-readable, and debuggable. SQLite would add a dependency and break git-trackability for no performance benefit at this scale.

**Reconsider when:** Agent log analysis becomes slow (>10k entries), or commitment/relationship queries need joins or aggregations that are painful to express as Python list comprehensions.

---

### D39: Stub plugin as test fixture, not a real plugin package

**Context:** Phase 2 needs a minimal plugin (D35) to test Worker and Quality Gate. Options: (A) test fixture in `tests/fixtures/`, (B) real plugin in `plugins/test-stub/`, (C) inline classes in test files.

**Decision:** Place the stub plugin in `tests/fixtures/stub_plugin/` as a test fixture. Register it programmatically in tests (not via entry points).

**Why:** The stub plugin exists only for testing. Making it a real package with pyproject.toml and entry points adds maintenance burden and pollutes the plugin namespace. Test fixtures are the standard location for test-only code. Plugin discovery via entry points is tested separately (unit test for the discovery function with mock entry points). The stub plugin tests the base class interface, not the discovery mechanism.

**Trade-off:** Doesn't exercise the full entry-point discovery path in integration tests. Acceptable because entry-point discovery is a 10-line function with its own unit test.
