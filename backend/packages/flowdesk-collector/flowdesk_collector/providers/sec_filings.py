"""SEC EDGAR filing-narrative fetcher (10-K / 10-Q primary documents).

Complements sec_edgar.py (which pulls XBRL *numbers*) by fetching the *narrative*
text — MD&A, risk factors, business description — for NOVA's filings grounding.
Free, no key. See docs/design/RFC_NOVA_FILINGS_GROUNDING.md.
"""

from __future__ import annotations

import logging
from datetime import date

import aiohttp

from flowdesk_collector.providers.sec_edgar import USER_AGENT

logger = logging.getLogger(__name__)

SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
ARCHIVE_DOC_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{doc}"

# Bound stored/parsed text so one filing can't blow up the DB or the embedder.
_MAX_CONTENT_CHARS = 400_000


def _html_to_text(html: str) -> str:
    """Strip an EDGAR primary document (HTML/XBRL) to readable text. Best-effort."""
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "lxml")
        for tag in soup(["script", "style", "table"]):  # tables are mostly XBRL noise
            tag.decompose()
        text = " ".join(soup.get_text(separator=" ", strip=True).split())
    except Exception:
        text = " ".join(html.split())
    return text[:_MAX_CONTENT_CHARS]


def _parse_date(s: str | None) -> date | None:
    try:
        return date.fromisoformat(s) if s else None
    except (ValueError, TypeError):
        return None


async def fetch_latest_filings(
    cik: int, forms: tuple[str, ...] = ("10-K", "10-Q"), per_form: int = 1
) -> list[dict]:
    """Return the latest `per_form` filings for each form type.

    Each dict: {form, accession, filing_date, period_end, url, title, content}.
    Returns [] on any fetch/parse failure (filings are a best-effort enrichment).
    """
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    out: list[dict] = []
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(SUBMISSIONS_URL.format(cik=cik)) as resp:
                if resp.status != 200:
                    logger.debug("EDGAR submissions %s → %s", cik, resp.status)
                    return []
                data = await resp.json(content_type=None)

            recent = (data.get("filings") or {}).get("recent") or {}
            acc = recent.get("accessionNumber", [])
            form_arr = recent.get("form", [])
            fdate = recent.get("filingDate", [])
            rdate = recent.get("reportDate", [])
            pdoc = recent.get("primaryDocument", [])
            pdesc = recent.get("primaryDocDescription", [])

            counts = dict.fromkeys(forms, 0)
            for i in range(len(acc)):
                f = form_arr[i] if i < len(form_arr) else None
                if f not in forms or counts.get(f, per_form) >= per_form:
                    continue
                doc = pdoc[i] if i < len(pdoc) else ""
                if not doc:
                    continue
                acc_nodash = acc[i].replace("-", "")
                url = ARCHIVE_DOC_URL.format(cik=cik, acc=acc_nodash, doc=doc)
                try:
                    async with session.get(url) as docresp:
                        if docresp.status != 200:
                            continue
                        html = await docresp.text()
                except Exception as exc:
                    logger.debug("EDGAR doc fetch failed %s: %s", url, exc)
                    continue
                content = _html_to_text(html)
                if len(content) < 500:  # parse yielded nothing useful
                    continue
                out.append(
                    {
                        "form": f,
                        "accession": acc[i],
                        "filing_date": _parse_date(fdate[i] if i < len(fdate) else None),
                        "period_end": _parse_date(rdate[i] if i < len(rdate) else None),
                        "url": url,
                        "title": (pdesc[i] if i < len(pdesc) else None) or f,
                        "content": content,
                    }
                )
                counts[f] += 1
                if all(counts[x] >= per_form for x in forms):
                    break
    except Exception as exc:
        logger.warning("fetch_latest_filings failed for CIK %s: %s", cik, exc)
        return []
    return out
