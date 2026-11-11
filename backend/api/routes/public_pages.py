"""Server-rendered public pages for SEO + sharing.

Mounted at the app root (no /api/v1 prefix); nginx proxies /s/, /sitemap.xml,
/robots.txt here. These return real HTML (content + OG/Twitter meta) so shared
NOVA analyses get rich link previews and are indexable — no SPA SSR needed.
"""

from __future__ import annotations

import html
import re

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse, PlainTextResponse, Response
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from flowdesk_core.config import get_settings
from flowdesk_core.database import get_db
from flowdesk_core.models.shared_analysis import SharedAnalysis

router = APIRouter(tags=["public-pages"])

SITE_URL = get_settings().site_url


def _render_md(text: str) -> str:
    """Minimal, safe markdown → HTML (escape first; headers/bold/bullets/paras)."""
    out: list[str] = []
    in_list = False
    for raw in text.split("\n"):
        line = html.escape(raw.rstrip())
        line = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", line)
        stripped = line.strip()
        if not stripped:
            if in_list:
                out.append("</ul>")
                in_list = False
            continue
        if stripped.startswith("- ") or stripped.startswith("* "):
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{stripped[2:]}</li>")
            continue
        if in_list:
            out.append("</ul>")
            in_list = False
        m = re.match(r"(#{1,3})\s+(.*)", stripped)
        if m:
            lvl = min(len(m.group(1)) + 1, 4)
            out.append(f"<h{lvl}>{m.group(2)}</h{lvl}>")
        else:
            out.append(f"<p>{line}</p>")
    if in_list:
        out.append("</ul>")
    return "\n".join(out)


def _meta_desc(content: str) -> str:
    plain = re.sub(r"[#*`>_-]", "", content).strip()
    plain = re.sub(r"\s+", " ", plain)
    return html.escape(plain[:155])


def _page_html(s: SharedAnalysis) -> str:
    title = html.escape(s.title)
    sym = html.escape(s.symbol) if s.symbol else ""
    desc = _meta_desc(s.content)
    url = f"{SITE_URL}/s/{s.slug}"
    cta = f"{SITE_URL}/stock/{sym}" if sym else SITE_URL
    body = _render_md(s.content)
    sym_badge = f'<span class="sym">{sym}</span>' if sym else ""
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{title} · FlowDesktop</title>
<meta name="description" content="{desc}"/>
<link rel="canonical" href="{url}"/>
<meta property="og:type" content="article"/>
<meta property="og:title" content="{title}"/>
<meta property="og:description" content="{desc}"/>
<meta property="og:url" content="{url}"/>
<meta property="og:image" content="{SITE_URL}/icon-512.png"/>
<meta property="og:site_name" content="FlowDesktop"/>
<meta name="twitter:card" content="summary"/>
<meta name="twitter:title" content="{title}"/>
<meta name="twitter:description" content="{desc}"/>
<meta name="twitter:image" content="{SITE_URL}/icon-512.png"/>
<link rel="icon" type="image/svg+xml" href="/logo.svg"/>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;600&display=swap" rel="stylesheet"/>
<style>
:root{{--bg:#0A0B0D;--panel:#121419;--rule:#23262d;--text:#e6e8ec;--dim:#9aa0aa;--faint:#6b7280;--nova:#3ddc97;--accent:#1e88e5}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--text);font-family:'IBM Plex Sans',system-ui,sans-serif;line-height:1.6}}
.wrap{{max-width:760px;margin:0 auto;padding:24px 20px 64px}}
header{{display:flex;align-items:center;gap:10px;padding:14px 0;border-bottom:1px solid var(--rule);margin-bottom:24px}}
header .logo{{font-weight:700;letter-spacing:-.01em;color:var(--text);text-decoration:none;font-size:18px}}
header .logo b{{color:var(--nova)}}
h1{{font-size:26px;font-weight:700;letter-spacing:-.01em;margin:0 0 6px}}
.sym{{font-family:'IBM Plex Mono',monospace;font-size:12px;color:var(--nova);border:1px solid var(--rule);border-radius:3px;padding:2px 7px;margin-left:8px;vertical-align:middle}}
.meta{{color:var(--faint);font-size:12px;font-family:'IBM Plex Mono',monospace;margin-bottom:20px}}
.content{{font-size:15px}}
.content h2{{font-size:19px;margin:22px 0 8px}} .content h3,.content h4{{font-size:16px;margin:18px 0 6px;color:var(--dim)}}
.content ul{{padding-left:20px}} .content li{{margin:3px 0}}
.content strong{{color:#fff}}
.cta{{display:inline-block;margin-top:28px;background:var(--nova);color:#06120c;font-weight:700;text-decoration:none;padding:11px 20px;border-radius:3px}}
.disc{{margin-top:28px;padding-top:16px;border-top:1px solid var(--rule);color:var(--faint);font-size:12px}}
a{{color:var(--accent)}}
</style>
</head><body><div class="wrap">
<header><a class="logo" href="{SITE_URL}">Flow<b>Desktop</b></a><span style="color:var(--faint);font-size:12px">· shared analysis by NOVA</span></header>
<h1>{title}{sym_badge}</h1>
<div class="meta">{s.view_count + 1} views · Powered by NOVA, FlowDesktop's AI analyst</div>
<div class="content">{body}</div>
<a class="cta" href="{cta}">Analyze {sym or "stocks"} on FlowDesktop →</a>
<div class="disc">FlowDesktop &amp; NOVA are research/educational tools — not financial advice. AI-generated analysis can be wrong and market data may be delayed. Always verify before investing.</div>
</div></body></html>"""


_NOT_FOUND = f"""<!doctype html><html><head><meta charset="utf-8"/><title>Not found · FlowDesktop</title>
<meta name="robots" content="noindex"/><style>body{{background:#0A0B0D;color:#9aa0aa;font-family:system-ui,sans-serif;display:flex;height:100vh;align-items:center;justify-content:center;margin:0}}</style>
</head><body><div>This shared analysis was not found. <a style="color:#3ddc97" href="{SITE_URL}">Go to FlowDesktop →</a></div></body></html>"""


@router.get("/s/{slug}", response_class=HTMLResponse)
async def shared_page(slug: str, db: AsyncSession = Depends(get_db)) -> Response:
    row = await db.scalar(select(SharedAnalysis).where(SharedAnalysis.slug == slug))
    if not row:
        return HTMLResponse(_NOT_FOUND, status_code=404)
    html_doc = _page_html(row)
    # Best-effort view count bump (don't fail the page on a write error).
    try:
        await db.execute(
            update(SharedAnalysis)
            .where(SharedAnalysis.id == row.id)
            .values(view_count=SharedAnalysis.view_count + 1)
        )
        await db.commit()
    except Exception:
        pass
    return HTMLResponse(html_doc)


@router.get("/sitemap.xml")
async def sitemap(db: AsyncSession = Depends(get_db)) -> Response:
    rows = (
        await db.execute(
            select(SharedAnalysis.slug, SharedAnalysis.created_at)
            .order_by(SharedAnalysis.created_at.desc())
            .limit(5000)
        )
    ).all()
    urls = [f"<url><loc>{SITE_URL}/</loc></url>"]
    for slug, created in rows:
        lastmod = f"<lastmod>{created.date().isoformat()}</lastmod>" if created else ""
        urls.append(f"<url><loc>{SITE_URL}/s/{slug}</loc>{lastmod}</url>")
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + "".join(urls) + "</urlset>"
    )
    return Response(content=xml, media_type="application/xml")


@router.get("/robots.txt", response_class=PlainTextResponse)
async def robots() -> str:
    return f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n"
