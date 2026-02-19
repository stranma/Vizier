# Vizier Use Cases (BDD Scenarios)

15 testable scenarios covering all agent communication pairs and safety mechanisms.

---

## Scenario 1: Happy Path -- Full Task Lifecycle

Tests the complete delegation chain: Sultan -> EA -> Pasha -> Scout -> Architect -> Worker -> QG -> Done.

```gherkin
Given a registered project "project-alpha" with plugin "software"
  And the project has no active specs
  And autonomy stage is "supervised"

When Sultan sends "Build JWT authentication" via Telegram

Then EA calls create_spec("001-jwt-auth", goal="Build JWT authentication", status=DRAFT)
  And spec file ".vizier/specs/001-jwt-auth/spec.md" is created with status DRAFT
  And EA sends STATUS_UPDATE to Sultan: "Task created, delegating to project-alpha"

When Pasha detects the new DRAFT spec via watchdog
Then Pasha calls delegate_to_scout("001-jwt-auth")
  And Pasha calls spawn_agent(role="scout", spec_id="001-jwt-auth")

When Scout subprocess starts
Then Scout calls web_search("python jwt library pypi")
  And Scout calls send_message(RESEARCH_REPORT) with candidates and recommendation
  And Scout calls update_spec_status(SCOUTED)
  And Scout subprocess exits(0)

When Pasha detects SCOUTED status via watchdog
Then Pasha calls delegate_to_architect("001-jwt-auth")
  And Pasha calls spawn_agent(role="architect", spec_id="001-jwt-auth")

When Architect subprocess starts
Then Architect calls read_file to read project context
  And Architect calls read_spec to read RESEARCH_REPORT
  And Architect calls send_message(PROPOSE_PLAN) with 4 sub-specs and DAG
  And Pasha's DAG validator accepts the plan (no cycles, all IDs valid)
  And Architect calls update_spec_status(DECOMPOSED) on parent
  And 4 sub-specs created as READY
  And Architect subprocess exits(0)

When Pasha detects READY sub-specs
Then Pasha checks depends_on: "001-data-model" has no dependencies
  And Pasha calls spawn_agent(role="worker", spec_id="001-jwt-auth/001-data-model")

When Worker subprocess starts
Then Worker calls read_file, write_file, edit_file to implement data model
  And Worker calls bash("uv run pytest tests/models/ -v") to verify
  And Worker calls git("add . && commit -m 'Add User model'")
  And Worker calls update_spec_status(REVIEW)
  And Worker subprocess exits(0)

When Pasha detects REVIEW status
Then Pasha calls spawn_agent(role="quality_gate", spec_id="001-jwt-auth/001-data-model")

When QG subprocess starts
Then QG calls run_tests("uv run pytest tests/models/ -v") and saves output to evidence/test_output.txt
  And QG calls bash("uv run ruff check src/models/") and saves output to evidence/lint_output.txt
  And QG calls bash("uv run pyright src/models/") and saves output to evidence/pyright_output.txt
  And QG calls git("diff HEAD~1") and saves output to evidence/diff.patch
  And QG calls send_message(QUALITY_VERDICT) with pass_fail="PASS" and 4 evidence links
  And QG calls update_spec_status(DONE)
  And QG subprocess exits(0)

When Pasha detects DONE on "001-data-model"
Then Pasha checks depends_on for remaining sub-specs
  And "002-token-service" has no unmet dependencies -> spawns Worker
  And "003-middleware" still blocked (depends on 001 + 002)
  And Pasha calls report_progress with updated status.json
```

**Infrastructure exercised**: spec_io, state_manager, watchdog, reconciler, SentinelEngine, ModelRouter, ToolRunner, Golden Trace

---

## Scenario 2: Escalation -- Worker Gets Stuck

Tests graduated retry (D25) and escalation chain to Sultan.

```gherkin
Given a READY spec "002-oauth" in project "project-alpha"
  And max_retries is 10

When Pasha spawns Worker for "002-oauth"
  And Worker fails with non-zero exit (e.g., cannot understand spec requirements)

Then Pasha detects crash, increments retries to 1
  And Pasha re-queues spec as READY
  And Pasha spawns new Worker (fresh context)

When Worker fails again on retries 2, 3, 4
Then at retry 3, ModelRouter bumps Worker to Opus tier
  And Pasha logs each failure to trace.jsonl

When Worker fails at retry 5
Then Pasha writes ESCALATION to "reports/project-alpha/escalations/"
  And escalation contains: severity="high", reason, attempted actions list
  And EA detects escalation file via watchdog on reports/ directory
  And EA sends Sultan: "002-oauth stuck after 5 retries. Needs human guidance."

When Sultan responds via Telegram with guidance
Then EA writes clarification to spec directory
  And Pasha detects clarification, re-spawns Worker with clarification context in system prompt
```

---

## Scenario 3: Rejection Loop -- QG Rejects, Worker Retries

Tests REVIEW -> REJECTED -> IN_PROGRESS -> REVIEW cycle with feedback.

```gherkin
Given Worker completed spec "003-login" and status is REVIEW

When QG spawns and runs mechanical pass (lint check)
  And ruff reports 3 lint errors

Then QG saves lint output to evidence/lint_output.txt
  And QG calls send_message(QUALITY_VERDICT) with:
    pass_fail="FAIL"
    criteria_results=[{criterion: "No lint errors", result: "FAIL", evidence_link: "evidence/lint_output.txt"}]
    suggested_fix=["Fix line-too-long in auth.py:45", "Fix unused-import in utils.py:2", "Fix missing-trailing-comma in config.py:12"]
  And QG calls update_spec_status(REJECTED)
  And QG writes feedback to specs/003-login/feedback/2026-02-19-001.md

When Pasha detects REJECTED, increments retries to 1
Then Pasha spawns fresh Worker with feedback file in context

When Worker reads feedback, fixes lint errors
  And Worker calls run_tests to verify
  And Worker commits and calls update_spec_status(REVIEW)

When QG spawns again
  And all passes succeed (mechanical + semantic)
Then QG saves all evidence files
  And QG calls send_message(QUALITY_VERDICT) with pass_fail="PASS"
  And QG calls update_spec_status(DONE)
```

---

## Scenario 4: Clarification -- Worker Needs Information

Tests async clarification chain: Worker -> Pasha -> EA -> Sultan -> back.

```gherkin
Given Worker is implementing spec "004-api" which says "add rate limiting"
  And spec does not specify rate limit values

When Worker calls send_message(REQUEST_CLARIFICATION):
  question="What should the rate limit be?"
  options=["100 req/min per user", "1000 req/min per IP", "Custom per endpoint"]
  blocking=true
  deadline="2026-02-19T12:00:00Z"

Then Worker calls ping_supervisor(spec_id="004-api", urgency="BLOCKER", message="Blocked on rate limit values")
  And ping file written to spec directory
  And Pasha's watchdog detects ping file within ~100ms

When Pasha reads the REQUEST_CLARIFICATION
Then Pasha calls escalate_to_ea(spec_id="004-api", reason="Worker needs rate limit values from Sultan")
  And Pasha writes escalation to reports/project-alpha/escalations/

When EA detects escalation
Then EA sends Sultan: "Worker on 004-api needs to know: What rate limits? Options: [100/min/user, 1000/min/IP, Custom]"

When Sultan replies "100 req/min per user, 10 req/sec burst"
Then EA writes answer to spec directory as a clarification response file
  And EA calls send_message(STATUS_UPDATE) to Pasha

When Pasha detects clarification response
Then Pasha re-spawns Worker with clarification in system prompt context
  And Worker reads clarification, implements 100 req/min rate limiting
  And Worker completes normally
```

---

## Scenario 5: Decomposition -- Architect Creates DAG of Sub-specs

Tests PROPOSE_PLAN with depends_on DAG (D52) and Pasha validation.

```gherkin
Given a SCOUTED spec "005-dashboard" with complexity HIGH
  And RESEARCH_REPORT recommends charting library "plotly"

When Pasha spawns Architect
Then Architect reads project context and RESEARCH_REPORT
  And Architect calls send_message(PROPOSE_PLAN) with:
    steps=[
      {id: "005-dashboard/001-data-model", depends_on: []},
      {id: "005-dashboard/002-chart-component", depends_on: []},
      {id: "005-dashboard/003-api-endpoint", depends_on: ["005-dashboard/001-data-model"]},
      {id: "005-dashboard/004-integration", depends_on: ["005-dashboard/002-chart-component", "005-dashboard/003-api-endpoint"]}
    ]

When Pasha receives PROPOSE_PLAN
Then Pasha's DAG validator runs topological sort
  And validator confirms: no cycles, all IDs exist, no self-references
  And Pasha accepts the plan
  And 4 sub-specs created as READY with depends_on in frontmatter
  And Parent spec transitions to DECOMPOSED

When Pasha evaluates the READY queue
Then "001-data-model" has no dependencies -> Worker spawned
  And "002-chart-component" has no dependencies -> Worker spawned (parallel)
  And "003-api-endpoint" depends on 001 (not DONE yet) -> SKIPPED
  And "004-integration" depends on 002+003 (not DONE yet) -> SKIPPED

When "001-data-model" reaches DONE
Then Pasha re-evaluates queue
  And "003-api-endpoint" now has all depends_on DONE -> Worker spawned
```

---

## Scenario 6: Multi-Project -- EA Manages Multiple Pashas

Tests EA cross-project coordination and status aggregation.

```gherkin
Given registered projects: "project-alpha" (software), "project-beta" (documents)
  And project-alpha has 2 active specs (1 IN_PROGRESS, 1 READY)
  And project-beta has 1 active spec (IN_PROGRESS)

When Sultan sends "/status"
Then EA reads status.json from both project report directories
  And EA reads project capability summaries from ProjectRegistry
  And EA synthesizes cross-project summary
  And EA sends Sultan: "Alpha: 2 specs active (auth 60%, data model queued). Beta: board deck 40% done."

When Sultan says "Prioritize the board deck, it's due Friday"
Then EA calls create_spec in project-beta with high priority
  And EA sends STATUS_UPDATE to project-beta's Pasha
  And Pasha adjusts scheduling to prioritize the board deck spec
```

---

## Scenario 7: Security Gating -- Sentinel Blocks Dangerous Tool Call

Tests Sentinel denylist and agent adaptation.

```gherkin
Given Worker is implementing spec "006-cleanup"

When Worker calls bash("rm -rf /opt/vizier/workspaces/old/")
Then SentinelEngine denylist matches "rm -rf"
  And Tool returns error: "Permission denied: Command matches denylist pattern 'rm -rf'"
  And error logged to trace.jsonl

When Worker receives the error
Then Worker adapts: calls bash("rm -r /opt/vizier/workspaces/old/specific-dir/")
  And Sentinel denylist does not match (no -rf flag)
  And Haiku evaluator assesses: ALLOW (targeted deletion, not recursive-force)
  And Command runs successfully

When Worker calls git("push --force origin main")
Then Sentinel git_classifier flags as dangerous (force-push to main)
  And Tool returns error: "Permission denied: Force push to main requires Sultan approval"

When Worker receives the error
Then Worker adapts: calls git("push origin feat/cleanup")
  And Sentinel git_classifier: ALLOW (push to feature branch)
  And Push succeeds
```

---

## Scenario 8: Budget Enforcement -- Approaching Token Limit

Tests 80%/100% budget thresholds (D33).

```gherkin
Given monthly budget is $100
  And current month spend is $79
  And Worker is implementing spec "007-refactor" (complex, high token usage)

When Worker's cumulative tokens put monthly total at $80
Then AgentRuntime triggers 80% budget alert
  And EA sends Sultan: "Budget at 80% ($80/$100). Projected to exceed by Feb 25."
  And Worker continues at current tier

When monthly spend reaches $100
Then AgentRuntime enforces 100% threshold
  And ModelRouter degrades all agents to haiku tier
  And EA notifies Sultan: "Budget reached. Agents degraded to Haiku tier."
  And Current Worker invocation continues at reduced tier
  And New invocations use Haiku only

When monthly spend reaches $120
Then AgentRuntime enforces 120% hard stop
  And No new agent invocations allowed
  And EA sends Sultan: "Budget exceeded 120%. All agent work halted until next month or budget increase."
```

---

## Scenario 9: Recovery -- Agent Crashes Mid-Task

Tests crash recovery via reconciliation (D22).

```gherkin
Given Worker is implementing spec "008-parser" with status IN_PROGRESS
  And Worker subprocess PID 12345 is running
  And Worker has written partial artifacts to disk

When Worker process crashes (out of memory, exit code 137)
Then Pasha's subprocess monitor detects non-zero exit
  And Pasha increments spec retries (0 -> 1)
  And Pasha logs crash to trace.jsonl
  And Spec stays IN_PROGRESS (will be re-queued)
  And Pasha spawns fresh Worker with clean context
  And New Worker reads partial artifacts from disk, continues from there

When daemon itself crashes and restarts
Then reconciler scans all specs on startup
  And Finds spec "008-parser" with status IN_PROGRESS
  And No running subprocess found for this spec
  And Reconciler transitions: IN_PROGRESS -> INTERRUPTED -> READY
  And Pasha's event loop picks up READY spec
  And Normal processing resumes
```

---

## Scenario 10: Retrospective -- System Learns from Failures

Tests pattern analysis and proposal generation.

```gherkin
Given project "project-alpha" completed cycle 42
  And 3 specs were rejected for "lint errors" in the last 5 cycles
  And 1 spec went STUCK with "test timeout" pattern
  And Golden Trace data available for all specs

When Retrospective agent triggers at cycle end
Then Retrospective calls read_spec and list_specs to gather all feedback files
  And Retrospective calls grep to find patterns in feedback/
  And Retrospective identifies: "lint rejection" appears 3x in last 5 cycles

Then Retrospective calls write_file to update .vizier/learnings.md:
  append="Workers should run ruff check before committing (3 rejections for lint in cycles 38-42)"
  And Retrospective calls send_message(PROPOSE_PLAN) with:
    proposal="Add mandatory lint pre-check to Worker system prompt"
    evidence="3/10 rejections were lint-only in last 5 cycles"
    status="PENDING"

When EA detects proposal
Then EA sends Sultan: "Retrospective suggests: Add lint check to Worker flow. Evidence: 3 lint rejections in last 5 cycles. /approve or /reject?"

When Sultan sends "/approve"
Then EA updates proposal status to APPROVED
  And Next cycle: Worker system prompt includes lint check instruction
  And Retrospective logs: "Proposal approved, measuring impact in next 5 cycles"
```

---

## Scenario 11: Scout Feedback -- Architect Requests Re-research (D48)

Tests the `request_more_research` tool and Scout re-invocation.

```gherkin
Given Scout completed research for spec "011-payments"
  And RESEARCH_REPORT has recommendation="BUILD_FROM_SCRATCH", confidence=0.6

When Architect spawns and reads RESEARCH_REPORT
Then Architect evaluates: confidence 0.6 is below threshold, recommendation seems wrong for payments
  And Architect calls request_more_research(
    spec_id="011-payments",
    questions=["Search for Python Stripe SDK", "Search for payment processing libraries with PCI compliance"]
  )

Then spec transitions back to DRAFT with research_questions attached
  And Pasha detects DRAFT, spawns Scout again

When Scout re-runs with targeted questions
Then Scout calls web_search("python stripe sdk"), web_search("python pci compliance payment library")
  And Scout finds Stripe SDK and stripe-python package
  And Scout calls send_message(RESEARCH_REPORT) with:
    candidates=[{name: "stripe-python", relevance: "high"}, ...]
    recommendation="USE_LIBRARY"
    confidence=0.95

When Architect spawns again
Then Architect reads updated RESEARCH_REPORT (confidence 0.95)
  And Architect proceeds with decomposition using Stripe SDK
```

---

## Scenario 12: QG Opus Escalation -- HIGH Complexity Review (D49)

Tests automatic Opus tier for semantic passes on complex specs.

```gherkin
Given Worker completed spec "012-auth-refactor" with complexity=HIGH
  And spec is in REVIEW status

When QG spawns
Then ModelRouter resolves: role=quality_gate, complexity=HIGH
  And Mechanical passes (1-2) use Sonnet tier
  And Semantic passes (3-5) use Opus tier

When QG runs Pass 1 (Hygiene, deterministic)
Then QG checks for debug artifacts, hardcoded values -- no issues found

When QG runs Pass 2 (Mechanical, deterministic)
Then QG calls run_tests("uv run pytest tests/auth/ -v")
  And saves output to evidence/test_output.txt -- all pass
  And QG calls bash("uv run ruff check src/auth/")
  And saves output to evidence/lint_output.txt -- clean

When QG runs Pass 3 (Test Validation, Opus tier)
Then ModelRouter upgrades to Opus for this pass
  And Opus-QG analyzes test quality: "Tests cover happy path but miss edge case where token is expired AND refresh token is revoked simultaneously"
  And QG calls send_message(QUALITY_VERDICT) with:
    pass_fail="FAIL"
    criteria_results=[{criterion: "Tests cover edge cases", result: "FAIL", evidence_link: "evidence/test_output.txt"}]
    suggested_fix=["Add test for simultaneous token+refresh expiry in test_auth.py"]

Then spec transitions to REJECTED with specific feedback
  And Worker retries with feedback, adds the missing test
  And QG re-runs, Opus catches no further issues -> DONE
```

---

## Scenario 13: Synchronous Ping -- Immediate Supervisor Notification (D50)

Tests `ping_supervisor` with BLOCKER urgency and sub-second response.

```gherkin
Given Worker is implementing spec "013-config" in project-alpha
  And Pasha's event loop is running with watchdog active

When Worker encounters a missing config file referenced in the spec
Then Worker calls ping_supervisor(
    spec_id="013-config",
    urgency="BLOCKER",
    message="Config file config/prod.yaml referenced in spec does not exist in project"
  )
  And ping_supervisor writes PING message as JSON file to specs/013-config/ping.json

Then Pasha's watchdog detects new file within ~100ms
  And Pasha reads PING message
  And urgency=BLOCKER triggers immediate handling + EA escalation

When Pasha reads the ping
Then Pasha calls escalate_to_ea with the BLOCKER message
  And EA sends Sultan: "Worker on 013-config blocked: config/prod.yaml missing. Please provide or clarify."

Note: Total latency from Worker ping to Pasha handling: < 200ms (watchdog detection)
  Compared to reconciliation-only: up to 15,000ms
```

---

## Scenario 14: Loop Guardian -- Detects Agent Spinning (D51)

Tests deterministic repeat detection and Haiku checkpoint HALT.

```gherkin
Given Worker is implementing spec "014-parser"
  And Loop Guardian configured: checkpoint_interval=5, max_identical_calls=3

When Worker calls bash("uv run pytest tests/parser/") -> fails
  And Worker calls bash("uv run pytest tests/parser/") -> fails (same command)
  And Worker calls bash("uv run pytest tests/parser/") -> fails (3rd identical call)

Then Loop Guardian deterministic detection triggers
  And Loop Guardian returns HALT
  And AgentRuntime writes ESCALATION message:
    reason="Agent repeated identical failing tool call 3 times"
    attempted=["bash: uv run pytest tests/parser/ (3x, all failed)"]
  And Worker subprocess is terminated
  And Pasha handles escalation (may re-decompose or escalate to EA)

--- Alternative: Non-identical but unproductive ---

When Worker makes 5 different tool calls but none make progress
  (e.g., read_file x3, grep x1, read_file x1 -- exploring but not writing)

Then Loop Guardian LLM checkpoint triggers at call #5
  And Haiku receives: last 5 tool calls + results summary
  And Haiku evaluates: "Agent is exploring but hasn't made progress toward the spec goal"
  And Haiku returns: WARN

Then AgentRuntime logs warning to trace.jsonl
  And Worker continues (WARN does not stop the agent)
  And At call #10, next Haiku checkpoint
  And If still no progress: Haiku returns HALT -> forced escalation
```

---

## Scenario 15: DAG Scheduling -- Pasha Respects Dependencies (D52)

Tests that Pasha holds dependent specs until prerequisites are DONE.

```gherkin
Given Architect decomposed spec "015-api" into:
  sub-spec A: "015-api/001-models" (depends_on: [])
  sub-spec B: "015-api/002-routes" (depends_on: ["015-api/001-models"])
  sub-spec C: "015-api/003-middleware" (depends_on: ["015-api/001-models"])
  sub-spec D: "015-api/004-tests" (depends_on: ["015-api/002-routes", "015-api/003-middleware"])
  And all 4 sub-specs have status READY

When Pasha evaluates the READY queue
Then Pasha checks depends_on for each:
  A: no dependencies -> spawn Worker immediately
  B: depends on A (status=READY, not DONE) -> SKIP
  C: depends on A (status=READY, not DONE) -> SKIP
  D: depends on B+C (not DONE) -> SKIP
  And only 1 Worker spawned (for A)

When A reaches DONE
Then Pasha re-evaluates queue on DONE event
  And B: depends on A (now DONE) -> spawn Worker
  And C: depends on A (now DONE) -> spawn Worker (parallel with B)
  And D: depends on B+C (B=IN_PROGRESS, C=IN_PROGRESS) -> SKIP

When B reaches DONE, C still IN_PROGRESS
Then Pasha re-evaluates: D depends on B (DONE) + C (IN_PROGRESS) -> still SKIP

When C reaches DONE
Then Pasha re-evaluates: D depends on B (DONE) + C (DONE) -> spawn Worker
  And D (integration tests) runs last, as intended by Architect's DAG
```

---

## Communication Pair Coverage

| Pair | Scenarios |
|------|-----------|
| Sultan <-> EA | 1, 2, 4, 6, 8, 10 |
| EA <-> Pasha | 1, 2, 4, 6 |
| Pasha <-> Scout | 1, 11 |
| Pasha <-> Architect | 1, 5, 11 |
| Pasha <-> Worker | 1, 2, 3, 4, 7, 8, 9, 13, 14, 15 |
| Pasha <-> QG | 1, 3, 12 |
| Pasha <-> EA (escalation) | 2, 4, 13 |
| Architect -> Scout (feedback) | 11 |
| Retrospective -> EA | 10 |
