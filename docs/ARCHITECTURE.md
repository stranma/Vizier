# Vizier v3 Architecture

> For shared glossary, deployment model, and component overview see
> [SULTANATE.md](../../EFM/sultan/SULTANATE.md).

## System Position

Vizier is one component in the Sultanate system:

```text
Sultan (human)
  |
  +-- Vizier CLI (this repo) -- province lifecycle, realm management
  |     |
  |     +-- writes to --> Divan (shared state store, ships with Janissary)
  |     +-- creates   --> Provinces (Docker containers)
  |
  +-- Janissary (separate repo) -- egress proxy, credential injection
  |     +-- Sentinel -- secret management, alert contextualization
  |     +-- Divan -- province registry, grants, audit log
  |
  +-- Provinces
        +-- Pasha (agent inside province)
        +-- Firman (container template)
        +-- Berat (agent profile)
```

## Vizier Internals

```text
vizier CLI
  |
  +-- cli.py          Click CLI entry point
  +-- province.py     Province lifecycle (create, start, stop, destroy)
  +-- divan.py        Divan HTTP client (read/write province state)
  +-- docker.py       Docker container management (subprocess-based)
  +-- models.py       Pydantic models (Province, Firman, Berat)
  +-- config.py       Configuration (Divan URL, Docker network settings)
```

### Key Design Decisions

1. **CLI, not MCP server.** Vizier is invoked directly by Sultan or scripts.
   No agent runtime dependency.

2. **Divan is the state store.** Vizier writes province state to Divan via HTTP.
   No local state files (no realm.json).

3. **Docker via subprocess.** Container management uses `docker` CLI commands
   via subprocess (no Docker SDK dependency). Safe execution via
   `subprocess.run()` with list args (no shell).

4. **Internal-only Docker network.** Provinces have no direct internet access.
   All egress through Janissary's HTTP proxy.

5. **Firman + Berat = Province.** A province is created from the combination
   of a container template (firman) and an agent profile (berat).

## Province Creation Flow

```text
1. Sultan: vizier create <firman> --berat <berat> --name <name>
2. Vizier reads firman spec (Docker image, bootstrap, runtime)
3. Vizier reads berat spec (soul, tools, security policy)
4. Vizier creates Docker container:
   --> internal Docker network only (no external route)
   --> HTTP_PROXY / HTTPS_PROXY pointing to Janissary
   --> workspace bootstrapped per firman
   --> agent runtime started per firman
5. Vizier writes to Divan:
   --> province ID, container IP, status=creating, firman, berat
6. Sentinel reads new province from Divan:
   --> provisions grants from berat security policy
   --> sets up whitelist from berat defaults
7. Vizier updates Divan: status=running
```

## Province Lifecycle States

```text
creating --> running --> stopped --> destroying
    |           |           |
    +-- failed  +-- failed  +-- failed
```

- **creating**: container being instantiated from firman
- **running**: container up, agent reachable
- **stopped**: container exists but not running
- **failed**: error state, operator attention required
- **destroying**: teardown in progress
