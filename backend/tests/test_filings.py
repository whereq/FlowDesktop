"""Filings grounding — the chunker still works; the source is documented as absent.

The whereq.cloud Data API exposes SEC filing *metadata* by CIK, not the
10-K/10-Q narrative that the grounding index embeds, and it does not map a
ticker to a CIK. FlowDesktop therefore ships the table, the chunker and the
search tool, but does not populate ``company_filings`` on its own.

These tests pin that contract down so it cannot be broken silently.
"""

from datetime import date
from types import SimpleNamespace

from api.services.tool_registry import ToolRegistry
from flowdesk_core.config import get_settings


def test_filings_grounding_is_off_by_default():
    """Nothing is fetched from a filing source until the operator says so."""
    assert get_settings().filings_enabled is False


def test_filing_search_tool_is_registered():
    names = {d["function"]["name"] for d in ToolRegistry().get_definitions()}
    assert "search_filings" in names


def test_chunks_for_filing_caps_and_headers():
    from flowdesk_collector.embedding_indexer import _chunks_for_filing

    s = get_settings()
    filing = SimpleNamespace(
        id=42,
        symbol="AAPL",
        form="10-K",
        filing_date=date(2026, 1, 15),
        content="x" * (s.filings_chunk_chars * (s.filings_max_chunks_per_doc + 5)),
    )
    chunks = _chunks_for_filing(filing)
    # capped per doc
    assert len(chunks) == s.filings_max_chunks_per_doc
    # each chunk carries provenance header + correct denormalized metadata
    assert chunks[0]["content"].startswith("[AAPL 10-K 2026-01-15]")
    assert chunks[0]["source_type"] == "filing" and chunks[0]["source_id"] == 42
    assert chunks[0]["symbols"] == ["AAPL"]
    assert chunks[0]["chunk_index"] == 0 and chunks[1]["chunk_index"] == 1


def test_chunks_for_filing_short_content():
    from flowdesk_collector.embedding_indexer import _chunks_for_filing

    filing = SimpleNamespace(
        id=1, symbol="MSFT", form="10-Q", filing_date=date(2026, 4, 1), content="short body"
    )
    chunks = _chunks_for_filing(filing)
    assert len(chunks) == 1 and "short body" in chunks[0]["content"]
