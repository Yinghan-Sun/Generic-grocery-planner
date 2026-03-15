FROM python:3.13-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

RUN python -m venv .venv
COPY pyproject.toml uv.lock ./
RUN .venv/bin/pip install .

FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PROD=1 \
    STORE_DISCOVERY_MODE=local

WORKDIR /app

COPY --from=builder /app/.venv .venv/
COPY . .

CMD ["/app/.venv/bin/python", "-m", "dietdashboard.app"]
