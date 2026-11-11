"""Data collectors — the jobs that fill the database.

Every collector here uses a **keyless** source by default:

* :mod:`.quotes` — Yahoo Finance (latest price for the whole universe)
* :mod:`.history` — Yahoo Finance (daily OHLCV history)
* :mod:`.altdata` — SEC EDGAR (filings + insider Form 4) and Yahoo (short interest)
* :mod:`.universe` — the bundled symbol list

Collectors are idempotent: re-running them updates rows rather than
duplicating them.
"""

from __future__ import annotations
