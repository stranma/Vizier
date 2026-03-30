# Vizier

Province orchestration CLI for [Sultanate](../EFM/sultan/SULTANATE.md) -- a secure
multi-agent deployment platform.

Vizier creates provinces (isolated Docker containers) from firmans (container templates)
and berats (agent profiles), manages their lifecycle, and writes all state to Divan.

## Quick Start

```bash
uv sync --group dev     # install dependencies
vizier list             # list all provinces
vizier create <firman>  # create a province from a firman
vizier status <province>
vizier stop <province>
vizier destroy <province>
```

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for system design.

## Product Specs

- [SULTANATE.md](../EFM/sultan/SULTANATE.md) -- system overview
- [VIZIER_PRD_V3.md](../EFM/sultan/VIZIER_PRD_V3.md) -- Vizier product requirements
