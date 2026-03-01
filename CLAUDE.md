# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Security

- **Real-time scanning**: The `security-guidance` plugin warns about command injection, unsafe deserialization, XSS, and dangerous shell usage
- **Hooks**: 5 security/productivity hooks in `.claude/hooks/` run automatically (see `docs/DEVELOPMENT_PROCESS.md`)
- **Secrets handling**: Never commit API keys, tokens, passwords, or private keys -- use environment variables or `.env` files (gitignored)
- **Unsafe operations**: Avoid unsafe deserialization, shell injection, `yaml.load` without SafeLoader in production code

---

## Project Context

**Vizier** is an autonomous multi-agent work system using the Ottoman court metaphor, built on **OpenClaw** as its runtime.

| Role | Description |
|------|-------------|
| **Sultan** | Human operator (CEO/CTO) |
| **Vizier** | Grand Vizier -- main agent, singleton, Opus-tier |
| **Pasha** | Per-project orchestrator |
| **Scout** | Prior art researcher |
| **Architect** | Decomposes tasks into specs |
| **Worker** | Fresh-context, one-spec-at-a-time executor |
| **Quality Gate** | Validates completed work |
| **Retrospective** | Analyzes failures, updates learnings |
| **Sentinel** | Deterministic security service (not an LLM agent) |

Core principles: fresh context per task, filesystem is the message bus (via MCP server), specs are the contract, human approval at boundaries, plugin extensibility.

**Architecture:** Vizier's domain intelligence is exposed as a **FastMCP server** (`vizier-mcp/`) that OpenClaw agents call via tool use. See `docs/ARCHITECTURE.md` and `docs/DECISIONS.md`.

---

## Development Commands

```bash
uv venv && uv sync --all-packages --group dev   # Setup
uv run pytest                                    # All tests
uv run pytest vizier-mcp/ -v                     # MCP server tests
uv run ruff check --fix . && uv run ruff format .  # Lint + format
uv run pyright                                   # Type check
```

---

## Code Style

Configuration lives in root `pyproject.toml`:

- **Formatter/Linter**: ruff (line-length: 120)
- **Type checker**: pyright (standard mode)
- **Docstrings**: reStructuredText format, PEP 257
- **No special Unicode characters** -- use plain ASCII (`[x]`, `[OK]`, `PASS`, `FAIL`)
- Use types everywhere; no obvious inline comments
- **LLM mocking**: Mock Anthropic client for Sentinel Haiku calls in all automated tests. No API credits in CI.

---

## Context Recovery Rule -- CRITICAL

After auto-compact or session continuation, read:

1. `docs/ARCHITECTURE.md` -- system topology, MCP server design, Sentinel
2. `docs/DECISIONS.md` -- decision log (D1-D62+)
3. `docs/IMPLEMENTATION_PLAN.md` -- current progress
4. Check `git log` and branch status to determine where you left off

---

## Development Process

Classify each task, then follow the matching path in `docs/DEVELOPMENT_PROCESS.md`:

| Path | When | Examples |
|------|------|---------|
| **Q** (Quick) | Trivial, single-location | Typo fix, config tweak, one-liner |
| **S** (Standard) | One session, clear scope | New feature, multi-file refactor |
| **P** (Project) | Phased, multi-session | Architectural change, large migration |

All agents are in `.claude/agents/` and use `subagent_type: "general-purpose"`. Do NOT use `feature-dev:code-reviewer`.

**PCC shorthand**: When "PCC" or "PCC now" is mentioned, execute S.5 through S.7 per `docs/DEVELOPMENT_PROCESS.md`.
