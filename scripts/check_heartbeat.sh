#!/usr/bin/env bash
set -euo pipefail

# Dead-man switch: checks Vizier heartbeat for staleness via HTTP health endpoint.
# Works in both Docker and bare-metal deployments.
#
# Usage: check_heartbeat.sh [health_url] [max_age_seconds]
# Default health_url: http://localhost:8080/health
# Default max_age: 45 seconds (3x the 15-second reconciliation interval)

HEALTH_URL="${1:-http://localhost:8080/health}"
MAX_AGE="${2:-45}"

RESPONSE=$(curl -sf "${HEALTH_URL}" 2>/dev/null) || {
    echo "CRITICAL: Health endpoint unreachable: ${HEALTH_URL}"
    exit 2
}

# Parse heartbeat age from the JSON response (read via stdin to avoid injection)
AGE=$(echo "${RESPONSE}" | python3 -c "
import json, sys
from datetime import datetime, timezone

try:
    data = json.load(sys.stdin)
    ts_str = data.get('heartbeat', {}).get('timestamp') or data.get('timestamp')
    if not ts_str:
        print('ERROR: No timestamp in response', file=sys.stderr)
        sys.exit(1)
    ts = datetime.fromisoformat(ts_str)
    age = (datetime.now(timezone.utc) - ts).total_seconds()
    print(f'{age:.0f}')
except Exception as e:
    print(f'ERROR: {e}', file=sys.stderr)
    sys.exit(1)
")

if [ $? -ne 0 ]; then
    echo "CRITICAL: Cannot parse heartbeat timestamp"
    exit 2
fi

if [ "${AGE}" -gt "${MAX_AGE}" ]; then
    echo "WARNING: Heartbeat stale (${AGE}s old, max ${MAX_AGE}s)"
    exit 1
fi

echo "OK: Heartbeat fresh (${AGE}s old)"
exit 0
