# syntax=docker/dockerfile:1.7
# Multi-stage production image for the Next.js frontend.
# - deps stage: install npm deps with build toolchain available
# - builder stage: run `next build`
# - runtime stage: minimal node image, non-root, /login healthcheck

ARG NODE_VERSION=22

FROM node:${NODE_VERSION}-slim AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci --no-audit --no-fund

FROM node:${NODE_VERSION}-slim AS builder
WORKDIR /app
# Next.js bakes `rewrites()` destinations at build time, so API_BASE_URL must be
# set here, not at runtime. Override with --build-arg if your backend lives
# elsewhere; the default points at the `backend` service in our compose stack.
ARG API_BASE_URL=http://backend:8000
# Sentry. NEXT_PUBLIC_* is inlined into the client bundle at build time, so the
# DSN must be present HERE — setting it at runtime does nothing. All default to
# empty, and the SDK no-ops without a DSN, so an unconfigured build is a normal
# build that reports nothing.
ARG NEXT_PUBLIC_SENTRY_DSN=""
ARG NEXT_PUBLIC_SENTRY_ENVIRONMENT="production"
ARG NEXT_PUBLIC_SENTRY_RELEASE=""
ARG SENTRY_ORG=""
ARG SENTRY_PROJECT=""
ENV API_BASE_URL=${API_BASE_URL} \
    NEXT_TELEMETRY_DISABLED=1 \
    NEXT_PUBLIC_SENTRY_DSN=${NEXT_PUBLIC_SENTRY_DSN} \
    NEXT_PUBLIC_SENTRY_ENVIRONMENT=${NEXT_PUBLIC_SENTRY_ENVIRONMENT} \
    NEXT_PUBLIC_SENTRY_RELEASE=${NEXT_PUBLIC_SENTRY_RELEASE} \
    SENTRY_ORG=${SENTRY_ORG} \
    SENTRY_PROJECT=${SENTRY_PROJECT}
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# Mount Next.js's incremental build cache so `next build` can reuse compiled
# output across CI runs. The mount is ephemeral to the build (never baked into
# a layer), and `next start` doesn't need .next/cache at runtime — so the
# runtime COPY of /app/.next below is unaffected. CI persists this mount across
# runs via buildkit-cache-dance (see deploy-prod.yml).
# SENTRY_AUTH_TOKEN comes in as a BuildKit secret, not an ARG: ARG values are
# recorded in the image history and would leak the token to anyone who can pull
# the image. Absent secret => no source map upload, build still succeeds.
RUN --mount=type=cache,target=/app/.next/cache \
    --mount=type=secret,id=sentry_auth_token,required=false \
    SENTRY_AUTH_TOKEN="$(cat /run/secrets/sentry_auth_token 2>/dev/null || true)" \
    npm run build

FROM node:${NODE_VERSION}-slim AS runtime
WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

# The node base image ships a non-root `node` user at UID 1000 — reuse it
# instead of creating a duplicate (which fails with UID-not-unique).

# Copy only what next start needs.
COPY --from=builder --chown=node:node /app/.next         ./.next
COPY --from=builder --chown=node:node /app/public        ./public
COPY --from=builder --chown=node:node /app/node_modules  ./node_modules
COPY --from=builder --chown=node:node /app/package.json  ./package.json
COPY --from=builder --chown=node:node /app/next.config.ts ./next.config.ts

USER node
EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD node -e "require('http').get('http://127.0.0.1:3000/login', r => process.exit(r.statusCode === 200 ? 0 : 1)).on('error', () => process.exit(1))"

CMD ["npx", "next", "start", "-H", "0.0.0.0", "-p", "3000"]
