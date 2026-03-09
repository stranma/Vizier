---
name: sync
description: Pre-flight workspace sync. Run at session start or before major work to check branch state, remote tracking, dirty files, and recent commits. Read-only -- makes no modifications.
---

# Sync Skill

Pre-flight check for workspace readiness. **Read-only -- this skill makes no modifications.**

## Steps

1. **Branch state** -- Run `git status` and `git branch -vv` to identify:
   - Current branch name
   - Tracking branch (if any)
   - Ahead/behind count
   - Dirty files (staged, unstaged, untracked)

2. **Remote sync** -- Run `git fetch origin` (dry-run mental model: just fetch, don't merge). Then compare:
   - Is the branch up to date with its remote tracking branch?
   - Are there upstream changes that need to be pulled/rebased?

3. **Recent history** -- Run `git log --oneline -10` to show recent commits. Identify:
   - Last commit message and author
   - Whether there are uncommitted changes on top

4. **Stash check** -- Run `git stash list` to see if there are stashed changes that might be forgotten.

5. **Report** -- Output a concise status summary:

```
## Workspace Sync

Branch: <branch> -> <tracking>
Status: <clean | dirty (N staged, M unstaged, K untracked)>
Remote: <up to date | N ahead, M behind | no tracking branch>
Stash:  <empty | N entries>
Recent: <last commit subject> (<age>)

<any warnings or action items>
```

## Warnings to surface

- Dirty working tree before starting new work
- Branch is behind remote (suggest pull/rebase)
- No remote tracking branch set
- Detached HEAD state
- Stashed changes older than 24 hours
- Branch name doesn't follow convention (fix/*, feat/*, refactor/*)
