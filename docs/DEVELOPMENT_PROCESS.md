# Development Process

Detailed development workflow for this repository. Referenced from `CLAUDE.md`.

---

## Context Recovery Rule -- CRITICAL

**After auto-compact or session continuation, ALWAYS read the relevant documentation files before continuing work:**

1. Read `docs/ARCHITECTURE.md` for system topology, MCP server design, agent definitions, Sentinel, communication model
2. Read `docs/DECISIONS.md` for the decision log (D1-D62+ and the decision map update in ARCHITECTURE.md section 7)
3. Read `docs/IMPLEMENTATION_PLAN.md` for current progress
4. Read `docs/CHANGELOG.md` for recent changes
5. Check git log and branch status to determine where you left off

This ensures continuity and prevents duplicated or missed work.

---

## Consistency Check -- MANDATORY

Before proposing any implementation approach, scan for conflicts with prior decisions:

1. Read `docs/DECISIONS.md` -- check resolved decisions and their rationale (D1-D62+)
2. Read `docs/ARCHITECTURE.md` -- check the decision map update (section 7) for kept/modified/replaced/reversed/dropped status

If a conflict is found, present it to the user before proceeding. Do NOT silently override a documented decision.

---

## Task Classification

Task complexity determines process depth. Classify each task, then follow the matching path. Within an activated path, execute all steps -- do not cherry-pick.

| Path | When to use | Examples |
|------|-------------|---------|
| **Q** (Quick) | Trivial, obvious, single-location change | Typo fix, config tweak, one-liner bug fix |
| **S** (Standard) | Fits in one session, clear scope | New feature, multi-file refactor, bug requiring investigation |
| **P** (Project) | Needs phased execution across sessions | Multi-phase feature, architectural change, large migration |

---

## Q. Quick Path

1. **Fix it** -- make the change
2. **Validate** -- run `uv run ruff check . && uv run ruff format --check . && uv run pytest`
3. **Commit**

If the fix fails twice or reveals unexpected complexity, promote to **S**.

---

## S. Standard Path

**S.1 Explore** -- Read relevant code and tests. Identify patterns/utilities to reuse. Understand scope.

**S.2 Plan** -- Read `docs/DECISIONS.md`. Check for conflicts with prior decisions; if a conflict is found, present the contradiction to the user before proceeding. Design approach. Identify files to modify. Log the feature request and any user decisions.

**S.3 Setup** -- Create feature branch (`fix/...`, `feat/...`, `refactor/...`). Run `git fetch origin` and sync with base branch.

**S.4 Build (TDD cycle)**
1. Create code structure (interfaces, types)
2. Write tests
3. Write implementation
4. Write docstrings for public APIs; record non-trivial decisions in `docs/IMPLEMENTATION_PLAN.md`
5. Iterate (back to step 2 if needed)

**S.5 Validate** -- run both in parallel via agents:

| Agent | File | What it does |
|-------|------|-------------|
| Code Quality | `.claude/agents/code-quality-validator.md` | Lint, format, type check (auto-fixes) |
| Test Coverage | `.claude/agents/test-coverage-validator.md` | Run tests, check coverage |

Pre-commit hygiene (before agents): no leftover `TODO`/`FIXME`/`HACK`, no debug prints, no hardcoded secrets.

All agents use `subagent_type: "general-purpose"`. Do NOT use `feature-dev:code-reviewer`.

**S.6 Ship**
1. Commit and push
2. Create PR (use `.claude/agents/pr-writer.md` agent to generate description)
3. Verify CI with `gh pr checks`
4. Code review: use `.claude/agents/code-reviewer.md` agent, or `.claude/agents/review-responder.md` if an automated reviewer (e.g., CodeRabbit) is configured. Fix Critical issues before merge.

**S.7 Document** -- Update `docs/CHANGELOG.md` with user-facing changes and `docs/DECISIONS.md` with decisions made. Use `.claude/agents/docs-updater.md` to verify.

**On failure:** fix the issue, amend or re-commit, re-run from the failed step. If multiple steps fail repeatedly, reassess scope.

---

## P. Project Path

### Autonomous Implementation Directive

**Mode: Fully autonomous. Do NOT wait for user approval between phases.**

Work through the implementation plan (`docs/IMPLEMENTATION_PLAN.md`) phase by phase:

1. **Do NOT use `EnterPlanMode`** -- plan internally by reading docs and code, then execute directly
2. **For each phase:** research requirements, implement using TDD (structure -> tests -> code), run full PCC (S.5 through S.7 + acceptance criteria), then move to the next phase
3. **Only stop if truly blocked:** unresolvable test failures, architectural contradictions that need human judgment, or missing external dependencies
4. **After auto-compact:** re-read this directive, `docs/IMPLEMENTATION_PLAN.md`, and `MEMORY.md` to recover context. Check git log and branch status to determine where you left off. Resume from there.
5. **Skip PCC steps that require user interaction:** PIRR warnings can be self-acknowledged with written justification. Code review findings that are Critical must be fixed; Warnings addressed if straightforward.
6. **Commit frequently:** after each sub-phase or logical unit of work, commit and push so progress is not lost to context limits
7. **Permission denial fallback:** If a tool is denied, work around it with a permitted alternative. If non-critical (e.g., CI check), skip and note it. If truly blocked, commit all progress, write a handoff note in the commit message, update IMPLEMENTATION_PLAN.md with status, and stop.
8. **Security hook workaround:** The `security-guidance` plugin blocks writes containing dangerous patterns. In test code, use alternative patterns (mock names, indirect references) to avoid triggering it.
9. **Continuous implementation:** After completing each phase, immediately start the next phase. Do not stop between phases. Continue until all planned phases are fully implemented or truly blocked.

### P.1 Analyze
- Explore codebase architecture and boundaries
- Read `docs/IMPLEMENTATION_PLAN.md`, `docs/CHANGELOG.md`, and `docs/DECISIONS.md` for prior decisions
- **Consistency check**: scan `docs/DECISIONS.md` for conflicts or obsolete entries. Prune stale decisions. If conflicts found, present the contradiction to the user before proceeding.

### P.2 Plan
- Design approach and write implementation plan in `docs/IMPLEMENTATION_PLAN.md`
- Define phases with acceptance criteria
- Every plan MUST include PIRR as a gate before each phase's implementation
- Every plan MUST include Phase Completion Steps referencing S.5-S.7 + acceptance criteria

### P.3 Execute (repeat per phase)

#### Pre-Implementation Readiness Review (PIRR)
**This step runs AFTER plan approval but BEFORE any code is written for a phase.**

- Invoke `.claude/agents/spec-readiness-reviewer.md` via Task tool (`subagent_type: "general-purpose"`)
- The agent reviews six dimensions: Acceptance Criteria Completeness, Spec-Plan Alignment, Prerequisites & Dependencies, Deployment Readiness, Architectural Decision Coverage, Validated Scenario Coverage
- Each dimension produces PASS, WARN, or FAIL

**Gate rules:**
- **Any FAIL** -> Block implementation. Fix the plan, specs, or decisions first. Re-run PIRR after fixes.
- **WARN items** -> Must be acknowledged with written justification before proceeding.
- **All PASS** -> Proceed to implementation.

**When to re-run PIRR:**
- After fixing any FAIL items
- After significant plan changes mid-phase
- When resuming a phase after a long pause (to verify prerequisites still hold)

| Check | When It Runs | Question It Answers |
|-------|-------------|---------------------|
| Consistency Check | During planning | "Does this plan CONTRADICT anything?" |
| PIRR | After plan approved, before coding | "Is this plan COMPLETE enough to implement?" |

#### Implementation
1. Create feature branch (`fix/...`, `feat/...`, `refactor/...`)
2. Sync with remote (`git fetch origin`)
3. Run Standard Path (S.4) for the phase
4. Run S.5 (Validate) + acceptance criteria (`.claude/agents/acceptance-criteria-validator.md`)
5. Run S.6 (Ship) + S.7 (Document)
6. Update `docs/IMPLEMENTATION_PLAN.md` (use `.claude/agents/implementation-tracker.md` or built-in `Plan` agent)
7. Write phase handoff note (2-5 sentences: what completed, deviations, risks, dependencies, intentional debt)

### P.4 Finalize
- Merge. Version bump and changelog consolidation if applicable.

---

## Failure Protocol

| Failure | Action |
|---|---|
| PIRR fails | Fix the plan, specs, or decisions. Re-run PIRR. Do NOT create feature branch until PIRR passes or all WARN items are acknowledged. |
| Validation (S.5) fails on current code | Fix, amend commit, re-run from S.5 |
| CI (S.6.3) fails on current code | Fix, push, re-run from S.6.3 |
| CI fails on pre-existing issue | Document separately, do not block current work |
| Code review flags architectural concern | Pause. Evaluate rework (back to S.4) vs. follow-up issue |
| Acceptance criteria (P.3) reveals previous phase regression | File as separate issue. Fix in current phase only if it's a direct regression |
| Multiple steps fail repeatedly | Stop. Reassess scope -- may need to split into smaller increments |

---

## Agent Reference

All custom agents are in `.claude/agents/` and use `subagent_type: "general-purpose"`.

| Step | Agent File | Purpose |
|------|-----------|---------|
| S.5 | `code-quality-validator.md` | Lint, format, type check |
| S.5 | `test-coverage-validator.md` | Tests and coverage |
| S.6.2 | `pr-writer.md` | Generate PR description |
| S.6.4 | `code-reviewer.md` | Independent code review |
| S.6.4 | `review-responder.md` | Handle automated reviewer comments |
| S.7 | `docs-updater.md` | Verify and update documentation |
| P.3 | `spec-readiness-reviewer.md` | Pre-implementation readiness review (PIRR) |
| P.3 | `acceptance-criteria-validator.md` | Verify acceptance criteria |
| P.3 | `implementation-tracker.md` | Verify plan matches reality |
| -- | `agent-auditor.md` | Audit agent definitions against best practices |
| -- | `security-auditor.md` | OWASP-based security analysis (read-only) |
| -- | `refactoring-specialist.md` | SOLID/code smell analysis (read-only) |
| -- | `output-evaluator.md` | LLM-as-Judge quality scoring |

---

## Hooks

5 hook scripts in `.claude/hooks/` run automatically via settings.json:

| Hook | Event | Matcher | Behavior |
|------|-------|---------|----------|
| `dangerous-actions-blocker.sh` | PreToolUse | Bash | Blocks `rm -rf`, `sudo`, `DROP DATABASE`, `git push --force`, secrets in args. Exit 2 = block. |
| `unicode-injection-scanner.sh` | PreToolUse | Edit\|Write | Blocks zero-width chars, RTL overrides, ANSI escapes, null bytes, tag chars. Exit 2 = block. |
| `output-secrets-scanner.sh` | PostToolUse | Bash | Scans output for AWS/Anthropic/OpenAI/GitHub keys, JWTs, private keys, DB URLs. Warns via systemMessage. |
| `auto-format.sh` | PostToolUse | Edit\|Write | Runs `uv run ruff format` and `uv run ruff check --fix` on edited .py files. Synchronous. |
| `test-on-change.sh` | PostToolUse | Edit\|Write | Discovers and runs associated test file. Informational (systemMessage on failure). |

All hooks require `jq` for JSON parsing and degrade gracefully if jq is missing.

---

## Commands

3 slash commands in `.claude/commands/`:

| Command | Purpose |
|---------|---------|
| `/catchup` | Context restoration after `/clear`. Reads IMPLEMENTATION_PLAN.md, CHANGELOG.md, git history; recommends next steps. |
| `/security-audit` | 6-phase Python security scan (deps, secrets, code patterns, input validation, config, scoring). Outputs A-F grade. |
| `/ship` | Pre-deployment checklist with 3 tiers: Blockers (tests, lint, types, secrets), High Priority (coverage, TODOs, docs), Recommended (git history, branch sync). |

---

## Rules

4 review rules in `.claude/rules/` auto-loaded as project context:

| Rule | Focus |
|------|-------|
| `architecture-review.md` | System design, dependencies, data flow, security boundaries |
| `code-quality-review.md` | DRY, error handling, type annotations, complexity |
| `performance-review.md` | N+1 queries, memory, caching, algorithmic complexity |
| `test-review.md` | Coverage gaps, test quality, edge cases, assertion quality |

These cover what linters cannot: architecture, design, and logic-level concerns.

---

## Changelog Format

Use [Keep a Changelog](https://keepachangelog.com/) format. Sections: Added, Changed, Deprecated, Removed, Fixed, Migration.

Entries must describe **user impact**, not just name the change:
- **Good**: "Users can now filter results by date range using `--since` and `--until` flags"
- **Bad**: "Added date filter"

Update changelog for every MINOR or MAJOR version bump. Patch updates are optional.

---

## PCC Shorthand

When the user says **"PCC"** or **"PCC now"**, execute S.5 through S.7 in order (Validate, Ship, Document).
