"""SEC Form 4 insider-transaction fetcher.

Lists an issuer's recent Form 4 filings (EDGAR browse atom feed) and parses the
non-derivative transactions from each ownership document. Free, no key. The parse
helpers are pure (network-free) so they're unit-testable.
See docs/design/RFC_NOVA_INSIDER_ACTIVITY.md.
"""

from __future__ import annotations

import logging
import re
from datetime import date
from xml.etree import ElementTree as ET

import aiohttp

from flowdesk_collector.providers.sec_edgar import USER_AGENT

logger = logging.getLogger(__name__)

ATOM_URL = (
    "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}"
    "&type=4&dateb=&owner=include&count={count}&output=atom"
)
SUBMISSION_TXT = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{accession}.txt"

_OWNERSHIP_RE = re.compile(r"<ownershipDocument>.*?</ownershipDocument>", re.DOTALL)
_ACC_RE = re.compile(r"<accession-number>\s*([^<]+?)\s*</accession-number>")
_FDATE_RE = re.compile(r"<filing-date>\s*([^<]+?)\s*</filing-date>")


def _txt(node, path: str) -> str | None:
    el = node.find(path)
    return el.text.strip() if el is not None and el.text else None


def _num(s: str | None) -> float | None:
    try:
        return float(s) if s not in (None, "") else None
    except (ValueError, TypeError):
        return None


def _pdate(s: str | None) -> date | None:
    try:
        return date.fromisoformat(s) if s else None
    except (ValueError, TypeError):
        return None


def _bool(s: str | None) -> bool:
    return str(s).strip() in ("1", "true", "True")


def extract_ownership_xml(submission_txt: str) -> str | None:
    """Pull the <ownershipDocument> XML out of a full Form 4 submission .txt."""
    m = _OWNERSHIP_RE.search(submission_txt or "")
    return m.group(0) if m else None


def parse_form4(xml: str) -> dict | None:
    """Parse a Form 4 ownership document into {owner..., transactions:[...]}.

    Returns None if the XML can't be parsed. Each transaction is a non-derivative
    line: {transaction_date, code, acquired_disposed, shares, price, shares_after}.
    """
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return None

    owner = root.find("reportingOwner")
    name = _txt(owner, "reportingOwnerId/rptOwnerName") if owner is not None else None
    rel = owner.find("reportingOwnerRelationship") if owner is not None else None
    title = _txt(rel, "officerTitle") if rel is not None else None
    is_director = _bool(_txt(rel, "isDirector")) if rel is not None else False
    is_officer = _bool(_txt(rel, "isOfficer")) if rel is not None else False
    is_ten_pct = _bool(_txt(rel, "isTenPercentOwner")) if rel is not None else False

    txns: list[dict] = []
    for t in root.findall("nonDerivativeTable/nonDerivativeTransaction"):
        amounts = t.find("transactionAmounts")
        shares = _num(_txt(amounts, "transactionShares/value")) if amounts is not None else None
        price = (
            _num(_txt(amounts, "transactionPricePerShare/value")) if amounts is not None else None
        )
        ad = _txt(amounts, "transactionAcquiredDisposedCode/value") if amounts is not None else None
        txns.append(
            {
                "transaction_date": _pdate(_txt(t, "transactionDate/value")),
                "code": _txt(t, "transactionCoding/transactionCode"),
                "acquired_disposed": ad,
                "shares": shares,
                "price": price,
                "shares_after": _num(
                    _txt(t, "postTransactionAmounts/sharesOwnedFollowingTransaction/value")
                ),
            }
        )

    return {
        "insider_name": name or "Unknown",
        "insider_title": title,
        "is_director": is_director,
        "is_officer": is_officer,
        "is_ten_pct": is_ten_pct,
        "transactions": txns,
    }


async def fetch_recent_form4(cik: int, max_filings: int = 8) -> list[dict]:
    """Return recent non-derivative insider transactions for an issuer.

    Each dict: {accession, filing_date, line_index, insider_name, insider_title,
    is_director, is_officer, is_ten_pct, transaction_date, code,
    acquired_disposed, shares, price, shares_after}. [] on failure.
    """
    headers = {"User-Agent": USER_AGENT}
    rows: list[dict] = []
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(ATOM_URL.format(cik=cik, count=max_filings)) as resp:
                if resp.status != 200:
                    return []
                atom = await resp.text()

            accs = _ACC_RE.findall(atom)
            fdates = _FDATE_RE.findall(atom)
            for idx, accession in enumerate(accs[:max_filings]):
                filing_date = _pdate(fdates[idx]) if idx < len(fdates) else None
                acc_nodash = accession.replace("-", "")
                url = SUBMISSION_TXT.format(cik=cik, acc=acc_nodash, accession=accession)
                try:
                    async with session.get(url) as r:
                        if r.status != 200:
                            continue
                        txt = await r.text()
                except Exception:
                    continue
                xml = extract_ownership_xml(txt)
                if not xml:
                    continue
                parsed = parse_form4(xml)
                if not parsed:
                    continue
                for line_index, tx in enumerate(parsed["transactions"]):
                    shares, price = tx.get("shares"), tx.get("price")
                    rows.append(
                        {
                            "accession": accession,
                            "filing_date": filing_date,
                            "line_index": line_index,
                            "insider_name": parsed["insider_name"],
                            "insider_title": parsed["insider_title"],
                            "is_director": parsed["is_director"],
                            "is_officer": parsed["is_officer"],
                            "is_ten_pct": parsed["is_ten_pct"],
                            "value": (shares * price) if (shares and price) else None,
                            **tx,
                        }
                    )
    except Exception as exc:
        logger.warning("fetch_recent_form4 failed for CIK %s: %s", cik, exc)
        return []
    return rows
