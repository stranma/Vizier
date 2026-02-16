#!/usr/bin/env bash
set -euo pipefail

# One-time migration from bare-metal (systemd) deployment to Docker.
# Run on the production server as the vizier user.
#
# Prerequisites:
#   - Docker Engine 24+ installed
#   - docker compose plugin installed
#   - User in the docker group (or run with sudo)
#
# Usage: bash scripts/migrate_to_docker.sh

VIZIER_ROOT="/opt/vizier"
CONFIG_DIR="${VIZIER_ROOT}/config"
REGISTRY="ghcr.io/stranma/vizier"

echo "=== Vizier: bare-metal -> Docker migration ==="

# 1. Stop the systemd service
if systemctl is-active --quiet vizier 2>/dev/null; then
    echo "[1/7] Stopping systemd vizier service..."
    sudo systemctl stop vizier
    sudo systemctl disable vizier
else
    echo "[1/7] systemd vizier service not running (skipped)"
fi

# 2. Create config directory and copy files
echo "[2/7] Setting up ${CONFIG_DIR}..."
mkdir -p "${CONFIG_DIR}"

for f in config.yaml projects.yaml .env; do
    if [ -f "${VIZIER_ROOT}/${f}" ]; then
        cp -p "${VIZIER_ROOT}/${f}" "${CONFIG_DIR}/${f}"
        echo "  Copied ${f}"
    else
        echo "  WARNING: ${VIZIER_ROOT}/${f} not found"
    fi
done

# 3. Remove stale named volume from previous docker-compose runs (if any)
if docker volume inspect vizier-config >/dev/null 2>&1; then
    echo "[3/7] Removing stale vizier-config volume..."
    docker volume rm vizier-config
else
    echo "[3/7] No stale vizier-config volume (skipped)"
fi

# 4. Pull the Docker image
echo "[4/7] Pulling Docker image ${REGISTRY}:latest..."
docker pull "${REGISTRY}:latest"

# 5. Copy docker-compose.yml
echo "[5/7] Copying docker-compose.yml to ${VIZIER_ROOT}/"
if [ -f "docker-compose.yml" ]; then
    cp docker-compose.yml "${VIZIER_ROOT}/docker-compose.yml"
elif [ -f "/opt/vizier-repo/docker-compose.yml" ]; then
    cp /opt/vizier-repo/docker-compose.yml "${VIZIER_ROOT}/docker-compose.yml"
else
    echo "  ERROR: docker-compose.yml not found. Copy it manually to ${VIZIER_ROOT}/"
    exit 1
fi

# 6. Start the container
echo "[6/7] Starting vizier-daemon container..."
cd "${VIZIER_ROOT}"
docker compose up -d

# 7. Verify health
echo "[7/7] Waiting for health endpoint..."
HEALTHY=false
for i in $(seq 1 30); do
    if curl -sf http://localhost:8080/health >/dev/null; then
        HEALTHY=true
        break
    fi
    echo "  Waiting (attempt $i/30)..."
    sleep 2
done

if [ "${HEALTHY}" = true ]; then
    echo ""
    echo "=== Migration complete ==="
    echo "Daemon is healthy. Next steps:"
    echo "  - Register projects: docker exec vizier-daemon uv run vizier register <name> --repo <url> --root /opt/vizier"
    echo "  - View logs:         docker compose logs -f vizier-daemon"
    echo "  - Check status:      curl http://localhost:8080/health"
else
    echo ""
    echo "=== Health check failed ==="
    echo "Check logs: docker compose -f ${VIZIER_ROOT}/docker-compose.yml logs vizier-daemon"
    exit 1
fi
