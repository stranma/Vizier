# Vizier Agents

## Pashas (Per-Project Orchestrators)

Each registered project has a dedicated Pasha sub-session. Pashas manage the
inner loop: Worker -> Quality Gate -> Done.

## Available Inner Agents (v1)

- **Worker**: Spec executor (Sonnet/Opus, spawned per spec, fresh context)
- **Quality Gate**: Work validator (Sonnet/Opus, spawned per review)

## v2 Agents (Deferred)

- **Scout**: Prior art researcher (Sonnet, spawned per research task)
- **Architect**: Task decomposer (Opus, spawned per decomposition)
- **Retrospective**: Failure analyzer (Opus, periodic)
