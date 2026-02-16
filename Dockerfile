FROM python:3.11-slim AS base

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

WORKDIR /app

COPY pyproject.toml uv.lock* ./
COPY libs/ libs/
COPY apps/ apps/
COPY plugins/ plugins/

RUN uv sync --all-packages --no-dev

RUN mkdir -p /opt/vizier/workspaces \
    /opt/vizier/reports \
    /opt/vizier/ea \
    /opt/vizier/security \
    /opt/vizier/checkout \
    /opt/vizier/logs

ENV VIZIER_ROOT=/opt/vizier

EXPOSE 8080

ENTRYPOINT ["uv", "run", "vizier"]
CMD ["start", "--root", "/opt/vizier"]
