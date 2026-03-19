#!/usr/bin/env bash
# Fetch secrets from Infisical and write them to .env for Docker Compose.
#
# Prerequisites:
#   - Infisical CLI installed (https://infisical.com/docs/cli/overview)
#   - Logged in via `infisical login` or machine identity configured
#
# Usage: bash scripts/fetch-secrets.sh [env-file]
#   env-file defaults to /opt/vizier/.env

set -euo pipefail

ENV_FILE="${1:-/opt/vizier/.env}"

if [ ! -f "$ENV_FILE" ]; then
    touch "$ENV_FILE"
fi

# Infisical project and environment
PROJECT_SLUG="${INFISICAL_PROJECT_SLUG:-vizier}"
ENV_SLUG="${INFISICAL_ENV_SLUG:-prod}"

echo "Fetching secrets from Infisical (project: $PROJECT_SLUG, env: $ENV_SLUG)"

if ! command -v infisical &> /dev/null; then
    echo "ERROR: infisical CLI not installed"
    echo "  Install: https://infisical.com/docs/cli/overview"
    exit 1
fi

# Secret mapping: Infisical secret name -> env var name
# Infisical stores secrets as KEY=VALUE; we fetch specific ones.
SECRETS=(
    "ANTHROPIC_API_KEY"
    "TELEGRAM_BOT_TOKEN"
    "TELEGRAM_ALLOWED_USERS"
    "GITHUB_TOKEN"
)

update_env_var() {
    local key="$1"
    local value="$2"
    local file="$3"

    grep -v "^${key}=" "$file" > "${file}.tmp" || true
    echo "${key}=${value}" >> "${file}.tmp"
    mv "${file}.tmp" "$file"
}

FETCHED=0
SKIPPED=0

for secret_name in "${SECRETS[@]}"; do
    echo -n "  $secret_name: "

    value=$(infisical secrets get "$secret_name" \
        --projectSlug "$PROJECT_SLUG" \
        --env "$ENV_SLUG" \
        --plain 2>/dev/null) || true

    if [ -n "$value" ]; then
        update_env_var "$secret_name" "$value" "$ENV_FILE"
        echo "OK"
        FETCHED=$((FETCHED + 1))
    else
        echo "not found (skipped)"
        SKIPPED=$((SKIPPED + 1))
    fi
done

chmod 600 "$ENV_FILE"
echo "Done: $FETCHED fetched, $SKIPPED skipped"
