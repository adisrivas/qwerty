# syntax=docker/dockerfile:1.7
# Backend image: FastAPI served by uvicorn, running as a non-root user.
# Build context is the repository root (see docker-compose.yml).

FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/opt/venv
WORKDIR /build
COPY backend/pyproject.toml backend/uv.lock backend/README.md ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/app ./app
RUN uv sync --frozen --no-dev

FROM python:3.12-slim AS runtime
RUN useradd --create-home --uid 10001 windforecast
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    WINDFORECAST_ENVIRONMENT=docker \
    WINDFORECAST_SNAPSHOT_DIR=/srv/windforecast/data/snapshots
WORKDIR /srv/windforecast
COPY --from=builder /opt/venv /opt/venv
COPY --chown=windforecast:windforecast backend/app ./app
COPY --chown=windforecast:windforecast backend/data/snapshots ./data/snapshots
USER windforecast
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=2).status == 200 else 1)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
