# Development Process

Detailed development workflow for this repository. Referenced from `CLAUDE.md`.

---

## Context Recovery Rule -- CRITICAL

**After auto-compact or session continuation, ALWAYS read the relevant documentation files before continuing work:**

1. Read `docs/ARCHITECTURE.md` for system topology and design
2. Read `docs/DECISIONS.md` for the decision log
3. Read `docs/IMPLEMENTATION_PLAN.md` for current progress
4. Check git log and branch status to determine where you left off

This ensures continuity and prevents duplicated or missed work.

---

## Consistency Check -- MANDATORY

Before proposing any implementation approach, scan for conflicts with prior decisions:

1. Read `docs/DECISIONS.md` -- check resolved decisions and their rationale

If a conflict is found, present it to the user before proceeding. Do NOT silently override a documented decision.

---

## Workflow Skills

Three skills drive the development loop. Scope (Q/S/P) is **auto-detected** -- no upfront classification needed.

| Skill | When to invoke | What it does |
|-------|---------------|-------------|
| `/sync` | Session start, before major work | Pre-flight workspace check: branch state, remote tracking, dirty files, recent commits. Read-only. |
| `/design` | After brainstorming, before coding | Reads DECISIONS.md for conflicts, classifies scope (Q/S/P), outputs plan in scope-appropriate format. For P-scoped plans, writes to IMPLEMENTATION_PLAN.md. |
| `/done` | When work is complete | Auto-detects scope from workspace signals, validates (3-tier checklist), ships (commit/push/PR/CI), documents (CHANGELOG/DECISIONS). |

### Scope Reference

Scope is detected by `/design` (estimate) and `/done` (actual), based on workspace signals:

| Scope | Signals | Examples |
|-------|---------|---------|
| **Q** (Quick) | 1-3 files, < 50 lines, on main branch | Typo fix, config tweak, one-liner bug fix |
| **S** (Standard) | 4-20 files, 50-500 lines, feature branch | New feature, multi-file refactor, bug requiring investigation |
| **P** (Project) | 20+ files, 500+ lines, IMPLEMENTATION_PLAN.md updated | Multi-phase feature, architectural change, large migration |

---

## Build Cycle (TDD)

When implementing, follow this cycle regardless of scope:

1. Create code structure (interfaces, types)
2. Write tests
3. Write implementation
4. Write docstrings for public APIs; record non-trivial decisions in `docs/IMPLEMENTATION_PLAN.md`
5. Iterate (back to step 2 if needed)

---

## P (Project) Path -- Autonomous Implementation

For P-scoped work, execute phases autonomously per the plan in `docs/IMPLEMENTATION_PLAN.md`:

1. **Do NOT use `EnterPlanMode`** -- plan internally by reading docs and code, then execute directly
2. **For each phase:** research requirements, implement using TDD, run `/done`, then move to the next phase
3. **Only stop if truly blocked:** unresolvable test failures, architectural contradictions that need human judgment, or missing external dependencies
4. **After auto-compact:** re-read this directive, `docs/IMPLEMENTATION_PLAN.md`, and `MEMORY.md` to recover context. Check git log and branch status to determine where you left off. Resume from there.
5. **Skip steps that require user interaction:** PIRR warnings can be self-acknowledged with written justification. Code review findings that are Critical must be fixed; Warnings addressed if straightforward.
6. **Commit frequently:** after each sub-phase or logical unit of work, commit and push so progress is not lost to context limits
7. **Permission denial fallback:** If a tool is denied, work around it with a permitted alternative. If non-critical (e.g., CI check), skip and note it. If truly blocked, commit all progress, write a handoff note in the commit message, update IMPLEMENTATION_PLAN.md with status, and stop.
8. **Security hook workaround:** The `security-guidance` plugin blocks writes containing dangerous patterns. In test code, use alternative patterns (mock names, indirect references) to avoid triggering it.
9. **Continuous implementation:** After completing each phase, immediately start the next phase. Do not stop between phases. Continue until all planned phases are fully implemented or truly blocked.

### Pre-Implementation Readiness Review (PIRR)

**This step runs AFTER plan approval but BEFORE any code is written for a phase.**

- Invoke `.claude/agents/spec-readiness-reviewer.md` via Task tool (`subagent_type: "general-purpose"`)
- The agent reviews six dimensions: Acceptance Criteria Completeness, Spec-Plan Alignment, Prerequisites & Dependencies, Deployment Readiness, Architectural Decision Coverage, Validated Scenario Coverage
- Each dimension produces PASS, WARN, or FAIL

**Gate rules:**
- **Any FAIL** -> Block implementation. Fix the plan, specs, or decisions first. Re-run PIRR after fixes.
- **WARN items** -> Must be acknowledged with written justification before proceeding.
- **All PASS** -> Proceed to implementation.

---

## Failure Protocol

| Failure | Action |
|---|---|
| PIRR fails | Fix the plan, specs, or decisions. Re-run PIRR. Do NOT create feature branch until PIRR passes or all WARN items are acknowledged. |
| Validation fails on current code | Fix, amend commit, re-run `/done` |
| CI fails on current code | Fix, push, re-check |
| CI fails on pre-existing issue | Document separately, do not block current work |
| Code review flags architectural concern | Pause. Evaluate rework vs. follow-up issue |
| Acceptance criteria reveals previous phase regression | File as separate issue. Fix in current phase only if it's a direct regression |
| Multiple steps fail repeatedly | Stop. Reassess scope -- may need to split into smaller increments |

---

## Agent Reference

All custom agents are in `.claude/agents/` and use `subagent_type: "general-purpose"`.

| Agent File | Purpose |
|-----------|---------|
| `code-quality-validator.md` | Lint, format, type check |
| `test-coverage-validator.md` | Tests and coverage |
| `pr-writer.md` | Generate PR description |
| `code-reviewer.md` | Independent code review |
| `review-responder.md` | Handle automated reviewer comments |
| `docs-updater.md` | Verify and update documentation |
| `spec-readiness-reviewer.md` | Pre-implementation readiness review (PIRR) |
| `acceptance-criteria-validator.md` | Verify acceptance criteria |
| `implementation-tracker.md` | Verify plan matches reality |
| `agent-auditor.md` | Audit agent definitions against best practices |
| `security-auditor.md` | OWASP-based security analysis (read-only) |
| `refactoring-specialist.md` | SOLID/code smell analysis (read-only) |
| `output-evaluator.md` | LLM-as-Judge quality scoring |

---

## Skills Reference

Skills in `.claude/skills/`:

| Skill | Description |
|-------|-------------|
| `/sync` | Pre-flight workspace sync (read-only) |
| `/design` | Brainstorming to structured plan |
| `/done` | Universal completion (validate, ship, document) |
| `/edit-permissions` | Manage permission rules in settings.json |

---

## Hooks

Hook scripts in `.claude/hooks/` run automatically via settings.json:

| Hook | Event | Matcher | Behavior |
|------|-------|---------|----------|
| `dangerous-actions-blocker.sh` | PreToolUse | Bash | Blocks `rm -rf`, `sudo`, `DROP DATABASE`, `git push --force`, secrets in args. Exit 2 = block. |
| `unicode-injection-scanner.sh` | PreToolUse | Edit\|Write | Blocks zero-width chars, RTL overrides, ANSI escapes, null bytes, tag chars. Exit 2 = block. |
| `output-secrets-scanner.sh` | PostToolUse | Bash | Scans output for AWS/Anthropic/OpenAI/GitHub keys, JWTs, private keys, DB URLs. Warns via systemMessage. |

All hooks require `jq` for JSON parsing and degrade gracefully if jq is missing.

---

## Commands

2 slash commands in `.claude/commands/`:

| Command | Purpose |
|---------|---------|
| `/catchup` | Context restoration after `/clear`. Reads IMPLEMENTATION_PLAN.md, CHANGELOG.md, git history; recommends next steps. |
| `/security-audit` | 6-phase Python security scan (deps, secrets, code patterns, input validation, config, scoring). Outputs A-F grade. |

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

When the user says **"PCC"** or **"PCC now"**, run `/done`.
