FROM ghcr.io/astral-sh/uv:bookworm-slim

WORKDIR /app

COPY dietdashboard/ dietdashboard/
COPY artifacts/ artifacts/
COPY data/data.db data/data.db
COPY data/store_discovery.db data/store_discovery.db
COPY pyproject.toml uv.lock ./

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_CACHE_DIR=/root/.cache/uv \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH=/app/.venv/bin:$PATH \
    PROD=1 \
    STORE_DISCOVERY_MODE=local \
    GUNICORN_WORKERS=1 \
    GUNICORN_THREADS=1 \
    GUNICORN_TIMEOUT=120 \
    GUNICORN_GRACEFUL_TIMEOUT=15 \
    NEARBY_STORES_TIMEOUT_S=3.0 \
    RECOMMENDATION_STORE_LOOKUP_TIMEOUT_S=2.0 \
    STORE_FIT_TIMEOUT_S=0.75

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-editable --no-dev --extra ml

EXPOSE 8000

CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:8000 --workers ${GUNICORN_WORKERS:-1} --threads ${GUNICORN_THREADS:-1} --timeout ${GUNICORN_TIMEOUT:-120} --graceful-timeout ${GUNICORN_GRACEFUL_TIMEOUT:-15} 'dietdashboard.app:create_app()'"]
