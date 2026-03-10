FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1

RUN apt-get update && apt-get install -y --no-install-recommends curl git && \
    rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /usr/local/bin/uv

WORKDIR /app

# ---------- dependency layer (cached) ----------
FROM base AS deps

COPY vizier-mcp/pyproject.toml vizier-mcp/pyproject.toml
COPY pyproject.toml pyproject.toml

RUN uv sync --directory vizier-mcp --no-dev --no-install-project

# ---------- application layer ----------
FROM deps AS app

COPY vizier-mcp/ vizier-mcp/

RUN uv sync --directory vizier-mcp --no-dev

RUN addgroup --system vizier && adduser --system --home /home/vizier --ingroup vizier vizier && \
    mkdir -p /data/vizier/projects && chown -R vizier:vizier /data/vizier

USER vizier

ENV VIZIER_ROOT=/data/vizier \
    HEALTH_PORT=8080 \
    MCP_TRANSPORT=streamable-http \
    MCP_PORT=8001

EXPOSE 8080 8001

VOLUME ["/data/vizier"]

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -sf http://localhost:8080/health || exit 1

ENTRYPOINT ["uv", "run", "--directory", "vizier-mcp", "python", "-m", "vizier_mcp"]
