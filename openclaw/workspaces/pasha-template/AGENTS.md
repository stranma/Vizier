# Pasha Inner Agents

## Scout
Prior art researcher. Spawned for DRAFT specs to find existing solutions.

## Architect
Task decomposer. Spawned for SCOUTED specs to create sub-specs with DAG.

## Worker
Spec executor. Spawned per READY spec. Fresh context, one spec, exit.

## Quality Gate
Work validator. Spawned per REVIEW spec. Multi-pass validation protocol.

## Retrospective
Failure analyzer. Spawned periodically or on STUCK specs.
