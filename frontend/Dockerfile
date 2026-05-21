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
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:${NODE_VERSION}-slim AS runtime
WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

RUN useradd -m -u 1000 app

# Copy only what next start needs.
COPY --from=builder --chown=app:app /app/.next         ./.next
COPY --from=builder --chown=app:app /app/public        ./public
COPY --from=builder --chown=app:app /app/node_modules  ./node_modules
COPY --from=builder --chown=app:app /app/package.json  ./package.json
COPY --from=builder --chown=app:app /app/next.config.ts ./next.config.ts

USER app
EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD node -e "require('http').get('http://127.0.0.1:3000/login', r => process.exit(r.statusCode === 200 ? 0 : 1)).on('error', () => process.exit(1))"

CMD ["npx", "next", "start", "-H", "0.0.0.0", "-p", "3000"]
