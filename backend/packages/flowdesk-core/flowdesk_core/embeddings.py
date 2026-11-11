"""Provider-agnostic text embeddings for NOVA semantic retrieval.

Embeddings are independent of the chat platform provider. Two paths:
  * MiniMax (`embo-01`, 1536-dim) — FlowDesktop's platform provider; its embeddings
    API differs from OpenAI's (a `type: db|query` field, vectors under `vectors`),
    so it's called directly over HTTP.
  * OpenAI / Google families — via LiteLLM (`litellm.aembedding`).

The model is configured via settings.embedding_model. `embedding_dim` must match
the vector(N) column in retrieval_chunks (migration 023). See
docs/design/RFC_NOVA_SEMANTIC_RETRIEVAL.md.
"""

from __future__ import annotations

import asyncio
import logging
import os
import threading

import httpx
import litellm

from flowdesk_core.config import get_settings

logger = logging.getLogger(__name__)

# sk-cp-* MiniMax keys use the global endpoint (not api.minimax.chat).
_MINIMAX_BASE = "https://api.minimax.io/v1"

# Lazily-loaded local fastembed model (ONNX, CPU). Loaded once per process; the
# model files are baked into the image at FASTEMBED_CACHE_PATH (no runtime
# download in prod).
_local_model = None
_local_model_lock = threading.Lock()


def _get_local_model():
    global _local_model
    if _local_model is None:
        with _local_model_lock:
            if _local_model is None:
                from fastembed import TextEmbedding

                cache_dir = os.environ.get("FASTEMBED_CACHE_PATH") or None
                _local_model = TextEmbedding(
                    model_name=get_settings().embedding_model, cache_dir=cache_dir
                )
                logger.info("Loaded local embedding model %s", get_settings().embedding_model)
    return _local_model


class EmbeddingError(Exception):
    """Raised when embeddings are unconfigured or the provider call fails."""


def _provider_for_model(model: str) -> str:
    # HuggingFace-style names (with a "/") are local fastembed models.
    if "/" in model:
        return "local"
    m = model.lower()
    if m.startswith("embo") or m.startswith("minimax"):
        return "minimax"
    if m.startswith("text-embedding-004") or m.startswith("gemini-embedding"):
        return "google"
    # text-embedding-3-*, text-embedding-ada-*, and anything else default to OpenAI.
    return "openai"


def embedding_model_id() -> str:
    """The configured embedding model id — also stored in retrieval_chunks.model
    so vectors can be filtered/re-indexed per model."""
    return get_settings().embedding_model


def _resolve() -> tuple[str, str, str, str | None]:
    """Return (provider, model_string, api_key, group_id|None) for the configured
    embedding model. Raises EmbeddingError if the provider key is missing."""
    s = get_settings()
    model = s.embedding_model
    provider = _provider_for_model(model)

    if provider == "local":
        return ("local", model, "", None)

    if provider == "minimax":
        key = s.minimax_api_key or ""
        if not key:
            raise EmbeddingError(
                f"Embedding model '{model}' needs MINIMAX_API_KEY but it is unset."
            )
        return ("minimax", model, key, s.minimax_group_id or "")

    key_attr = "google_ai_api_key" if provider == "google" else "openai_api_key"
    key = getattr(s, key_attr, "") or ""
    if not key:
        raise EmbeddingError(
            f"Embedding model '{model}' needs {key_attr} but it is unset. "
            "Set the key or change settings.embedding_model."
        )
    prefix = "gemini/" if provider == "google" else "openai/"
    return (provider, f"{prefix}{model}", key, None)


def is_configured() -> bool:
    """True when embeddings can be produced (provider key present)."""
    try:
        _resolve()
        return True
    except EmbeddingError:
        return False


async def _minimax_embed(
    texts: list[str], api_key: str, group_id: str, kind: str
) -> list[list[float]]:
    """Call MiniMax's embeddings endpoint directly (non-OpenAI shape).

    kind: 'db' to embed stored documents, 'query' to embed a search query —
    MiniMax uses asymmetric vectors, so this matters for retrieval quality.

    NOTE: sk-cp-* keys on api.minimax.io are self-scoped — the token carries the
    group, and sending a GroupId query param triggers 1004 "token not match
    group". (The legacy api.minimax.chat endpoint required GroupId; this one must
    NOT.) group_id is accepted for signature compatibility but intentionally unused.
    """
    etype = "query" if kind == "query" else "db"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"model": get_settings().embedding_model, "type": etype, "texts": texts}
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(f"{_MINIMAX_BASE}/embeddings", headers=headers, json=payload)
            r.raise_for_status()
            body = r.json()
    except Exception as exc:  # noqa: BLE001 — normalize to one error type
        raise EmbeddingError(str(exc)[:300]) from exc

    base = body.get("base_resp") or {}
    status = base.get("status_code")
    if status not in (0, None):
        raise EmbeddingError(f"minimax embeddings status {status}: {base.get('status_msg')}")
    vectors = body.get("vectors")
    if not vectors:
        raise EmbeddingError("minimax embeddings: no vectors in response")
    return vectors


def _local_embed_sync(texts: list[str]) -> list[list[float]]:
    model = _get_local_model()
    # paraphrase-multilingual-MiniLM is symmetric — no query/passage prefix.
    return [v.tolist() for v in model.embed(texts)]


async def _local_embed(texts: list[str]) -> list[list[float]]:
    """Embed with the local ONNX model off the event loop (CPU-bound)."""
    try:
        return await asyncio.to_thread(_local_embed_sync, texts)
    except Exception as exc:  # noqa: BLE001
        raise EmbeddingError(str(exc)[:300]) from exc


async def embed_texts(texts: list[str], *, kind: str = "db") -> list[list[float]]:
    """Embed a batch of texts in one provider call. Order matches the input.

    kind: 'db' (documents, default) or 'query' — only affects MiniMax.
    Empty input → []. Raises EmbeddingError on provider failure so callers can
    decide to skip (indexer) or surface a friendly error (tool).
    """
    if not texts:
        return []
    provider, model_string, api_key, group_id = _resolve()

    if provider == "local":
        return await _local_embed(texts)

    if provider == "minimax":
        return await _minimax_embed(texts, api_key, group_id or "", kind)

    try:
        resp = await litellm.aembedding(
            model=model_string, input=texts, api_key=api_key, timeout=30
        )
    except Exception as exc:  # noqa: BLE001
        raise EmbeddingError(str(exc)[:300]) from exc
    data = sorted(resp["data"], key=lambda d: d.get("index", 0))
    return [d["embedding"] for d in data]


async def embed_query(text: str) -> list[float]:
    """Embed a single query string (uses the 'query' asymmetry on MiniMax)."""
    vecs = await embed_texts([text], kind="query")
    if not vecs:
        raise EmbeddingError("Empty embedding response for query.")
    return vecs[0]
