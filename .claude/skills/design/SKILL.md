---
name: design
description: Crystallize brainstorming into a structured plan. Reads DECISIONS.md for conflicts, auto-classifies scope (Q/S/P), outputs plan in scope-appropriate format. For P-scoped plans, writes to IMPLEMENTATION_PLAN.md.
---

# Design Skill

Transforms brainstorming output into a structured, actionable plan.

## Prerequisites

- A brainstorming session has produced ideas, constraints, and direction
- If no brainstorming has occurred, prompt the user to describe what they want to build/fix/change

## Steps

### 1. Consistency check

Read `docs/DECISIONS.md` and scan for conflicts with the proposed approach:
- Check resolved decisions and their rationale
- Read `docs/ARCHITECTURE.md` section 7 (decision map) for kept/modified/replaced/reversed/dropped status
- If a conflict is found, **present it to the user before proceeding**. Do NOT silently override a documented decision.

### 2. Classify scope

Estimate scope from the brainstorming output:

| Scope | Signal | Examples |
|-------|--------|----------|
| **Q** (Quick) | Single file, obvious fix, < 30 min | Typo, config tweak, one-liner |
| **S** (Standard) | Multiple files, one session, clear scope | New feature, multi-file refactor |
| **P** (Project) | Multiple phases, cross-session, architectural | Large migration, new subsystem |

State the classification explicitly: "This looks like a **S (Standard)** task."

### 3. Output plan

Format depends on scope:

#### Q (Quick)
Just state what to do in 1-3 sentences. No formal plan needed.

#### S (Standard)
Use `EnterPlanMode` and write a plan covering:
- **What changes** -- files to create/modify/delete
- **Approach** -- how to implement (key decisions, patterns to follow)
- **Testing** -- what tests to write or update
- **Risks** -- anything that could go wrong

#### P (Project)
Use `EnterPlanMode` and write a comprehensive plan. After approval, also write/update `docs/IMPLEMENTATION_PLAN.md` with:
- Phase breakdown with acceptance criteria
- Dependencies between phases
- PIRR gates before each phase

### 4. Decision logging

If the plan introduces new architectural decisions:
- Draft a decision entry (D-number, context, decision, alternatives, trade-offs)
- These will be committed to `docs/DECISIONS.md` during `/done`

## Notes

- The scope classification here is an **estimate**. The actual scope is detected by `/done` at completion time from workspace signals (branch, diff size, plan state).
- For P-scoped work, every phase MUST include PIRR as a gate and reference the agent files in `.claude/agents/`.
