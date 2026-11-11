"""Proactive Insights ("NOVA Pulse") — deterministic scoring + message copy.

Pure functions, no DB/LLM. Guards the P1 relevance logic so threshold tuning
(config) and scoring changes don't silently regress.
"""

import json
from types import SimpleNamespace

import flowdesk_core.llm_platform as llm_platform
from flowdesk_collector.pulse import (
    narrate_insights,
    proactive_message,
    proactive_score,
    profile_brief,
)


def _sig(**kw):
    base = {
        "id": 1,
        "sentiment": 0.8,
        "confidence": 0.9,
        "impact_horizon": "short",
        "signal_type": "earnings",
        "sectors_affected": ["Technology"],
        "summary_en": "Strong beat.",
        "theme_tags": ["AI"],
    }
    base.update(kw)
    return SimpleNamespace(**base)


def _profile(**kw):
    base = {
        "risk_tolerance": None,
        "horizon": None,
        "style": None,
        "preferred_sectors": None,
        "avoided_sectors": None,
    }
    base.update(kw)
    return SimpleNamespace(**base)


def test_no_conviction_scores_zero():
    assert proactive_score(_sig(sentiment=0.0), None, 0.0) == 0.0
    assert proactive_score(_sig(confidence=0.0), None, 0.0) == 0.0


def test_recency_decays_score():
    fresh = proactive_score(_sig(), None, 0.0)
    stale = proactive_score(_sig(), None, 24.0)
    assert fresh > stale > 0


def test_no_profile_uses_neutral_fit():
    # base 0.9*0.8=0.72, recency=1, horizon=style=0.85 → 0.72*0.7225 ≈ 0.520
    score = proactive_score(_sig(), None, 0.0)
    assert 0.50 < score < 0.54


def test_matching_horizon_beats_mismatch():
    swing = _profile(horizon="swing")  # short → 1.0
    longt = _profile(horizon="long_term")  # short → 0.7
    assert proactive_score(_sig(impact_horizon="short"), swing, 0.0) > proactive_score(
        _sig(impact_horizon="short"), longt, 0.0
    )


def test_avoided_sector_heavily_downweighted():
    avoid = _profile(avoided_sectors=["Technology"])
    prefer = _profile(preferred_sectors=["Technology"])
    assert proactive_score(_sig(), avoid, 0.0) < proactive_score(_sig(), prefer, 0.0)


def test_style_favored_signal_scores_higher():
    momentum = _profile(style="momentum")  # favors corporate/sector/geopolitical
    favored = proactive_score(_sig(signal_type="sector"), momentum, 0.0)
    unfavored = proactive_score(_sig(signal_type="earnings"), momentum, 0.0)
    assert favored > unfavored


def test_message_uses_summary_and_direction():
    title, body = proactive_message("NVDA", _sig(sentiment=0.7, confidence=0.8))
    assert "NVDA" in title and "bullish" in title
    assert "Strong beat." in body and "80%" in body


def test_message_falls_back_to_themes():
    title, body = proactive_message(
        "TSLA", _sig(summary_en=None, theme_tags=["EV demand"], sentiment=-0.6)
    )
    assert "bearish" in title
    assert "EV demand" in body


def test_profile_brief():
    assert profile_brief(None) == "unknown profile"
    p = _profile(risk_tolerance="aggressive", horizon="swing", style="growth")
    assert profile_brief(p) == "aggressive risk, swing horizon, growth style"


# --- narration (P2) ------------------------------------------------------


async def _fake_llm(payload):
    async def _call(system, user, **kw):
        return payload

    return _call


async def test_narrate_parses_aligned_json(monkeypatch):
    sigs = [_sig(id=1), _sig(id=2)]
    for s, sym in zip(sigs, ["NVDA", "AMD"], strict=False):
        s._pulse_symbol = sym
    payload = json.dumps(
        {
            "notes": [
                {"i": 0, "en": "NVDA matters.", "zh": "英伟达重要。"},
                {"i": 1, "en": "AMD matters.", "zh": "超威重要。"},
            ]
        }
    )
    monkeypatch.setattr(llm_platform, "call_platform_llm", await _fake_llm(payload))
    out = await narrate_insights(sigs, _profile(style="growth"))
    assert out == [
        {"en": "NVDA matters.", "zh": "英伟达重要。"},
        {"en": "AMD matters.", "zh": "超威重要。"},
    ]


async def test_narrate_incomplete_batch_falls_back_to_none(monkeypatch):
    sigs = [_sig(id=1), _sig(id=2)]
    payload = json.dumps({"notes": [{"i": 0, "en": "only one"}]})  # missing i=1
    monkeypatch.setattr(llm_platform, "call_platform_llm", await _fake_llm(payload))
    assert await narrate_insights(sigs, None) is None


async def test_narrate_no_llm_returns_none(monkeypatch):
    monkeypatch.setattr(llm_platform, "call_platform_llm", await _fake_llm(None))
    assert await narrate_insights([_sig()], None) is None


async def test_narrate_zh_defaults_to_en_when_missing(monkeypatch):
    payload = json.dumps({"notes": [{"i": 0, "en": "english only"}]})
    monkeypatch.setattr(llm_platform, "call_platform_llm", await _fake_llm(payload))
    out = await narrate_insights([_sig()], None)
    assert out == [{"en": "english only", "zh": "english only"}]
