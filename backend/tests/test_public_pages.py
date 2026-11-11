"""Server-rendered share page — safe markdown rendering + meta."""

from api.routes.public_pages import _meta_desc, _render_md


def test_escapes_html():
    out = _render_md("<script>alert(1)</script>")
    assert "<script>" not in out
    assert "&lt;script&gt;" in out


def test_headers_bold_bullets():
    md = "# Title\n\nSome **bold** text\n\n- one\n- two"
    out = _render_md(md)
    assert "<h2>Title</h2>" in out
    assert "<strong>bold</strong>" in out
    assert out.count("<li>") == 2
    assert "<ul>" in out and "</ul>" in out


def test_paragraphs():
    assert "<p>hello world</p>" in _render_md("hello world")


def test_meta_desc_strips_and_truncates():
    d = _meta_desc("# NVDA\n\n**Strong** quarter with lots of detail " * 20)
    assert "#" not in d and "*" not in d
    assert len(d) <= 155
