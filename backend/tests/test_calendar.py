"""Calendar — the NOVA tool surface.

The FMP earnings-calendar provider is gone: market events come from the local
``market_events`` table. The tool that reads it stays.
"""

from api.services.tool_registry import ToolRegistry


def test_calendar_tool_is_registered():
    names = {d["function"]["name"] for d in ToolRegistry().get_definitions()}
    assert "get_calendar_events" in names


def test_calendar_tool_can_be_subset():
    defs = ToolRegistry().get_definitions(names=["get_calendar_events"])
    assert len(defs) == 1
    assert defs[0]["function"]["name"] == "get_calendar_events"
