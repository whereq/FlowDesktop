"""Calendar provider parse helpers + tool registration."""

from datetime import date
from decimal import Decimal

from api.services.tool_registry import ToolRegistry
from flowdesk_collector.providers.fmp import _cal_date, _cal_dec


def test_cal_date_parses_and_guards():
    assert _cal_date("2026-06-17") == date(2026, 6, 17)
    assert _cal_date("2026-06-17 12:00:00") == date(2026, 6, 17)
    assert _cal_date("") is None
    assert _cal_date(None) is None
    assert _cal_date("not-a-date") is None


def test_cal_dec_parses_and_guards():
    assert _cal_dec("1.23") == Decimal("1.23")
    assert _cal_dec(0) == Decimal("0")  # explicit zero is meaningful
    assert _cal_dec("") is None
    assert _cal_dec(None) is None
    assert _cal_dec("oops") is None


def test_calendar_tool_is_registered():
    names = {d["function"]["name"] for d in ToolRegistry().get_definitions()}
    assert "get_calendar_events" in names


def test_calendar_tool_can_be_subset():
    defs = ToolRegistry().get_definitions(names=["get_calendar_events"])
    assert len(defs) == 1
    assert defs[0]["function"]["name"] == "get_calendar_events"
