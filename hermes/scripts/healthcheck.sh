#!/usr/bin/env bash
# Health check for the Hermes-Vizier container.
# Verifies the hermes gateway process is running.
set -euo pipefail

pgrep -f "hermes gateway" > /dev/null 2>&1 || exit 1
