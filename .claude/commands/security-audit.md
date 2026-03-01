---
allowed-tools: Read, Glob, Grep, Bash
description: Run a 6-phase Python-specific security posture scan with A-F grading.
---

# Security Audit

Perform a comprehensive security audit of this Python project.

## Phase 1: Dependency Security

- Run `uv run pip-audit` if available, otherwise check `pyproject.toml` for known-vulnerable packages
- Check for pinned vs unpinned dependencies
- Flag any dependencies with known CVEs

## Phase 2: Secrets Scan

Search the entire codebase for leaked secrets:
- API keys: patterns like `sk-`, `AKIA`, `ghp_`, `gho_`
- Private keys: `-----BEGIN.*PRIVATE KEY-----`
- Database URLs with credentials: `(postgres|mysql|mongodb)://.*:.*@`
- Hardcoded passwords: `password\s*=\s*['"][^'"]+`
- `.env` files that should be gitignored
- Check `.gitignore` includes `.env`, `.env.*`

## Phase 3: Code Pattern Analysis

Scan Python source files for unsafe patterns:
- `eval()` and `exec()` usage
- `pickle.loads()` (arbitrary code execution)
- `subprocess(shell=True)` (command injection)
- `yaml.load()` without `SafeLoader`
- `os.system()` calls
- SQL string concatenation (injection risk)
- `assert` used for validation (stripped in `-O` mode)
- `__import__()` with user input

## Phase 4: Input Validation

Check API boundaries and user input handling:
- Are function parameters validated at entry points?
- Are file paths sanitized against traversal (`../`)?
- Are URL inputs validated?
- Is there proper error handling at system boundaries?

## Phase 5: Configuration Security

Review project configuration:
- `.claude/settings.json` -- check for overly permissive patterns
- GitHub Actions workflows -- check for secret handling
- Docker configuration (if present) -- check for root user, exposed ports
- CORS configuration (if present)

## Phase 6: Score and Report

Calculate a security posture score (0-100) and assign a grade:

| Grade | Score | Meaning |
|-------|-------|---------|
| A | 90-100 | Excellent -- no critical issues, minor improvements only |
| B | 80-89 | Good -- no critical issues, some medium-priority findings |
| C | 70-79 | Adequate -- no critical issues but notable gaps |
| D | 60-69 | Needs work -- critical issues present |
| F | 0-59 | Failing -- multiple critical issues, immediate action needed |

**Scoring deductions:**
- Critical (leaked secret, eval with user input): -20 each
- High (unpinned deps, shell=True): -10 each
- Medium (missing input validation): -5 each
- Low (style issues, missing .gitignore entries): -2 each

Present the full report:

```markdown
# Security Audit Report

## Score: [X]/100 (Grade: [A-F])

## Critical Issues
- [issues requiring immediate fix]

## High Priority
- [issues to fix soon]

## Medium Priority
- [issues to plan for]

## Low Priority
- [nice-to-have improvements]

## Remediation Plan
1. [ordered steps to fix issues]
```
