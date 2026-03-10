#!/usr/bin/env bash
# CI deploy dry-run: validates deploy-critical steps without real secrets or Docker socket.
# Run locally with: bash scripts/ci-deploy-dry-run.sh

set -euo pipefail

PASS=0
FAIL=0
VIZIER_IMAGE="vizier-mcp-dryrun"
OPENCLAW_IMAGE="ghcr.io/openclaw/openclaw:latest"

fail() { echo "FAIL: $1"; FAIL=$((FAIL + 1)); }
pass() { echo "PASS: $1"; PASS=$((PASS + 1)); }

# ── [1/4] Build vizier-mcp Docker image ──────────────────────────────────────
echo ""
echo "=== [1/4] Build vizier-mcp Docker image ==="
if docker build -t "$VIZIER_IMAGE" -f Dockerfile . ; then
    pass "Docker image built successfully"
else
    fail "Docker image build failed"
fi

# ── [2/4] Start vizier-mcp, wait for /health ─────────────────────────────────
echo ""
echo "=== [2/4] Start vizier-mcp and check /health ==="
CONTAINER_NAME="vizier-mcp-dryrun-$$"
# Start container with minimal env (no real API key needed for health check)
docker run -d --name "$CONTAINER_NAME" \
    -e VIZIER_ROOT=/data/vizier \
    -e HEALTH_PORT=8080 \
    -e MCP_TRANSPORT=streamable-http \
    -e MCP_PORT=8001 \
    "$VIZIER_IMAGE" >/dev/null

cleanup_container() {
    docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
}
trap cleanup_container EXIT

HEALTHY=false
for i in $(seq 1 20); do
    if docker exec "$CONTAINER_NAME" curl -sf http://localhost:8080/health >/dev/null 2>&1; then
        HEALTHY=true
        break
    fi
    echo "  waiting for /health (attempt $i/20)..."
    sleep 2
done

if [ "$HEALTHY" = "true" ]; then
    pass "/health endpoint responded"
    docker exec "$CONTAINER_NAME" curl -s http://localhost:8080/health
    echo ""
else
    fail "/health did not respond within 40s"
    echo "Container logs:"
    docker logs "$CONTAINER_NAME" --tail=30
fi

# ── [3/4] Verify runtime dependencies in container ───────────────────────────
echo ""
echo "=== [3/4] Verify runtime dependencies ==="
DEPS_OK=true
for dep in curl git; do
    if docker exec "$CONTAINER_NAME" which "$dep" >/dev/null 2>&1; then
        pass "$dep is installed"
    else
        fail "$dep is NOT installed (required by MCP tools)"
        DEPS_OK=false
    fi
done

# ── [4/5] Validate openclaw.json structure ───────────────────────────────────
echo ""
echo "=== [3/4] Validate openclaw.json structure ==="
CONFIG_FILE="openclaw/config/openclaw.json"

if python3 - "$CONFIG_FILE" <<'PYEOF'
import json, sys

with open(sys.argv[1]) as f:
    cfg = json.load(f)

errors = []

if 'agents' not in cfg:
    errors.append('missing top-level key: agents')
if 'gateway' not in cfg:
    errors.append('missing top-level key: gateway')
if 'plugins' not in cfg:
    errors.append('missing top-level key: plugins')

plugins = cfg.get('plugins', {}).get('entries', {})
adapter = plugins.get('mcp-adapter')
if adapter is None:
    errors.append('missing plugins.entries.mcp-adapter')
else:
    if not adapter.get('enabled'):
        errors.append('mcp-adapter is not enabled')
    servers = adapter.get('config', {}).get('servers', [])
    if len(servers) == 0:
        errors.append('mcp-adapter has no servers configured')

if errors:
    for e in errors:
        print(f'  ERROR: {e}')
    sys.exit(1)
PYEOF
then
    pass "openclaw.json structure is valid"
else
    fail "openclaw.json validation failed"
fi

# ── [5/5] Plugin install dry-run ─────────────────────────────────────────────
echo ""
echo "=== [4/4] Plugin install dry-run (mcp-adapter) ==="

# Use openclaw image if available, fall back to node:20-slim
PLUGIN_IMAGE="$OPENCLAW_IMAGE"
if ! docker pull "$OPENCLAW_IMAGE" >/dev/null 2>&1; then
    echo "  openclaw image not available, falling back to node:20-slim"
    PLUGIN_IMAGE="node:20-slim"
    docker pull "$PLUGIN_IMAGE" >/dev/null 2>&1
fi

if docker run --rm "$PLUGIN_IMAGE" sh -c "
    npx openclaw plugins install openclaw-mcp-adapter
"; then
    pass "mcp-adapter plugin install succeeded"
else
    fail "mcp-adapter plugin install failed"
fi

# ── Summary ──────────────────────────────────────────────────────────────────
echo ""
echo "========================================"
echo "  DRY-RUN RESULT: $PASS passed, $FAIL failed"
echo "========================================"

if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
