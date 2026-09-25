# syntax=docker/dockerfile:1.7
# CTCV web (PWA) — build context = repo root (brief D14):
#   docker compose -f deploy/docker-compose.yml --profile cpu build web
# Stage 1 builds apps/web with pnpm (Vite → apps/web/dist); stage 2 serves the static
# bundle with Caddy: SPA fallback to /index.html and /v1 → api:8000 reverse proxy
# (deploy/caddy/Caddyfile.web). In prod the edge caddy sits in front of this container.

ARG NODE_IMAGE=node:20-alpine
ARG CADDY_IMAGE=caddy:2-alpine
ARG PNPM_VERSION=10.18.0

# ------------------------------------------------------------------ build
FROM ${NODE_IMAGE} AS build
ARG PNPM_VERSION
RUN npm install -g "pnpm@${PNPM_VERSION}"
WORKDIR /workspace

# Manifests first so the pnpm store layer survives source edits (lockfile optional in E01).
COPY package.json pnpm-workspace.yaml pnpm-lock.yaml* ./
COPY apps/web/package.json apps/web/
RUN --mount=type=cache,target=/root/.local/share/pnpm/store \
    if [ -f pnpm-lock.yaml ]; then pnpm install --frozen-lockfile; else pnpm install; fi

COPY apps/web apps/web
COPY config config
RUN pnpm -C apps/web build

# ------------------------------------------------------------------ serve
FROM ${CADDY_IMAGE} AS runtime
COPY deploy/caddy/Caddyfile.web /etc/caddy/Caddyfile
COPY --from=build /workspace/apps/web/dist /srv
RUN caddy validate --config /etc/caddy/Caddyfile

EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD ["wget", "-qO-", "http://127.0.0.1/healthz"]
# caddy:2-alpine's default CMD (`caddy run --config /etc/caddy/Caddyfile --adapter caddyfile`) is kept.
