---
name: done
description: Universal completion command. Auto-detects scope (Q/S/P) from workspace signals, validates with 3-tier checklist, ships (commit/push/PR/CI), and documents (CHANGELOG/DECISIONS). Replaces /ship.
---

# Done Skill

Universal task completion. Detects what you built, validates it, ships it, and documents it.

## Phase 1: Detect scope

Auto-detect scope from workspace signals -- do NOT ask the user to classify.

| Signal | Q (Quick) | S (Standard) | P (Project) |
|--------|-----------|--------------|-------------|
| Branch | On main/master | Feature branch | Feature branch |
| Files changed | 1-3 | 4-20 | 20+ or multi-phase |
| Diff size | < 50 lines | 50-500 lines | 500+ lines |
| Plan state | No plan | Plan exists | `IMPLEMENTATION_PLAN.md` updated |
| Test changes | None or trivial | Tests added/modified | Tests across multiple modules |

Use the **highest matching scope**. State it: "Detected scope: **S (Standard)**"

If signals conflict (e.g., 2 files changed but 200-line diff), use judgment and explain.

## Phase 2: Validate

Run the 3-tier validation checklist. Execute checks, don't just list them.

### Tier 1: Blockers (must ALL pass)

- [ ] Tests pass: `uv run pytest`
- [ ] Lint clean: `uv run ruff check .`
- [ ] Format clean: `uv run ruff format --check .`
- [ ] Type check clean: `uv run pyright`
- [ ] No secrets in diff: scan for API keys, tokens, passwords, private keys
- [ ] No debug code: no `breakpoint()`, `print()` debugging, `# TODO REMOVE`

### Tier 2: High Priority (should pass)

- [ ] Test coverage: new code has tests, edge cases covered
- [ ] No TODOs in shipping code (TODOs in test stubs are OK)
- [ ] Documentation current: docstrings for public APIs
- [ ] No unused imports or dead code in changed files

### Tier 3: Recommended (nice to have)

- [ ] Git history clean: logical commits, meaningful messages
- [ ] Branch up to date with base branch
- [ ] CHANGELOG entry drafted (for S and P scope)

**Report format:**

```
## Validation Report

Tier 1 (Blockers):    [PASS] 6/6
Tier 2 (High Priority): [PASS] 4/4 | [WARN] 0
Tier 3 (Recommended): [PASS] 2/3 | [WARN] 1

<details for any WARN or FAIL items>
```

**Gate:** All Tier 1 items must pass. Tier 2 warnings need justification. Tier 3 is advisory.

## Phase 3: Ship

Action depends on detected scope:

### Q (Quick) -- Commit

1. Stage and commit with a descriptive message
2. Push to current branch (usually main/master)

### S (Standard) -- Land

1. Stage and commit (or verify existing commits)
2. Push to feature branch with `-u` flag
3. Create PR using `.claude/agents/pr-writer.md` agent for description
4. Verify CI passes: `gh pr checks`
5. Run code review: `.claude/agents/code-reviewer.md` agent
   - If automated reviewer (e.g., CodeRabbit) is configured, use `.claude/agents/review-responder.md` instead
   - Fix Critical issues before proceeding
6. Report PR URL to user

### P (Project) -- Deliver

1. Same as S (Land) steps 1-6
2. Additionally:
   - Run `.claude/agents/acceptance-criteria-validator.md` against phase criteria
   - Update `docs/IMPLEMENTATION_PLAN.md` with phase completion status
   - Write phase handoff note (2-5 sentences: what completed, deviations, risks)

## Phase 4: Document

### Always (all scopes)
- Update `docs/DECISIONS.md` if new decisions were made

### S and P scope
- Update `docs/CHANGELOG.md` with user-facing changes
- Use `.claude/agents/docs-updater.md` to verify documentation is current

### P scope additionally
- Update `docs/IMPLEMENTATION_PLAN.md` with completion status
- Consolidate phase notes

## Error handling

| Failure | Action |
|---------|--------|
| Tier 1 blocker fails | Fix it, re-run Phase 2 |
| CI fails | Fix, push, re-check |
| Code review flags Critical | Fix, re-run review |
| PR creation fails | Check branch state, fix, retry |
| Multiple failures | Stop and reassess -- may need to split work |
