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

# Write secrets from environment into Hermes .env (never committed to image).
{
    [ -n "${ANTHROPIC_API_KEY:-}" ] && echo "ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}"
    [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && echo "TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}"
    [ -n "${TELEGRAM_ALLOWED_USERS:-}" ] && echo "TELEGRAM_ALLOWED_USERS=${TELEGRAM_ALLOWED_USERS}"
    [ -n "${GITHUB_TOKEN:-}" ] && echo "GITHUB_TOKEN=${GITHUB_TOKEN}"
} > "$HERMES_ENV"

chmod 600 "$HERMES_ENV"

echo "Hermes-Vizier starting: $*"
exec "$@"
