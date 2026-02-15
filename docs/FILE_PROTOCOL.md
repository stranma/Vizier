# Vizier File Protocol

## Overview

All inter-agent communication happens through the filesystem. This document defines the directory layout, file formats, naming conventions, and state transitions.

## Directory Layout

### Per-project: `.vizier/`

```
.vizier/
+-- constitution.md                    # Project principles (human-written)
+-- config.yaml                        # Plugin selection, model overrides
+-- learnings.md                       # Retrospective output (append-only)
+-- state.json                         # Runtime state (.gitignored)
|
+-- specs/                             # Task specifications
|   +-- 001-feature-name/
|   |   +-- spec.md                    # Main spec (Architect writes)
|   |   +-- 001-subtask.md             # Sub-spec (decomposed)
|   |   +-- 002-subtask.md
|   |   +-- feedback/                  # Quality Gate rejection notes
|   |       +-- 2026-02-15-001.md
|   +-- 002-another-feature/
|       +-- spec.md
|
+-- proposals/                         # Retrospective proposals (human reviews)
    +-- 2026-02-15-prompt-update.md
    +-- 2026-02-15-criteria-change.md
```

### Server-wide: `/opt/vizier/reports/`

```
reports/
+-- <project-name>/
|   +-- status.json                    # Current state (overwritten each cycle)
|   +-- YYYY-MM-DD-cycle-NNN.md       # Per-cycle progress report
|   +-- escalations/                   # Blockers requiring human input
|       +-- YYYY-MM-DD-NNN.md
+-- ea-inbox/                          # Human messages parsed by EA
    +-- YYYY-MM-DD-NNN.json
```

### Plugin layout (in Vizier repo)

```
plugins/
+-- software/                          # Built-in plugin
|   +-- pyproject.toml                 # Entry point registration
|   +-- vizier_plugins/software/
|       +-- __init__.py                # SoftwarePlugin(BasePlugin)
|       +-- worker.py                  # SoftwareCoder(BaseWorker)
|       +-- quality_gate.py            # SoftwareQualityGate(BaseQualityGate)
|       +-- architect_guide.py         # Decomposition patterns
|       +-- tools.py                   # Tool restrictions
|       +-- prompts/
|       |   +-- worker.md              # Jinja2 template
|       |   +-- quality_gate.md
|       |   +-- architect_guide.md
|       +-- criteria/
|           +-- tests_pass.md
|           +-- lint_clean.md
|           +-- type_check.md
|           +-- no_debug_artifacts.md
|           +-- test_meaningfulness.md
+-- documents/                         # Built-in plugin
    +-- pyproject.toml
    +-- vizier_plugins/documents/
        +-- __init__.py
        +-- worker.py                  # DocumentWriter(BaseWorker)
        +-- quality_gate.py            # DocumentReviewer(BaseQualityGate)
        +-- prompts/
        +-- criteria/
```

## Spec Lifecycle

```
DRAFT -> READY -> IN_PROGRESS -> REVIEW -> DONE
                       |            |
                       |            +-> REJECTED -> IN_PROGRESS (retry, graduated)
                       |                              retry 3: bump model tier
                       |                              retry 5: alert Pasha
                       |                              retry 7: Architect re-decomposes
                       +-> STUCK (after 10 retries)
                       |     |
                       |     +-> DECOMPOSED -> new sub-specs created
                       |
                       +-> INTERRUPTED (daemon shutdown)
                             |
                             +-> READY (on restart, re-queued)
```

### State transitions

| From | To | Who | Trigger |
|------|----|-----|---------|
| (new) | DRAFT | EA/Sultan | Task received |
| DRAFT | READY | Architect | Spec fully decomposed with acceptance criteria |
| DRAFT | DECOMPOSED | Architect | Split into sub-specs |
| READY | IN_PROGRESS | Worker | Picked from queue |
| IN_PROGRESS | REVIEW | Worker | Worker exits cleanly (implicit completion) |
| REVIEW | DONE | Quality Gate | All Completion Protocol passes succeed |
| REVIEW | REJECTED | Quality Gate | Any PCC pass failed, feedback written |
| REJECTED | IN_PROGRESS | Worker | Retry with feedback (model tier bumped at retry 3) |
| IN_PROGRESS | STUCK | System | Retry count exceeds 10 |
| STUCK | DECOMPOSED | Architect/Retrospective | Broken into smaller specs |
| IN_PROGRESS | INTERRUPTED | System | Daemon graceful shutdown |
| INTERRUPTED | READY | System | Daemon restart (re-queued with fresh context) |

### Reconciliation

Events (filesystem watch) are an optimization, not the source of truth. The filesystem IS the source of truth.

On daemon start and periodically (configurable, e.g., every 60 seconds), the Pasha scans all spec files and rebuilds state from disk. If a filesystem event was missed (watchdog overflow, crash), reconciliation catches it on the next cycle.

This means: if a spec file says `status: REVIEW` but the Pasha's in-memory state still shows `IN_PROGRESS`, reconciliation corrects this.

## File Formats

### spec.md frontmatter

```yaml
---
id: "001-feature-name"
status: READY          # DRAFT | READY | IN_PROGRESS | REVIEW | DONE | REJECTED | STUCK | DECOMPOSED
priority: 1            # lower = higher priority
complexity: medium     # low | medium | high (used by model router)
retries: 0             # incremented on each REJECTED -> IN_PROGRESS cycle
max_retries: 10        # STUCK threshold
parent: null           # parent spec ID if this is a sub-spec
plugin: software       # which plugin handles this spec (inherited from project config)
created: 2026-02-15T10:00:00Z
updated: 2026-02-15T10:00:00Z
assigned_to: null      # worker instance ID when IN_PROGRESS
---
```

### state.json

```json
{
  "project": "project-alpha",
  "plugin": "software",
  "current_cycle": 42,
  "active_agents": {
    "manager": { "pid": 1234, "since": "2026-02-15T10:00:00Z" },
    "worker": { "pid": 1235, "spec": "001-auth/002-jwt", "since": "2026-02-15T10:05:00Z" }
  },
  "queue": ["001-auth/003-login", "002-dashboard/001-layout"],
  "last_retrospective": "2026-02-15T09:00:00Z"
}
```

### status.json (in reports/)

```json
{
  "project": "project-alpha",
  "plugin": "software",
  "updated": "2026-02-15T10:30:00Z",
  "cycle": 42,
  "specs_total": 12,
  "specs_done": 8,
  "specs_in_progress": 1,
  "specs_stuck": 0,
  "current_task": "001-auth/002-jwt-middleware",
  "blockers": [],
  "last_completion": "2026-02-15T10:15:00Z"
}
```

## Naming Conventions

| Entity | Pattern | Example |
|--------|---------|---------|
| Spec directory | `NNN-kebab-name/` | `001-user-auth/` |
| Sub-spec file | `NNN-kebab-name.md` | `002-jwt-middleware.md` |
| Cycle report | `YYYY-MM-DD-cycle-NNN.md` | `2026-02-15-cycle-042.md` |
| Feedback file | `YYYY-MM-DD-NNN.md` | `2026-02-15-001.md` |
| Escalation | `YYYY-MM-DD-NNN.md` | `2026-02-15-001.md` |
| Proposal | `YYYY-MM-DD-description.md` | `2026-02-15-prompt-update.md` |

## Filesystem Watch Events

Agents subscribe to specific paths:

| Agent | Watches | For |
|-------|---------|-----|
| Pasha | `.vizier/specs/**` | New specs (DRAFT), status changes |
| Worker | `.vizier/specs/**/` | READY specs (pick next task) |
| Quality Gate | `.vizier/specs/**/` | REVIEW status (validate) |
| Retrospective | `.vizier/specs/**/feedback/` | Rejections, STUCK transitions |
| EA | `/opt/vizier/reports/**/` | Progress updates, escalations |

## Concurrency Rules

- Only ONE agent writes to a given spec file at a time (enforced by state.json assignment)
- Multiple agents can READ any file concurrently
- state.json updates use file-level locking (fcntl/msvcrt)
- Reports directory: only the project's Pasha writes; EA only reads
- Plugin files are read-only at runtime (installed as packages)
