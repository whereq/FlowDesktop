# =============================================================================
# FlowDesktop API — production Dockerfile
#
# Build context is the REPOSITORY ROOT (not docker/api):
#     docker build -f docker/api/Dockerfile .
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: builder — resolve and install dependencies
# -----------------------------------------------------------------------------
FROM python:3.12-slim-bookworm AS builder

WORKDIR /build

# gcc/libpq-dev are needed to build any dependency without a prebuilt wheel.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# ── Dependency layer ───────────────────────────────────────────────────────
# Only the manifests and the two local packages are copied here, so a change
# to the application code does not invalidate the dependency layer.
COPY backend/pyproject.toml backend/uv.lock ./backend/
COPY backend/packages/flowdesk-core/pyproject.toml ./backend/packages/flowdesk-core/
COPY backend/packages/flowdesk-core/flowdesk_core ./backend/packages/flowdesk-core/flowdesk_core
COPY backend/packages/flowdesk-collector/pyproject.toml ./backend/packages/flowdesk-collector/
COPY backend/packages/flowdesk-collector/flowdesk_collector ./backend/packages/flowdesk-collector/flowdesk_collector

ENV PATH="/opt/venv/bin:$PATH"

# Install FROM uv.lock, never from pyproject.toml alone.
#
# `uv export --locked` reads the pinned lockfile and fails the build when
# pyproject.toml and uv.lock have drifted apart — a stale lock is a loud
# error rather than a silently different install. It is a local read of
# uv.lock: no network, no credentials, no private package index.
#
# The two local packages are path dependencies, so they are installed from
# ./packages — there is nothing to fetch over the network.
#
# `--extra embeddings` pulls in the local ONNX embedding model, so the model
# can be baked into the image below and semantic search needs no runtime
# download.
RUN cd backend \
    && uv venv /opt/venv \
    && uv export --locked --extra embeddings --no-dev --no-emit-project --no-hashes --no-editable \
         --format requirements.txt -o /tmp/requirements.txt \
    && uv pip install --no-cache -r /tmp/requirements.txt

# -----------------------------------------------------------------------------
# Stage 2: runtime — minimal production image
# -----------------------------------------------------------------------------
FROM python:3.12-slim-bookworm AS runtime

LABEL maintainer="FlowDesktop contributors"
LABEL description="FlowDesktop API service"

RUN groupadd -r flowdesktop && useradd -r -g flowdesktop flowdesktop

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Bake the local embedding model into the image so semantic search works
# offline and no model is downloaded on first request. Placed BEFORE the
# application-code COPY so ordinary code changes reuse this cached layer.
#
# A download failure must NOT fail the build: the model comes from a public
# model hub, and a user behind a firewall or a mirror should still get a
# working image. The embedding model is loaded lazily, so without it only the
# optional semantic-search feature is affected — it will fetch the model on
# first use instead.
ENV FASTEMBED_CACHE_PATH=/app/.fastembed
RUN python -c "import os; from fastembed import TextEmbedding; TextEmbedding('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2', cache_dir=os.environ['FASTEMBED_CACHE_PATH'])" \
    || echo "[build] WARNING: could not pre-download the embedding model. The image still builds; semantic search will download it on first use."

# ── Application layer ──────────────────────────────────────────────────────
COPY backend/api ./api
COPY backend/flowdesk ./flowdesk
COPY backend/worker ./worker
COPY backend/evals ./evals
COPY backend/alembic ./alembic
COPY backend/alembic.ini ./alembic.ini

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

RUN chown -R flowdesktop:flowdesktop /app

USER flowdesktop

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
