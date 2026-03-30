# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Security

- **Real-time scanning**: The `security-guidance` plugin warns about command injection, unsafe deserialization, XSS, and dangerous shell usage
- **Hooks**: Security hooks in `.claude/hooks/` run automatically (see `docs/DEVELOPMENT_PROCESS.md`)
- **Secrets handling**: Never commit API keys, tokens, passwords, or private keys -- use environment variables or `.env` files (gitignored)
- **Unsafe operations**: Avoid unsafe deserialization, shell injection, `yaml.load` without SafeLoader in production code

---

## Project Context

**Vizier** is the province orchestration CLI for **Sultanate** -- a secure multi-agent
deployment platform using the Ottoman court metaphor. See
[SULTANATE.md](../EFM/sultan/SULTANATE.md) and
[VIZIER_PRD_V3.md](../EFM/sultan/VIZIER_PRD_V3.md) for full product specs.

| Term | Role |
|------|------|
| **Sultan** | Human operator -- decides, approves, overrides |
| **Vizier** | Province orchestration CLI -- creates provinces, manages realm, writes to Divan |
| **Janissary** | Security infrastructure -- egress proxy, credential injection (separate repo) |
| **Sentinel** | Security advisory agent -- secret management, alerts (ships with Janissary) |
| **Divan** | Shared state store -- province registry, grants, audit log (ships with Janissary) |
| **Province** | Isolated Docker container -- one agent per province |
| **Pasha** | Agent inside a province -- runs tasks, reports to Sultan |
| **Firman** | Container template -- Docker image, workspace bootstrap, runtime startup |
| **Berat** | Agent profile -- soul, instructions, tools, security policy |

**Architecture:** Vizier is a CLI tool running on the host as a dedicated `vizier` user
with Docker group access. It creates provinces (Docker containers) from firmans + berats,
manages their lifecycle, and writes all state to Divan (HTTP API). Vizier does NOT handle
security (Janissary), secrets (Sentinel), or agent runtime (Hermes/other).

---

## Development Commands

```bash
uv venv && uv sync --group dev              # Setup
uv run pytest                                # All tests
uv run ruff check --fix . && uv run ruff format .  # Lint + format
uv run pyright                               # Type check
```

---

## Code Style

Configuration lives in root `pyproject.toml`:

- **Formatter/Linter**: ruff (line-length: 120)
- **Type checker**: pyright (standard mode)
- **Docstrings**: reStructuredText format, PEP 257
- **No special Unicode characters** -- use plain ASCII (`[x]`, `[OK]`, `PASS`, `FAIL`)
- Use types everywhere; no obvious inline comments

---

## Context Recovery Rule -- CRITICAL

After auto-compact or session continuation, read:

1. `docs/ARCHITECTURE.md` -- system topology and design
2. `docs/DECISIONS.md` -- decision log
3. `docs/IMPLEMENTATION_PLAN.md` -- current progress
4. Check `git log` and branch status to determine where you left off

---

## Development Process

Three workflow skills drive the development loop (see `docs/DEVELOPMENT_PROCESS.md`):

| Skill | When | What it does |
|-------|------|-------------|
| `/sync` | Session start, before major work | Pre-flight workspace check (branch, remote, dirty files) |
| `/design` | After brainstorming, before coding | Crystallizes ideas into a plan, auto-classifies scope (Q/S/P) |
| `/done` | When work is complete | Validates, ships, and documents -- auto-detects actual scope |

All agents are in `.claude/agents/` and use `subagent_type: "general-purpose"`. Do NOT use `feature-dev:code-reviewer`.

**PCC shorthand**: When "PCC" or "PCC now" is mentioned, run `/done`.
