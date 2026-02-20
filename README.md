# Vizier

Autonomous multi-agent work system, built on OpenClaw.

Vizier receives high-level tasks from humans, decomposes them into actionable specs, executes them through specialized agents, and reports back. It uses the **Ottoman court metaphor**: the Sultan (human) speaks to the Vizier (main agent), who delegates to Pashas (per-project orchestrators), who manage inner agents (Scout, Architect, Worker, Quality Gate, Retrospective).

## Architecture

**OpenClaw** provides the runtime: multi-channel messaging (Telegram, WhatsApp, Discord, Web UI, mobile), session management, tool infrastructure, and memory. **Vizier's MCP server** provides the domain intelligence: spec lifecycle, Sentinel security, DAG scheduling, quality gates, and plugin extensibility.

```
Sultan (any channel)
  -> OpenClaw Gateway
    -> Vizier (main agent, Opus, persistent session)
      -> Pasha-{project} (sub-session per project)
        -> Scout, Architect, Worker, Quality Gate, Retrospective
      -> Vizier MCP Server (FastMCP, Python)
        -> Spec tools, Sentinel, Orchestration, DAG, Evidence, Plugins, Budget
```

See `docs/ARCHITECTURE.md` for the full specification.

## Project Structure

| Directory | Purpose |
|-----------|---------|
| `vizier-mcp/` | FastMCP server -- all Vizier domain logic |
| `openclaw/` | OpenClaw workspace config (SOUL.md files, agent definitions) |
| `docs/` | Architecture spec, decision log, changelog |

## Development

```bash
uv sync --all-packages --group dev    # Install dependencies
uv run pytest vizier-mcp/ -v          # Run MCP server tests
uv run ruff check . && uv run ruff format --check .  # Lint
uv run pyright                        # Type check
```

## License

MIT
