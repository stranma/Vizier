---
allowed-tools: Read, Glob, Grep, Bash
description: Restore context after /clear or session start. Analyzes git history, recent changes, and project state to recommend next steps.
---

# Context Restoration

Restore full project context and recommend next steps.

## Steps

1. **Read project documentation**
   - Read `docs/IMPLEMENTATION_PLAN.md` for current phase status
   - Read `docs/CHANGELOG.md` for recent changes
   - Read `docs/ARCHITECTURE.md` for system topology and design decisions
   - Read `docs/DECISIONS.md` for the decision log
   - Read `CLAUDE.md` for development methodology

2. **Analyze git state**
   - Run `git log --oneline -20` for recent commit history
   - Run `git status` for uncommitted changes
   - Run `git branch -a` to see all branches
   - Run `git diff --stat HEAD~5..HEAD` for recent file changes

3. **Scan for outstanding work**
   - Search for `TODO`, `FIXME`, `HACK`, `XXX` markers in recently modified files
   - Check for any failing tests with `uv run pytest --tb=no -q`
   - Check for lint issues with `uv run ruff check .`

4. **Summarize and recommend**

Present findings in this format:

```markdown
## Current State
- Branch: [branch name]
- Phase: [current phase from IMPLEMENTATION_PLAN.md]
- Uncommitted changes: [yes/no, summary]

## Recent Work (last 5 commits)
- [commit summaries]

## Outstanding Items
- [TODOs, failing tests, lint issues]

## Recommended Next Steps
1. [most important action]
2. [second priority]
3. [third priority]
```
