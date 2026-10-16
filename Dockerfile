FROM ghcr.io/astral-sh/uv:0.9.25 AS uv-binary

FROM python:3.12-slim AS builder

COPY --from=uv-binary /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev


FROM python:3.12-slim AS runtime

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

RUN useradd --create-home --shell /bin/bash appuser
USER appuser

COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv
COPY --chown=appuser:appuser alembic.ini ./alembic.ini
COPY --chown=appuser:appuser src/ ./src

EXPOSE 8888

CMD ["sh", "-c", "alembic upgrade head && uvicorn src.api.main:app --host 0.0.0.0 --port 8888"]
