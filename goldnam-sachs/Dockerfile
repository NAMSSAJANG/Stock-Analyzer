# syntax=docker/dockerfile:1
FROM node:24-bookworm-slim AS web
WORKDIR /build
COPY web/package.json web/pnpm-lock.yaml ./web/
RUN --mount=type=secret,id=build_ca \
    if [ -f /run/secrets/build_ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/build_ca; fi; \
    npm install --global pnpm@12.21.0 && cd web && pnpm install --frozen-lockfile
COPY web ./web
COPY engine/goldnam_engine/_version.py ./engine/goldnam_engine/_version.py
ENV NEXT_TELEMETRY_DISABLED=1
RUN cd web && pnpm build

FROM ghcr.io/astral-sh/uv:0.13.9 AS uv
FROM python:3.12-slim
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY --chmod=755 engine/goldnam_engine ./engine/goldnam_engine
COPY --chmod=755 jobs ./jobs
COPY --chmod=755 api ./api
COPY --chmod=755 scripts/serve.py ./scripts/serve.py
RUN --mount=type=secret,id=build_ca \
    if [ -f /run/secrets/build_ca ]; then export SSL_CERT_FILE=/run/secrets/build_ca; fi; \
    uv sync --system-certs --frozen --no-dev --extra api && \
    useradd --create-home --uid 10001 goldnam && mkdir -p /app/.data && chown goldnam /app/.data
COPY --from=web --chmod=755 /build/web/out ./web/out
ENV PATH="/app/.venv/bin:$PATH" WEB_STATIC_DIR=/app/web/out PYTHONDONTWRITEBYTECODE=1 MPLCONFIGDIR=/tmp/matplotlib XDG_CACHE_HOME=/tmp/cache
USER goldnam
EXPOSE 10000
CMD ["python", "scripts/serve.py"]
