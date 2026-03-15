FROM ghcr.io/astral-sh/uv:bookworm-slim

WORKDIR /app

COPY dietdashboard/ dietdashboard/
COPY data/data.db data/data.db
COPY data/store_discovery.db data/store_discovery.db
COPY pyproject.toml uv.lock ./

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_CACHE_DIR=/root/.cache/uv \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH=/app/.venv/bin:$PATH \
    PROD=1 \
    STORE_DISCOVERY_MODE=local

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-editable --no-dev

EXPOSE 8000

CMD ["python", "-m", "dietdashboard.app"]
