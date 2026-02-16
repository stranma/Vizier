#!/usr/bin/env bash
set -euo pipefail

# Docker entrypoint for Vizier daemon.
# On first boot (no config.yaml), runs `vizier init` to create the directory
# structure and default config. Then exec's the daemon so it becomes PID 1
# and receives SIGTERM from `docker stop` directly.

VIZIER_ROOT="${VIZIER_ROOT:-/opt/vizier}"

if [ ! -f "${VIZIER_ROOT}/config.yaml" ]; then
    echo "First run detected -- initializing ${VIZIER_ROOT}"
    if ! uv run vizier init --root "${VIZIER_ROOT}"; then
        echo "ERROR: vizier init failed"
        exit 1
    fi
fi

exec uv run vizier "$@"
