#!/usr/bin/env bash
# Hermes-Vizier entrypoint: writes secrets from env vars to Hermes .env file,
# then starts the requested command (default: hermes gateway).
set -euo pipefail

# Validate required security config
if [ -z "${TELEGRAM_ALLOWED_USERS:-}" ]; then
    echo "FATAL: TELEGRAM_ALLOWED_USERS is not set -- gateway would be open to all users"
    exit 1
fi

export HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
HERMES_ENV="${HERMES_HOME}/.env"

# Detect authentication method
HAS_AUTH_JSON=false
if [ -f "${HERMES_HOME}/auth.json" ] && [ -s "${HERMES_HOME}/auth.json" ]; then
    HAS_AUTH_JSON=true
fi

if [ "$HAS_AUTH_JSON" = "false" ] && [ -z "${ANTHROPIC_API_KEY:-}" ]; then
    echo "FATAL: No authentication found."
    echo "  Either mount auth.json (subscription auth) or set ANTHROPIC_API_KEY."
    echo ""
    echo "  Subscription auth (recommended):"
    echo "    1. Run 'hermes login' or 'hermes model' locally"
    echo "    2. Mount ~/.hermes/auth.json into the container"
    echo ""
    echo "  API key auth:"
    echo "    Set ANTHROPIC_API_KEY in .env"
    exit 1
fi

if [ "$HAS_AUTH_JSON" = "true" ]; then
    echo "Auth: using subscription credentials (auth.json)"
else
    echo "Auth: using API key"
fi

# Write secrets from environment into Hermes .env (never committed to image).
{
    [ -n "${ANTHROPIC_API_KEY:-}" ] && echo "ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}"
    [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && echo "TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}"
    [ -n "${TELEGRAM_ALLOWED_USERS:-}" ] && echo "TELEGRAM_ALLOWED_USERS=${TELEGRAM_ALLOWED_USERS}"
    [ -n "${GITHUB_TOKEN:-}" ] && echo "GITHUB_TOKEN=${GITHUB_TOKEN}"
    [ -n "${COPILOT_GITHUB_TOKEN:-}" ] && echo "COPILOT_GITHUB_TOKEN=${COPILOT_GITHUB_TOKEN}"
} > "$HERMES_ENV"

chmod 600 "$HERMES_ENV"

echo "Hermes-Vizier starting: $*"
exec "$@"
