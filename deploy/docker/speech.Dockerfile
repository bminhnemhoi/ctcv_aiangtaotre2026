# syntax=docker/dockerfile:1.7
# CTCV speech service — build context = repo root (brief D14):
#   docker compose -f deploy/docker-compose.yml --profile cpu build speech
# Two stages: `builder` resolves the uv workspace (third-party deps in their own cached
# layer, then the workspace packages as editable installs so the dev overlay can bind-mount
# sources for hot reload); `runtime` copies /app into a non-root image. Nothing in here
# downloads a model — models arrive at runtime through the HF cache volume.
# The four Python Dockerfiles differ only in service name, port, APT packages and
# start period (deploy/tests/test_deploy.py::test_python_dockerfiles_are_consistent).

ARG PYTHON_IMAGE=python:3.12-slim

# ------------------------------------------------------------------ builder
FROM ${PYTHON_IMAGE} AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

# 1. Manifests of every workspace member (uv needs the whole graph to honour uv.lock).
COPY pyproject.toml uv.lock ./
COPY libs/core/pyproject.toml libs/core/README.md libs/core/
COPY services/api/pyproject.toml services/api/
COPY services/agent/pyproject.toml services/agent/
COPY services/speech/pyproject.toml services/speech/
COPY services/vision/pyproject.toml services/vision/
COPY sandbox/pyproject.toml sandbox/
COPY drills/pyproject.toml drills/
COPY data/pyproject.toml data/
COPY training/pyproject.toml training/
COPY eval/pyproject.toml eval/

# 2. Third-party dependencies only (cached until uv.lock changes).
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-workspace --package ctcv-speech

# 3. Sources: shared lib, config (yaml/schemas/prompts), scenario data and this service.
COPY libs/core libs/core
COPY config config
COPY sandbox sandbox
COPY drills drills
COPY services/speech services/speech

# 4. Workspace packages — editable by default, --no-editable as the fallback (task spec).
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --package ctcv-speech \
    || uv sync --frozen --no-dev --no-editable --package ctcv-speech

# ------------------------------------------------------------------ runtime
FROM ${PYTHON_IMAGE} AS runtime

ARG APT_PACKAGES="ffmpeg libgomp1"
RUN set -eux; \
    if [ -n "$APT_PACKAGES" ]; then \
      apt-get update \
      && apt-get install -y --no-install-recommends $APT_PACKAGES \
      && rm -rf /var/lib/apt/lists/*; \
    fi; \
    groupadd --gid 10001 ctcv; \
    useradd --uid 10001 --gid ctcv --create-home --shell /usr/sbin/nologin ctcv; \
    mkdir -p /var/cache/ctcv/tts /var/cache/ctcv/hf /var/lib/ctcv; \
    chown -R ctcv:ctcv /var/cache/ctcv /var/lib/ctcv

WORKDIR /app
COPY --from=builder --chown=ctcv:ctcv /app /app
COPY --chown=ctcv:ctcv deploy/docker/healthcheck.py deploy/docker/serve.py /app/

ENV PATH="/app/.venv/bin:$PATH" \
    CTCV_REPO_ROOT=/app \
    CTCV_ENV=prod \
    HF_HOME=/var/cache/ctcv/hf \
    TTS_CACHE_DIR=/var/cache/ctcv/tts \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER ctcv
EXPOSE 8020

# GET /health must answer 200 (brief §3). Same probe as the compose healthcheck.
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=3 \
    CMD ["python", "/app/healthcheck.py", "8020", "/health"]

# Spec form: `uvicorn ctcv_speech.main:app --host 0.0.0.0 --port 8020`. serve.py resolves the
# real ASGI target (main:app | asgi:app | app:create_app …, or CTCV_APP_TARGET) and runs
# uvicorn with it, so the image survives the services' own layout choices.
CMD ["python", "/app/serve.py", "ctcv_speech", "8020"]
