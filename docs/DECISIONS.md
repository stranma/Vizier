# Vizier v2 Decision Log

Decisions prefixed DV2- to distinguish from v1 (D1-D88+).

## DV2-1: Repository Scope -- Vizier + Sentinel Only

This repository contains Vizier and Sentinel only. Pashas run inside devcontainers but their internals are out of scope. We define the interface (manifest contract) for launching, monitoring, and killing them.

## DV2-2: Sentinel = Two Layers

- **SentinelGate**: Deterministic MCP proxy (Go binary). CEL-based policies, quotas, RBAC, full audit log. Pre-action gate.
- **Sentinel Agent**: OpenClaw LLM agent. Reviews audit logs, evaluates cost reasonableness, detects data leaks, alerts Sultan.

Focus is cost control and data leak detection, not destruction prevention.

## DV2-3: Sultan Talks to Both Agents via Telegram

- Vizier: main conversation channel (task delegation, status, briefings)
- Sentinel: separate channel (read-only alerts, direct queries)

## DV2-4: Pashas Run Inside Devcontainers

Container = security boundary. Same devcontainer model from v1 (D88). Pasha + Workers isolated per project.

## DV2-5: Modular Pasha via Manifest

Pasha defined by project template, not by Vizier. Contract via `.pasha/manifest.json`:

```json
{
  "name": "project-pasha",
  "version": "1.0.0",
  "runtime": "openclaw",
  "entrypoint": ".pasha/launch.sh",
  "soul": ".pasha/SOUL.md",
  "status_file": ".pasha/status.json",
  "capabilities": [],
  "env_requires": []
}
```

Vizier reads manifest, writes task.json, executes entrypoint, polls status_file.

## DV2-6: v1 Docs Archived

v1 docs (ARCHITECTURE.md, IMPLEMENTATION_PLAN.md, DECISIONS.md) moved to `docs/v1/`. Fresh v2 versions created from PRD v2 discussion.

## DV2-7: Phase 2 -- Agent Control Tools

Four new MCP tools for Pasha lifecycle and knowledge linking:
- `pasha_launch`: manifest-based launch with task + acceptance criteria
- `pasha_status`: poll Pasha state with process liveness check
- `agent_kill`: terminate Pasha process inside container
- `knowledge_link`: link knowledge project to work project

Tool count: 6 -> 10.
