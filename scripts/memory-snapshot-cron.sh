#!/usr/bin/env bash
# Host cron wrapper -- runs memory-snapshot.sh inside a one-off alpine/git container.
# The production image has no git, so we use a separate container that mounts
# the same vizier-data volume.
#
# Cron entry (installed by deploy.yml):
#   0 2 * * * /opt/vizier/scripts/memory-snapshot-cron.sh >> /opt/vizier/memory-snapshot.log 2>&1
#
# See docs/DECISIONS.md D87 for rationale.
set -euo pipefail

echo "$(date -Iseconds) Starting memory snapshot..."

docker run --rm \
  -v vizier-data:/data/vizier \
  -v /opt/vizier/vizier-mcp/scripts/memory-snapshot.sh:/snapshot.sh:ro \
  alpine/git:latest \
  /bin/sh /snapshot.sh

echo "$(date -Iseconds) Memory snapshot complete."
