# syntax=docker/dockerfile:1.7
# Multi-stage production image for the FastAPI backend.
# - Builder installs deps with build toolchain available.
# - Runtime image has libpq5 only, runs as non-root, has a /health probe.

ARG PYTHON_VERSION=3.12

FROM python:${PYTHON_VERSION}-slim AS builder
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --user --no-warn-script-location -r requirements.txt


FROM python:${PYTHON_VERSION}-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/home/app/.local/bin:$PATH \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    DEBIAN_FRONTEND=noninteractive \
    # The builder stage installed Python deps with `pip install --user`,
    # so they live under /home/app/.local after the COPY below. Tell
    # Python explicitly to use that as the user site base — without this
    # root would look in /root/.local (empty) and `playwright install`
    # would fail with ModuleNotFoundError.
    PYTHONUSERBASE=/home/app/.local

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 curl tini \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 1000 app

WORKDIR /app

COPY --from=builder --chown=app:app /root/.local /home/app/.local

# Chromium + its system libs for headless PDF rendering (Tier 14 papers
# use KaTeX inside a real browser so output matches the Question Bank
# preview byte-for-byte). --with-deps invokes apt-get under the hood,
# so this runs as root before USER app. ~280 MB added to the image.
RUN mkdir -p /ms-playwright \
    && apt-get update \
    && /home/app/.local/bin/playwright install --with-deps chromium \
    && chown -R app:app /ms-playwright \
    && rm -rf /var/lib/apt/lists/*

COPY --chown=app:app . .

USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--proxy-headers", "--forwarded-allow-ips", "*"]
