"""Congressional trades — the surface is kept, the source is documented as absent.

The whereq.cloud Data API does not expose congressional (STOCK Act)
disclosures, so FlowDesktop ships the table and the NOVA tool but does not
populate ``congress_trades`` on its own. Populate it yourself to switch the
panel on.
"""

from api.services.tool_registry import ToolRegistry
from flowdesk_core.models.congress_trade import CongressTrade


def test_congress_tool_is_registered():
    names = {d["function"]["name"] for d in ToolRegistry().get_definitions()}
    assert "get_congress_trades" in names


def test_congress_table_keeps_its_columns():
    cols = {c.name for c in CongressTrade.__table__.columns}
    assert {"symbol", "politician", "chamber", "txn_type", "transaction_date"} <= cols
