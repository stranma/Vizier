---
allowed-tools: Read, Glob, Grep, Bash
description: Pre-deployment verification with 3 tiers -- Blockers, High Priority, and Recommended checks.
---

# Ship Checklist

Run pre-deployment verification before merging or releasing.

## Tier 1: Blockers (must ALL pass)

These will prevent shipping if any fail:

1. **Tests pass**
   - Run `uv run pytest -x -q`
   - All tests must pass with zero failures

2. **Lint clean**
   - Run `uv run ruff check .`
   - Zero lint errors

3. **Type check clean**
   - Run `uv run pyright`
   - Zero type errors

4. **No secrets in codebase**
   - Search for: `sk-`, `AKIA`, `ghp_`, `password=`, `secret=`, `-----BEGIN.*PRIVATE KEY`
   - Zero matches in tracked files (exclude `.env.example`)

5. **No debug code**
   - Search for: `breakpoint()`, `pdb.set_trace()`, `print(` in non-test source files
   - Flag any found (prints may be intentional -- list for review)

## Tier 2: High Priority (should pass)

These are important but may have valid exceptions:

1. **Test coverage**
   - Run `uv run pytest --cov --cov-report=term-missing -q`
   - Flag any source files with 0% coverage

2. **No TODOs in shipping code**
   - Search for `TODO`, `FIXME`, `HACK`, `XXX` in source files
   - List all found with file:line

3. **Documentation current**
   - Check `docs/CHANGELOG.md` has entries for current work
   - Check `docs/IMPLEMENTATION_PLAN.md` status is up to date

4. **No unused imports**
   - Run `uv run ruff check --select F401 .`
   - List any unused imports found

## Tier 3: Recommended (nice to have)

1. **Git history clean**
   - Run `git log --oneline -10` and check for WIP/fixup commits
   - Suggest squashing if messy

2. **Branch up to date**
   - Run `git fetch origin` and check if behind base branch
   - Suggest rebase if diverged

3. **Version consistent**
   - Run `python scripts/check_versions.py` if available
   - Check all packages have synchronized MAJOR.MINOR

## Report Format

```
# Ship Checklist Results

## Blockers
- [PASS] Tests: X passed, 0 failed
- [PASS] Lint: 0 errors
- [PASS] Types: 0 errors
- [PASS] Secrets: none found
- [PASS] Debug code: none found

## High Priority
- [PASS] Coverage: X% average
- [WARN] TODOs: 3 found (list below)
- [PASS] Docs: up to date

## Recommended
- [INFO] Git history: clean
- [WARN] Branch: 2 commits behind origin/master

## Verdict: [READY TO SHIP / BLOCKERS FOUND / REVIEW NEEDED]
```
