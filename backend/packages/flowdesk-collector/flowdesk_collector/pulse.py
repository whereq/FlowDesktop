"""NOVA Pulse — proactive insight relevance scoring.

Pulse decides which market signals are worth pushing to a user. Ranking is
deterministic and lives in plain Python here, so an LLM is only ever spent on
the handful of insights that survive the cutoff.

The score for a (signal, user-profile) pair is::

    score = confidence * |sentiment| * recency * horizon_fit * style_fit * sector_mult

``recency`` decays with a ~8h half-life (``exp(-age_hours / 12)``). The three
fit factors are multipliers in ``[0.0, 1.0]`` except ``sector_mult`` which may
also boost (1.15) or suppress (0.4) a signal for a user who explicitly prefers
or avoids the affected sectors.

A signal with no conviction (no sentiment or no confidence) always scores
``0.0`` and is therefore never pushed.
"""

from __future__ import annotations

import json
import logging
import math

from flowdesk_core.config import get_settings

logger = logging.getLogger("flowdesk-collector.pulse")

# ---------------------------------------------------------------------------
# Fit tables
# ---------------------------------------------------------------------------

# signal.impact_horizon in {intraday, short, medium, long}
# profile.horizon       in {day, swing, long_term}
_HORIZON_FIT: dict[str, dict[str, float]] = {
    "day": {"intraday": 1.0, "short": 0.9, "medium": 0.7, "long": 0.6},
    "swing": {"intraday": 0.8, "short": 1.0, "medium": 0.9, "long": 0.7},
    "long_term": {"intraday": 0.6, "short": 0.7, "medium": 0.9, "long": 1.0},
}

# signal.signal_type in {earnings, macro, geopolitical, sector, regulatory, corporate}
# profile.style       in {value, growth, income, momentum, mixed}
_STYLE_FAVORS: dict[str, set[str]] = {
    "value": {"earnings", "regulatory", "corporate"},
    "growth": {"earnings", "sector", "corporate"},
    "income": {"earnings", "regulatory", "macro"},
    "momentum": {"corporate", "sector", "geopolitical"},
}


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def proactive_score(signal, profile, age_hours: float) -> float:
    """Deterministic relevance score for a (signal, user-profile) pair.

    Returns ``0.0`` when the signal carries no conviction.
    """
    sentiment = abs(signal.sentiment or 0.0)
    confidence = signal.confidence or 0.0
    base = confidence * sentiment
    if base <= 0:
        return 0.0

    recency = math.exp(-max(age_hours, 0.0) / 12.0)  # ~8h half-life

    horizon_fit = 0.85
    style_fit = 0.85
    sector_mult = 1.0
    if profile is not None:
        if profile.horizon and signal.impact_horizon:
            horizon_fit = _HORIZON_FIT.get(profile.horizon, {}).get(signal.impact_horizon, 0.7)
        if profile.style and profile.style != "mixed":
            favored = _STYLE_FAVORS.get(profile.style, set())
            style_fit = 1.0 if signal.signal_type in favored else 0.8
        affected = set(signal.sectors_affected or [])
        if affected:
            if profile.avoided_sectors and affected & set(profile.avoided_sectors):
                sector_mult = 0.4
            elif profile.preferred_sectors and affected & set(profile.preferred_sectors):
                sector_mult = 1.15
    return base * recency * horizon_fit * style_fit * sector_mult


def proactive_message(symbol: str, signal) -> tuple[str, str]:
    """Templated (no-LLM) push copy. Used as a fallback when narration fails."""
    s = signal.sentiment or 0.0
    direction = "bullish" if s > 0.05 else "bearish" if s < -0.05 else "mixed"
    conf = int(round((signal.confidence or 0.0) * 100))
    title = f"{symbol} — {direction} {signal.signal_type or 'signal'}"
    summary = (signal.summary_en or "").strip()
    if summary:
        body = summary
    else:
        themes = ", ".join(signal.theme_tags or [])
        body = f"New {signal.signal_type or 'market'} signal for {symbol}."
        if themes:
            body += f" Themes: {themes}."
    body += f" (NOVA confidence {conf}%)"
    return title, body


def profile_brief(profile) -> str:
    """One-line investor-profile descriptor, used inside the narration prompt."""
    if profile is None:
        return "unknown profile"
    bits = []
    if profile.risk_tolerance:
        bits.append(f"{profile.risk_tolerance} risk")
    if profile.horizon:
        bits.append(f"{profile.horizon} horizon")
    if profile.style:
        bits.append(f"{profile.style} style")
    return ", ".join(bits) or "unknown profile"


async def narrate_insights(insights, profile) -> list[dict] | None:
    """Batch, profile-aware "why it matters" for a user's pushable insights.

    One LLM call covers all of a user's surviving insights. Returns a list of
    ``{"en": str, "zh": str}`` aligned to ``insights``, or ``None`` on any
    failure — the caller then falls back to :func:`proactive_message`.
    """
    from flowdesk_core.llm_platform import call_platform_llm

    settings = get_settings()

    items = []
    for i, sig in enumerate(insights):
        items.append(
            {
                "i": i,
                "symbol": getattr(sig, "_pulse_symbol", ""),
                "type": sig.signal_type,
                "sentiment": round(sig.sentiment or 0.0, 2),
                "confidence": round(sig.confidence or 0.0, 2),
                "summary": (sig.summary_en or "").strip()[:300],
                "themes": (sig.theme_tags or [])[:4],
            }
        )

    system = (
        "You are NOVA, a markets analyst writing short proactive alerts. For each "
        "input signal, write a 1-2 sentence note on WHY IT MATTERS to an investor "
        f"with this profile: {profile_brief(profile)}. Be concrete and specific; "
        "reference the catalyst and the holding. This is analysis, NOT financial "
        "advice — never tell the user to buy or sell. Return STRICT JSON: "
        '{"notes":[{"i":<int>,"en":"...","zh":"..."}]} with one entry per input '
        "(zh = Simplified Chinese translation of en)."
    )
    user = json.dumps({"signals": items}, ensure_ascii=False)

    raw = await call_platform_llm(
        system,
        user,
        max_tokens=settings.proactive_narrate_max_tokens,
        json_mode=True,
        temperature=0.4,
    )
    if not raw:
        return None
    try:
        data = json.loads(raw)
        notes = {int(n["i"]): n for n in data.get("notes", [])}
        out: list[dict] = []
        for i in range(len(insights)):
            n = notes.get(i)
            if not n or not (n.get("en") or "").strip():
                return None  # incomplete → fall back to the template for the batch
            out.append({"en": n["en"].strip(), "zh": (n.get("zh") or n["en"]).strip()})
        return out
    except Exception:
        logger.debug("Pulse narration failed", exc_info=True)
        return None


# ---------------------------------------------------------------------------
# Auto-tuning
# ---------------------------------------------------------------------------


def decide_cutoff(
    current: float,
    up: int,
    down: int,
    *,
    min_votes: int,
    step: float,
    lo: float,
    hi: float,
) -> tuple[float, str]:
    """Adjust the Pulse relevance cutoff from aggregate feedback votes.

    Pure function — no I/O — so it is trivial to unit test.

    - below quorum -> hold (not enough fuel yet)
    - low approval (< 50%) -> raise the cutoff (be more selective)
    - high approval (>= 80%) -> lower the cutoff (widen coverage), if there is headroom
    - otherwise -> hold

    The result is always clamped to ``[lo, hi]``.
    """
    total = up + down
    if total < min_votes:
        return current, f"insufficient feedback ({total}/{min_votes} votes) — hold {current:.3f}"
    approval = up / total
    if approval < 0.5:
        new = min(hi, round(current + step, 4))
        verb = "raise" if new > current else "hold (at max)"
        return new, f"approval {approval:.0%} of {total} → {verb} cutoff {current:.3f}→{new:.3f}"
    if approval >= 0.8:
        new = max(lo, round(current - step, 4))
        verb = "lower" if new < current else "hold (at min)"
        return new, f"approval {approval:.0%} of {total} → {verb} cutoff {current:.3f}→{new:.3f}"
    return current, f"approval {approval:.0%} of {total} — hold {current:.3f}"
