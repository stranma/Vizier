# Vizier v3 Decision Log

Decisions prefixed DV3-. For v2 decisions (DV2-), see git tag `v2-archive`.

## DV3-1: Clean Start for v3

v2 codebase (FastMCP server + Hermes-as-Vizier) archived at git tag `v2-archive`.
v3 reimplements Vizier as a CLI tool per VIZIER_PRD_V3.md:

- CLI on host (not MCP server in Docker)
- State in Divan (not realm.json)
- Provinces are Docker containers created from firmans + berats
- Security delegated to Janissary/Sentinel (separate repo)

Development tooling (.claude/ agents, hooks, rules, skills) preserved -- orthogonal to
product architecture.
