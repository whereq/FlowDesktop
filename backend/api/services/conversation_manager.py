"""Manages multi-turn conversation history within token budget constraints."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TokenBudget:
    total: int
    reserved_for_response: int
    system_prompt: int = 0
    conversation: int = 0


# Soft cap on how much *history* (older turns) we forward each turn, regardless
# of how large the model's context window is. The frontend re-sends the full
# transcript every turn, so without this a 1M-context model (e.g. MiniMax) would
# keep paying for the entire growing conversation. Recent turns are always sent
# verbatim; everything older is collapsed into a compact extractive summary.
# ~4000 tokens ≈ 8-10 recent turns of normal chat — plenty of working memory.
_HISTORY_SOFT_CAP_TOKENS = 4000


class ConversationManager:
    """Manages conversation history within token budget constraints.

    For multi-turn analytical conversations (e.g. user refines investment
    analysis across 5-10 turns), this component decides what fits in the
    context window and what gets summarized.
    """

    def prepare_messages(
        self,
        messages: list[dict],
        context: str,
        model: str,
        max_tokens: int = 4096,
    ) -> list[dict]:
        """Prepare messages for the LLM with token budget management."""
        # Estimate model context window
        limit = self._model_context_limit(model)
        system_tokens = self._count_tokens(context, model)

        budget = TokenBudget(
            total=limit,
            reserved_for_response=max_tokens,
            system_prompt=system_tokens,
            conversation=limit - max_tokens - system_tokens,
        )

        if budget.conversation < 0:
            budget.conversation = 0

        # Proactive token optimization: never forward more history than the soft
        # cap even when the real context window is far larger. This is a no-LLM,
        # zero-added-cost compaction — it only shrinks the request.
        effective_budget = min(budget.conversation, _HISTORY_SOFT_CAP_TOKENS)

        fitted = self._fit_conversation(messages, effective_budget, model)

        return [{"role": "system", "content": context}] + fitted

    def _model_context_limit(self, model: str) -> int:
        """Return context window size for known models (rough estimates)."""
        limits = {
            "gpt-4o": 128000,
            "gpt-4o-mini": 128000,
            "gpt-4-turbo": 128000,
            "gpt-4": 8192,
            "claude-sonnet-4": 200000,
            "claude-haiku-4": 200000,
            "claude-3-5-sonnet": 200000,
            "claude-3-5-haiku": 200000,
            "gemini-2.0-flash": 1000000,
            "gemini-2.5-pro": 1000000,
            "deepseek-chat": 128000,
            "deepseek-reasoner": 128000,
            "qwen-max": 32000,
            "qwen-plus": 32000,
            "minimax-01": 1000000,
        }
        model_lower = model.lower()
        for key, limit in limits.items():
            if key in model_lower:
                return limit
        return 128000  # safe fallback

    def _count_tokens(self, text: str, model: str) -> int:
        """Rough token estimate: ~4 chars per token for typical LLM input."""
        return max(1, len(text) // 4)

    def _fit_conversation(
        self,
        messages: list[dict],
        token_budget: int,
        model: str,
    ) -> list[dict]:
        """Fit messages into token budget, summarizing older ones if needed.

        The final message (the current user turn) is always kept verbatim even
        if it alone exceeds the budget — dropping it would discard the actual
        question. Older turns that don't fit are collapsed into one extractive
        summary block prepended to the kept tail.
        """
        if not messages:
            return []

        result: list[dict] = []
        used = 0
        kept_index = len(messages)  # index of the oldest verbatim-kept message

        for i in range(len(messages) - 1, -1, -1):
            msg = messages[i]
            msg_tokens = self._count_tokens(msg.get("content", ""), model)
            # Always keep the most recent message; keep the rest while they fit.
            if not result or used + msg_tokens <= token_budget:
                result.insert(0, msg)
                used += msg_tokens
                kept_index = i
            else:
                break

        older = messages[:kept_index]
        if older:
            summary = self._summarize_older_turns(older)
            if summary:
                result.insert(
                    0,
                    {
                        "role": "system",
                        "content": f"Summary of earlier conversation:\n{summary}",
                    },
                )

        return result

    def _summarize_older_turns(self, messages: list[dict]) -> str:
        """Extractive summary of older turns — key points, no LLM call.

        Deterministic and free: keeps the gist (what the user asked, what NOVA
        answered) without forwarding the full older transcript.
        """
        points = []
        for msg in messages:
            role = msg.get("role")
            content = (msg.get("content") or "").strip()
            if not content:
                continue
            if role == "user":
                points.append(f"User asked: {content[:200]}")
            elif role == "assistant":
                first_line = content.split("\n", 1)[0][:200]
                points.append(f"NOVA replied: {first_line}")
        return "\n".join(points[-10:])  # keep the last ~10 salient points
