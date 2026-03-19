# Vizier

Autonomous multi-agent work system, built on Hermes.

Vizier manages **provinces** -- isolated work domains created from reusable **firmans** (templates). Each province has its own Pasha, workspace, credentials, outbound access policy, and GitHub output. The Sultan (human operator) steers via Telegram; work output is a GitHub pull request.

## Architecture

**Hermes Agent** (Nous Research) provides the runtime: agent sessions, Telegram gateway, tool calling, sub-agent delegation, and MCP integration. **Vizier's MCP server** provides the domain intelligence: realm management, container lifecycle, and (in later phases) province orchestration, Sentinel security, and secret brokerage.

```
Sultan (Telegram + GitHub)
  -> Vizier (Hermes agent, Opus, reactive realm manager)
    -> Provinces (isolated work domains from firmans)
      -> Pasha (Hermes agent per province)
        -> Tools, workspace, scoped credentials, security boundary
    -> Vizier MCP Server (FastMCP, Python)
      -> Realm tools, Container tools, Health endpoints
  -> Sentinel Core (deterministic security enforcement)
```

See `docs/ARCHITECTURE.md` and `docs/PRD_V2.md` for the full specification.

## Project Structure

| Directory | Purpose |
|-----------|---------|
| `vizier-mcp/` | FastMCP server -- Vizier domain logic (realm, containers, health) |
| `hermes/` | Hermes Agent config -- Dockerfile, config.yaml, SOUL.md, AGENTS.md |
| `docs/` | Architecture, PRD, implementation plan, decision log, changelog |
| `tests/` | Root-level tests (agents, hooks, permissions, Hermes config) |

## Quick Start

```bash
# Development
uv sync --all-packages --group dev    # Install dependencies
uv run pytest vizier-mcp/ -v          # Run MCP server tests
uv run pytest tests/ -v               # Run tooling + Hermes config tests
uv run ruff check . && uv run ruff format --check .  # Lint
uv run pyright                        # Type check

# Deployment (Docker Compose)
cp .env.example .env                  # Fill in API keys and Telegram config
docker compose up -d                  # Starts vizier-mcp + hermes-vizier
```

## License

MIT
