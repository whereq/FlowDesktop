"""Data collectors — the jobs that fill the database.

Every collector here reads from the whereq.cloud Data API with the operator's
API key:

* :mod:`.universe` — the instrument catalog
* :mod:`.quotes` — the latest price for the whole universe
* :mod:`.history` — daily OHLCV history
* :mod:`.altdata` — short interest and insider Form 4 transactions
* :mod:`.mapping` — pure payload → ORM value mappings shared by the above

Collectors are idempotent: re-running them updates rows rather than
duplicating them.
"""

from __future__ import annotations
