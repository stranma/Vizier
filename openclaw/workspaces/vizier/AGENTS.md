# Vizier Agents

## Pashas (Per-Project Orchestrators)

Each registered project has a dedicated Pasha sub-session. Pashas manage the
inner loop: Scout -> Architect -> Worker -> Quality Gate -> Done.

## Available Inner Agents

- **Scout**: Prior art researcher (Sonnet, spawned per research task)
- **Architect**: Task decomposer (Opus, spawned per decomposition)
- **Worker**: Spec executor (Sonnet/Opus, spawned per spec, fresh context)
- **Quality Gate**: Work validator (Sonnet/Opus, spawned per review)
- **Retrospective**: Failure analyzer (Opus, periodic)
