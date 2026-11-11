"""LLM Gateway — orchestrates chat requests through LiteLLM."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from types import SimpleNamespace

import litellm

from api.services.context_builder import ContextBuilder
from api.services.conversation_manager import ConversationManager
from api.services.tool_registry import ToolRegistry
from flowdesk_core.config import get_settings
from flowdesk_core.llm_platform import (
    DEFAULT_MODELS as _PLATFORM_DEFAULT_MODELS,
)
from flowdesk_core.llm_platform import (
    KEY_MAP as _KEY_MAP,
)
from flowdesk_core.llm_platform import (
    build_litellm_model_string,
    chat_model_for,
    is_anthropic_adaptive_model,
    provider_api_base,
    resolve_platform_provider,
    strip_thinking,
)

logger = logging.getLogger(__name__)

# Chat uses a richer Anthropic model than the internal platform tasks; override it.
# All other provider defaults come from llm_platform.DEFAULT_MODELS.
DEFAULT_MODELS: dict[str, str] = {
    **_PLATFORM_DEFAULT_MODELS,
    "anthropic": "claude-opus-4-8",
}

# Max number of tool-call rounds before forcing a final answer. Prevents an
# LLM from looping on tools indefinitely (cost + latency guard).
_MAX_TOOL_ROUNDS = 6


def _provenance_from_result(name: str, content: str | None) -> dict | None:
    """Trust layer: pull a verifiable provenance entry from a tool result.

    Returns {tool, source?, as_of?, symbol?} so the UI can show where a fact came
    from and how fresh it is. Tools that expose no source/timestamp still yield a
    bare {tool: name} so the legacy label chip renders. None only on parse failure.
    """
    try:
        data = json.loads(content) if content else None
    except (ValueError, TypeError):
        return {"tool": name}
    entry: dict = {"tool": name}
    if isinstance(data, dict):
        as_of = data.get("as_of") or data.get("timestamp") or data.get("date")
        if data.get("source"):
            entry["source"] = data["source"]
        if as_of:
            entry["as_of"] = as_of
        if data.get("symbol"):
            entry["symbol"] = data["symbol"]
    return entry


# Keywords that signal an analytical/multi-step question worth escalating to the
# heavy reasoning model. Simple lookups ("price of AAPL") stay on the cheap model.
_HEAVY_QUERY_HINTS: tuple[str, ...] = (
    "analyz",
    "analys",
    "compare",
    "comparison",
    "vs ",
    " versus",
    "strategy",
    "should i",
    "valuation",
    "undervalued",
    "overvalued",
    "forecast",
    "predict",
    "outlook",
    "thesis",
    "recommend",
    "deep dive",
    "deep-dive",
    "evaluate",
    "assess",
    "risk",
    "hedge",
    "portfolio",
    "diversif",
    "allocate",
    "scenario",
    "why is",
    "why did",
    "explain why",
    "implications",
    "macro",
    "correlation",
    "fundamental",
    "dcf",
    "intrinsic",
    "moat",
    "competitive",
)

# Chinese analytical cues (substring match; the keyword path is English-only
# otherwise, which silently routed zh analytical questions to the cheap model).
_HEAVY_QUERY_HINTS_ZH: tuple[str, ...] = (
    "分析",
    "对比",
    "比较",
    "估值",
    "该不该买",
    "值得买",
    "值得投资",
    "预测",
    "展望",
    "策略",
    "对冲",
    "投资组合",
    "为什么",
    "基本面",
    "风险",
    "宏观",
    "相关性",
    "深入",
    "建议",
    "前景",
    "走势",
)


def _last_user_text(messages: list[dict]) -> str:
    for m in reversed(messages):
        if m.get("role") == "user":
            c = m.get("content")
            return c if isinstance(c, str) else json.dumps(c)
    return ""


def _classify_heavy(messages: list[dict]) -> bool:
    """Keyword/length heuristic: does this turn look analytical (→ heavy)?

    Returns True on a clear heavy signal; False = no keyword signal (which the
    async router treats as "undecided" and resolves with embeddings).
    """
    last_user = _last_user_text(messages)
    text = last_user.lower()
    if any(h in text for h in _HEAVY_QUERY_HINTS):
        return True
    if any(h in last_user for h in _HEAVY_QUERY_HINTS_ZH):
        return True
    # Long or multi-question prompts tend to need deeper reasoning.
    return bool(len(last_user) > 280 or text.count("?") + last_user.count("？") >= 2)


async def _route_heavy(messages: list[dict]) -> bool:
    """Tier decision: keyword/length first (fast), then a multilingual local-
    embedding fallback for whatever keywords miss (paraphrases, other languages)."""
    if _classify_heavy(messages):
        return True
    from api.services.router import route_heavy_embedding

    emb = await route_heavy_embedding(_last_user_text(messages))
    return emb if emb is not None else False


class LLMError(Exception):
    """Structured LLM error with a machine-readable code sent to the frontend."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _classify_rate_limit(exc: Exception) -> str:
    """Distinguish temporary rate-limit (429) from permanent quota exhaustion."""
    lower = str(exc).lower()
    quota_keywords = (
        "insufficient_quota",
        "exceeded your current quota",
        "billing",
        "credit balance",
        "upgrade your plan",
        "exceeded your monthly",
        "hard limit",
        "max_tokens",
        "quota exceeded",
    )
    if any(k in lower for k in quota_keywords):
        return "quota_exhausted"
    return "rate_limit"


def resolve_api_key(
    mode: str,
    provider_name: str,
    user_supplied_key: str | None,
) -> str:
    """Resolve the API key for BYOK mode only."""
    if not user_supplied_key:
        raise ValueError("BYOK mode requires X-LLM-Api-Key header")
    return user_supplied_key


class LLMGateway:
    """Central coordinator. Routes requests through LiteLLM."""

    def __init__(self):
        self.conversation_manager = ConversationManager()
        self.context_builder = ContextBuilder()
        self.tool_registry = ToolRegistry()

    async def stream_chat(
        self,
        *,
        provider_name: str,
        model: str,
        api_key: str,
        messages: list[dict],
        db,
        user_id: str | None = None,
        symbols: list[str] | None = None,
        locale: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        api_base: str | None = None,
        allow_routing: bool = False,
        tool_names: list[str] | None = None,
        system_suffix: str | None = None,
        force_tier: str | None = None,
        history_summary: str | None = None,
    ) -> AsyncIterator[dict]:
        """Stream chat response as dict chunks.

        api_base: set by the caller for platform providers that require a custom
        endpoint (e.g. MiniMax sk-cp-* keys use api.minimax.io, not the LiteLLM
        default api.minimax.chat).  Pass None for BYOK or providers with standard
        endpoints.

        allow_routing: when True (platform mode), escalate analytical questions to
        the provider's heavy reasoning model. BYOK respects the user's chosen model.

        Skill scoping (used by the Skill Runner; all optional):
            tool_names:    restrict the exposed tools to this subset (token saver).
            system_suffix: focused skill instructions appended to NOVA's base prompt.
            force_tier:    'light' | 'heavy' to pin the model tier for this skill,
                           overriding the per-turn classifier (platform mode only).
        """
        # Build context from DB
        context_dict = await self.context_builder.build(db, user_id, symbols, locale)
        system_prompt = self.context_builder.render_system_prompt(context_dict)
        if system_suffix:
            system_prompt = f"{system_prompt}\n\n{system_suffix}"
        if history_summary:
            system_prompt = f"{system_prompt}\n\n## Earlier in this conversation\n{history_summary}"

        # Smart routing: pick the model tier for this turn (platform mode only).
        if allow_routing:
            if force_tier in ("light", "heavy"):
                heavy = force_tier == "heavy"
            else:
                heavy = await _route_heavy(messages)
            routed = chat_model_for(provider_name, heavy=heavy)
            if routed:
                if routed != model:
                    logger.info(
                        "NOVA routing: %s tier → %s",
                        "heavy" if heavy else "light",
                        routed,
                    )
                model = routed

        # Resolve LiteLLM model string — switches to OpenAI-compat mode when
        # api_base is set (e.g. openai/MiniMax-M3 + api_base=https://api.minimax.io/v1)
        litellm_model = build_litellm_model_string(provider_name, model, api_base)

        # Anthropic adaptive-thinking models (Opus 4.x / Fable 5 / Sonnet 4.6)
        # reject temperature and use adaptive thinking instead.
        is_adaptive = provider_name == "anthropic" and is_anthropic_adaptive_model(model)
        prepared_messages = self.conversation_manager.prepare_messages(
            messages=messages,
            context=system_prompt,
            model=litellm_model,
            max_tokens=max_tokens,
        )

        # Get tool definitions (skill-scoped subset when tool_names is provided)
        tool_defs = self.tool_registry.get_definitions(tool_names)

        # Anthropic prompt caching: cache the (large, stable) system prompt and
        # tool definitions so repeated turns in a session pay ~0.1x for the prefix.
        # No-op for other providers (LiteLLM ignores cache_control elsewhere).
        if provider_name == "anthropic":
            self._apply_anthropic_cache(prepared_messages, tool_defs)

        import time as _time

        _t0 = _time.monotonic()
        _usage = None
        try:
            current_messages = prepared_messages
            # Tool-call loop: LLM may request several rounds of tool calls then continue.
            # is_first_pass tracks whether we are in the pre-tool-call phase.
            # Content streamed during a tool-call pass is intentional reasoning
            # ("I'll fetch the data…") that we don't want to show the user — it
            # gets replaced by a progress signal and cleared on the frontend.
            is_first_pass = True
            tool_rounds = 0
            tools_used: list[str] = []  # tool names, for the legacy Sources chip
            sources: list[dict] = []  # provenance entries {tool, source, as_of, symbol}

            while True:
                litellm_kwargs: dict = {
                    "model": litellm_model,
                    "messages": current_messages,
                    "tools": tool_defs,
                    "stream": True,
                    "api_key": api_key,
                    "max_tokens": max_tokens,
                }
                # Adaptive-thinking Anthropic models reject temperature; others use it.
                if is_adaptive:
                    litellm_kwargs["thinking"] = {"type": "adaptive"}
                else:
                    litellm_kwargs["temperature"] = temperature
                # After the round cap, stop offering tools so the model must answer.
                if tool_rounds >= _MAX_TOOL_ROUNDS:
                    litellm_kwargs["tool_choice"] = "none"
                if api_base:
                    litellm_kwargs["api_base"] = api_base
                response = await litellm.acompletion(**litellm_kwargs)

                # Accumulate streaming chunks; tool calls arrive in pieces.
                full_content = ""
                # index → {id, function: {name, arguments}}
                tc_accum: dict[int, dict] = {}
                finish_reason = None

                async for chunk in response:
                    # Opportunistically capture token usage if the provider
                    # includes it (some send a final usage-only chunk with no
                    # choices) — used for observability, never required.
                    if getattr(chunk, "usage", None):
                        _usage = chunk.usage
                    if not chunk.choices:
                        continue
                    choice = chunk.choices[0]
                    delta = choice.delta
                    finish_reason = choice.finish_reason

                    # Accumulate tool call fragments across chunks
                    if delta.tool_calls:
                        for tc in delta.tool_calls:
                            idx = tc.index
                            if idx not in tc_accum:
                                tc_accum[idx] = {
                                    "id": "",
                                    "type": "function",
                                    "function": {"name": "", "arguments": ""},
                                }
                            if tc.id:
                                tc_accum[idx]["id"] = tc.id
                            if tc.function:
                                if tc.function.name:
                                    tc_accum[idx]["function"]["name"] += tc.function.name
                                if tc.function.arguments:
                                    tc_accum[idx]["function"]["arguments"] += tc.function.arguments

                    # Stream content to the caller.
                    # During the first pass we still stream so the user sees activity,
                    # but if this pass ends with tool_calls we'll send a clear signal.
                    if delta.content:
                        full_content += delta.content
                        if not is_first_pass:
                            # Subsequent passes → stream directly (this is the real answer)
                            yield {"delta": delta.content, "finish_reason": None}

                # If the LLM requested tool calls, execute them and loop.
                if finish_reason == "tool_calls" and tc_accum:
                    tool_rounds += 1
                    # Coerce malformed/empty tool-call arguments to valid JSON.
                    # We echo these tool_calls back on the next request, and strict
                    # providers (e.g. MiniMax) reject invalid argument JSON with
                    # "invalid function arguments json string". A bad-args call
                    # then degrades to an error tool result instead of a 400.
                    for _tc in tc_accum.values():
                        _args = _tc["function"].get("arguments") or ""
                        try:
                            json.loads(_args)
                        except Exception:
                            _tc["function"]["arguments"] = "{}"
                    # Build duck-typed objects that ToolRegistry.execute() expects
                    tool_call_objects = [
                        SimpleNamespace(
                            id=tc["id"],
                            function=SimpleNamespace(
                                name=tc["function"]["name"],
                                arguments=tc["function"]["arguments"],
                            ),
                        )
                        for tc in (tc_accum[i] for i in sorted(tc_accum))
                    ]

                    for tc in (tc_accum[i] for i in sorted(tc_accum)):
                        name = tc["function"]["name"]
                        if name and name not in tools_used:
                            tools_used.append(name)

                    tool_results = await self.tool_registry.execute(tool_call_objects, db, user_id)

                    # Trust layer: extract verifiable provenance (source + as-of) from
                    # each tool result so the UI can show WHERE a fact came from, not
                    # just which tool ran.
                    id2name = {tc["id"]: tc["function"]["name"] for tc in tc_accum.values()}
                    for tr in tool_results:
                        prov = _provenance_from_result(
                            id2name.get(tr["tool_call_id"], "tool"), tr.get("content")
                        )
                        if prov and prov not in sources:
                            sources.append(prov)

                    # Signal the frontend: discard the pre-tool reasoning text and
                    # show a progress indicator while we fetch data.
                    yield {"status": "fetching_data", "clear_content": True}

                    # Surface any gated-action proposals as confirmation cards.
                    for tr in tool_results:
                        if tr.get("proposal"):
                            yield {"type": "action_proposal", **tr["proposal"]}
                        if tr.get("chart"):
                            yield {"type": "chart", "chart": tr["chart"]}

                    # Append assistant turn (with tool_calls) then each tool result
                    current_messages.append(
                        {
                            "role": "assistant",
                            "content": full_content or None,
                            "tool_calls": [tc_accum[i] for i in sorted(tc_accum)],
                        }
                    )
                    for tr in tool_results:
                        current_messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tr["tool_call_id"],
                                "content": tr["content"],
                            }
                        )
                    is_first_pass = False
                    # Loop back to get the LLM's response incorporating tool results
                    continue

                # Normal finish — yield buffered content if still on first pass
                # (means no tools were called; the content is the actual answer)
                if is_first_pass and full_content:
                    clean = strip_thinking(full_content)
                    if clean:
                        yield {"delta": clean, "finish_reason": None}
                # Citations: tell the UI which data tools backed this answer, plus
                # verifiable per-source provenance (source + as-of) when available.
                if tools_used:
                    yield {"type": "tools_used", "tools": tools_used}
                if sources:
                    yield {"type": "sources", "sources": sources}

                # Observability: one structured line per NOVA run.
                _obs = {
                    "operation": "nova_run",
                    "model": model,
                    "tier": "heavy"
                    if (allow_routing and force_tier == "heavy")
                    else "light"
                    if (allow_routing and force_tier == "light")
                    else "auto",
                    "exposed_tools": len(tool_defs),
                    "tool_rounds": tool_rounds,
                    "tools_used": tools_used,
                    "latency_ms": int((_time.monotonic() - _t0) * 1000),
                }
                if _usage is not None:
                    _obs["input_tokens"] = getattr(_usage, "prompt_tokens", None)
                    _obs["output_tokens"] = getattr(_usage, "completion_tokens", None)
                logger.info("NOVA run complete", extra=_obs)
                break

        except litellm.RateLimitError as exc:
            code = _classify_rate_limit(exc)
            raise LLMError(code, str(exc)[:300]) from exc
        except litellm.AuthenticationError as exc:
            raise LLMError("auth_error", str(exc)[:300]) from exc
        except litellm.ContextWindowExceededError as exc:
            raise LLMError("context_too_long", str(exc)[:300]) from exc
        except litellm.ServiceUnavailableError as exc:
            raise LLMError("provider_unavailable", str(exc)[:300]) from exc
        except Exception as exc:
            logger.error("LLM streaming error: %s", exc)
            raise LLMError("transient", str(exc)[:300]) from exc

    @staticmethod
    def _apply_anthropic_cache(messages: list[dict], tool_defs: list[dict]) -> None:
        """Add an Anthropic cache_control breakpoint (in place) on the system
        message so repeated turns in a session reuse the large, stable system
        prompt at ~0.1x cost.

        LiteLLM forwards cache_control to the Anthropic API. Other providers
        ignore it, so this is only called for the Anthropic path.
        """
        try:
            for msg in messages:
                if msg.get("role") == "system" and isinstance(msg.get("content"), str):
                    msg["content"] = [
                        {
                            "type": "text",
                            "text": msg["content"],
                            "cache_control": {"type": "ephemeral"},
                        }
                    ]
                    break
        except Exception as exc:  # never let caching break a chat
            logger.debug("anthropic cache setup skipped: %s", exc)


# Cheapest model per provider for key validation (1-token ping)
_VALIDATION_MODELS: dict[str, str] = {
    "openai": "openai/gpt-4o-mini",
    "anthropic": "anthropic/claude-haiku-4-5-20251001",
    "google": "google/gemini-2.0-flash",
    "deepseek": "deepseek/deepseek-chat",
    "qwen": "qwen/qwen-turbo",
    "minimax": "minimax/MiniMax-M3",
}


async def validate_provider_key(provider: str, api_key: str) -> tuple[bool | None, str]:
    """Validate a BYOK API key by making a 1-token completion.

    Returns (valid, message_code) where message_code is a machine-readable key
    the frontend maps to a localised string — never a raw exception message.

    valid=True   → key authenticated (or rate-limited, meaning it works)
    valid=False  → provider explicitly rejected the key (401/403)
    valid=None   → inconclusive: network/connection error, cannot confirm or deny
    """
    model = _VALIDATION_MODELS.get(provider.lower())
    if not model:
        return None, "unknown_provider"

    try:
        await litellm.acompletion(
            model=model,
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=1,
            api_key=api_key,
            timeout=15,
        )
        return True, "valid"
    except litellm.RateLimitError:
        return True, "rate_limited"
    except litellm.AuthenticationError:
        return False, "invalid"
    except (litellm.APIConnectionError, litellm.APITimeoutError, litellm.Timeout):
        # Network-level failure — cannot confirm key validity; do not mark as invalid
        logger.warning("Key validation connection error for provider=%s", provider)
        return None, "connection_error"
    except Exception as exc:
        # Any other error (provider-side 5xx, unexpected format, etc.) — also inconclusive
        logger.warning("Key validation error for provider=%s: %s", provider, exc)
        return None, "connection_error"


def build_provider_list() -> list[dict]:
    """Build the provider+models list, tagging platform availability."""
    settings = get_settings()
    providers = []

    for name, default_model in DEFAULT_MODELS.items():
        key_attr = _KEY_MAP.get(name, "")
        platform_key = getattr(settings, key_attr, "") if key_attr else ""
        providers.append(
            {
                "name": name,
                "models": _model_list_for_provider(name, default_model),
                "platform_available": bool(platform_key),
            }
        )

    return providers


# Re-export resolve_platform_provider and provider_api_base so chat.py can
# import everything it needs from a single gateway module.
__all__ = [
    "LLMGateway",
    "LLMError",
    "resolve_platform_provider",
    "provider_api_base",
    "resolve_api_key",
    "build_provider_list",
    "validate_provider_key",
]


def _model_list_for_provider(name: str, default: str) -> list[dict]:
    """Return the list of known models for a provider."""
    all_models: dict[str, list[str]] = {
        "openai": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"],
        "anthropic": [
            "claude-opus-4-8",
            "claude-sonnet-4-6",
            "claude-haiku-4-5-20251001",
        ],
        "google": ["gemini-2.0-flash", "gemini-2.5-pro", "gemini-1.5-flash"],
        "deepseek": ["deepseek-chat", "deepseek-reasoner"],
        "qwen": ["qwen-max", "qwen-plus", "qwen-turbo"],
        "minimax": ["MiniMax-M3", "MiniMax-M2.7", "MiniMax-M2.5"],
    }
    models = all_models.get(name, [default])
    return [{"id": m, "label": m} for m in models]
