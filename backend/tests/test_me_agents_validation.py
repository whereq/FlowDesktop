"""Custom-agent validation guardrails (reserved names, tool subset, slugging)."""

import pytest
from fastapi import HTTPException

from api.routes.me_agents import CustomAgentIn, _slug, _validate


def _body(**kw):
    base = {
        "name": "Dividend Hunter",
        "title": "Dividend Hunter",
        "system_prompt": "Find high-yield, safe-payout names.",
        "tools": ["get_stock_quote"],
        "model_tier": "auto",
    }
    base.update(kw)
    return CustomAgentIn(**base)


def test_slug_normalizes():
    assert _slug("Dividend Hunter!") == "dividend_hunter"
    assert _slug("  A/B  C ") == "a_b_c"


def test_valid_agent_passes():
    out = _validate(_body())
    assert out["name"] == "dividend_hunter"
    assert out["tools"] == ["get_stock_quote"]
    assert out["model_tier"] == "auto"


def test_reserved_native_name_rejected():
    with pytest.raises(HTTPException) as e:
        _validate(_body(name="research_analyst", title="x"))
    assert e.value.status_code == 400


def test_unknown_tool_rejected():
    with pytest.raises(HTTPException) as e:
        _validate(_body(tools=["get_stock_quote", "not_a_real_tool"]))
    assert e.value.status_code == 400


def test_blank_prompt_rejected():
    with pytest.raises(HTTPException):
        _validate(_body(system_prompt="   "))


def test_too_many_tools_rejected():
    with pytest.raises(HTTPException):
        _validate(_body(tools=[f"tool_{i}" for i in range(11)]))


def test_invalid_tier_falls_back_to_auto():
    out = _validate(_body(model_tier="ludicrous"))
    assert out["model_tier"] == "auto"
