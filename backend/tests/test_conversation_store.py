"""Pure-logic tests for conversation persistence helpers (no DB)."""

from api.services.conversation_store import _title_from


def test_title_from_short():
    assert _title_from("Compare NVDA vs AMD") == "Compare NVDA vs AMD"


def test_title_from_empty():
    assert _title_from("") == "New conversation"
    assert _title_from("   ") == "New conversation"


def test_title_from_collapses_whitespace():
    assert _title_from("hello\n\n   world") == "hello world"


def test_title_from_truncates():
    t = _title_from("x" * 200)
    assert len(t) == 81 and t.endswith("…")
