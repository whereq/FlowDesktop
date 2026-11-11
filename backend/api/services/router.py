"""Multilingual intent routing for NOVA — local-embedding fallback.

The legacy routers (_classify_heavy tier selection, classify_skill suggestion)
are English keyword matchers, so a Chinese or paraphrased query is misrouted
(e.g. an analytical zh question stays on the cheap model). This module adds an
embedding-based fallback that reuses the LOCAL fastembed model
(flowdesk.embeddings) — multilingual (en/zh) and paraphrase-robust at no API
cost. It runs only when keyword matching is inconclusive, so the hot path stays
fast. Every path is defensive: on any failure it returns None ("undecided") and
the caller keeps its previous behavior — routing never breaks a chat.
"""

from __future__ import annotations

import logging

import numpy as np

from flowdesk_core.embeddings import embed_query, embed_texts, is_configured

logger = logging.getLogger(__name__)

# Exemplars describe the two tiers. The multilingual model maps zh queries near
# the English exemplars, so a handful per tier (plus a few zh) covers both.
_HEAVY_EXEMPLARS: tuple[str, ...] = (
    "analyze this stock in depth",
    "compare these companies and tell me which is the better buy",
    "should I buy this — is it a good investment",
    "valuation and fundamentals: is it over- or undervalued",
    "build a trading strategy and hedge my portfolio risk",
    "why is the stock moving and what is the macro impact",
    "forecast, outlook, and investment thesis",
    "深入分析这只股票的基本面和估值",
    "比较这几家公司哪一个更值得买入",
    "这只股票现在值得投资吗 该不该买",
    "帮我制定交易策略并对冲投资组合风险",
    "为什么这只股票在涨 宏观影响是什么",
)
_LIGHT_EXEMPLARS: tuple[str, ...] = (
    "what is the current price of this stock",
    "show me the latest quote and volume",
    "what is the ticker symbol for this company",
    "how much is it trading at right now",
    "这只股票现在多少钱",
    "查一下最新报价和成交量",
)

# Tuning: decide by MARGIN (robust to absolute-scale differences across models).
# Tier: decide by margin (robust to absolute-scale differences across models).
# Skill: precision-favoring cutoff — keyword classify_skill already covers the
# precise English cases, so the embedding fallback only needs to surface
# confident (mostly non-English) matches; below this it returns None (no
# suggestion), which is safe. Tuned on en+zh samples (junk peaked ~0.20).
_TIER_MARGIN = 0.03
_SKILL_MIN_SIM = 0.33

_cache: dict[str, np.ndarray] = {}


async def _exemplar_vecs(key: str, texts: tuple[str, ...]) -> np.ndarray:
    if key not in _cache:
        _cache[key] = _normalize(np.asarray(await embed_texts(list(texts), kind="query")))
    return _cache[key]


def _normalize(m: np.ndarray) -> np.ndarray:
    if m.ndim == 1:
        return m / (np.linalg.norm(m) + 1e-9)
    return m / (np.linalg.norm(m, axis=1, keepdims=True) + 1e-9)


async def route_heavy_embedding(text: str) -> bool | None:
    """True/False if the query clearly leans heavy/light by embedding similarity;
    None when inconclusive or embeddings are unavailable."""
    if not text or not is_configured():
        return None
    try:
        q = _normalize(np.asarray(await embed_query(text)))
        heavy = await _exemplar_vecs("heavy", _HEAVY_EXEMPLARS)
        light = await _exemplar_vecs("light", _LIGHT_EXEMPLARS)
        sh = float((heavy @ q).max())
        sl = float((light @ q).max())
        if sh - sl >= _TIER_MARGIN:
            return True
        if sl - sh >= _TIER_MARGIN:
            return False
        return None
    except Exception as exc:  # noqa: BLE001 — never break routing
        logger.debug("tier embedding route failed: %s", exc)
        return None


def _skill_docs() -> dict[str, str]:
    from api.services.skills import SKILLS

    return {
        name: f"{s.title}. {s.description} " + " ".join(s.example_prompts)
        for name, s in SKILLS.items()
    }


async def route_skill_embedding(text: str) -> str | None:
    """Best-matching native skill name by embedding similarity, or None."""
    if not text or not is_configured():
        return None
    try:
        docs = _skill_docs()
        names = list(docs)
        if "skills" not in _cache:
            _cache["skills"] = _normalize(
                np.asarray(await embed_texts([docs[n] for n in names], kind="db"))
            )
        D = _cache["skills"]
        q = _normalize(np.asarray(await embed_query(text)))
        sims = D @ q
        i = int(sims.argmax())
        return names[i] if float(sims[i]) >= _SKILL_MIN_SIM else None
    except Exception as exc:  # noqa: BLE001
        logger.debug("skill embedding route failed: %s", exc)
        return None
