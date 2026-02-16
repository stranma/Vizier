#!/usr/bin/env bash
set -euo pipefail

# Vizier server setup script
# Creates the /opt/vizier directory structure and configures the daemon

VIZIER_ROOT="${VIZIER_ROOT:-/opt/vizier}"
VIZIER_USER="${VIZIER_USER:-vizier}"

echo "Setting up Vizier at ${VIZIER_ROOT}..."

# Create vizier user if it doesn't exist
if ! id -u "${VIZIER_USER}" >/dev/null 2>&1; then
    useradd --system --home-dir "${VIZIER_ROOT}" --shell /usr/sbin/nologin "${VIZIER_USER}"
    echo "Created user: ${VIZIER_USER}"
fi

# Create directory structure
dirs=(
    "${VIZIER_ROOT}"
    "${VIZIER_ROOT}/workspaces"
    "${VIZIER_ROOT}/reports"
    "${VIZIER_ROOT}/ea"
    "${VIZIER_ROOT}/ea/commitments"
    "${VIZIER_ROOT}/ea/relationships"
    "${VIZIER_ROOT}/security"
    "${VIZIER_ROOT}/checkout"
    "${VIZIER_ROOT}/logs"
)

for dir in "${dirs[@]}"; do
    mkdir -p "${dir}"
done
echo "Created directory structure"

# Set ownership
chown -R "${VIZIER_USER}:${VIZIER_USER}" "${VIZIER_ROOT}"
echo "Set ownership to ${VIZIER_USER}"

# Create default config if not exists
if [ ! -f "${VIZIER_ROOT}/config.yaml" ]; then
    cat > "${VIZIER_ROOT}/config.yaml" << 'YAML'
vizier_root: /opt/vizier
workspaces_dir: workspaces
reports_dir: reports
ea_data_dir: ea
security_dir: security
max_concurrent_agents: 5
reconciliation_interval_seconds: 15
heartbeat_path: heartbeat.json
monthly_budget_usd: 100.0
health_check_port: 8080
autonomy:
  stage: 1
  auto_approve_plugins: []
YAML
    echo "Created default config.yaml"
fi

# Create .env template if not exists
if [ ! -f "${VIZIER_ROOT}/.env" ]; then
    cat > "${VIZIER_ROOT}/.env" << 'ENV'
# Vizier Environment Variables
# Copy this file and fill in your values

# LLM API Keys
ANTHROPIC_API_KEY=
OPENAI_API_KEY=

# Telegram Bot
TELEGRAM_BOT_TOKEN=
TELEGRAM_ALLOWED_USER_IDS=

# Langfuse (optional)
LANGFUSE_NEXTAUTH_SECRET=changeme
LANGFUSE_SALT=changeme

# GitHub (for project cloning)
GITHUB_TOKEN=
ENV
    chmod 600 "${VIZIER_ROOT}/.env"
    echo "Created .env template (fill in your values)"
fi

# Create empty projects registry if not exists
if [ ! -f "${VIZIER_ROOT}/projects.yaml" ]; then
    cat > "${VIZIER_ROOT}/projects.yaml" << 'YAML'
projects: []
YAML
    echo "Created empty projects.yaml"
fi

# Install systemd service if systemd is available
if command -v systemctl >/dev/null 2>&1; then
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    SERVICE_FILE="${SCRIPT_DIR}/../vizier.service"
    if [ -f "${SERVICE_FILE}" ]; then
        cp "${SERVICE_FILE}" /etc/systemd/system/vizier.service
        systemctl daemon-reload
        echo "Installed systemd service"
        echo "  Enable with: systemctl enable vizier"
        echo "  Start with:  systemctl start vizier"
    fi
fi

echo ""
echo "Vizier setup complete!"
echo ""
echo "Next steps:"
echo "  1. Edit ${VIZIER_ROOT}/.env with your API keys"
echo "  2. Register projects: vizier register <name> --repo <url>"
echo "  3. Start daemon: vizier start (or systemctl start vizier)"
