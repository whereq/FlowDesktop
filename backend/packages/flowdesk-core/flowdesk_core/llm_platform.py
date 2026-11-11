"""Shared platform LLM utilities — used by both the API and the collector.

Two concerns live here:
  1. Provider resolution  — which provider/key to use for platform (non-BYOK) calls
  2. Structured LLM calls — call_platform_llm() wraps LiteLLM for internal jobs
     (market signal extraction, sector narrative generation)

Keep this module free of API-layer or collector-layer imports so it can be
imported from both containers without side effects.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any

import litellm

from flowdesk_core.config import get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Provider registry — single source of truth for both API and collector
# ---------------------------------------------------------------------------

# Default model per provider used in platform mode.
# Prefer cheaper/faster models for internal structured tasks;
# llm_gateway overrides with richer models for interactive chat.
DEFAULT_MODELS: dict[str, str] = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-haiku-4-5-20251001",
    "google": "gemini-2.0-flash",
    "deepseek": "deepseek-chat",
    "qwen": "qwen-plus",
    "minimax": "MiniMax-M3",
}

# ---------------------------------------------------------------------------
# Chat model tiers — used by the interactive NOVA chat (not internal jobs).
# "light" is the cheap default for simple lookups; "heavy" is escalated for
# analytical / multi-step questions (smart routing). Same provider/key/base —
# only the model id changes — so escalation never switches credentials.
# ---------------------------------------------------------------------------
CHAT_LIGHT_MODELS: dict[str, str] = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-haiku-4-5-20251001",
    "google": "gemini-2.0-flash",
    "deepseek": "deepseek-chat",
    "qwen": "qwen-plus",
    "minimax": "MiniMax-M3",
}
CHAT_HEAVY_MODELS: dict[str, str] = {
    "openai": "gpt-4o",
    "anthropic": "claude-opus-4-8",
    "google": "gemini-2.5-pro",
    "deepseek": "deepseek-reasoner",
    "qwen": "qwen-max",
    "minimax": "MiniMax-M2.7",
}


def chat_model_for(provider: str, *, heavy: bool) -> str:
    """Return the chat model id for a provider at the requested tier."""
    table = CHAT_HEAVY_MODELS if heavy else CHAT_LIGHT_MODELS
    return table.get(provider) or DEFAULT_MODELS.get(provider, "")


def is_anthropic_adaptive_model(model: str) -> bool:
    """True for Anthropic models that use adaptive thinking and reject
    temperature/budget_tokens (Opus 4.x, Fable 5, Sonnet 4.6)."""
    m = model.lower()
    return any(tag in m for tag in ("claude-opus-4", "claude-fable-5", "claude-sonnet-4-6"))


# Settings attribute that holds each provider's API key
KEY_MAP: dict[str, str] = {
    "openai": "openai_api_key",
    "anthropic": "anthropic_api_key",
    "google": "google_ai_api_key",
    "deepseek": "deepseek_api_key",
    "qwen": "qwen_api_key",
    "minimax": "minimax_api_key",
}

# Auto-selection order when PLATFORM_LLM_PROVIDER is not set
PROVIDER_ORDER: list[str] = ["openai", "anthropic", "google", "deepseek", "qwen", "minimax"]

# Providers that wrap output in <think>…</think> reasoning blocks
_REASONING_PROVIDERS: frozenset[str] = frozenset({"deepseek", "minimax"})

# Providers that support response_format={"type": "json_object"}
_JSON_MODE_PROVIDERS: frozenset[str] = frozenset({"openai", "deepseek", "minimax"})

# LiteLLM model-string prefix per provider (native routing, no api_base override)
_MODEL_PREFIX: dict[str, str] = {
    "openai": "openai/",
    "anthropic": "anthropic/",
    "google": "gemini/",
    "deepseek": "deepseek/",
    "qwen": "qwen/",
    "minimax": "minimax/",
}

# Custom api_base overrides for providers that need non-default endpoints.
# MiniMax sk-cp-* keys must use the global platform API (api.minimax.io),
# not the regional one LiteLLM defaults to (api.minimax.chat).
# When an api_base is set we switch to OpenAI-compatible mode ("openai/" prefix).
_API_BASE_OVERRIDES: dict[str, str] = {
    "minimax": "https://api.minimax.io/v1",
}


# ---------------------------------------------------------------------------
# Provider resolution
# ---------------------------------------------------------------------------


def resolve_platform_provider() -> tuple[str, str, str]:
    """Return (provider_name, model, api_key) for the configured platform provider.

    Respects PLATFORM_LLM_PROVIDER env var; falls back to the first provider
    with a configured API key in PROVIDER_ORDER.

    Raises ValueError if no provider is configured.
    """
    settings = get_settings()
    explicit = (settings.platform_llm_provider or "").strip().lower()
    order = [explicit] if explicit and explicit in KEY_MAP else PROVIDER_ORDER

    for name in order:
        key = getattr(settings, KEY_MAP[name], "")
        if key:
            _apply_provider_env(name, settings)
            return name, DEFAULT_MODELS[name], key

    raise ValueError(
        "No platform LLM provider configured. "
        "Set at least one *_API_KEY and optionally PLATFORM_LLM_PROVIDER."
    )


def _apply_provider_env(name: str, settings: Any) -> None:
    """Set any extra env vars a provider requires (e.g. group IDs)."""
    if name == "minimax" and getattr(settings, "minimax_group_id", ""):
        os.environ["MINIMAX_GROUP_ID"] = settings.minimax_group_id


def provider_api_base(provider: str) -> str | None:
    """Return the custom api_base for a provider, or None for LiteLLM default routing."""
    return _API_BASE_OVERRIDES.get(provider)


def build_litellm_model_string(provider: str, model: str, api_base: str | None = None) -> str:
    """Return the LiteLLM model string for a provider/model pair.

    When api_base is set (custom endpoint), switch to OpenAI-compatible mode
    so LiteLLM routes to the overridden base URL rather than the provider's default.
    """
    if api_base:
        # OpenAI-compatible mode: "openai/<model>" + custom api_base
        return f"openai/{model}"
    return f"{_MODEL_PREFIX.get(provider, provider + '/')}{model}"


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------


def strip_thinking(text: str) -> str:
    """Remove <think>…</think> reasoning blocks from LLM output."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


# ---------------------------------------------------------------------------
# Generic platform LLM call (non-streaming, via LiteLLM)
# ---------------------------------------------------------------------------


async def call_platform_llm(
    system: str,
    user: str,
    *,
    max_tokens: int = 1024,
    timeout: int = 60,
    json_mode: bool = False,
    temperature: float = 0.7,
    provider: str | None = None,
) -> str | None:
    """Call the platform LLM and return the raw text response, or None on failure.

    - json_mode=True  → requests JSON output (supported providers only) and
                        should be used for structured extraction tasks.
    - json_mode=False → plain text; suitable for narrative generation.

    Reasoning blocks (<think>…</think>) are stripped automatically for providers
    that emit them (DeepSeek, MiniMax).

    Callers are responsible for parsing JSON when json_mode=True.
    """
    try:
        if provider:
            # Explicit provider (e.g. force MiniMax for translation); fall back to the
            # configured default if that provider has no key.
            settings = get_settings()
            api_key = (
                getattr(settings, KEY_MAP.get(provider, ""), "") if KEY_MAP.get(provider) else ""
            )
            if api_key:
                _apply_provider_env(provider, settings)
                model = chat_model_for(provider, heavy=False)
            else:
                provider, model, api_key = resolve_platform_provider()
        else:
            provider, model, api_key = resolve_platform_provider()
    except ValueError as exc:
        logger.warning("call_platform_llm: %s", exc)
        return None

    api_base = provider_api_base(provider)
    litellm_model = build_litellm_model_string(provider, model, api_base)

    kwargs: dict[str, Any] = {
        "model": litellm_model,
        "api_key": api_key,
        "max_tokens": max_tokens,
        "timeout": timeout,
        "temperature": temperature,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    if api_base:
        kwargs["api_base"] = api_base
    if json_mode and provider in _JSON_MODE_PROVIDERS:
        kwargs["response_format"] = {"type": "json_object"}

    try:
        resp = await litellm.acompletion(**kwargs)
        content = resp.choices[0].message.content or ""
        if provider in _REASONING_PROVIDERS:
            content = strip_thinking(content)
        return content.strip() or None
    except Exception as exc:
        logger.error("call_platform_llm [%s/%s]: %s", provider, model, exc)
        return None
