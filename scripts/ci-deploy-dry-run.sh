#!/usr/bin/env bash
# CI deploy dry-run: validates deploy-critical steps without real secrets or Docker socket.
# Run locally with: bash scripts/ci-deploy-dry-run.sh

set -euo pipefail

PASS=0
FAIL=0
VIZIER_IMAGE="vizier-mcp-dryrun"

fail() { echo "FAIL: $1"; FAIL=$((FAIL + 1)); }
pass() { echo "PASS: $1"; PASS=$((PASS + 1)); }

# -- [1/4] Build vizier-mcp Docker image ──────────────────────────────────────
echo ""
echo "=== [1/4] Build vizier-mcp Docker image ==="
if docker build -t "$VIZIER_IMAGE" -f Dockerfile . ; then
    pass "Docker image built successfully"
else
    fail "Docker image build failed"
fi

# -- [2/4] Start vizier-mcp, wait for /health ─────────────────────────────────
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

# -- [3/4] Verify runtime dependencies in container ───────────────────────────
echo ""
echo "=== [3/4] Verify runtime dependencies ==="
for dep in curl git; do
    if docker exec "$CONTAINER_NAME" which "$dep" >/dev/null 2>&1; then
        pass "$dep is installed"
    else
        fail "$dep is NOT installed (required by MCP tools)"
    fi
done

# -- [4/4] Validate Hermes configuration ──────────────────────────────────────
echo ""
echo "=== [4/4] Validate Hermes config.yaml ==="
CONFIG_FILE="hermes/config.yaml"

if python3 - "$CONFIG_FILE" <<'PYEOF'
import sys
import yaml

with open(sys.argv[1]) as f:
    cfg = yaml.safe_load(f)

errors = []

# Model configuration
model = cfg.get("model", {})
if model.get("provider") != "anthropic":
    errors.append("model.provider must be 'anthropic'")
if "opus" not in model.get("default", ""):
    errors.append("model.default must be an Opus-tier model")

# MCP server configuration
mcp = cfg.get("mcp_servers", {})
if "vizier" not in mcp:
    errors.append("missing mcp_servers.vizier")
else:
    vizier = mcp["vizier"]
    if "url" not in vizier:
        errors.append("mcp_servers.vizier missing 'url'")

# Fallback model
fallback = cfg.get("fallback_model", {})
if not fallback:
    errors.append("missing fallback_model")

if errors:
    for e in errors:
        print(f"  ERROR: {e}")
    sys.exit(1)
PYEOF
then
    pass "Hermes config.yaml is valid"
else
    fail "Hermes config.yaml validation failed"
fi

# -- Summary ──────────────────────────────────────────────────────────────────
echo ""
echo "========================================"
echo "  DRY-RUN RESULT: $PASS passed, $FAIL failed"
echo "========================================"

if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
