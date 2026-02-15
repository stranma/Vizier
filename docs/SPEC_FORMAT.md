# Vizier Spec Format

## Overview

A spec is the contract between Architect and Worker. The Architect writes it; the Worker consumes it. If the Worker needs to "figure things out," the spec was underspecified — the Architect failed, not the Worker.

The spec format is universal across project types. What varies is the content of each section, guided by the active plugin's Architect guide and criteria library.

## Spec Structure

```markdown
---
id: "001-feature/002-subtask"
status: READY
priority: 1
complexity: medium
retries: 0
max_retries: 10
parent: "001-feature"
plugin: software
created: 2026-02-15T10:00:00Z
updated: 2026-02-15T10:00:00Z
assigned_to: null
requires_approval: false       # if true, EA shows diff to Sultan before commit
---

# [Short descriptive title]

## Context

Why this task exists. What it's part of. What the user/system needs.
Link to parent spec if this is a sub-task.

## Requirements

What must be true when this task is done. Written as concrete, testable statements.

- The system MUST ...
- The function MUST accept ... and return ...
- The file `path/to/file.py` MUST contain ...

## Artifacts

Exact list of files/outputs to create or modify. The Worker should not need to search.

| Artifact | Action | Description |
|----------|--------|-------------|
| `src/auth/jwt.py` | CREATE | JWT token generation and validation |
| `src/auth/__init__.py` | MODIFY | Export new module |
| `tests/auth/test_jwt.py` | CREATE | Unit tests for JWT module |

## Contract

The domain-specific interface or structure contract.

For software: function signatures, class interfaces, data shapes.
For finance: input assumptions, output metrics, formula logic.
For documents: outline, section structure, source requirements.

## Acceptance Criteria

Each criterion MUST be independently verifiable. Prefer automated checks.
Criteria can reference the plugin's criteria library by name.

- [ ] @criteria/tests_pass: `uv run pytest tests/auth/test_jwt.py`
- [ ] @criteria/lint_clean: `uv run ruff check src/auth/`
- [ ] `generate_token` returns a valid JWT string
- [ ] `validate_token` raises `InvalidTokenError` for expired tokens
- [ ] `validate_token` raises `InvalidTokenError` for malformed tokens

## Notes

Optional: edge cases, gotchas, related decisions, links to learnings.md entries.
```

## Criteria References

Specs can reference reusable criteria from the plugin's criteria library:

```markdown
- [ ] @criteria/tests_pass: `uv run pytest {test_files}`
- [ ] @criteria/lint_clean: `uv run ruff check {source_files}`
```

The `@criteria/` prefix tells the Quality Gate to load the full criteria definition from the plugin. This ensures consistent evaluation standards across specs.

### Criteria Snapshotting

When the Architect creates a spec, `@criteria/` references are resolved and their definitions are snapshotted (embedded) into the spec at creation time. The Quality Gate evaluates against the snapshotted version, not the current plugin library.

**Why:** If `@criteria/tests_pass` changes between spec creation and quality gate evaluation, the Worker implemented against the old criteria but would be judged by the new ones. Snapshotting prevents this version mismatch.

## Rules for Architects

1. **Be specific about artifacts** — list every file/output the Worker will produce
2. **Provide contracts** — the Worker implements to a contract, not designs one
3. **Make criteria automatable** — "run this command, expect this output"
4. **One concern per spec** — if it touches unrelated subsystems, split it
5. **Set complexity honestly** — this drives model selection for the Worker
6. **Reference learnings** — check `learnings.md` for known pitfalls in this project
7. **Use plugin criteria library** — reference `@criteria/` for standard checks
8. **Follow plugin decomposition patterns** — use the plugin's Architect guide

## Rules for Workers

1. **Bounded exploration** — you can read any project file to understand context, but can only write to artifacts listed in the spec. Log any files you read beyond the artifact list.
2. **Don't expand scope** — implement exactly what's specified, nothing more
3. **Implicit completion** — exit cleanly when done. The system transitions the spec to REVIEW automatically. No magic signal needed.
4. **Write feedback if stuck** — explain what's blocking in the spec's feedback/ directory
5. **One spec, one commit** — atomic changes tied to specific specs
6. **Use only allowed tools** — the plugin defines which tools are available, enforced by Sentinel (allowlist + denylist + Haiku)

## Spec Examples by Plugin

### Software (plugin: software)

**Artifacts**: source files, test files
**Contract**: function signatures, class interfaces, data shapes
**Criteria**: `@criteria/tests_pass`, `@criteria/lint_clean`, `@criteria/type_check`, `@criteria/test_meaningfulness`

### Finance (plugin: finance)

**Artifacts**: spreadsheet files, sheet names, cell ranges
**Contract**: input assumptions, output metrics, formula logic
**Criteria**: `@criteria/formulas_validate`, `@criteria/totals_crossref`, `@criteria/assumptions_documented`

### Documents (plugin: documents)

**Artifacts**: document files, section structure
**Contract**: outline, key points per section, source requirements
**Criteria**: `@criteria/structure_complete`, `@criteria/facts_sourced`, `@criteria/formatting_standards`
