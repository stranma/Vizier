# Vizier

Autonomous multi-agent work system.

Vizier receives high-level tasks from humans, decomposes them into actionable specs, executes them through specialized agents, and reports back. It operates on a server, works on multiple projects in parallel, and communicates with humans through an Executive Assistant (EA) agent.

## Architecture

The system uses the **Ottoman court metaphor**:

- **Sultan** -- Human operator
- **Vizier / EA** -- Executive Assistant (singleton, always-on)
- **Pasha** -- Per-project orchestrator
- **Architect** -- Task decomposer
- **Worker** -- Spec executor (fresh context per task)
- **Quality Gate** -- Work validator

See `docs/ARCHITECTURE.md` for the full system topology.

## Packages

| Package | Path | Description |
|---------|------|-------------|
| `vizier-core` | `libs/core/` | Core library (runtime, models, plugin base) |
| `vizier-daemon` | `apps/daemon/` | Server process (EA + event loop + Telegram bot) |
| `vizier-cli` | `apps/cli/` | CLI tool (`vizier init`, `register`, `start`, `status`) |
| `vizier-plugin-software` | `plugins/software/` | Software development plugin |
| `vizier-plugin-documents` | `plugins/documents/` | Document production plugin |

## Development

```bash
# Install dependencies
uv sync --group dev

# Run tests
uv run pytest

# Lint and format
uv run ruff check --fix . && uv run ruff format .

# Type check
uv run pyright
```

## License

MIT
