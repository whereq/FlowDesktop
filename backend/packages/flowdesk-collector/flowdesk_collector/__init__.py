"""Data collection service.

FlowDesktop does not scrape market data. The collector is a **sync client**:
it pulls the symbol universe, quotes, daily history, short interest and
insider transactions from the whereq.cloud Data API with the operator's API
key, and writes them into the local database so the app and NOVA's tools
read from a local, fast store.

Everything the collector needs is in :mod:`flowdesk_core.whereq_cloud`.
"""
