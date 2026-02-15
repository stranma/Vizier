# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Security

- **Real-time scanning**: The `security-guidance` plugin runs automatically during code editing, warning about command injection, eval/exec, pickle deserialization, XSS, and os.system() usage
- **Secrets handling**: Never commit API keys, tokens, passwords, or private keys -- use environment variables or `.env` files (which are gitignored)
- **Unsafe operations**: Avoid `eval`, `exec`, `pickle.loads`, `subprocess(shell=True)`, and `yaml.load` without SafeLoader in production code. If required, document the justification in a code comment
- **Code review**: The code-reviewer agent (PCC step 9) checks for logic-level security issues (authorization bypass, TOCTOU, data exposure) that static pattern matching cannot catch

---

## Project Context

**Vizier** is an autonomous multi-agent work system using the Ottoman court metaphor:

| Role | Description |
|------|-------------|
| **Sultan** | Human operator (CEO/CTO) |
| **Vizier / EA** | Executive Assistant -- singleton, always-on, Opus-tier agent. Receives tasks, routes to projects, reports to Sultan |
| **Pasha** | Per-project orchestrator -- event-driven, owns project lifecycle |
| **Architect** | Decomposes tasks into specs using plugin-specific patterns |
| **Worker** | Fresh-context, one-spec-at-a-time executor (Ralph Wiggum pattern) |
| **Quality Gate** | Validates completed work via automated checks + LLM review |
| **Retrospective** | Analyzes failures, updates learnings and prompts |
| **Sentinel** | Deterministic security service (not an LLM agent) |

Core principles: fresh context per task, filesystem is the message bus, specs are the contract, human approval at boundaries, plugin extensibility.

---

## Repository Structure

This is a **monorepo** using uv workspaces:

```
vizier/
├── apps/                    # Executable applications (entry points)
│   ├── daemon/              # Vizier daemon (EA + event loop + Telegram bot)
│   └── cli/                 # Vizier CLI (init, register, start, status)
├── libs/                    # Reusable libraries (imported, not executed)
│   └── core/                # Core library (runtime, models, tools, plugins base)
├── plugins/                 # Domain-specific plugins
│   ├── software/            # Software development plugin
│   └── documents/           # Document production plugin
├── tests/                   # Root-level tests
├── scripts/                 # Development & maintenance scripts
├── docs/                    # Design documents (ARCHITECTURE, TECH_STACK, etc.)
└── pyproject.toml           # Root workspace config (uv, ruff, pyright, pytest)
```

### Packages

| Package | Path | Purpose |
|---------|------|---------|
| **vizier-core** | `libs/core/` | Core library: agent runtime, spec state machine, event loop, model router, plugin loader, Pydantic models |
| **vizier-daemon** | `apps/daemon/` | Server process: EA agent, project registry, agent lifecycle, Telegram bot (aiogram) |
| **vizier-cli** | `apps/cli/` | CLI tool: `vizier init`, `register`, `start`, `status` (click + rich) |
| **vizier-plugin-software** | `plugins/software/` | Software dev plugin: SoftwareCoder worker, SoftwareQualityGate |
| **vizier-plugin-documents** | `plugins/documents/` | Document plugin: DocumentWriter worker, DocumentReviewer gate |

---

## Development Commands

### Dependencies

- Create virtual environment: `uv venv`
- Install all dependencies: `uv sync --all-packages --group dev`

### Code Quality

- Lint and format: `uv run ruff check --fix . && uv run ruff format .`
- Type check: `uv run pyright`
- Run all tests: `uv run pytest`
- Run package tests: `uv run pytest libs/core/ -v` or `uv run pytest apps/daemon/ -v`

### Running Commands

Use `uv run` from the repo root for all commands:

```bash
uv run pytest                           # All tests
uv run pytest libs/core/ -v             # Core tests only
uv run pytest apps/daemon/ -v           # Daemon tests only
uv run pytest apps/cli/ -v              # CLI tests only
uv run pytest plugins/ -v               # All plugin tests
uv run ruff check .                     # Lint
uv run ruff format .                    # Format
uv run pyright                          # Type check
```

---

## Allowed Operations

**Read-only commands are always allowed without explicit permission:**
- `git status`, `git log`, `git diff`, `git branch`
- `ls`, `cat`, `head`, `tail`, `grep`, `find`
- `pytest` (running tests)
- `ruff check` (linting without --fix)
- Any command that only reads and does not modify files

---

## Code Style

Configuration lives in root `pyproject.toml`:

- **Formatter/Linter**: ruff (line-length: 120)
- **Type checker**: pyright (standard mode)
- **Docstrings**: reStructuredText format, PEP 257
- **No special Unicode characters** in code or output -- use plain ASCII (`[x]`, `[OK]`, `PASS`, `FAIL`)
- Use types everywhere possible
- No obvious inline comments

---

## Testing

- **Framework**: pytest
- **Test locations**: `tests/` (root), `libs/*/tests/`, `apps/*/tests/`, `plugins/*/tests/`
- **Markers**: `slow`, `integration`, `production`
- **Coverage**: `uv run pytest --cov --cov-report=term-missing`
- **LLM mocking**: Mock `litellm.completion()` in all automated tests. No API credits in CI.

---

## Version Management

All packages should maintain synchronized MAJOR.MINOR versions. Patch versions can differ.

```bash
# Check versions across packages
python scripts/check_versions.py
```

| Client | Server | Compatible? |
|--------|--------|-------------|
| 1.2.3  | 1.2.7  | YES |
| 1.2.3  | 1.3.0  | NO |

---

## Context Recovery Rule -- CRITICAL

**After auto-compact or session continuation, ALWAYS read the relevant documentation files before continuing work:**

1. Read `docs/IMPLEMENTATION_PLAN.md` for current progress and phase status
2. Read `docs/ARCHITECTURE.md` for system topology, plugin system, roles & permissions
3. Read `docs/TECH_STACK.md` for dependency choices and rationale
4. Read `docs/FILE_PROTOCOL.md` for spec format, state machine, filesystem conventions
5. Read `docs/AGENT_SPECS.md` for agent role details
6. Read any package-specific documentation relevant to the task

This ensures continuity and prevents duplicated or missed work.

---

## Development Methodology

**Test-Driven Development Process** -- MANDATORY for all new development:

1. **Create code structure** -- Define classes, functions, constants with proper type annotations
2. **Write unit tests** -- Test the interface and expected behavior before implementation
3. **Write implementation** -- Implement the actual functionality to pass tests
4. **Iterate** -- If not finished, return to step 2 for next increment
5. **Run integration tests** -- Validate complete workflow after unit tests pass
6. **Run Phase Completion Checklist** -- See below. This is NOT optional.

**Key Principles:**
- Structure first, tests second, implementation third
- All tests must pass before moving to next increment
- Integration tests validate the complete workflow

**CRITICAL -- Phase Completion Checklist Integration:**
- Every implementation plan MUST explicitly include the Phase Completion Checklist steps as part of each phase's deliverables
- When writing plans (in plan mode), the "Phase Completion Steps" section MUST reference the checklist by name and list all 11 steps (0-10)
- When executing a phase, the checklist MUST be run IN FULL before proceeding to the next phase -- do NOT batch them all to the end
- If a plan does not mention the Phase Completion Checklist, the plan is INCOMPLETE and must be revised

---

## Phase Completion Checklist (PCC) -- MANDATORY

**After completing EACH implementation phase, run ALL checks in order.**
**Do NOT skip steps. Do NOT defer them. Do NOT batch to the end.**

### Agent Reference -- CRITICAL

The PCC uses custom agents defined in `.claude/agents/`. These are NOT built-in `subagent_type` values.
To invoke a custom agent, use the `Task` tool with `subagent_type: "general-purpose"` and copy the agent's
full system prompt (the markdown body from its `.md` file) into the `prompt` parameter. Alternatively,
ask Claude to "use the [agent-name] agent" and it will delegate automatically.

**Do NOT use `feature-dev:code-reviewer`** -- always use the custom `.claude/agents/code-reviewer.md`.

| PCC Step | Agent File | Task subagent_type | Purpose |
|----------|-----------|---------------------|---------|
| 3a | `.claude/agents/code-quality-validator.md` | `general-purpose` | Lint, format, type check (auto-fixes) |
| 3b | `.claude/agents/test-coverage-validator.md` | `general-purpose` | Run tests, check coverage |
| 3c | `.claude/agents/acceptance-criteria-validator.md` | `general-purpose` | Verify acceptance criteria |
| 4 | Built-in `Plan` agent | `Plan` | Check implementation plan accuracy |
| 5 | `.claude/agents/docs-updater.md` | `general-purpose` | Update IMPLEMENTATION_PLAN.md, CHANGELOG.md |
| 7 | `.claude/agents/pr-writer.md` | `general-purpose` | Generate PR description |
| 9 | `.claude/agents/code-reviewer.md` | `general-purpose` | Independent code review |
| 9 | `.claude/agents/review-responder.md` | `general-purpose` | Respond to automated reviewer comments |
| -- | `.claude/agents/implementation-tracker.md` | `general-purpose` | Verify plan matches reality |

---

### 0. Sync with Remote
- Run `git fetch origin` and check for divergence from the base branch
- If behind, pull or rebase before proceeding
- **If rebase introduces conflicts: STOP. Resolve all conflicts before continuing.**

### 1. Pre-Commit Hygiene
Before committing, verify the working tree is clean of development artifacts:
- No leftover `TODO`, `FIXME`, `HACK`, or `XXX` markers that shouldn't ship
- No debug prints, `console.log`, `breakpoint()`, or commented-out code blocks
- No hardcoded test values, secrets, or localhost URLs
- If any are found, fix them before proceeding

### 2. Commit & Push
- Commit all changes with a descriptive message
- Push to remote repository
- Never leave uncommitted work at end of phase

### 3. Parallel Validation (run as concurrent sub-agents)

Spawn the following **three agents in parallel**. Gate on ALL completing successfully.

#### 3a. Code Quality Agent (`.claude/agents/code-quality-validator.md`)
- Invoke via Task tool: `subagent_type: "general-purpose"` with the agent's system prompt
- Runs linting (`ruff check`), formatting (`ruff format --check`), type checking (`pyright`)
- Auto-fixes issues where possible
- Fix any remaining issues, amend the commit, and re-push if needed

#### 3b. Test Agent (`.claude/agents/test-coverage-validator.md`)
- Invoke via Task tool: `subagent_type: "general-purpose"` with the agent's system prompt
- Verifies all tests pass, code coverage is adequate, no regressions introduced

#### 3c. Acceptance Criteria Agent (`.claude/agents/acceptance-criteria-validator.md`)
- Invoke via Task tool: `subagent_type: "general-purpose"` with the agent's system prompt
- Verify ALL acceptance criteria from the **current phase AND all previous phases** (cumulative)
- For automatable criteria, run **actual checks** -- do not rely on self-assessment alone
- For non-automatable criteria, document how each was verified
- Document any failing criteria -- these MUST be fixed before proceeding

### 4. Implementation Plan Check Agent (built-in `Plan` or `.claude/agents/implementation-tracker.md`)
- Use the built-in `Plan` agent (`subagent_type: "Plan"`) to verify `IMPLEMENTATION_PLAN.md`
- Alternatively, use `.claude/agents/implementation-tracker.md` via `subagent_type: "general-purpose"`
- Check documented status matches actual implementation
- Update plan document if discrepancies found
- Verify all phase deliverables are actually complete

### 5. Documentation Update Agent (`.claude/agents/docs-updater.md`) -- CRITICAL
**This step is often missed. Invoke via Task tool: `subagent_type: "general-purpose"` with the docs-updater system prompt.**

The agent should update:

- **`docs/IMPLEMENTATION_PLAN.md`**:
  - Change phase status from "In Progress" to "Complete"
  - Update status summary table
  - Mark all task checkboxes as `[x]`
- **`docs/CHANGELOG.md`** (running draft):
  - Append user-facing changes for this phase
  - Use [Keep a Changelog](https://keepachangelog.com/) format
  - Focus on: Added features, Changed behavior, Bug fixes

**After the agent runs, review its output for accuracy BEFORE committing doc updates.**

### 6. Version Bump Changelog (if applicable)
**When bumping MINOR or MAJOR versions, finalize changelogs:**
- Consolidate running changelog entries
- Add: Breaking changes, Migration notes, Upgrade instructions

### 7. Create Pull Request (`.claude/agents/pr-writer.md`)
- Use the pr-writer agent (`subagent_type: "general-purpose"` with the agent's system prompt) to generate the PR description
- Create a PR from the feature branch to the base branch using `gh pr create`
- Verify the PR has no merge conflicts before proceeding
- If working directly on the base branch, skip this step

### 8. Verify CI Pipeline
- Check that all CI checks pass on the PR using `gh pr checks <pr-number>`
- If any checks fail, fix the issues, push, and re-check
- Do not proceed until all checks are green

### 9. Code Review (`.claude/agents/code-reviewer.md` or `.claude/agents/review-responder.md`)
- If an automated reviewer (e.g., CodeRabbit) is configured:
  - Invoke `.claude/agents/review-responder.md` via Task tool (`subagent_type: "general-purpose"`) to triage and handle comments
  - Apply straightforward fixes automatically
  - Flag architectural concerns for human review
  - Push fixes and wait for re-review
- If no automated reviewer is configured:
  - Invoke `.claude/agents/code-reviewer.md` via Task tool (`subagent_type: "general-purpose"` with the code-reviewer system prompt)
  - Do NOT use the built-in `feature-dev:code-reviewer` -- always use the custom `.claude/agents/code-reviewer.md`
  - Fix any Critical issues before proceeding
  - Address Warnings if straightforward; otherwise document as known debt
  - Suggestions are optional -- apply at your discretion

### 10. Phase Handoff Note
Write a brief (2-5 sentence) handoff summary:
- What was completed and any deviations from the plan
- Open questions or known risks for the next phase
- Dependencies or prerequisites the next phase should be aware of
- Any technical debt introduced intentionally (and why)

---

## Failure & Rollback Protocol

If a step fails, follow this decision tree:

| Failure | Action |
|---|---|
| **Steps 3a/3b/3c fail on current phase's code** | Fix the issue, amend commit, re-run from Step 2 |
| **Step 3c reveals a previous phase's criteria now failing** | File as a separate bug/issue. Fix in current phase only if it's a direct regression |
| **Step 8 (CI) fails on pre-existing issue** | Document the issue, file separately, do NOT block the current phase |
| **Step 8 (CI) fails on current phase's code** | Fix, push, re-run from Step 8 |
| **Step 9 (code review) flags an architectural concern** | Pause. Evaluate whether it requires rework (go back to Step 2) or can be addressed as follow-up |
| **Multiple steps fail repeatedly** | Stop. Reassess the phase scope -- it may need to be split into smaller increments |

---

## Changelog Maintenance -- MANDATORY

**Changelogs must be updated for every MINOR or MAJOR version bump.**

### When to Update

| Version Change | Changelog Required? |
|----------------|---------------------|
| Patch (1.0.0 -> 1.0.1) | Optional (bug fixes) |
| Minor (1.0.0 -> 1.1.0) | **YES** |
| Major (1.0.0 -> 2.0.0) | **YES** |

### Format (Keep a Changelog)

```markdown
## [X.Y.Z] - YYYY-MM-DD

### Added
- New features (describe user benefit, not implementation)

### Changed
- Changes to existing functionality

### Deprecated
- Features to be removed in future

### Removed
- Features removed in this release

### Fixed
- Bug fixes

### Migration
- Required code changes for users upgrading
```

### What to Include

**DO include:** New API fields/parameters, changed defaults, performance improvements, breaking changes with migration steps, new features.

**DON'T include:** Internal refactoring, CI/CD changes, infrastructure updates (unless they affect API), test improvements.

---

## Planning Requirement

### Consistency Check -- MANDATORY

Before proposing any implementation approach, scan for conflicts with prior decisions:

1. Read `docs/IMPLEMENTATION_PLAN.md` -- check Decisions & Trade-offs tables for entries that contradict the current request
2. Read `docs/ARCHITECTURE.md` -- check for constraints or conventions that conflict with the proposed approach
3. Read `docs/DECISIONS.md` -- check resolved decisions and their rationale
4. Review relevant sections of `CLAUDE.md` -- check for constraints or conventions that conflict with the proposed approach

If a conflict is found, present it to the user before proceeding:
- Quote the specific prior decision or constraint
- Explain the contradiction
- Ask whether to proceed with the new direction (updating docs to reflect the change) or adjust the approach to align with the existing decision

Do NOT silently override a documented decision. Deliberate pivots are fine -- undocumented ones are not.

### Phase Completion Steps

When creating implementation plans (in plan mode), ALWAYS include a "Phase Completion Steps" section that explicitly states:

> After each phase, execute the Phase Completion Checklist (steps 0-10 from CLAUDE.md): sync remote, pre-commit hygiene, commit & push, parallel validation (`.claude/agents/code-quality-validator.md` + `.claude/agents/test-coverage-validator.md` + `.claude/agents/acceptance-criteria-validator.md` -- all invoked via `subagent_type: "general-purpose"`), Plan agent or `.claude/agents/implementation-tracker.md` for implementation check, `.claude/agents/docs-updater.md` for documentation + changelog, create PR with `.claude/agents/pr-writer.md`, verify CI, code review with `.claude/agents/code-reviewer.md` (NOT `feature-dev:code-reviewer`) or `.claude/agents/review-responder.md`, phase handoff note. Consult the Failure & Rollback Protocol if any step fails. See the Agent Reference table in the PCC section for exact invocation details.

This ensures the checklist is visible in the plan and not forgotten during execution.
