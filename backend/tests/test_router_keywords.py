"""Tier-router keyword path (multilingual). The embedding fallback needs the
local model and is exercised separately; here we guard the fast, deterministic
keyword/length signals — especially the Chinese cues added for NOVA routing."""

from api.services.llm_gateway import _classify_heavy


def _u(text: str):
    return [{"role": "user", "content": text}]


def test_en_heavy():
    assert _classify_heavy(_u("Give me a deep valuation analysis of NVDA")) is True


def test_en_light():
    assert _classify_heavy(_u("price of AAPL")) is False


def test_zh_heavy_keyword():
    assert _classify_heavy(_u("深入分析这只股票的基本面")) is True
    assert _classify_heavy(_u("对冲我的投资组合风险")) is True


def test_zh_light():
    assert _classify_heavy(_u("苹果现在多少钱")) is False


def test_zh_double_question_is_heavy():
    assert _classify_heavy(_u("这只股票怎么样？现在能买吗？")) is True


def test_empty_is_light():
    assert _classify_heavy(_u("")) is False
