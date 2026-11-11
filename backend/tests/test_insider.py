"""Insider activity — the Data API mapping and the NOVA tool surface.

The Form 4 parser is gone: insider transactions are synced from the
whereq.cloud Data API, which returns already-parsed rows. The payload → ORM
mapping is covered in ``test_collector_mapping.py``; this file covers the
tool surface and the model contract.
"""

from api.services.tool_registry import ToolRegistry
from flowdesk_core.models.insider_transaction import InsiderTransaction


def test_insider_tool_is_registered():
    names = {d["function"]["name"] for d in ToolRegistry().get_definitions()}
    assert "get_insider_activity" in names


def test_insider_tool_can_be_subset():
    defs = ToolRegistry().get_definitions(names=["get_insider_activity"])
    assert len(defs) == 1
    assert defs[0]["function"]["name"] == "get_insider_activity"


def test_cik_is_optional():
    """The Data API addresses insider activity by ticker, not by CIK."""
    assert InsiderTransaction.__table__.columns["cik"].nullable is True


def test_line_index_holds_the_api_transaction_id():
    """It is what keeps (accession, line_index) unique across re-syncs."""
    col = InsiderTransaction.__table__.columns["line_index"]
    assert col.nullable is False
    assert col.type.__class__.__name__ == "BigInteger"


def test_accession_and_line_index_are_unique_together():
    constraints = {c.name for c in InsiderTransaction.__table__.constraints}
    assert "uq_insider_txn" in constraints
