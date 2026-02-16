#!/usr/bin/env bash
set -euo pipefail

# Dead-man switch: checks Vizier heartbeat for staleness
# Run this from cron or an external monitor
#
# Usage: check_heartbeat.sh [vizier_root] [max_age_seconds]
# Default max_age: 45 seconds (3x the 15-second reconciliation interval)

VIZIER_ROOT="${1:-/opt/vizier}"
MAX_AGE="${2:-45}"
HEARTBEAT_FILE="${VIZIER_ROOT}/heartbeat.json"

if [ ! -f "${HEARTBEAT_FILE}" ]; then
    echo "CRITICAL: Heartbeat file not found: ${HEARTBEAT_FILE}"
    exit 2
fi

# Parse timestamp from heartbeat.json
TIMESTAMP=$(python3 -c "
import json, sys
from datetime import datetime, timezone

try:
    with open('${HEARTBEAT_FILE}') as f:
        data = json.load(f)
    ts = datetime.fromisoformat(data['timestamp'])
    age = (datetime.now(timezone.utc) - ts).total_seconds()
    print(f'{age:.0f}')
except Exception as e:
    print(f'ERROR: {e}', file=sys.stderr)
    sys.exit(1)
")

if [ $? -ne 0 ]; then
    echo "CRITICAL: Cannot read heartbeat timestamp"
    exit 2
fi

if [ "${TIMESTAMP}" -gt "${MAX_AGE}" ]; then
    echo "WARNING: Heartbeat stale (${TIMESTAMP}s old, max ${MAX_AGE}s)"
    exit 1
fi

echo "OK: Heartbeat fresh (${TIMESTAMP}s old)"
exit 0
