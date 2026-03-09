#!/usr/bin/env bash
# Daily git snapshot of Vizier memory files.
# Designed to run as a cron job: 0 2 * * * /path/to/memory-snapshot.sh
#
# Initializes a separate git repo at VIZIER_ROOT on first run.
# Commits all tracked state changes (specs, learnings, feedback, traces, budget, alerts).
# Optionally pushes to a configured remote.
#
# See docs/DECISIONS.md D87 for rationale.
set -euo pipefail

VIZIER_ROOT="${VIZIER_ROOT:-/data/vizier}"
cd "$VIZIER_ROOT" || exit 1

# Ensure git identity is always set (survives .git/config corruption)
git config user.name  "vizier-mcp"  2>/dev/null || true
git config user.email "vizier@localhost" 2>/dev/null || true

# Initialize repo if needed (idempotent)
if [ ! -d .git ]; then
    git init
    git config user.name "vizier-mcp"
    git config user.email "vizier@localhost"

    cat > .gitignore << 'IGNORE'
# Vizier memory versioning - auto-generated
# See docs/DECISIONS.md D87

# Rotated logs (high volume)
logs/

# Audit logs (high volume, rotated)
audit/
**/.vizier/audit.jsonl

# Atomic write temporaries
*.tmp

# Python / OS artifacts
__pycache__/
.DS_Store
IGNORE

    git add .gitignore
    git commit -m "[vizier] initialize memory versioning"
fi

# Stage all changes and exit if nothing to commit
git add -A
git diff --cached --quiet && exit 0

git commit -m "[vizier] daily snapshot $(date +%Y-%m-%d)"

# Push to remote if one is configured
if git remote get-url origin &>/dev/null; then
    git push origin HEAD 2>&1 || echo "Warning: push to remote failed" >&2
fi
