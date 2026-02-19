# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Autonomous Implementation Directive

**Mode: Fully autonomous. Do NOT wait for user approval between phases.**

Work through the implementation plan (`docs/IMPLEMENTATION_PLAN.md`) phase by phase:

1. **Do NOT use `EnterPlanMode`** -- plan internally by reading docs and code, then execute directly
2. **For each phase:** research requirements, implement using TDD (structure -> tests -> code), run quality checks (lint, format, typecheck, tests), commit directly to master, then move to the next phase
3. **Only stop if truly blocked:** unresolvable test failures, architectural contradictions that need human judgment, or missing external dependencies
4. **After auto-compact:** re-read this directive, `docs/IMPLEMENTATION_PLAN.md`, and `MEMORY.md` to recover context. Check git log and branch status to determine where you left off. Resume from there.
5. **Commit directly to master:** No feature branches, no PRs. Commit and push directly to master after each sub-phase or logical unit of work. This keeps things simple and avoids context loss.
6. **Commit frequently:** after each sub-phase or logical unit of work, commit and push so progress is not lost to context limits
7. **Permission denial fallback:** If a tool is denied, work around it with a permitted alternative. If non-critical (e.g., CI check), skip and note it. If truly blocked, commit all progress, write a handoff note in the commit message, update IMPLEMENTATION_PLAN.md with status, and stop.
8. **Security hook workaround:** The `security-guidance` plugin blocks writes containing dangerous patterns. In test code, use alternative patterns (mock names, indirect references) to avoid triggering it.
9. **Continuous implementation:** After completing each phase, immediately start the next phase. Do not stop between phases. Continue until all planned phases (13-22) are fully implemented or truly blocked.

### Simplified Phase Completion (replaces full PCC for now)

For each phase:
1. Run quality checks: `uv run ruff check . && uv run ruff format --check . && uv run pyright`
2. Run tests: `uv run pytest libs/core/ -q && uv run pytest apps/daemon/ -q && uv run pytest apps/cli/ -q`
3. Fix any failures
4. Commit to master with descriptive message
5. Update `docs/IMPLEMENTATION_PLAN.md` status
6. Move to next phase

Skip: PIRR, feature branches, PRs, CI verification, code review agents, docs-updater agent. These add overhead without value during rapid prototyping.

---

## Security

- **Real-time scanning**: The `security-guidance` plugin runs automatically during code editing
- **Secrets handling**: Never commit API keys, tokens, passwords, or private keys -- use environment variables or `.env` files (which are gitignored)
- **Unsafe operations**: Avoid dangerous patterns in production code (shell injection, unsafe deserialization, unvalidated YAML loading). If required, document the justification in a code comment.

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

**Agent architecture (post-D46 reset):** All agents are Claude API instances using `anthropic.Anthropic` with `client.messages.create(tools=...)` (D47). Communication via typed Pydantic messages (D54). See `docs/AGENT_PROTOCOL.md` for the 3-contract protocol and `docs/AGENT_SPECS.md` for per-agent details.

---

## Repository Structure

This is a **monorepo** using uv workspaces:

```
vizier/
  apps/                    # Executable applications (entry points)
    daemon/                # Vizier daemon (EA + event loop + Telegram bot)
    cli/                   # Vizier CLI (init, register, start, status)
  libs/                    # Reusable libraries (imported, not executed)
    core/                  # Core library (runtime, models, tools, plugins base)
  plugins/                 # Domain-specific plugins
    software/              # Software development plugin
    documents/             # Document production plugin
  tests/                   # Root-level tests
  scripts/                 # Development and maintenance scripts
  docs/                    # Design documents (ARCHITECTURE, TECH_STACK, etc.)
  pyproject.toml           # Root workspace config (uv, ruff, pyright, pytest)
```

### Packages

| Package | Path | Purpose |
|---------|------|---------|
| **vizier-core** | `libs/core/` | Core library: agent runtime, spec state machine, event loop, model router, plugin loader, Pydantic models |
| **vizier-daemon** | `apps/daemon/` | Server process: EA agent, project registry, agent lifecycle, Telegram bot (aiogram) |
| **vizier-cli** | `apps/cli/` | CLI tool: `vizier init`, `register`, `start`, `status` (click + rich) |
| **vizier-plugin-software** | `plugins/software/` | Software dev plugin: write-set patterns, criteria, system prompts |
| **vizier-plugin-documents** | `plugins/documents/` | Document plugin: write-set patterns, criteria, system prompts |

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

## Shell Command Style

- **Always use absolute paths** instead of `cd /path && command` chains
- **Use `TaskOutput` tool** to read background task results instead of `tail`/`cat` on task output files
- **Do not use `git -C <path>`** -- run git commands from the working directory

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
- **LLM mocking**: Mock `anthropic.Anthropic` client in all automated tests. No API credits in CI.

---

## Context Recovery Rule -- CRITICAL

**After auto-compact or session continuation, ALWAYS read the relevant documentation files before continuing work:**

1. Read `docs/IMPLEMENTATION_PLAN.md` for current progress and phase status
2. Read `docs/AGENT_PROTOCOL.md` for the 3-contract communication protocol
3. Read `docs/AGENT_SPECS.md` for agent role details, tools, and messages
4. Read `docs/ARCHITECTURE.md` for system topology, plugin system, roles & permissions
5. Read `docs/FILE_PROTOCOL.md` for spec format, state machine, filesystem conventions

This ensures continuity and prevents duplicated or missed work.

---

## Development Methodology

**Test-Driven Development Process** -- MANDATORY for all new development:

1. **Create code structure** -- Define classes, functions, constants with proper type annotations
2. **Write unit tests** -- Test the interface and expected behavior before implementation
3. **Write implementation** -- Implement the actual functionality to pass tests
4. **Document as you go** -- Add docstrings to public APIs, inline comments for non-obvious logic
5. **Iterate** -- If not finished, return to step 2 for next increment
6. **Run quality checks** -- lint, format, typecheck, all tests pass
7. **Commit to master** -- Descriptive commit message, push

---

## Consistency Check -- MANDATORY

Before proposing any implementation approach, scan for conflicts with prior decisions:

1. Read `docs/IMPLEMENTATION_PLAN.md` -- check Decisions and Trade-offs tables
2. Read `docs/DECISIONS.md` -- check resolved decisions and their rationale (D1-D59)
3. Read `docs/AGENT_PROTOCOL.md` -- check the 3 contracts for consistency

If a conflict is found, present it to the user before proceeding. Do NOT silently override a documented decision.
