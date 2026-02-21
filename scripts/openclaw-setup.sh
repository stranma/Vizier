#!/usr/bin/env bash
# OpenClaw first-time setup script.
# Run this on the server after initial deployment to configure Telegram pairing.
#
# Usage: bash scripts/openclaw-setup.sh

set -euo pipefail

COMPOSE_DIR="/opt/vizier"

echo "=== OpenClaw First-Time Setup ==="
echo ""

# Check prerequisites
if ! command -v docker &>/dev/null; then
    echo "ERROR: docker is not installed"
    exit 1
fi

if ! docker compose -f "$COMPOSE_DIR/docker-compose.yml" ps openclaw --format '{{.State}}' 2>/dev/null | grep -q running; then
    echo "ERROR: openclaw container is not running"
    echo "Run: cd $COMPOSE_DIR && docker compose up -d"
    exit 1
fi

# Check for Telegram bot token
token_val=$(grep "^TELEGRAM_BOT_TOKEN=" "$COMPOSE_DIR/.env" 2>/dev/null | cut -d= -f2- || true)
if [ -z "$token_val" ] || [[ "$token_val" == your-* ]]; then
    echo "WARNING: TELEGRAM_BOT_TOKEN not set in $COMPOSE_DIR/.env"
    echo ""
    echo "To get a bot token:"
    echo "  1. Open Telegram and message @BotFather"
    echo "  2. Send /newbot and follow the prompts"
    echo "  3. Copy the token and add to $COMPOSE_DIR/.env:"
    echo "     TELEGRAM_BOT_TOKEN=123456:ABC-DEF..."
    echo "  4. Restart: cd $COMPOSE_DIR && docker compose restart openclaw"
    echo ""
fi

echo "Telegram Pairing Instructions:"
echo "  1. Find your bot in Telegram (search by the name you gave @BotFather)"
echo "  2. Send /start to the bot"
echo "  3. The bot will reply with a pairing code"
echo "  4. Approve the pairing on the server:"
echo "     docker exec openclaw openclaw approve-pairing <code>"
echo ""
echo "After pairing, you can message the bot directly to interact with Vizier."
echo ""
echo "Verify the setup:"
echo "  curl -s http://localhost:18789/ | python3 -m json.tool"
echo ""
echo "=== Setup complete ==="
