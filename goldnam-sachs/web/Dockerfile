FROM node:24-slim AS build
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
RUN --mount=type=secret,id=build_ca \
    if [ -f /run/secrets/build_ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/build_ca; fi; \
    npm install --global pnpm@12.21.0
COPY web/package.json web/pnpm-lock.yaml ./web/
RUN --mount=type=secret,id=build_ca \
    if [ -f /run/secrets/build_ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/build_ca; fi; \
    cd web && pnpm install --frozen-lockfile
COPY engine/goldnam_engine/_version.py ./engine/goldnam_engine/_version.py
COPY web ./web
RUN cd web && pnpm build
FROM nginx:stable-alpine
COPY --from=build /app/web/out /usr/share/nginx/html
