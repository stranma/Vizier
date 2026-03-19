FROM python:3.11-bookworm AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl ca-certificates gnupg \
    && rm -rf /var/lib/apt/lists/*

# Node.js 22 (required by Hermes for MCP npx servers)
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# uv (Python package manager)
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /usr/local/bin/uv

# ---------- install hermes-agent ----------
FROM base AS hermes-install

# Pin to a specific version for reproducible builds.
# Update this when upgrading Hermes.
ARG HERMES_VERSION=main

RUN git clone --recurse-submodules --depth 1 \
    -b ${HERMES_VERSION} \
    https://github.com/NousResearch/hermes-agent.git /opt/hermes-agent

WORKDIR /opt/hermes-agent

RUN uv venv /opt/hermes-venv --python 3.11 \
    && VIRTUAL_ENV=/opt/hermes-venv uv pip install -e ".[mcp,messaging,cli]"

# ---------- runtime ----------
FROM base AS runtime

# Copy the installed venv and hermes source
COPY --from=hermes-install /opt/hermes-venv /opt/hermes-venv
COPY --from=hermes-install /opt/hermes-agent /opt/hermes-agent

ENV PATH="/opt/hermes-venv/bin:$PATH" \
    HERMES_HOME=/home/hermes/.hermes

# Create non-root user
RUN useradd -m -s /bin/bash hermes \
    && mkdir -p $HERMES_HOME/sessions $HERMES_HOME/logs $HERMES_HOME/memories $HERMES_HOME/skills \
    && mkdir -p /workspace \
    && chown -R hermes:hermes /home/hermes /workspace

# Copy Vizier-specific configuration
COPY config.yaml $HERMES_HOME/config.yaml
COPY SOUL.md $HERMES_HOME/SOUL.md
COPY AGENTS.md /workspace/AGENTS.md
COPY scripts/entrypoint.sh /usr/local/bin/entrypoint.sh
COPY scripts/healthcheck.sh /usr/local/bin/healthcheck.sh

RUN chmod +x /usr/local/bin/entrypoint.sh /usr/local/bin/healthcheck.sh \
    && chown -R hermes:hermes $HERMES_HOME /workspace

USER hermes
WORKDIR /workspace

HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
    CMD /usr/local/bin/healthcheck.sh

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["hermes", "gateway"]
