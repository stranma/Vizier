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
          Default 15s interval, compensates for Windows reliability
          Why: watchdog can miss events under load
        Atomic writes via os.replace D40
          Write-then-rename for all spec writes
          Why: prevents half-written files on crash
        Spec state-age monitoring
          Pasha checks time_in_state during reconciliation
          Why: detects silently stuck specs
        Alt rejected: polling loop - wasteful, burns tokens on idle checks
        Alt rejected: message queue Redis/NATS - unnecessary infrastructure
      Filesystem as message bus
        Why: zero infrastructure dependency
        Why: state survives restarts
        Why: every agent naturally has access
        Why: git-trackable history
        Alt rejected: Redis pub/sub - adds ops complexity for no benefit at this scale
    Agent Roles -- RESET D46, rigid agents deleted, rebuilding with tool use
      EA - Executive Assistant singleton
        Replaces Secretary - much broader scope
        Why: single human interface to everything
        Why: gatekeeper of human attention
        Monolithic and powerful - Claude Code pattern
          Why: Grand Vizier was the most capable person, not a receptionist
          Why: fresh LLM call per message, no accumulated state
          Why: internal modularity via handler functions, not agent split
          JIT prompt assembly D42
            Always-loaded core ~2500 tokens + conditional modules
            Deterministic classifier, zero routing cost
          Behavioral anchor: priorities.yaml
            Sultan-maintained, EA reads on every call
          MCP plugin discovery D43
            EA discovers per-project plugin tools at startup
            Quick queries bypass spec lifecycle
          Telegram slash commands
            /status /ask /checkin /focus /session /approve /budget /priorities
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
          Repeated action detection: 3+ identical tool calls -> escalate
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
      Plugin MCP exposure D43
        Plugins optionally expose tools via FastMCP
        Quick queries bypass spec lifecycle
        Why: simple queries dont need full spec round-trip
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
      Progressive autonomy D44
        Shadow -> Gated -> Supervised -> Autonomous
        Measurable graduation criteria per stage
        Sultan approval required for each transition
      Dead-man switch
        heartbeat.json updated every reconciliation cycle
        External monitor alerts if stale
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
      Observability - two layers
        Structured JSONL D28 for EA consumption
        Langfuse D45 for developer debugging
          Self-hosted, native LiteLLM callback
          Docker Compose alongside daemon
      VCR record-replay testing D41
        Extends litellm mock strategy
        VIZIER_VCR_MODE: record / replay / off
        Cassettes in tests/cassettes/
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
**Decision:** Fresh context per task for Workers. Pasha and EA maintain lightweight Python event loops (no LLM in the loop -- fresh LLM call per message/event).
**Why:** Long sessions accumulate stale context and hallucinated state. Fresh starts force agents to verify reality from disk.

### D3: Rules-based model routing, not a Scheduler agent
**Context:** Original proposal had a dedicated Scheduler agent deciding which model to use.
**Decision:** Replace with a 20-line rules-based router. Resolution order: spec complexity > project config > plugin default > framework default.
**Why:** Using an LLM to decide which LLM to call is wasteful meta-reasoning.

### D4: Filesystem as message bus, not Redis/NATS
**Context:** Agents need to communicate state changes (new spec, spec done, etc.).
**Decision:** Filesystem with watchdog-based event detection. No message queue.
**Why:** Zero infrastructure dependency. State survives restarts. Git-trackable. Every agent naturally has access. At single-server scale, filesystem watch is fast enough.

### D5: EA replaces Secretary -- three communication layers
**Context:** Originally had a "Secretary" that routed tasks. Evolved through: Secretary with two modes -> Secretary as EA -> EA with direct Pasha sessions.
**Decision:** Executive Assistant (EA) replaces Secretary. Three layers: (1) EA on Telegram for async/mobile (delegation, status, briefings, commitments), (2) Direct Pasha sessions for deep project discussions, (3) Autonomous operation with no human. EA is the gatekeeper of human attention.
**Why:** A CEO doesn't just delegate -- they need proactive briefings, commitment tracking, calendar awareness, and the ability to drop into deep working sessions when needed. A "Secretary" was too narrow.

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
**Why:** Deep creative/technical work can't be mediated through a routing layer. Like a CEO sitting down with a VP for a working session -- the EA steps back but stays aware.

### D13: Vizier as a personal AI operating system, not just coding
**Context:** Started as "autonomous coding system." Evolved as we recognized the same orchestration serves any knowledge work.
**Decision:** Vizier is a personal AI operating system for knowledge workers. EA = interface to everything. Project teams = autonomous agents for any domain. Plugin system = extensible to any structured work.
**Why:** The orchestration (Pasha -> Architect -> Worker -> Quality Gate) is domain-agnostic. The plugin system already supports non-code work. Adding EA's real-world awareness makes it a complete system for anyone who works with information.

### D14: Own thin runtime over Claude Agent SDK (or any framework)
**Context:** Evaluated 8 agent frameworks (Claude Agent SDK, LangGraph, CrewAI, AutoGen/Microsoft Agent Framework, Smolagents, OpenAI Agents SDK, Google ADK, Agno). Claude Agent SDK was the strongest candidate -- it provides built-in file ops, bash, search, editing, subagent spawning, and context compaction for free.
**Decision:** Build our own thin runtime (~1500 lines). Do not adopt any framework as foundation. Keep Claude Agent SDK as a future optional backend for the `software` plugin's Worker.
**Why:**
- **Orchestration mismatch**: Every framework assumes either LLM-driven orchestration (Claude SDK, CrewAI, OpenAI SDK) or graph-driven orchestration (LangGraph, Microsoft Agent Framework). Our event-driven, code-driven filesystem orchestration is the product differentiator -- adopting someone else's orchestration means giving it away.
- **Claude Agent SDK specifics**: It wraps the entire CLI binary as a subprocess (~55-73 MB). Each `query()` call has ~12s startup overhead (no daemon mode). Alpha status (v0.1.36, pre-1.0) with known issues: multi-agent OOM kills, lock file corruption, Windows initialization hangs. Anthropic-only -- breaks our LiteLLM multi-provider strategy.
- **Cost of independence**: ~500 lines of custom tool implementation (file ops + bash + search) is cheap insurance against depending on alpha software for the core product.
- **Re-evaluation trigger**: When Agent SDK reaches 1.0, adds daemon mode (eliminating 12s overhead), and fixes multi-agent stability, consider it as optional backend for `SoftwareCoder`. The plugin system supports this swap without changing orchestration code.
**Trade-off:** We implement tools ourselves (~500 lines) that the SDK provides for free. But we gain: full control, lower latency, multi-provider support, production stability, and no 55MB binary dependency.
**Alt rejected:** Claude Agent SDK as foundation -- LLM-driven loop, Anthropic-only, alpha stability.
**Alt rejected:** LangGraph -- graph-driven, stateful by design (opposite of fresh-context), heavy LangChain abstractions.
**Alt rejected:** CrewAI -- agents share context (opposite of fresh-context), moving toward paid platform.
**Alt rejected:** Smolagents -- minimal and fast, but no orchestration layer, code-agent paradigm doesn't match tool-restriction model. Worth reading for patterns.

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

**Gaps identified in Vizier that EFM has:** Pre-commit approval UI (human reviews diff before commit). Addressable by adding `requires_approval` flag to specs -- EA shows diff in Telegram, gates the commit.
**Gaps in EFM that Vizier covers:** Commitment tracking with deadlines, calendar integration, proactive briefings, cross-project visibility, meta-improvement (Retrospective), multi-project support, plugin extensibility.
**Why:** EFM's bot is a "single-threaded operations assistant" for one project. Vizier generalizes this into a multi-project autonomous work system while preserving all of EFM's operational capabilities.

### D16: Ottoman court naming -- Sultan, Vizier, Pasha, Sentinel
**Context:** System needed clear role names. "TeamCoder" was too narrow (coding only). "User" and "admin" are bland.
**Decision:** Adopt Ottoman court metaphor selectively. Human = Sultan. EA = Vizier. Per-project orchestrator = Pasha (replaces "Manager"). Security = Sentinel. The product itself = Vizier. Architect, Worker, Quality Gate, Retrospective keep functional names -- Ottoman equivalents (Kadi, Scribe, Nisanci) are too obscure.
**Why:** Sultan, Vizier, Pasha, and Sentinel are widely recognized words that create instant mental models. Pashas governed provinces (projects) autonomously but reported upward to the Vizier -- exactly the per-project orchestrator role. Names should clarify, not require a history lesson.

### D17: Git-only sync with file checkout/checkin for direct edits
**Context:** Need to sync project files between Sultan's machine and Vizier server. Options: git only, git + OneDrive/rclone, git + Syncthing.
**Decision:** Git-only. All agent edits go through git. When Sultan needs to edit files directly (e.g., Excel), EA manages a checkout/checkin flow: copy file to `checkout/` folder, Sultan edits, EA copies back and commits.
**Why:** Git provides atomic operations, history, and conflict resolution. Cloud sync (OneDrive, Syncthing) adds infrastructure, latency, and conflict issues. Since Sultan primarily interacts through agents (Telegram, CLI), git covers 95% of cases. The checkout/checkin pattern handles the remaining 5% (direct file editing) cleanly.
**Trade-off:** Binary files (Excel) don't diff well in git. Acceptable -- these files are edited infrequently and the checkout flow provides the safety net.

### D18: Permission model -- least privilege per role
**Context:** Need to define what each agent can read and write. Agents should not have unrestricted access.
**Decision:** Role-based permissions: EA reads everything but writes only to ea/ data and DRAFT specs. Pasha reads/writes own project only. Worker reads/writes only files listed in its spec. Sentinel reads all outbound requests and can block operations.
**Why:** Principle of least privilege. Workers that can read the whole filesystem are a security risk. Pashas that can modify other projects break isolation. EA needs broad read access to correlate across projects but doesn't need write access to source code.
**Key design:** EA to Pasha communication is through specs/ (EA writes DRAFT) and reports/ (Pasha writes status). No direct calls. Consistent with filesystem-as-bus.

### D21: EA stays monolithic and powerful -- rejected "god object" critique

**Context:** Design review raised concern that EA has 13+ responsibilities (routing, status, briefings, commitments, calendar, file relay, sessions, check-ins, cross-project coordination, direct Q&A, focus mode, proactive alerts) and violates the fresh-context principle by being "always-on." Proposed splitting EA into thin router + specialized handler agents.

**Decision:** Reject the critique. EA stays as a single, powerful Opus-tier agent. No architectural split.

**Why (three arguments):**

1. **Ottoman metaphor is correct.** The historical Grand Vizier wasn't a receptionist -- he was the most capable, most trusted person in the empire. He handled everything *because* he understood the full picture. Splitting the Vizier into router + specialists is like replacing the Grand Vizier with a helpdesk. That's the opposite of the metaphor's intent.

2. **Claude Code pattern.** Claude Code is a "god object" by software engineering definitions: it reads files, writes code, runs tests, does git, searches the web, creates PRs. And it works brilliantly because the user talks to ONE capable agent. EA should follow this pattern: one capable agent that handles anything the Sultan throws at it. Making it "dumb" by splitting would be like replacing Claude Code with a menu system.

3. **The anti-pattern doesn't apply.** Software god objects fail because they accumulate mutable state. EA doesn't -- each incoming message spawns a fresh LLM call with relevant state loaded from disk. The "always-on" part is a Python event loop (no LLM), not an LLM sitting in memory. Internal modularity (separate handler functions for delegation, status, check-in, file ops) provides testability without architectural splitting.

**Internal structure:** Python event loop (always-on, deterministic) receives messages. Each message triggers a fresh Opus-tier LLM call with only the relevant state loaded (commitments, status files, relationships, etc.). Handler functions are separate Python code units, testable in isolation, but orchestrated by a single agent prompt.

**EA scenarios validated:** 7 distinct usage scenarios confirmed this design -- morning briefing, delegation, deep sessions, proactive crisis management, file checkout/checkin, structured check-ins, cross-project coordination, and direct Q&A. All work naturally with a single powerful agent.

---

### D22: Filesystem reconciliation -- events as optimization, disk as truth

**Context:** Design review identified that watchdog can miss filesystem events (inotify overflow, crash during processing, no ordering guarantees, Windows falls back to polling). No acknowledgment or replay mechanism exists.

**Decision:** Add periodic reconciliation. On daemon start and periodically (configurable, default 15 seconds, recommended 10-30s), scan all spec files and rebuild/verify state from disk. Filesystem events are an optimization (instant notification), not the source of truth. If an event is missed, reconciliation catches it on the next cycle. On Windows, ReadDirectoryChangesW is less reliable than inotify -- shorter intervals compensate.

**Why:** This turns a fragile event-notification system into a robust state-reconciliation system. The fresh-context pattern already assumes agents read from disk -- reconciliation just ensures the Pasha's view of spec states is always consistent with reality.

**Trade-off:** Reconciliation adds a periodic scan (cheap -- just reading file metadata and frontmatter). Worst case latency for a missed event is one reconciliation cycle.

---

### D23: Workers get bounded read-only exploration

**Context:** Design review challenged "if Worker needs to explore, Architect failed" as too rigid. Workers encounter runtime errors, missing transitive dependencies, and undiscovered config files that the Architect couldn't predict.

**Decision:** Allow Workers bounded read-only exploration beyond the artifact list. Workers can read (but NOT write) any file in the project. They must log what files they read beyond the artifact list. Write access stays restricted to spec artifacts only.

**Why:** In practice, Architects are 90% right about artifacts. The remaining 10% (runtime import errors, config files, test fixtures) shouldn't require a full re-decomposition cycle (Worker exits, Pasha, Architect, new spec, Worker retries). Bounded read access handles the 80% of these edge cases cheaply.

**Constraints:** Workers still cannot write beyond the artifact list. Any file reads beyond the artifact list are logged for Retrospective analysis (if Workers consistently read files not in specs, it indicates Architect prompt needs improvement).

---

### D24: Permission enforcement via allowlist + denylist + Haiku

**Context:** Design review noted that regex-based tool restrictions are bypassable (simple patterns blocked but equivalent commands via indirect invocation pass). Permissions are aspirational, not enforced.

**Decision:** Replace regex-only tool restrictions with a three-tier enforcement model via Sentinel:

| Tier | Mechanism | Cost | Example |
|---|---|---|---|
| **Allowlist** | Deterministic pattern match | Zero | `read_file`, `write_file` to spec artifacts, `pytest`, `ruff` |
| **Denylist** | Deterministic pattern match | Zero | Destructive filesystem commands, `force push`, secret patterns |
| **Ambiguous** | Haiku evaluates intent | ~$0.001/call | Indirect command invocation, unfamiliar bash commands |

Sentinel intercepts every tool call. Allowlisted calls pass through instantly. Denylisted calls are blocked instantly. Anything else gets a Haiku evaluation of whether the call is safe given the agent's role and current spec.

**Why:** Haiku can understand that an indirect invocation of a destructive command is dangerous even though it doesn't match a string pattern. The allowlist ensures 90%+ of calls (common operations) have zero latency/cost overhead. Only unusual calls hit the LLM.

**Trade-off:** Every tool call goes through Sentinel, adding a function call overhead. But allowlist/denylist checks are microseconds, and Haiku calls (~$0.001 each) only trigger for ambiguous cases. This is much cheaper than recovering from a destructive action.

---

### D25: Graduated retry strategy

**Context:** Design review noted that flat retry up to `max_retries: 10` wastes budget on fundamentally unimplementable specs. 10 retries at Sonnet-tier could cost $50-100 with no progressive response.

**Decision:** Implement graduated retry with escalating interventions:

| Retry | Action |
|---|---|
| 1-2 | Normal retry with feedback from Quality Gate |
| 3 | Bump Worker model tier (Haiku to Sonnet to Opus) |
| 5 | Alert Pasha for spec review |
| 7 | Architect re-decomposes the spec |
| 10 | STUCK |

**Why:** Progressive response catches different failure modes at appropriate cost. Model bumping solves capability issues cheaply. Pasha review catches spec ambiguity. Re-decomposition handles over-scoped specs. Each threshold is a circuit breaker.

**Repeated action detection (BudgetMLAgent):** If a Worker performs an identical tool call 3+ consecutive times, escalate immediately to the next threshold. This catches stuck loops that the diverse-failure retry logic above misses -- a Worker retrying the same failing command is not making progress regardless of which retry count it's on.

**Trade-off:** More complex retry logic (~50 lines vs ~10). But prevents the worst case: spending $100 on a spec that needed re-decomposition at retry 3.

---

### D26: Retrospective always requires human approval

**Context:** Design review asked when "initially" ends for Retrospective proposals requiring human approval. Auto-approval risks silent system degradation (e.g., Retrospective learns "be lenient on tests" from rejection patterns).

**Decision:** All Retrospective proposals require human approval. Always. No auto-approve, no graduation to autonomous changes. Learnings.md remains direct-write (append-only, low-risk observations). But any change to prompts, criteria, or process rules requires Sultan approval via EA.

**Why:** The cost of human review is one Telegram message per proposal. The cost of a bad auto-approved prompt change is cascading quality degradation across all future specs. The asymmetry strongly favors mandatory approval.

---

### D27: LiteLLM as library, not proxy

**Context:** Original design specified LiteLLM in proxy mode (Docker container). Design review noted Vizier is 100% Python -- running a separate Docker proxy adds infrastructure, latency, and complexity for no benefit.

**Decision:** Use `litellm.completion()` as a Python library call. No Docker container. No network hop.

**Why:** Proxy mode is useful when multiple non-Python services need LLM access. Vizier is a single Python application. Library mode gives the same functionality (model routing, cost tracking, tier aliases) without the operational overhead.

**Reconsider when:** Vizier adds non-Python components that need LLM access, or when running multiple Vizier instances that should share a cost budget.

---

### D28: Structured logging from Phase 1

**Context:** Design review noted no observability story -- no logging, metrics, tracing, or cost tracking. For a system that runs autonomously and burns API budget, this is unacceptable.

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

**Decision (completion signal):** Remove magic completion string. Worker completion is implicit: Worker exits cleanly, spec transitions to REVIEW. If Worker exits with an error or writes feedback, spec stays IN_PROGRESS or gets feedback file.

**Why:** LLMs can hallucinate the signal early. Implicit completion (clean exit = done) is more reliable and doesn't depend on the LLM outputting a specific string.

**Decision (criteria versioning):** When Architect creates a spec, `@criteria/` references are resolved and snapshotted into the spec file at creation time. Quality Gate evaluates against the snapshotted criteria, not the current plugin library version.

**Why:** If `@criteria/tests_pass` changes between spec creation and quality gate evaluation, the Worker implemented against the old criteria but gets judged by the new ones. Snapshotting prevents this version mismatch.

**Decision (graceful shutdown):** Add INTERRUPTED state to the spec lifecycle. When daemon stops, any IN_PROGRESS specs transition to INTERRUPTED. On restart, INTERRUPTED specs are treated as READY (re-queued, Worker gets fresh context).

**Why:** Without this, daemon restart leaves specs permanently IN_PROGRESS with no agent working on them. Reconciliation (D22) would eventually catch this, but an explicit state is cleaner.

---

### D30: Phase reordering -- Sentinel to Phase 1, CLI entry point in Phase 2

**Context:** Design review noted Sentinel is bundled with EA in Phase 6, but it's a deterministic Python service that enforces tool-call permissions (D24) -- foundational infrastructure, not an afterthought. Also, Phases 2-4 can't be tested end-to-end without a way to create specs (EA is Phase 6).

**Decision:**
- Move Sentinel (deterministic policy engine, allowlist/denylist/Haiku tool enforcement) from Phase 6 to Phase 1.
- Add a minimal CLI entry point in Phase 2 that creates DRAFT/READY specs manually, bypassing EA for testing.
- Phase 6 retains EA + Telegram + communication (Sentinel's LLM content scanner moves here since it depends on EA for approvals).

**Why:** Sentinel's tool-call enforcement (D24) must exist before Workers run in Phase 2. Building Workers without permission enforcement means testing against an unrealistic environment. The CLI entry point enables end-to-end testing of the inner loop (Phase 2) without waiting for EA (Phase 6).

---

### D20: Three-layer use of claude-code-python-template

**Context:** `claude-code-python-template` provides project scaffolding (uv monorepo, ruff/pyright/pytest), TDD methodology, 7 Claude Code quality-gate agents, an 11-step Phase Completion Checklist (PCC), and CI/CD setup. Vizier needs development infrastructure, will manage Python projects, and needs its own validation protocol for completed specs.

**Decision:** Use the template in three distinct layers:

**Layer 1 -- Template for building Vizier (adopted)**
Use the template to scaffold Vizier's own monorepo, development methodology, and CI/CD. The template's 7 Claude Code agents serve as quality gates during Vizier's own development. CLAUDE.md customized for Vizier-specific conventions.

**Layer 2 -- Template as a Vizier project type (adopted)**
The software plugin offers claude-code-python-template as a scaffolding option for Python projects that Vizier manages. The Architect knows the template's conventions; the Worker knows its toolchain; the Quality Gate validates against its standards.

**Layer 3 -- Selective inspiration for Vizier's agents (partially adopted)**

Adopted:
- **PCC as Completion Protocol** -- After any spec enters REVIEW, Quality Gate runs a structured multi-pass validation protocol inspired by the template's 11-step PCC. Adapted from interactive checklist to event-driven protocol.
- **Deterministic checks first** -- Fast mechanical checks (lint, format, type check, secret scan) run before any LLM-based review. Fail fast, fail cheap.
- **Cumulative acceptance criteria** -- Validate not just current spec criteria but relevant parent/sibling spec criteria that could be affected by the change.
- **Parallel validation** -- Independent checks run concurrently where possible (e.g., lint + type check + format in parallel).

Not adopted:
- Template's agent architecture -- Claude Code subagents (run in IDE session, use Claude Code tools) are fundamentally different from Vizier's agents (event-driven, filesystem-based, fresh-context, LiteLLM-backed).
- 1:1 mapping of template's 7 agents to Vizier roles -- Vizier's Quality Gate subsumes code-quality-validator + test-coverage-validator + acceptance-criteria-validator + code-reviewer into a single structured protocol.
- Linear checklist model -- Vizier uses state machines, not step-by-step interactive checklists.
- Template's implementation-tracker and docs-updater as separate concerns -- in Vizier, the Pasha handles plan tracking and the Retrospective handles documentation of learnings.

**Why:** The template excels as development tooling (Layer 1) and as a project type offering (Layer 2). Its validation concepts (PCC, deterministic-first, cumulative criteria) are universally valuable and transfer cleanly to Vizier's architecture. Its agent implementation model doesn't transfer -- Vizier's fresh-context, filesystem-based, event-driven design is fundamentally different and deliberately so (see D14).

**Trade-off:** Layer 1 means we depend on the template's CLAUDE.md conventions during development, which is a process dependency. But since we control both projects, this is manageable. Layer 3's selective adoption means we don't get the template's agents "for free" -- we implement PCC natively in the Quality Gate. But this is the right cost: Vizier's Quality Gate needs to work for any domain (documents, finance), not just Claude Code sessions.

---

### D31: Component replacement evaluation -- build vs. borrow

**Context:** Evaluated whether existing tools could replace any Vizier component, based on competitive landscape analysis (CrewAI, LangGraph, AutoGen, OpenAI Agents SDK, Claude Agent SDK, Temporal, Prefect, Qodo, CodeRabbit, Invariant, Lakera Guard, EvoAgentX).

**Decision:** No component replacements. Vizier's core value (EA + Plugin System + File Protocol) has no external equivalent. Proposed replacements either break core architectural principles or provide marginal benefit over the current design.

**Evaluated and rejected:**

| Component | Proposed replacement | Why rejected |
|---|---|---|
| Sentinel | Invariant/Snyk Guardrails + Lakera Guard | Sentinel's allowlist/denylist/Haiku model (D24) is simpler, more integrated, and purpose-built for Vizier's tool-call enforcement. Bolting on 2-3 external tools adds complexity. |
| Quality Gate | Qodo + CodeRabbit | PR-level tools for software only. Vizier's Quality Gate works across domains (docs, finance) via plugin system + PCC (D20). |
| Architect | LangGraph Deep Agents | Graph-driven orchestration -- explicitly rejected in D14. Opposite of Vizier's event-driven model. |
| Orchestration | Temporal / Prefect | Would replace filesystem-as-message-bus -- a core principle (D4). Reconciliation (D22) addresses the reliability concern without adding infrastructure. |

**Monitor for future consideration:**

| Tool | Potential use | When to revisit |
|---|---|---|
| Lakera Guard | Prompt injection detection on inbound Telegram messages | Phase 6 (EA) -- could complement Sentinel's content scanner for untrusted inbound messages |
| EvoAgentX | Automatic prompt optimization for Retrospective | Phase 5+ -- academic (EMNLP 2025), needs maturity. Could help Retrospective propose better prompt changes. |

**Already adopted (confirmed):** LiteLLM (library, D27), aiogram 3.x, watchdog + reconciliation (D22), Jinja2, Pydantic, uv, ruff, pyright, pytest.

**Why no framework adoption:** Every evaluated framework (8 total) assumes either LLM-driven or graph-driven orchestration. Vizier's event-driven, filesystem-based, code-driven orchestration is the product differentiator (D14). Adopting a framework means giving away the core design.

---

### D32: Calendar integration -- dual provider (Google + Microsoft 365)

**Context:** Sultan uses personal Google account and company Microsoft 365 (algoenergy.cz, Outlook). Need calendar access for EA's meeting prep, deadline awareness, and scheduling.

**Decision:** Use both MCP servers: workspace-mcp for Google Calendar (personal), Microsoft 365 MCP Server for Outlook (company). EA reads from both and presents a unified calendar view. MCP protocol makes multi-provider clean -- EA has two calendar tool sources.

**Why:** Real executive assistants check all their boss's calendars, not just one. Sultan's meetings span personal and company contexts. EA must see both to correlate commitments with calendar events accurately.

---

### D33: Cost budget enforcement -- degrade + alert

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

### D34: Testing strategy -- mock litellm, no API credits in CI

**Context:** Vizier makes LLM calls via `litellm.completion()`. Tests need to verify agent behavior without burning API credits on every test run.

**Decision:** Mock `litellm.completion()` in all automated tests. Return canned responses that exercise the code paths being tested. No real LLM calls in CI, ever.

**Test layers:**
- **Unit tests**: Pure Python logic (file protocol, state machine, model router, Sentinel allowlist/denylist, plugin loader, reconciliation). No mocking needed -- these don't touch LLM.
- **Agent tests**: Mock `litellm.completion()`, test that agent runtime correctly handles responses (spec transitions, file writes, git commits, feedback generation).
- **Sentinel Haiku tests**: Mock `litellm.completion()` for Haiku evaluator, test classification of safe/dangerous tool calls.
- **Integration tests**: Run full Worker to Quality Gate loop with mocked LLM. Verify spec lifecycle from READY to REVIEW to DONE/REJECTED.
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

The stub plugin is minimal but complete: it has a Worker that writes files, a Quality Gate that checks files exist, prompt templates, and one criteria (`@criteria/file_exists`). This exercises the full Worker to Quality Gate to DONE/REJECTED flow without needing real code generation.

**Why:** A stub plugin that's too simple (no tools, no checks) doesn't test the real code paths. A stub that's too complex delays Phase 2. This design hits the sweet spot: exercises all base class methods while being trivial to implement.

---

### D19: Sentinel -- deterministic security service with Haiku content scanner
**Context:** Agents that web search, fetch URLs, receive files, and modify CI pipelines need security guardrails. Options: full LLM agent, deterministic service, hybrid.
**Decision:** Sentinel is a deterministic Python service for 95% of operations (whitelists, regex secret scanning, permission enforcement, git operation classification). Spawns a Haiku-tier LLM call only for evaluating untrusted web content and inbound files from unknown sources.
**Why:** Security checks should be fast, deterministic, and cheap. LLM-based security would burn tokens on every operation. But novel threats (prompt injection in fetched content) need intelligence -- Haiku is cheap enough for on-demand scanning.
**Dangerous operations requiring Sultan approval:** GitHub Actions changes, force push, branch delete, history rewrite, new dependencies. Sentinel blocks, EA asks Sultan, decision flows back.
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

---

### D40: Atomic writes via os.replace()

**Context:** Spec files are written by multiple agents (Architect, Worker, Quality Gate, Pasha). A crash or power loss during `write_text()` can leave a half-written file on disk. Half-written frontmatter means the file is unparseable, and reconciliation cannot recover the spec state.

**Decision:** All spec file writes use write-then-rename: write to `<path>.tmp`, then `os.replace(tmp, path)`. `os.replace()` is atomic on both POSIX (rename syscall) and Windows (MoveFileEx with MOVEFILE_REPLACE_EXISTING).

**Why:** Atomic writes ensure that the spec file is always either the old version or the new version, never a partial write. The cost is trivial (one extra syscall per write). This is standard practice in database engines, text editors, and configuration managers.

**Trade-off:** A stale `.tmp` file may be left behind if a crash occurs between `write_text` and `os.replace`. This is harmless -- the next successful write overwrites it, and `.tmp` files are not read by any agent.

---

### D41: VCR/Record-Replay testing

**Context:** D34 mandates mocking `litellm.completion()` in all tests. As agent prompts evolve, maintaining canned mock responses becomes a maintenance burden. Record/replay (VCR-style) testing records real LLM responses once and replays them in CI, giving realistic test data without ongoing API costs.

**Decision:** Extend the litellm mock strategy into cassette-based record/replay. Controlled by `VIZIER_VCR_MODE` environment variable:

| Mode | Behavior |
|------|----------|
| `record` | Call real LLM, save request/response to cassette file |
| `replay` | Load cassette, assert request matches, return recorded response |
| `off` (default) | Standard mock behavior (existing tests unchanged) |

Cassettes stored in `tests/cassettes/`, committed to git. Each cassette is a JSON file keyed by request hash.

**Why:** VCR testing provides realistic LLM responses without ongoing API costs. When prompts change, re-record the affected cassettes (one-time cost). Extends D34 rather than replacing it -- existing mock-based tests remain the default.

**Trade-off:** Cassette files are large (full LLM responses). Acceptable because they're committed to git and only re-recorded when prompts change significantly.

---

### D42: JIT prompt assembly for EA

**Context:** The EA has 13+ responsibilities (D21). Loading the full prompt for every responsibility into every LLM call wastes context window and increases cost. But splitting EA into separate agents was rejected (D21) because it breaks the monolithic design.

**Decision:** Dynamic prompt composition: always-loaded core (~2,500 tokens) plus conditional modules loaded by a deterministic classifier.

**Always loaded (~2,500 tokens):**
- Court context + EA identity preamble
- `priorities.yaml` content
- Active commitments summary
- Project registry + Pasha communication protocol
- Delegation + status instructions

**JIT modules (loaded by deterministic classifier):**

| Module | Tokens | Trigger |
|--------|--------|---------|
| Check-in protocol | ~1,000 | `/checkin` command |
| File checkout/checkin | ~800 | File-related keywords |
| Calendar integration | ~600 | Calendar/meeting keywords |
| Cross-project coordination | ~500 | Multi-project references |
| Budget enforcement | ~400 | Budget/cost keywords |
| Morning briefing format | ~500 | Scheduled briefing trigger |
| Proactive behaviors | ~500 | Scheduled proactive check |

**Classifier:** Deterministic (regex + keyword + slash command detection), not LLM-based. Zero routing cost. Consistent with D21 (internal modularity, not architectural splitting).

**Why:** A typical EA message needs ~3,000-4,000 tokens of prompt instead of ~7,000+. At Opus-tier pricing, this saves ~40% on input tokens per EA call. The classifier is trivially testable (pure Python regex/keyword matching).

**Trade-off:** Classifier must be maintained as EA capabilities grow. Misclassification means a module isn't loaded and the EA may give a less informed response. Mitigated by keeping the always-loaded core comprehensive enough to handle common cases.

---

### D43: Plugin MCP exposure

**Context:** Plugins define domain-specific capabilities (tools, validation, code generation). Currently, using plugin capabilities requires the full spec lifecycle (DRAFT -> READY -> Worker -> REVIEW -> DONE). Some queries are simple enough that routing through the spec lifecycle is overhead ("run the tests for this file", "check the lint status").

**Decision:** Plugins optionally expose capabilities as MCP tools via FastMCP (already in TECH_STACK.md). EA discovers per-project plugin MCP tools at startup. Quick queries that match exposed tools bypass the spec lifecycle.

**Example:**

```python
class SoftwarePlugin(BasePlugin):
    def get_mcp_tools(self) -> list[MCPTool]:
        return [
            MCPTool(name="run_tests", description="Run project tests", handler=self._run_tests),
            MCPTool(name="lint_check", description="Check lint status", handler=self._lint_check),
        ]
```

EA can invoke `run_tests` directly when Sultan asks "are the tests passing?" without creating a spec.

**Why:** FastMCP is already in the stack. Plugin MCP exposure is optional (plugins that don't expose tools work exactly as before). This addresses the "simple query overhead" problem without breaking the spec lifecycle for complex work.

**Trade-off:** Plugins now have two interfaces (spec-based for complex work, MCP for quick queries). Acceptable because the MCP interface is optional and read-only by convention.

---

### D44: Progressive autonomy rollout

**Context:** Deploying a fully autonomous agent system from day one is risky. Production agent systems (Shopify Sidekick, claude-chief-of-staff) use staged rollouts where autonomy increases as trust is established.

**Decision:** Four stages with explicit graduation criteria:

| Stage | Name | Behavior | Graduation Criteria |
|-------|------|----------|---------------------|
| 1 | Shadow | EA proposes actions, Sultan approves all | 50+ correct proposals, <5% override rate |
| 2 | Gated | Per-spec Sultan approval before Worker starts | 20+ specs completed without rejection |
| 3 | Supervised | Autonomous execution, EA surfaces all completions | 50+ specs, <10% rejection rate, cost within budget |
| 4 | Autonomous | EA filters what to surface, full autonomy | Sultan explicitly approves transition |

**Configuration:**

```yaml
# /opt/vizier/config.yaml
autonomy:
  stage: 2  # gated
  auto_approve_plugins: []  # empty = all need approval
  stage_history:
    - stage: 1
      entered: 2026-03-01
      graduated: 2026-03-15
      reason: "50 proposals, 2% override rate"
```

Each stage transition requires Sultan approval. Stage history is logged for auditability.

**Why:** Progressive autonomy reduces risk while building trust. The Sultan can see exactly what the system would do (Stage 1) before letting it act. Each stage has measurable graduation criteria, not subjective "feels ready."

**Trade-off:** Slower initial deployment. The system is less useful in Stage 1-2 because it requires more human interaction. But the cost of a bad autonomous action (wrong code committed, wrong message sent) is much higher than the cost of a few weeks of supervised operation.

---

### D45: Langfuse observability

**Context:** D28 provides structured JSONL logging for EA consumption (cost tracking, morning briefings). But developers debugging agent behavior need trace-level visibility: which prompt was sent, what the LLM returned, how long each step took, where failures occurred. JSONL logs are insufficient for this -- they capture outcomes, not process.

**Decision:** Self-hosted Langfuse for agent tracing. Native LiteLLM callback integration (LiteLLM has built-in Langfuse support). Docker Compose deployment alongside the Vizier daemon.

**Two complementary observability layers:**

| Layer | Tool | Audience | Purpose |
|-------|------|----------|---------|
| Operational | Structured JSONL (D28) | EA, Sultan | Cost tracking, status summaries, morning briefings |
| Developer | Langfuse | Developer/Sultan | Prompt debugging, trace analysis, latency profiling |

**Integration:** LiteLLM's `success_callback` and `failure_callback` send trace data to Langfuse automatically. No changes to agent code -- the callback is configured once in the LiteLLM setup.

```python
import litellm
litellm.success_callback = ["langfuse"]
litellm.failure_callback = ["langfuse"]
```

**Why:** Langfuse is open-source, self-hostable (no data leaves the server), and has native LiteLLM integration. The setup is ~5 lines of Python + a Docker Compose service. It provides prompt versioning, cost breakdown per trace, and latency analysis that JSONL logs cannot.

**Trade-off:** Adds a Docker Compose dependency (Langfuse server + PostgreSQL). Acceptable for a production deployment. Langfuse is optional -- the system works without it (JSONL logs are the primary layer).

---

### D46: Agent System Reset -- delete rigid agents, rebuild with tool use

**Context:** The first-generation agent system (Phases 1f, 2-6, 8-10) followed a rigid prompt-in/response-out pattern: agents received a single prompt, returned a single response, and were parsed for structured output. This prevented tool use, supervisor interaction, partial progress, and long-horizon reasoning. The system needed to be rebuilt from scratch with Claude's native tool use capabilities.

**Decision:** Delete the entire agent layer (BaseAgent, AgentRunner, all *Runtime classes, Pasha orchestrator, lifecycle management, plugin implementations). Keep all infrastructure (models, file protocol, LLM factory, secrets, sentinel, watcher, tools, plugin framework, deployment). Rebuild agents in a new iteration with tool-using, interactive patterns.

**What was deleted:**
- Agent base classes and subprocess runner (agent/, agent_runner/)
- All agent runtimes (architect/, worker/, quality_gate/, scout/, retrospective/, ea/)
- Orchestration (pasha/, lifecycle/, logging/)
- Plugin interfaces for rigid agents (BaseWorker, BaseQualityGate)
- Plugin implementations (SoftwarePlugin, DocumentsPlugin)
- Daemon process orchestration (VizierDaemon, Heartbeat)
- 565 tests covering deleted code

**What was kept (infrastructure):**
- Models, file protocol, state manager, criteria
- LLM factory, model router
- Secrets (Azure, EnvFile, Composite)
- Sentinel (policy engine, content scanner)
- Watcher (filesystem monitoring, reconciler)
- Tools (ToolExecutor, secret_check)
- Plugin framework (BasePlugin, discovery, templates, criteria_loader, tool_registry)
- Daemon config, health check, Telegram transport
- CLI, deployment, CI/CD

**Why delete rather than refactor:**
- The rigid pattern was baked into every agent: BaseAgent forced a single prompt/response cycle, AgentRunner was a subprocess harness for this pattern, all runtimes parsed LLM output as text. Converting to tool use would mean rewriting every file anyway.
- Clean deletion makes it explicit that the new agents are a new design, not a patch on the old one.
- Infrastructure is orthogonal to agent architecture -- it works unchanged with any agent pattern.

**Why now:**
- Before investing in new features (LLM-first EA, interactive agents), the old code needed to be removed to avoid confusion about what's active vs. deprecated.
- The infrastructure foundation (409 passing tests, 0 lint/pyright errors) provides a stable base for the rebuild.

**Trade-off:** Temporary loss of all agent capabilities (daemon start disabled, no plugin implementations). Acceptable because the old agents were not deployed in production and the infrastructure remains fully tested and operational.

**Supersedes:** D14 (own thin runtime) is partially obsolete -- the new agents will use Claude's tool use natively rather than a custom prompt-in/response-out runtime. D35 (stub plugin) and D39 (stub as fixture) are obsolete -- the StubPlugin was simplified to test only BasePlugin without BaseWorker/BaseQualityGate.

---

### D47: Anthropic Python SDK with tool_use as agent foundation

**Context:** After the Agent System Reset (D46), agents need to be rebuilt with tool use. Two options: (A) Claude Agent SDK (wraps CLI as subprocess), (B) Anthropic Python SDK (direct API with tool_use).

**Decision:** Use the Anthropic Python SDK directly. Each agent is a tool_use loop calling `client.messages.create(tools=...)`. No Claude Agent SDK.

**Why:**
- Direct API calls -- no subprocess overhead, no ~12s startup, no 55MB binary
- Full control over the agent loop: Sentinel PreToolUse hooks, budget enforcement, structured logging, Golden Trace
- Stable, production-ready package (not pre-1.0 alpha)
- Windows-friendly (no CLI binary initialization issues)
- Custom tools needed (spec CRUD, delegation, escalation) -- Agent SDK built-in tools don't cover our use cases
- Claude-only simplification: multi-provider (D27/litellm) adds complexity without current benefit

**Supersedes:** D14 (own thin runtime -- now uses Anthropic SDK directly), D27 (litellm multi-provider -- now Claude-only).

---

### D48: Scout Feedback Loop -- Architect can request more research

**Context:** Scout is a one-shot bottleneck. If Scout hallucinates a wrong library or declares "no research needed" for a complex task, Architect works from poisoned data.

**Decision:** Architect gets a `request_more_research(spec_id, questions)` tool. This transitions the spec back to DRAFT with research questions attached, triggering a second Scout pass. Scout's output includes confidence markers; Architect evaluates them before proceeding.

**Why:** One-shot research is fragile. The feedback loop is cheap (one extra Scout invocation) and prevents expensive failures downstream.

---

### D49: QG Model Tier Escalation -- Opus for HIGH complexity

**Context:** Sonnet-Worker and Sonnet-QG share the same model capabilities. If Worker makes a subtle logic error, QG with the same "brain" has a high probability of missing it.

**Decision:** Two-pronged fix: (1) QG must run real tests -- mandatory `run_tests` before any LLM pass. (2) For HIGH complexity specs, QG escalates to Opus tier for semantic/logic passes (3-5). Mechanical passes (1-2) always use Sonnet.

**Why:** Real test output is ground truth. Opus-tier QG for complex specs provides a stronger "second opinion" on logic correctness.

---

### D50: Synchronous Supervisor Notification -- ping_supervisor

**Context:** Filesystem-mediated handoffs have 0-15s latency (reconciliation interval). A Worker blocked on a question shouldn't wait 15 seconds.

**Decision:** Add `ping_supervisor(spec_id, urgency, message)` tool. Writes the message file AND triggers immediate Pasha attention via watchdog filesystem event (~100ms). Three urgency levels: INFO (next reconciliation), QUESTION (immediate), BLOCKER (immediate + EA escalation).

**IPC mechanism:** Watchdog filesystem events. The file write IS the signal. No new IPC mechanism needed.

---

### D51: Loop Guardian -- behavioral checkpoint for agent spinning

**Context:** Sentinel gates individual tool calls but doesn't detect behavioral patterns like an agent looping on the same failing command.

**Decision:** Loop Guardian in AgentRuntime: (1) Deterministic: identical tool calls 3+ times triggers HALT. (2) LLM checkpoint every N calls (default 5): Haiku evaluates progress. Returns CONTINUE/WARN/HALT. Cost: ~$0.001 per checkpoint.

**Why:** Sentinel prevents dangerous actions. Loop Guardian prevents expensive non-progress. Complementary mechanisms.

---

### D52: Spec Dependency DAG -- depends_on field

**Context:** Architect creates sub-specs without expressing dependencies. Pasha might assign them in wrong order.

**Decision:** Extend spec frontmatter with `depends_on: list[str]`. Pasha only assigns Workers to specs whose prerequisites are DONE. Deterministic DAG validator (topological sort, no cycles, all IDs exist) runs before accepting PROPOSE_PLAN.

**Why:** Prevents wasted work and enables safe parallelism for independent sub-specs.

---

### D53: Integration Tests from Phase 14 -- not deferred to Phase 22

**Context:** Deferring integration tests to Phase 22 means building 8 phases before discovering structural problems.

**Decision:** Phase 14 includes mocked integration tests from day one (simulated handoffs, Sentinel blocking, Loop Guardian, budget enforcement). Phase 22 becomes real-LLM-only validation.

**Why:** Mocked integration tests are cheap and catch structural problems early.

---

### D54: Structured Message Schema -- typed Pydantic messages (Contract A)

**Context:** First-generation agents communicated via free text parsed with regex. Fragile and a primary cause of failures.

**Decision:** All inter-agent communication uses typed Pydantic models. Eight types: TASK_ASSIGNMENT, STATUS_UPDATE, REQUEST_CLARIFICATION, PROPOSE_PLAN, ESCALATION, QUALITY_VERDICT, RESEARCH_REPORT, PING. Serialized as JSON to spec directory.

**Why:** Pydantic validation at serialization time. JSON Schema auto-generated. No regex parsing.

---

### D55: Write-set via glob patterns -- replaces fixed artifact list

**Context:** Fixed artifact lists were too restrictive. Workers needed flexibility to create test files or update configs.

**Decision:** Plugin defines write-set as glob patterns (e.g., `src/**/*.py`, `tests/**/*.py`). Sentinel enforces via glob matching. Individual specs can further restrict.

**Why:** Categorical boundaries ("all Python in src/") give flexibility within limits. Zero-cost enforcement.

---

### D56: QG Structured Verdicts with evidence -- QUALITY_VERDICT

**Context:** First-generation QG produced text verdicts. No machine-verification that QG actually ran tests.

**Decision:** QUALITY_VERDICT is JSON with per-criterion PASS/FAIL + evidence_link (file path). Plugin declares mandatory evidence types. Pasha validates completeness deterministically.

**Why:** Evidence links make verdicts auditable. Mandatory evidence prevents LLM-only verdicts.

---

### D57: Golden Trace per spec -- trace.jsonl

**Context:** Multi-agent interactions are hard to debug.

**Decision:** Every tool call, message, and state transition appended to `specs/NNN/trace.jsonl`. Retrospective reads traces for pattern analysis.

**Why:** Per-spec timeline enables debugging, analysis, and improvement. JSONL is append-only and machine-readable.

---

### D58: Adaptive reconciliation interval

**Context:** Fixed 15s interval is suboptimal -- too slow when busy, wasteful when idle.

**Decision:** Interval adapts: active (5-10s), baseline (15s), idle (30s->60s->120s backoff). Watchdog events still fire instantly.

**Why:** Reduces I/O when idle, increases responsiveness when busy.

---

### D59: EA project capability summary

**Context:** EA needs informed routing decisions without being fully plugin-aware.

**Decision:** EA reads per-project capability summary from ProjectRegistry (plugin type, CI signals, definition of done, critical tools, autonomy stage).

**Why:** Provides routing context without coupling EA to plugin implementation.

### D60: Azure Key Vault as production secret store

**Context:** Daemon needs API keys (Anthropic, Telegram, etc.) securely stored. Hard-coded env vars are fragile and insecure in production.

**Decision:** Azure Key Vault (`https://vizier.vault.azure.net/`) as production secret store. `.env` fallback for local development. Secret store abstraction via `libs/core/vizier/core/secrets/`.

**Why:** Centralized rotation, audit trail, no secrets on disk in production. Azure fits existing deployment target.

### D61: Thread pool replaces subprocess-per-agent

**Context:** D37 specified asyncio daemon + subprocess per agent invocation. D47 changed agents to Anthropic SDK API calls (just HTTP requests). Subprocess isolation is now overkill.

**Decision:** Agents run in daemon thread pool via `asyncio.run_in_executor(None, runtime.run, task)`. Supersedes D37 subprocess model.

**Why:** D47 agents are synchronous Anthropic API calls -- subprocess isolation adds complexity without benefit. Each AgentRuntime still gets fresh message list (Ralph Wiggum pattern preserved). Anthropic client (httpx) is thread-safe. `max_concurrent_agents` config controls parallelism via semaphore.

### D62: Model ID update to current API versions

**Context:** Claude model IDs changed from dated versions (e.g., `claude-opus-4-20250514`) to current naming (e.g., `claude-opus-4-6`). ModelTierConfig had litellm "anthropic/" prefix baked in.

**Decision:** Update all factory defaults and ModelTierConfig to current Anthropic API model IDs: `claude-opus-4-6`, `claude-sonnet-4-6`, `claude-haiku-4-5-20251001`. Remove "anthropic/" prefix from ModelTierConfig since we use Anthropic SDK directly, not litellm.

**Why:** Keeps factory defaults aligned with current API. Removes litellm artifact from D27 era that no longer applies after D47.

---

### D63: OpenClaw Architectural Reset -- Vizier-on-OpenClaw

**Context:** Vizier phases 0-22 built a custom daemon (VizierDaemon), transport layer (aiogram/Telegram), agent runtime (Anthropic SDK tool loop), and orchestration infrastructure. OpenClaw is an open-source gateway that provides all of this plus multi-channel messaging (Telegram, WhatsApp, Discord, iMessage, Web UI, mobile apps), session management, tool infrastructure, and memory -- battle-tested and maintained by a dedicated team.

**Decision:** Rebuild Vizier on top of OpenClaw. Replace the custom daemon, transport, and agent runtime with OpenClaw's equivalents. Preserve Vizier's domain intelligence (spec lifecycle, agent orchestration, quality gates, Sentinel security, DAG scheduling, plugin extensibility) as a FastMCP server that OpenClaw agents call via tool use.

**What's replaced by OpenClaw:**
- VizierDaemon (asyncio event loop, subprocess/thread management)
- TelegramTransport (aiogram long polling)
- AgentRuntime (Anthropic SDK tool loop, Sentinel hook, Loop Guardian, Golden Trace)
- Agent lifecycle management (spawn, timeout, crash detection)
- Conversation history (ConversationLog, ConversationTurn)
- Health check server
- CLI (vizier init, register, start, status)

**What's preserved as MCP server:**
- Spec state machine and lifecycle (DRAFT -> SCOUTED -> DECOMPOSED -> READY -> ... -> DONE)
- Sentinel policy engine (allowlist/denylist/Haiku)
- DAG validator (topological sort, cycle detection)
- Evidence checker
- Write-set glob pattern matching
- Pydantic message models (Contract A)
- Budget tracking and enforcement
- Plugin concept (as MCP tool providers)

**Why:**
- OpenClaw's UX ecosystem (Web UI, mobile apps, browser tools, memory) vs building everything custom
- Massive reduction in custom code -- OpenClaw already built what Vizier's daemon does
- Vizier's unique value is domain intelligence (spec lifecycle, quality gates, Sentinel), not transport/session infrastructure
- Multi-channel support (Telegram + WhatsApp + Discord + Web) for free vs building each adapter

**Supersedes:** D10 (EA built into Vizier -- reversed, now runs on OpenClaw), D14 (own thin runtime -- reversed, OpenClaw is the runtime), D36 (Telegram first -- dropped, OpenClaw handles all channels), D37 (asyncio + subprocess -- dropped, OpenClaw manages sessions), D47 (Anthropic SDK direct -- modified, OpenClaw manages LLM calls for agents).

**Trade-off:** Dependency on OpenClaw as the runtime platform. If OpenClaw development stalls or diverges, Vizier would need to fork or rebuild. Mitigated by: MCP server is self-contained and portable (works with any MCP-compatible host), domain logic is not coupled to OpenClaw internals.

---

### D64: EA renamed to Vizier (the Grand Vizier)

**Context:** The main agent was called "EA" (Executive Assistant) in the old architecture, while "Vizier" was the product name. This was confusing -- the product and its main agent had different names, and "EA" undersold the agent's role.

**Decision:** Rename the main agent from "EA" to "Vizier" (the Grand Vizier). The product is still called Vizier. The main agent IS the Vizier.

**Why:** The historical Grand Vizier was the most capable person in the Ottoman empire (D21). The main agent should carry that name directly. "EA" was a compromise from when the product needed a separate identity from its agents. With OpenClaw as runtime, the agent IS the product's presence.

---

### D65: All inner agents are OpenClaw sub-sessions

**Context:** In the old architecture (D37, D47, D61), inner agents (Scout, Architect, Worker, QG, Retrospective) were either subprocess invocations or thread pool tasks calling the Anthropic SDK directly. This required custom lifecycle management, crash detection, timeout handling, and concurrency control.

**Decision:** All inner agents (including Pasha) are OpenClaw sub-sessions. Pasha is a persistent sub-session (long-lived, one per project). Scout, Architect, Worker, Quality Gate, and Retrospective are spawned sub-sessions (fresh context, exit after task).

**Why:** OpenClaw handles session lifecycle (spawn, timeout, cleanup), model selection, context management, and crash recovery. This eliminates ~500 lines of custom lifecycle code. The fresh-context principle (D2) is preserved -- spawned sub-sessions start with a clean slate.

---

### D66: Per-Pasha Sentinels via MCP tools

**Context:** In the old architecture, Sentinel was a daemon-level service with a PreToolUse hook in AgentRuntime. Each tool call went through a centralized Sentinel check.

**Decision:** Each project has a dedicated Sentinel configuration (write-set, allowlist, denylist, role permissions). Sentinel is enforced via MCP tools (`sentinel_check_write`, `sentinel_check_command`) that agents call before performing sensitive operations. The MCP server loads per-project policies from `projects/{project-id}/sentinel.yaml`.

**Why:** Per-project Sentinel allows different security policies per project (a docs project has different write-sets than a software project). MCP tool enforcement means agents explicitly check permissions, making the security model visible in agent prompts and tool calls rather than hidden in runtime hooks.

**Trade-off:** Agents must explicitly call Sentinel tools (vs automatic interception in old architecture). Mitigated by: SOUL.md prompts instruct agents to always check, and the MCP server can refuse operations that weren't pre-validated.

---

### D67: Sentinel Enforcement via OpenClaw Tool Policy

**Context:** D66 moved Sentinel to MCP tools, but agents could still bypass Sentinel by using OpenClaw's native bash/exec or web_fetch tools directly, since SOUL.md instructions are not enforceable.

**Decision:** Block native bash/exec and web_fetch via OpenClaw tool policy configuration. Force all agents through `run_command_checked` and `web_fetch_checked` MCP tools, which combine Sentinel validation with execution. In-scope file writes remain unrestricted (OpenClaw native file_write within project workspace). Out-of-scope writes still require `sentinel_check_write`.

**Why:** Tool policy enforcement is physical, not behavioral. An agent cannot bypass what is not available to it. This closes the "agents skip MCP calls" loophole without relying on prompt compliance.

**Trade-off:** Adds latency to every command/fetch (Sentinel check + execution in one round trip). Acceptable because the alternative (no enforcement) means Sentinel is advisory-only.

---

### D68: Worker Mandatory Self-Verification

**Context:** Workers previously transitioned to REVIEW immediately after implementation. Quality Gate's 5-pass protocol included mechanical checks (tests, lint, types) that should have been caught earlier, wasting a QG invocation on easily fixable issues.

**Decision:** Workers must run `verify_tests`, `verify_lint`, and `verify_types` before transitioning to REVIEW. All three must pass. QG protocol reduced from 5 passes to 4 (mechanical checks shifted to Worker). QG now focuses on semantic quality: hygiene, criteria evaluation, consistency, and verdict.

**Why:** Shifting mechanical verification to the Worker saves a full QG round-trip for every lint error or test failure. Workers fix their own messes. QG spends its (potentially Opus-tier) budget on semantic evaluation, not catching missing semicolons.

**Trade-off:** Workers take slightly longer per spec (running verification). Net positive because fewer rejection cycles.

---

### D69: Lightweight Research-on-Demand Tool

**Context:** The full Scout pipeline (spawn sub-session, web search, write research.md, transition spec) is heavyweight for simple "does library X support feature Y?" queries during Architect decomposition.

**Decision:** New `research_topic(query, depth)` MCP tool provides lightweight research. `depth="shallow"` does a quick web search and summary. `depth="deep"` does thorough multi-source investigation. The full Scout pipeline is preserved for standalone research tasks (DRAFT -> SCOUTED).

**Why:** Architect currently has to either guess or request a full Scout round-trip for simple lookups. `research_topic` gives Architect on-demand research without the overhead of spawning a sub-session and transitioning spec state.

**Trade-off:** Duplicates some Scout capability. Acceptable because the use cases are different: Scout produces comprehensive research reports; `research_topic` answers quick questions.

---

### D70: Learnings Injection via MCP

**Context:** Retrospective writes learnings to `learnings.md`, but no agent reads them systematically. Learnings accumulate without being actionable. All agents reading the entire file on startup (as originally envisioned) would waste context window.

**Decision:** New `get_relevant_learnings(project_id, spec_id?, agent_role?)` MCP tool returns keyword-matched learnings relevant to the current task. Pasha calls it before spawning any agent and includes results in the spawn context.

**Why:** Targeted injection is more effective than dumping the entire learnings file. Keyword matching keeps the implementation simple and deterministic. Makes Retrospective output directly actionable.

**Trade-off:** Keyword matching may miss relevant learnings with different phrasing. Mitigated by Retrospective SOUL.md guidance on writing learnings with clear keywords.

---

### D71: Dynamic Pipeline Selection by Pasha

**Context:** The spec lifecycle forces every spec through the full pipeline (Scout -> Architect -> Worker -> QG), even when simpler paths would suffice. A typo fix doesn't need research or decomposition.

**Decision:** No formal `task_type` field. Pasha decides dynamically which agents to spawn per spec based on complexity, description, and context. SOUL.md provides guidance for common shortcuts: bugfix (skip Scout/Architect), research-only (Scout only), documentation (lighter QG), complex feature (full pipeline). Existing state machine transitions already support these shortcuts (e.g., DRAFT -> READY bypasses Scout and Architect).

**Why:** A formal task_type taxonomy would need constant maintenance and wouldn't capture edge cases. Pasha (Opus-tier) can judge spec nature from context. The state machine already permits the shortcuts.

**Trade-off:** Less predictable pipeline per spec. Acceptable because Pasha's judgment is informed by learnings and the full spec context.

---

### D72: Agent Behavior Eval Suite

**Context:** SOUL.md prompts define agent behavior (Worker must call verify_tests before REVIEW, Pasha must inject learnings, etc.), but there's no way to test that these instructions produce the expected behavior patterns.

**Decision:** Formal eval suite in `tests/test_agent_evals.py` testing SOUL.md behavioral contracts via mocked scenarios. Tests validate expected tool call sequences (Worker calls run_command_checked, not native bash) and decision patterns (Pasha skips Scout for bugfixes). Uses mock MCP servers returning controlled responses.

**Why:** TDD for agent prompts. If a SOUL.md change breaks expected behavior (e.g., Worker stops calling verify_tests), the eval catches it. Mocked scenarios test behavioral patterns, not LLM output quality.

**Trade-off:** Evals are fragile if SOUL.md wording changes significantly. Mitigated by testing tool call patterns (stable) rather than exact response text (volatile).

---

### D73: Context Management for Persistent Agents

**Context:** Persistent agents (Vizier, Pasha) accumulate context over long sessions. Without active management, they degrade -- forgetting commitments, losing track of project state, making contradictory decisions.

**Decision:** Rely on OpenClaw's compaction, memory flush, and MEMORY.md. SOUL.md instructs Vizier and Pasha to proactively write critical state to memory (commitments, pending decisions, project priorities). Compaction settings configured for orchestrator sessions (80% trigger, memory flush on compact).

**Why:** OpenClaw already provides the infrastructure. SOUL.md guidance ensures agents use it proactively rather than reactively (writing to memory after important updates, not just when compaction triggers). No custom code needed.

**Trade-off:** Depends on agents following SOUL.md memory instructions. Mitigated by compaction + memory flush as a safety net.

---

### D74: Scope Guidance for Architect

**Context:** Analysis of claude-code-ultimate-guide (19K-line research) found that Workers perform best with focused, narrow tasks. Architect sub-specs that touch 10+ files often exceed Worker's ability to maintain coherence.

**Decision:** Soft guidance only. Architect SOUL.md recommends 1-3 files per sub-spec, suggests splitting at 5+. No enforcement mechanism. Trust the Architect (Opus-tier).

**Why:** Hard enforcement would be brittle (some logical changes genuinely touch many files). Soft guidance achieves 90% of the benefit. The Architect is Opus-tier and can exercise judgment about when to deviate.

**Trade-off:** No guarantee of compliance. Acceptable because strict limits would cause more harm (artificial splits) than good.

---

### D75: Architecture Simplification for v1

**Context:** After the OpenClaw reset (D63) and the D67-D74 improvements, the architecture specifies 35+ MCP tools, 11 tool groups, 7 agent roles -- but the codebase has 0 lines of working code. A combined overengineering review and independent product review identified 17 issues across 4 urgency levels. The over-specification blocks forward progress: there is too much to implement before anything works end-to-end. Two resets and 74 decisions without a single task processed is a pattern that must be broken.

**Decision:** Simplify to a v1 scope that enables the first working end-to-end loop (Sultan -> Vizier -> Pasha -> Worker -> QG -> Done). Specific changes:

1. **Tool surface reduced from 35+ to 15.** v1 keeps: spec_create, spec_read, spec_list, spec_transition, spec_update, spec_write_feedback, run_command_checked, sentinel_check_write, web_fetch_checked, orch_scan_specs, orch_check_ready, orch_assign_worker, orch_write_ping, dag_check_dependencies, project_get_config. Everything else deferred to v2.

2. **Agent roles reduced from 7 to 4.** v1: Vizier, Pasha, Worker, Quality Gate. Scout deferred (Worker uses web_search directly). Architect deferred (Pasha decomposes simple specs or delegates to Worker). Retrospective deferred (manual learnings for v1).

3. **Pasha trigger model: Vizier-initiated.** No polling loop. Vizier creates spec + sends message to Pasha. Pasha handles it and reports back when done. Eliminates expensive Opus-as-doorbell-watcher anti-pattern.

4. **One Voice policy.** Only the Grand Vizier communicates with the Sultan. No other agent messages the Sultan directly. All status updates, questions, and escalations flow through the chain: Worker -> Pasha -> Vizier -> Sultan.

5. **Graduated retry simplified from 5 levels to 2.** Retry 1-3: normal retry with QG feedback. Retry 4+: mark STUCK, escalate to Vizier. Model bumping, re-decomposition, and self-review are v2 refinements.

6. **Plugin framework deferred.** project_get_config tool returns hardcoded software project configuration (write-set patterns, criteria). No BasePlugin, no entry points, no plugin discovery.

7. **Budget system deferred entirely.** No usage data exists. OpenClaw tracks token usage natively. Add budget enforcement when real cost patterns emerge.

8. **Evidence system deferred.** Quality Gate writes markdown verdict via spec_write_feedback. No evidence_check, no evidence_write_verdict, no structured evidence links.

9. **DAG simplified.** 1 tool (dag_check_dependencies) instead of 3. dag_validate and dag_get_order are v2.

10. **Spec state machine simplified.** v1 removes SCOUTED and DECOMPOSED states (no Scout or Architect). DRAFT -> READY directly. Full state machine preserved for v2.

11. **File locking.** MCP server uses file locking on spec writes to prevent race conditions between concurrent agents. Atomic writes (D40) preserved.

12. **Sentinel Learning.** After a command is approved by Haiku 3 times for the same project, auto-promote to the project allowlist. Reduces repeated Haiku latency for common operations. Stored in sentinel_learned.yaml.

13. **Mandatory context read for Workers.** Worker SOUL.md requires reading the project's learnings.md file at task start. Simple file read, no MCP tool needed.

**Why:**
- The system must process its first task before optimizing for its hundredth
- Every deferred feature can be added incrementally after v1 works
- 15 tools is still a substantial server; the reduction is from "overwhelming" to "ambitious but achievable"
- Independent review flagged Pasha polling and notification overload as UX-breaking issues that must be solved pre-v1

**Supersedes/modifies:** D25 (graduated retry simplified from 5 to 2 levels), D68 (verification tools deferred -- Worker uses run_command_checked directly), D69 (research tool deferred -- Architect not in v1), D70 (learnings tool deferred -- Workers read file directly), D72 (agent evals deferred until agents exist), D74 (Architect scope guidance deferred with Architect).

**Preserved unchanged:** D67 (Sentinel enforcement via tool policy), D71 (dynamic pipeline selection -- simplified for v1 to Worker-only or escalate), D73 (context management for persistent agents).

**Trade-off:** v1 lacks the full pipeline (no Scout research, no Architect decomposition, no Retrospective learning loop). Pasha must handle decomposition directly or push it to Workers. This limits complexity of tasks v1 can handle. Acceptable because: getting the basic loop working validates the entire architecture, and v2 features can be added incrementally.

---

### D76: Crash Recovery & Zombie Detection

**Context:** If the MCP server restarts or a Worker session dies mid-task, specs can remain permanently IN_PROGRESS with no agent working on them. The existing INTERRUPTED state (D29) and atomic writes (D40) provide basic crash safety, but there is no specified startup recovery sequence, no zombie detection threshold, and no claim expiration mechanism.

**Decision:**

1. **MCP startup scan.** On server startup, scan all specs across all projects. Any spec in IN_PROGRESS with no live OpenClaw session transitions to INTERRUPTED. INTERRUPTED specs become READY on next Pasha activation.

2. **Claim timeout.** `orch_assign_worker` sets a `claimed_at` timestamp on the spec. If `time_in_state` exceeds `claim_timeout` (default 30 minutes, configurable per project via project config), Pasha treats the spec as a zombie on its next activation.

3. **Zombie recovery.** Pasha transitions zombie specs: IN_PROGRESS -> INTERRUPTED -> READY. This counts as a retry attempt (increments retry counter), preventing infinite zombie loops from escalating to STUCK at retry 4+.

4. **MCP server is stateless.** The server reads everything from disk on each tool call. No in-memory state survives restart. This was implied by D22 ("disk is truth") but is now explicitly required: the server must not cache spec state between requests.

**Modifies:** D29 (INTERRUPTED -- adds startup scan trigger), D22 (reconciliation -- adds explicit statelessness requirement).

**Why:** Without startup recovery, a server restart during active work silently orphans specs. Without claim timeout, a crashed Worker session leaves specs locked forever. Both are inevitable in production.

**Trade-off:** Zombie detection counts as a retry, so a spec that zombies 4 times will STUCK even if the problem was infrastructure, not the spec. Acceptable because: infrastructure instability causing 4 consecutive session deaths is itself a problem worth escalating.

---

### D77: Worker Escape Hatch (IMPOSSIBLE Signal)

**Context:** A Worker discovers a spec is fundamentally impossible -- not "hard to implement" but "logically contradictory," "references non-existent APIs," or "acceptance criteria conflict." The existing BLOCKER ping (orch_write_ping) doesn't distinguish "I need help" from "the spec itself is wrong." Without this distinction, the Worker enters a graduated retry loop that wastes tokens on an unfixable spec.

**Decision:**

1. **New ping urgency: IMPOSSIBLE.** Added alongside existing QUESTION and BLOCKER urgencies. Semantics: "the spec itself is defective, not the implementation."

2. **Worker protocol.** Worker calls `orch_write_ping(urgency=IMPOSSIBLE, message="[specific reason spec is wrong]")`. Worker does NOT continue implementation or enter retry -- it waits for Pasha's response.

3. **Pasha response.** On receiving an IMPOSSIBLE ping, Pasha transitions the spec to STUCK with `reason: spec_defect`. Escalates to Vizier with the Worker's reasoning. This does NOT count as a retry attempt (the spec is defective, not the implementation).

4. **Context bridge.** Worker MAY read any file in the project for context. This explicitly includes parent specs, sibling specs, and feedback from other specs. Reading is never a contamination risk; only writing is controlled by Sentinel. This was already implied by "bounded exploration" but is now explicitly stated.

**Why:** Without an escape hatch, a Worker stuck on a defective spec burns through 3 retries before hitting STUCK, wasting tokens and time. IMPOSSIBLE allows immediate escalation with preserved reasoning.

**Trade-off:** A Worker might incorrectly classify a difficult spec as IMPOSSIBLE. Acceptable because: Pasha (Opus-tier) evaluates the reasoning and can override (reassign the spec). False IMPOSSIBLE is cheaper than false retries.

---

### D78: Sentinel Error Contract

**Context:** `run_command_checked` currently conflates "Sentinel blocked it" with "command ran but failed." The return type documentation shows `{"allowed": bool, "output": str, "exit_code": int}` on success and denial reason on block, but doesn't clearly separate the three possible outcomes. Workers can't distinguish a policy denial from an environment failure (network error, missing binary, permission denied).

**Decision:**

1. **Three return shapes.** `run_command_checked` returns one of:
   - **Denied:** `{"allowed": false, "reason": str}` -- Sentinel policy blocked the command
   - **Succeeded:** `{"allowed": true, "exit_code": 0, "stdout": str, "stderr": str}` -- command ran and exited cleanly
   - **Failed:** `{"allowed": true, "exit_code": N, "stdout": str, "stderr": str}` -- command ran but exited with error

2. **Worker responsibility.** Worker interprets exit codes. Non-zero exit code means Worker decides: fix the cause and retry the command, try an alternative approach, or escalate via ping.

3. **Undo ownership.** Worker owns cleanup of its own damage. If a command succeeds but breaks the build (e.g., `npm install` adds a bad dependency), Worker must fix it before transitioning to REVIEW. Quality Gate validates the build is green but does NOT perform rollbacks.

4. **Environment failures.** Network errors, missing binaries, permission issues all surface as non-zero exit codes with stderr output. Worker handles them like any other command failure. The Sentinel is not "environment aware" -- it validates policy, not execution environment.

**Impact:** Update `run_command_checked` stub docstring to show three return shapes with `stdout` and `stderr` fields. Update `web_fetch_checked` similarly: `{"safe": false, "reason": str}` (injection detected) vs `{"safe": true, "content": str, "status_code": int}` (clean fetch) vs `{"safe": true, "content": str, "status_code": N, "error": str}` (fetch failed).

**Why:** Clear error semantics let Workers make intelligent decisions (retry on transient failure, escalate on policy denial, fix on build break). Ambiguous returns force Workers to guess.

**Trade-off:** Slightly more complex return type parsing for Workers. Acceptable because: Workers are LLM agents that handle structured JSON naturally.

---

### D79: Dependency Stall Prevention

**Context:** Spec C depends on specs A and B. A passes QG and reaches DONE. B is REJECTED by QG and enters retry. The current `orch_check_ready` returns `{"ready": false, "blocking": ["spec-B"]}` but doesn't indicate WHY B is blocking (is it just in progress, or has it failed?). If B eventually reaches STUCK, spec C is stalled indefinitely with no visibility into the root cause.

**Decision:**

1. **Terminal success required.** A dependency is "satisfied" only when the dependency spec reaches DONE. All other states (DRAFT, READY, IN_PROGRESS, REVIEW, REJECTED, STUCK, INTERRUPTED) count as "not satisfied."

2. **Stall detection.** If a blocking dependency is in a terminal failure state (STUCK) or otherwise unresolvable, `orch_check_ready` returns an enriched response: `{"ready": false, "blocking": ["spec-B"], "stall_reason": "dependency_stuck"}`. Without a stall, the response is just `{"ready": false, "blocking": ["spec-B"]}`.

3. **Pasha stall handling.** When Pasha sees `stall_reason` in the response, it evaluates the stalled dependency:
   - Dependency STUCK: escalate to Vizier with context ("spec C blocked because dependency B is STUCK")
   - Vizier decides: re-scope C, re-attempt B, or mark C as STUCK too

4. **No premature triggering.** `orch_assign_worker` must internally call `orch_check_ready` as a guard before assigning. Worker is never spawned for a spec with unsatisfied dependencies, even if Pasha explicitly requests assignment.

**Why:** Without stall detection, blocked specs accumulate silently. Pasha sees "not ready" but doesn't know if it's a temporary wait (dependency in progress) or a permanent stall (dependency STUCK). The `stall_reason` field makes this visible.

**Trade-off:** Adds complexity to `orch_check_ready` return type. Acceptable because: dependency stalls are a real production scenario and silent stalls waste resources (Pasha keeps checking a spec that can never become ready).

### D80: MVP Build Priority

**Context:** After D75 (simplification) and D76-D79 (stress-test fixes), an external architecture review (Gemini) argued we should cut further: from 15 tools to ~9, from 8 states to 5, and defer D76/D77/D79 entirely. The core argument: "You have a Production v1 architecture when you should have a Technical MVP."

**Analysis of feedback:**

| Suggestion | Verdict | Why |
|------------|---------|-----|
| Drop Sentinel Learning (auto-promote) | AGREE | No usage data exists yet. Haiku 3-tier evaluation stays. Only the auto-promote-to-allowlist after N approvals is deferred. |
| Drop Zombie Detection (D76) | PARTIALLY AGREE | Formal reaper logic is overkill for one-person-watching-the-screen. Keep decision documented, defer implementation. |
| Drop IMPOSSIBLE ping (D77) | AGREE | BLOCKER + natural language message achieves the same result. Pasha (Opus) interprets "this spec is impossible because X" without a formal urgency enum. |
| Drop DAG dependencies (D79) | AGREE | First 10+ specs will be linear (one at a time). No DAG needed. |
| ~9 tools | TOO FEW | Forgets Pasha needs to scan specs and Workers need to ping back. Actual MVP minimum is 11. |
| 5 states (no REJECTED/STUCK) | WRONG | QG WILL reject specs on day 1. Without REJECTED, there's no retry loop. Without STUCK, specs retry forever. INTERRUPTED needed for crash safety. All 8 states essential. |
| "Delete 40% of code" | MISLEADING | There IS no code. D76-D79 are decision documents, not implementations. Cost of documented decisions is zero. Cost of not having them when needed is high. |

**Decision:**

1. **11 MVP tools (Phase A):** spec_create, spec_read, spec_list, spec_transition, spec_update, spec_write_feedback, sentinel_check_write, run_command_checked, web_fetch_checked, orch_write_ping, project_get_config. These are the minimum to get a spec from DRAFT to DONE.

2. **4 deferred tools (Phase B):** orch_scan_specs (spec_list covers it), orch_check_ready (no dependencies for linear specs), orch_assign_worker (Pasha uses spec_transition directly), dag_check_dependencies (no DAG for linear specs). Build when multi-spec projects start.

3. **All 8 states preserved.** REJECTED and STUCK are day-1 essential. INTERRUPTED is needed for crash safety.

4. **D76-D79 decisions preserved as design docs.** They cost nothing to keep and will be needed when the system scales. Not deleting documented decisions.

5. **Sentinel Learning set to false.** Haiku 3-tier evaluation (allowlist -> denylist -> Haiku) stays as-is. Auto-promote-to-allowlist deferred until usage data exists.

**Why:** Build the minimum that lets the first spec go from DRAFT to DONE. Everything else is Phase B -- designed, documented, built when needed.

**Trade-off:** Phase B tools will need implementation when multi-spec projects start. Acceptable because: the architecture is designed, the decisions are documented, and adding 4 tools later is straightforward.

### D81: Scoped Secret Injection for run_command_checked

**Context:** Agents need secrets to do useful work (e.g., `git clone` a private repo requires `GITHUB_TOKEN`), but the MCP server's process environment contains ALL secrets (`ANTHROPIC_API_KEY`, `TELEGRAM_BOT_TOKEN`, etc.). Currently `run_command_checked` calls `create_subprocess_shell` with no `env` argument, inheriting the full environment. Any agent command can read any secret via `env` or `printenv`. The old codebase (pre-D63) had a `ToolExecutor` with scoped secret injection and a `secret_check` tool -- both were deleted in the architectural reset and never rebuilt.

**Decision:** Two changes:

1. **Scoped secret injection in `run_command_checked`.** Instead of inheriting the full environment, the subprocess gets a clean environment with only the secrets explicitly allowed for the command type. Scoping rules are defined per-project in `sentinel.yaml`:

```yaml
secret_scopes:
  git:
    commands: ["git *"]
    secrets: ["GITHUB_TOKEN"]
  build:
    commands: ["npm *", "cargo *", "uv *"]
    secrets: ["GITHUB_TOKEN"]
```

When a command matches a scope's pattern, only those secrets (plus non-secret env vars like `PATH`, `HOME`, `LANG`) are injected. Commands matching no scope get zero secrets. This is fail-closed: unlisted secrets are never exposed.

2. **`secret_check` MCP tool.** Agents can verify whether a required secret is configured without seeing its value. Returns `{"name": str, "exists": bool}`. Vizier uses this to tell Workers "GITHUB_TOKEN is configured, you can clone" or "not configured, ask the Sultan."

3. **Deploy pipeline addition.** Add `github-pat` to Azure Key Vault. Update the deploy workflow to fetch it and write `GITHUB_TOKEN=<value>` to `.env`. The vizier-mcp container already reads `.env` via `env_file`.

**Why:** Principle of least privilege. An agent running `pytest` should not have access to `ANTHROPIC_API_KEY`. An agent running `git clone` needs `GITHUB_TOKEN` but not `TELEGRAM_BOT_TOKEN`. The old codebase had this right -- secrets exist only for the lifetime of the subprocess, scoped to what the command actually needs.

**Trade-off:** Adds complexity to `_execute_command`. Scoping rules need maintenance as new tools/secrets are added. Acceptable because: the alternative (all secrets visible to all commands) is a real security risk, and the scoping config is declarative and auditable.
