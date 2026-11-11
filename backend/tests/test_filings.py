"""Filings ingestion — pure helpers (HTML strip + date parse), no network/DB."""

from datetime import date

from flowdesk_collector.providers.sec_filings import _MAX_CONTENT_CHARS, _html_to_text, _parse_date


def test_html_to_text_strips_tags_and_scripts():
    html = """
    <html><head><style>.x{color:red}</style><script>evil()</script></head>
    <body><h1>Risk Factors</h1><p>Demand may <b>decline</b>.</p>
    <table><tr><td>9</td></tr></table></body></html>
    """
    txt = _html_to_text(html)
    assert "Risk Factors" in txt and "Demand may decline" in txt
    assert "evil()" not in txt and "color:red" not in txt
    assert "9" not in txt  # tables dropped (XBRL noise)


def test_html_to_text_caps_length():
    big = "<p>" + ("word " * 200_000) + "</p>"
    assert len(_html_to_text(big)) <= _MAX_CONTENT_CHARS


def test_html_to_text_handles_garbage():
    assert isinstance(_html_to_text("not real <html"), str)


def test_parse_date():
    assert _parse_date("2026-03-31") == date(2026, 3, 31)
    assert _parse_date(None) is None
    assert _parse_date("") is None
    assert _parse_date("garbage") is None


def test_chunks_for_filing_caps_and_headers():
    from types import SimpleNamespace

    from flowdesk_collector.embedding_indexer import _chunks_for_filing
    from flowdesk_core.config import get_settings

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
    from types import SimpleNamespace

    from flowdesk_collector.embedding_indexer import _chunks_for_filing

    filing = SimpleNamespace(
        id=1, symbol="MSFT", form="10-Q", filing_date=date(2026, 4, 1), content="short body"
    )
    chunks = _chunks_for_filing(filing)
    assert len(chunks) == 1 and "short body" in chunks[0]["content"]
