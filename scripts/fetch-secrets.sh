#!/usr/bin/env bash
# Fetch secrets from Azure Key Vault and write them to .env for Docker Compose.
#
# OpenClaw is a pre-built container that reads secrets from environment variables.
# vizier-mcp has built-in Key Vault support, but OpenClaw does not. This script
# bridges the gap by pulling secrets from Key Vault into the shared .env file
# before docker compose up.
#
# Prerequisites:
#   - Azure CLI installed and logged in (az login), OR
#   - Managed Identity configured on the VM
#   - AZURE_KEY_VAULT_URL set in .env or environment
#
# Usage: bash scripts/fetch-secrets.sh [env-file]
#   env-file defaults to /opt/vizier/.env

set -euo pipefail

ENV_FILE="${1:-/opt/vizier/.env}"

if [ ! -f "$ENV_FILE" ]; then
    echo "ERROR: $ENV_FILE not found"
    exit 1
fi

# Read vault URL from .env or environment
VAULT_URL="${AZURE_KEY_VAULT_URL:-}"
if [ -z "$VAULT_URL" ]; then
    VAULT_URL=$(grep "^AZURE_KEY_VAULT_URL=" "$ENV_FILE" 2>/dev/null | cut -d= -f2- || true)
fi

if [ -z "$VAULT_URL" ]; then
    echo "AZURE_KEY_VAULT_URL not set -- skipping Key Vault fetch"
    exit 0
fi

echo "Fetching secrets from Key Vault: $VAULT_URL"

# Extract vault name from URL (https://myvault.vault.azure.net/ -> myvault)
VAULT_NAME=$(echo "$VAULT_URL" | sed 's|https://||;s|\.vault\.azure\.net.*||')

# Secret mapping: env-var-name -> key-vault-secret-name
declare -A SECRETS=(
    ["ANTHROPIC_API_KEY"]="anthropic-api-key"
    ["TELEGRAM_BOT_TOKEN"]="telegram-bot-token"
    ["TELEGRAM_SULTAN_CHAT_ID"]="telegram-sultan-chat-id"
)

update_env_var() {
    local key="$1"
    local value="$2"
    local file="$3"

    # Remove existing line (if any) and append new value
    grep -v "^${key}=" "$file" > "${file}.tmp" || true
    echo "${key}=${value}" >> "${file}.tmp"
    mv "${file}.tmp" "$file"
}

FETCHED=0
FAILED=0

for env_var in "${!SECRETS[@]}"; do
    kv_name="${SECRETS[$env_var]}"
    echo -n "  $env_var ($kv_name): "

    value=$(az keyvault secret show --vault-name "$VAULT_NAME" --name "$kv_name" --query value -o tsv 2>/dev/null) || true

    if [ -n "$value" ]; then
        update_env_var "$env_var" "$value" "$ENV_FILE"
        echo "OK"
        FETCHED=$((FETCHED + 1))
    else
        echo "not found (skipped)"
        FAILED=$((FAILED + 1))
    fi
done

echo "Done: $FETCHED fetched, $FAILED skipped"
