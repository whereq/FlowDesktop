# Data sources

FlowDesktop is a **client of the whereq.cloud Data API**. It does not scrape
anything. Every market-data request goes to one host with your key in the
`X-API-Key` header, and the result is written into your own PostgreSQL
database so the app and NOVA's tools read from a local, fast store.

```
whereq.cloud Data API  ──X-API-Key──▶  collector  ──▶  PostgreSQL  ──▶  API  ──▶  browser
```

---

## The key

The key is sent in the `X-API-Key` request header on every call. It is
required: the client refuses to make a request without one, and the API
rejects a request whose key is missing or invalid (`401`/`403`).

```bash
# backend/.env or docker/.env
WHEREQ_API_KEY=wq_live_your_key_here
WHEREQ_API_URL=https://api.whereq.cloud
```

Some endpoints on the API are reachable without a key. FlowDesktop still
sends it — the key is what turns the data on for your deployment, and there is
no code path that falls back to anonymous access.

A key with the **`filings`** scope unlocks the SEC filing endpoints. Keys may
also carry a `news` scope.

### What happens without a key

| Where | Behaviour |
|---|---|
| The API at boot | Logs a warning naming `WHEREQ_API_KEY`. It still starts — a missing key is a setup problem, not a crash. |
| Any data request | Raises `WhereqCloudAuthError`. Nothing is fetched. |
| The `/providers/status` endpoint | Reports the source as unavailable. |

---

## What the API provides

| Endpoint family | Used for | Notes |
|---|---|---|
| `GET /v1/stats` | Dataset counters | Instrument, quote and bar totals. |
| `GET /v1/catalog` | Exchange coverage | Each exchange carries its market and currency. |
| `GET /v1/catalog/symbols` | The instrument universe | Paginated: `limit` ≤ 10000, `offset`. Filterable by `exchange` and `sector`. |
| `GET /v1/catalog/symbol/{symbol}` | One instrument's profile | Name, exchange, market, currency, sector, industry, market cap, coverage flags. |
| `GET /v1/equities/{symbol}/quote` | The latest quote | |
| `GET /v1/equities/quotes` | Quotes for a batch | Max 50 symbols per request. |
| `GET /v1/equities/{symbol}/history` | Daily OHLCV bars | `start`, `end`, `limit` ≤ 2000. Newest bar first. |
| `GET /v1/alt/short-interest/{symbol}` | Short-interest history | One row per settlement date. |
| `GET /v1/alt/insider/{symbol}` | Insider Form 4 transactions | `days` ≤ 3650, `limit` ≤ 500. |
| `GET /v1/edgar/filings` | SEC filing metadata | `cik` required. Needs the `filings` scope. |

### Coverage

Fifteen exchanges are covered, spanning the US, Canada, China, Hong Kong,
Japan, Singapore, Taiwan, Korea, the UK, Australia, Brazil, Germany and India.
The exact list and the instrument count per exchange come from
`GET /v1/catalog`, and the collector reads it at sync time — so your
`stocks` table reflects the API's coverage rather than a snapshot bundled
into the repository.

---

## How the sync works

The collector (`flowdesk-collector`) runs on a schedule and writes into your
database.

| Job | Schedule | Writes |
|---|---|---|
| `sync_universe` | 00:01 daily | `stocks`, `provider_status` |
| `collect_quotes` | every 5 minutes, market hours only | `quotes` |
| `collect_history` | every 4 hours | `historical_prices` |
| `collect_insider` | 02:30 daily | `insider_transactions` |
| `collect_short_interest` | 03:00 daily | `short_interest` |

The instrument universe is synced **exchange by exchange**. The catalog's
exchange list carries each exchange's market and currency, which the
per-symbol listing does not, so one pass over the exchange list plus one paged
pass per exchange gives every row a correct market and currency.

Instruments the catalog stops listing are **soft-deleted** (`is_active =
false`), never removed — their quotes and history stay intact.

Payloads are mapped to rows by pure functions in
`flowdesk_collector/collectors/mapping.py`. The mappings handle the three
places where the API and the ORM disagree:

* the API sends decimal numbers as **strings** (`"325.7500"`) — they become
  `Decimal` columns;
* the API sends **naive** ISO timestamps — a timestamp that carries a zone is
  converted to UTC before it is stored;
* insider transactions carry a stable platform row `id` but **no CIK**, so
  that id becomes `line_index` and keeps `(accession, line_index)` unique,
  which is what makes a re-sync idempotent.

---

## The two gaps

Two surfaces FlowDesktop used to fill are **not** served by the Data API. The
tables, tools and UI panels are all still there and work — they are simply
empty until you populate them.

### 1. SEC filing narrative

The Data API exposes SEC filings as **metadata** — form, filing date, report
date, accession number, document URL — and it addresses them by **CIK**, not
by ticker. It exposes no ticker→CIK mapping, and it does not return the
10-K/10-Q narrative text.

That text is what FlowDesktop's filing-grounding feature needs: the
`company_filings` table holds the document narrative, which the embedding
indexer chunks into `retrieval_chunks`, which is what NOVA's `search_filings`
tool searches.

**So:** FlowDesktop does not populate `company_filings` for you, and
`FILINGS_ENABLED` defaults to `false`.

**To turn it on:** populate `company_filings` yourself — write a small script
that fetches the documents you want and inserts the rows, or point
FlowDesktop at your own EDGAR source. The schema, the chunker
(`flowdesk_collector/embedding_indexer.py`) and the search tool all work
against a populated table.

The `/api/v1/market-data/{symbol}/filings` route and the StockDetail filings
panel read the table and will fill in as soon as it has rows.

### 2. Congressional trades

The Data API does not expose congressional (STOCK Act) disclosures.

**So:** the `congress_trades` table stays empty, and with it the
`get_congress_trades` tool and the StockDetail congress panel.

**To turn it on:** populate `congress_trades` yourself. The columns are
`symbol`, `politician`, `chamber`, `txn_type`, `amount_range`,
`transaction_date`, `disclosure_date`, `source` and `dedup_hash`.

---

## Adding another source

The collector is deliberately narrow: one client, one auth path, explicit
field mappings. If you want to pull from somewhere else, do it behind the
same boundary:

1. add a method to `flowdesk_core/whereq_cloud.py`, or a sibling client
   module in `flowdesk_core/`;
2. map its payloads to ORM values in `flowdesk_collector/collectors/mapping.py`;
3. add a collector in `flowdesk_collector/collectors/` and register a job in
   `flowdesk_collector/scheduler.py`.

Keep the mapping functions pure — they take a payload and return column
values, with no database or network access — and the mapping stays unit
testable.
