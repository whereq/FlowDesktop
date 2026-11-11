# FlowDesktop — Database Reference

The PostgreSQL schema for FlowDesktop: 51 tables, one Alembic migration tree,
two required extensions.

**Contents**

1. [Overview](#1-overview)
2. [Required extensions](#2-required-extensions)
3. [How migrations work](#3-how-migrations-work)
4. [Domain: universe and prices](#4-domain-universe-and-prices)
5. [Domain: alternative data](#5-domain-alternative-data)
6. [Domain: market intelligence](#6-domain-market-intelligence)
7. [Domain: user](#7-domain-user)
8. [Domain: chat and agents](#8-domain-chat-and-agents)
9. [Domain: simulator](#9-domain-simulator)
10. [Domain: platform](#10-domain-platform)
11. [Indexes and unique constraints](#11-indexes-and-unique-constraints)
12. [The soft-delete convention](#12-the-soft-delete-convention)
13. [Schema drift detection](#13-schema-drift-detection)
14. [Contributor workflow](#14-contributor-workflow)

---

## 1. Overview

| Property | Value |
|---|---|
| Database | PostgreSQL 17 |
| Tables | 51 |
| Indexes | 78 explicit indexes, plus the unique constraints' implicit indexes |
| Migrations | One revision: `0001_initial_schema` |
| ORM | SQLAlchemy 2.0 declarative, in `flowdesk_core.models` |
| Async driver | `asyncpg` |
| Sync driver | `psycopg` (via `psycopg[binary]`), `psycopg2-binary` also shipped |
| Extensions | `vector` (pgvector), `pg_trgm` |

### 1.1 Table groups

| Domain | Tables | Purpose |
|---|---|---|
| **Universe and prices** | 3 | The symbol spine, the quote log, the daily OHLCV series. |
| **Alternative data** | 8 | Filings, insider trades, short interest, congressional trades, XBRL fundamentals, macro series, the event calendar, Chinese names. |
| **Market intelligence** | 6 | Raw news, AI signals, sector aggregates, themes, relationships. |
| **User** | 10 | Per-user state keyed by the OIDC subject UUID. |
| **Chat and agents** | 9 | Conversations, messages, custom agents, schedules, the vector index, shared analyses, shadow trades, Pulse ledgers. |
| **Simulator** | 5 | Accounts, orders, positions, fills, snapshots. |
| **Platform** | 10 | Provider health and catalogue, coverage telemetry, the data-source catalogue, the multi-domain registry spine, translations. |

### 1.2 Conventions

**Ownership.** User-scoped tables carry `keycloak_id` (a `uuid` column holding
the OIDC subject). It is the owner key on every row belonging to a person. The
API derives it from the verified JWT and never from a client-supplied value.

**Primary keys.** Most tables use a surrogate `id`. Three user tables use
`keycloak_id` as the primary key directly, because there is exactly one row per
user: `user_profiles`, `notification_prefs`, `chat_quotas`, and
`investor_profile`.

**Money.** Every monetary column is `numeric`, never `float`. Cash quantises to
four decimal places; prices to six. See
[design-low-level-design.md §13.2](design-low-level-design.md#132-decimal-money-handling).

**Arrays.** PostgreSQL native `ARRAY` columns are used for list-shaped data:
`text[]` for symbols, sectors, regions, and theme tags; `varchar[]` for tool
names and role lists. They are indexed with the GIN index operator class where
containment queries need them.

**Timestamps.** `DateTime` columns are `TIMESTAMP WITHOUT TIME ZONE` and are
written in UTC. The `created_at` columns that use `server_default=now()` are
the exception in style only — the value is still UTC.

**Soft deletes.** Only `stocks` uses one, via `is_active`. See
[§12](#12-the-soft-delete-convention).

---

## 2. Required extensions

| Extension | Used by | Failure symptom if missing |
|---|---|---|
| `vector` (pgvector) | `retrieval_chunks.embedding` | The `retrieval_chunks` table fails to create; the semantic search tools report "embeddings unavailable". |
| `pg_trgm` | Trigram indexes for symbol and name search | The tables create, but trigram index creation fails and symbol search falls back to a slow scan. |

### 2.1 Creating them

```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

Two places do this for you:

- `docker/db/init-extensions.sql` — runs once, when the compose stack first
  initialises the database.
- `backend/alembic/env.py` — `_ensure_extensions()` runs before the first
  migration, on a separate connection. It is best-effort: if the role lacks
  the privilege, the migration prints a warning and continues.

> The extension files must be installed on the server. If PostgreSQL reports
> `could not open extension control file`, install the pgvector package for
> your distribution and restart PostgreSQL.

### 2.2 The pgvector column

`retrieval_chunks.embedding` is `pgvector.sqlalchemy.vector.VECTOR(dim=384)`.
The width is fixed at 384 by the migration and must match the configured
`embedding_dim` (default `384`, the local
`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` model).

Changing the embedding model therefore requires a migration that alters the
column and a re-index of the existing chunks under the new model id. The
`retrieval_chunks.model` column records which model produced each vector, so
a mixed-model state is detectable rather than silent.

---

## 3. How migrations work

### 3.1 The single initial revision

`backend/alembic/versions/0001_initial_schema.py` — revision
`0001_initial_schema`, `down_revision = None`. It creates all 51 tables, all
indexes, and all unique constraints in one pass.

```bash
cd backend
alembic upgrade head
```

Run it from `backend/` — `alembic.ini` sets `script_location = alembic` and
`prepend_sys_path = .`, both relative to the working directory.

### 3.2 The connection string

`alembic.ini` deliberately leaves `sqlalchemy.url` unset so no connection
string is ever committed. `backend/alembic/env.py` resolves the URL from
`get_settings().database_url`, falling back to the `DATABASE_URL` environment
variable, and raises if neither is set.

### 3.3 The extension quirk

`run_migrations_online()` creates the extensions on a **separate connection**
that it commits independently, then runs the migrations on a second connection.

The reason is in the source comment: executing DDL on the migration's own
connection auto-begins a transaction, Alembic then sees a transaction already
in progress and skips its own commit, and the migration is silently rolled
back when the connection closes. The extensions must not share the migration's
connection.

### 3.4 Autogenerate configuration

`env.py` sets `compare_type=True` and `compare_server_default=True`, so
autogenerate detects column type and server-default changes, not just added and
dropped columns.

### 3.5 What the API never does

`flowdesk_core.database.init_db()` runs `SELECT 1` only. It deliberately does
**not** call `Base.metadata.create_all()` — that races with Alembic and
produces `DuplicateTable` errors. The docstring says so explicitly.

---

## 4. Domain: universe and prices

### 4.1 `stocks`

The symbol spine. Every market-data table either references it by `stock_id`
or carries the symbol as a denormalised text column.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | `integer` | no | PK, autoincrement |
| `symbol` | `varchar(20)` | no | **Unique**, indexed. Yahoo Finance canonical format (`AAPL`, `600519.SS`) |
| `name` | `varchar(255)` | no | English name |
| `name_cn` | `varchar(100)` | yes | Chinese name |
| `exchange` | `varchar(50)` | yes | `NYQ`, `NMS`, `SHH`, `SHZ`, `TOR`, … |
| `sector` | `varchar(100)` | yes | |
| `industry` | `varchar(100)` | yes | |
| `market_cap` | `bigint` | yes | |
| `market` | `varchar(5)` | no | Default `US` |
| `currency` | `varchar(5)` | no | Default `USD` |
| `priority_tier` | `integer` | no | Default `2`. Lower is collected first |
| `is_active` | `boolean` | no | Default `True`. The soft-delete flag |
| `created_at` | `datetime` | no | |
| `updated_at` | `datetime` | no | Auto-updates on write |

**Constraints and indexes.** `ix_stocks_symbol` on `symbol`, **unique**.

**Notes.** The exchange column stores raw provider codes. The API normalises
them for display through `_EXCHANGE_CANONICAL` in `api/routes/stocks.py`, which
maps `SHH`/`SHG` → `SSE`, `SHZ`/`SZE` → `SZSE`, `NYSE`/`NYS`/`NYA`/`NYB` →
`NYQ`, `NASDAQ`/`NIM` → `NMS`, `TOR`/`TXS` → `TSX`. A filter on a canonical
code is expanded to all its stored variants before the query runs.

### 4.2 `quotes`

An append-only log — one row per symbol per collection run. A symbol that
stops trading still has a visible price history.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | `integer` | no | PK |
| `stock_id` | `integer` | no | FK → `stocks.id` |
| `price` | `numeric(12,4)` | no | The last price |
| `open_price` | `numeric(12,4)` | yes | |
| `high` | `numeric(12,4)` | yes | |
| `low` | `numeric(12,4)` | yes | |
| `close` | `numeric(12,4)` | yes | |
| `volume` | `bigint` | yes | |
| `change` | `numeric(12,4)` | yes | Absolute change |
| `change_percent` | `numeric(8,4)` | yes | Percentage change |
| `provider` | `varchar(50)` | yes | Usually `yahoo` |
| `timestamp` | `datetime` | no | The quote's own time, not the insert time |
| `created_at` | `datetime` | no | |

**Constraints and indexes.**
- `uq_quotes_stock_timestamp` on `(stock_id, timestamp)` — **unique**. Makes a
  re-run within the same timestamp idempotent.
- `idx_quotes_stock_id` on `stock_id` — the per-symbol history query.
- `idx_quotes_timestamp` on `timestamp` — the "latest quote across the market"
  query.

### 4.3 `historical_prices`

The daily OHLCV series.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | `integer` | no | PK |
| `stock_id` | `integer` | no | FK → `stocks.id` |
| `date` | `date` | no | The trading day |
| `open_price` | `numeric(12,4)` | yes | |
| `high` | `numeric(12,4)` | yes | |
| `low` | `numeric(12,4)` | yes | |
| `close` | `numeric(12,4)` | yes | |
| `adj_close` | `numeric(12,4)` | yes | The provider's adjusted close |
| `volume` | `bigint` | yes | |
| `provider` | `varchar(50)` | yes | |
| `adjustment` | `varchar(32)` | yes | `split_adjusted` / `split_dividend_adjusted` / `unadjusted` / `unknown` |
| `created_at` | `datetime` | no | |

**Constraints and indexes.**
- `uq_historical_stock_date` on `(stock_id, date)` — **unique**. Re-fetching a
  trading day does not duplicate it.
- `idx_historical_stock_date` on `(stock_id, date)` — the chart and indicator
  query.

**The `adjustment` column.** Providers disagree about what a "close" means:
some return the raw traded price, some adjust for splits, some for splits and
dividends. Stitching two providers' series without recording the convention
produces a chart with a fake jump in it. The per-provider basis is documented
in `flowdesk_collector/providers/base.py`.

---

## 5. Domain: alternative data

### 5.1 `company_filings`

One row per fetched SEC 10-K / 10-Q primary document.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | `bigint` | no | PK, autoincrement |
| `symbol` | `varchar(20)` | no | Indexed |
| `cik` | `bigint` | no | The SEC filer id |
| `form` | `varchar(12)` | no | `10-K` or `10-Q` |
| `filing_date` | `date` | no | |
| `period_end` | `date` | yes | The period the filing covers |
| `accession` | `varchar(30)` | no | The SEC accession number |
| `title` | `varchar(300)` | yes | |
| `url` | `text` | yes | |
| `content` | `text` | no | The document text — the source for the embedding index |
| `fetched_at` | `datetime` | no | |

**Constraints and indexes.**
- `uq_filing_accession` on `accession` — **unique**. The accession number is
  globally unique per SEC, which is what makes the collector's dedup set
  correct.
- `ix_company_filings_symbol` on `symbol`.
- `idx_filing_symbol_form` on `(symbol, form)` — the "latest 10-K for this
  symbol" query.

### 5.2 `insider_transactions`

One row per SEC Form 4 non-derivative transaction line.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | `bigint` | no | PK, autoincrement |
| `symbol` | `varchar(20)` | no | Indexed |
| `cik` | `bigint` | no | |
| `accession` | `varchar(30)` | no | The Form 4 accession |
| `line_index` | `integer` | no | The line within the filing |
| `filing_date` | `date` | yes | |
| `transaction_date` | `date` | yes | |
| `insider_name` | `varchar(150)` | no | |
| `insider_title` | `varchar(120)` | yes | |
| `is_director` | `boolean` | no | |
| `is_officer` | `boolean` | no | |
| `is_ten_pct` | `boolean` | no | A 10% owner |
| `transaction_code` | `varchar(2)` | yes | `P` = open-market purchase, `S` = sale, also `A`/`M`/`F`/`G` |
| `acquired_disposed` | `varchar(1)` | yes | `A` or `D` |
| `shares` | `numeric(18,4)` | yes | |
| `price` | `numeric(14,4)` | yes | |
| `value` | `numeric(20,2)` | yes | `shares × price` |
| `shares_owned_after` | `numeric(18,4)` | yes | |

**Constraints and indexes.**
- `uq_insider_txn` on `(accession, line_index)` — **unique**. One row per
  transaction line.
- `ix_insider_transactions_symbol` on `symbol`.
- `ix_insider_transactions_symbol_date` on `(symbol, transaction_date)`.

> The index name is deliberately table-qualified. PostgreSQL index names are
> schema-global, so `ix_insider_symbol_date` would collide with the index on
> the singular `insider_transaction` table in a shared database.

### 5.3 `short_interest`

One snapshot per symbol per settlement date.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | `bigint` | no | PK, autoincrement |
| `symbol` | `varchar(32)` | no | Indexed |
| `settlement_date` | `date` | no | The reporting date |
| `short_interest` | `bigint` | no | The share count — `NOT NULL`, so a row without it is never written |
| `prior_short_interest` | `bigint` | yes | The previous month's count |
| `avg_daily_volume` | `bigint` | yes | |
| `days_to_cover` | `float` | yes | |
| `short_pct_of_float` | `float` | yes | A **fraction**, 0.0–1.0. The API multiplies by 100 for display |
| `short_pct_of_outstanding` | `float` | yes | |
| `change_pct` | `float` | yes | Month-over-month change |
| `source` | `varchar(32)` | no | Default `Yahoo Finance` |
| `created_at` | `datetime` | no | Server default `now()` |

**Constraints and indexes.**
- `uq_short_interest_symbol_date` on `(symbol, settlement_date)` — **unique**.
- `ix_short_interest_symbol` on `symbol`.

> The column names are FINRA-shaped (`settlement_date`, `short_interest`,
  `days_to_cover`). The provider returns Yahoo-shaped keys
  (`as_of_date`, `shares_short`, `short_ratio`), so a mapping layer converts
  between them — `_short_interest_row` in
  `api/services/lazy_market_data.py` and `_short_interest_payload` in
  `api/services/tool_registry.py`. Both are pure functions, so the mapping is
  unit-tested independently of the database.

### 5.4 `congress_trades`

One US congressional stock transaction (STOCK Act disclosure).

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | `bigint` | no | PK, autoincrement |
| `dedup_hash` | `varchar(64)` | no | A SHA-1 over chamber, politician, ticker, date, type, and amount |
| `symbol` | `varchar(20)` | no | Indexed |
| `chamber` | `varchar(8)` | no | `senate` or `house` |
| `politician` | `varchar(150)` | no | |
| `party` | `varchar(20)` | yes | |
| `transaction_date` | `date` | yes | The trade date |
| `disclosure_date` | `date` | yes | When it became public — usually 45 days later |
| `txn_type` | `varchar(12)` | yes | `buy`, `sell`, `exchange` |
| `amount_range` | `varchar(60)` | yes | The disclosed range, not an exact amount |
| `source` | `varchar(40)` | no | |
| `created_at` | `datetime` | no | |

**Constraints and indexes.**
- `uq_congress_trade_hash` on `dedup_hash` — **unique**. The disclosure feed
  re-publishes the same records, so the hash is the identity.
- `ix_congress_trades_symbol` on `symbol`.
- `ix_congress_symbol_date` on `(symbol, transaction_date)`.

### 5.5 `fundamental_data`

One XBRL fact per filing.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | `integer` | no | PK |
| `symbol` | `varchar(20)` | no | Indexed |
| `cik` | `varchar(10)` | yes |  |
| `concept` | `varchar(100)` | no | The XBRL concept — `Revenues`, `NetIncomeLoss`, `Assets`, … |
| `value` | `numeric(20,4)` | yes |  |
| `unit` | `varchar(50)` | yes | `USD`, `shares`, … |
| `period_start` | `date` | yes | |
| `period_end` | `date` | no | |
| `form` | `varchar(20)` | yes | `10-K` / `10-Q` |
| `fiscal_year` | `integer` | yes | |
| `fiscal_quarter` | `integer` | yes | |
| `provider` | `varchar(20)` | no | `sec_edgar` |
| `filed_date` | `date` | yes | When the fact became public — the point-in-time anchor |
| `accession` | `varchar(24)` | yes | The source filing's accession |
| `created_at` | `datetime` | no | |

**Constraints and indexes.**
- `uq_fundamental_symbol_concept_period_form` on
  `(symbol, concept, period_end, form)` — **unique**. One fact per concept per
  period per form, so a restatement in a later filing is a new row and the
  history is auditable.
- `ix_fundamental_data_symbol` on `symbol`.
- `ix_fundamental_data_filed_date` on `filed_date`.

### 5.6 `macro_indicators`

One time-series point.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | `integer` | no | PK |
| `series_id` | `varchar(50)` | no | `FEDFUNDS`, `DGS10`, `CPIAUCSL`, `UNRATE`, `GDPC1` |
| `series_name` | `varchar(100)` | yes |  |
| `value` | `numeric(20,6)` | yes | |
| `indicator_date` | `date` | no | |
| `unit` | `varchar(100)` | yes |  |
| `frequency` | `varchar(20)` | yes | |
| `provider` | `varchar(20)` | no |  |
| `created_at` | `datetime` | no | |

**Constraints and indexes.**
- `uq_macro_series_date` on `(series_id, indicator_date)` — **unique**.
- `ix_macro_series_date` on `(series_id, indicator_date)`.
- `ix_macro_indicators_series_id` on `series_id`.

### 5.7 `market_events`

The earnings and dividend calendar. Both kinds live in one table,
discriminated by `kind`, so the calendar feed is a single query.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | `integer` | no | PK |
| `symbol` | `varchar(20)` | no | Indexed |
| `kind` | `varchar(12)` | no | `earnings` or `dividend` |
| `event_date` | `date` | no | The report date, or the ex-dividend date |
| `time_of_day` | `varchar(4)` | yes | `before_open`, `after_close`, … |
| `eps_estimate` | `numeric(20,4)` | yes |  |
| `eps_actual` | `numeric(20,4)` | yes |  |
| `revenue_estimate` | `numeric(24,2)` | yes |  |
| `revenue_actual` | `numeric(24,2)` | yes |  |
| `fiscal_period` | `varchar(16)` | yes | `Q3`, `FY2026` |
| `amount` | `numeric(20,6)` | yes | The dividend amount |
| `currency` | `varchar(8)` | yes |  |
| `pay_date` | `date` | yes | |
| `record_date` | `date` | yes | |
| `frequency` | `varchar(16)` | yes | `quarterly`, `annual` |
| `provider` | `varchar(20)` | no |  |
| `created_at` | `datetime` | no | |
| `updated_at` | `datetime` | no | |

**Constraints and indexes.**
- `uq_market_event` on `(symbol, kind, event_date)` — **unique**.
- `ix_market_events_symbol` on `symbol`.
- `idx_market_event_date_kind` on `(event_date, kind)` — the "what's coming up"
  query.

### 5.8 `chinese_stock_names`

The Chinese name registry, kept separate from `stocks.name_cn` because it is
populated by a bulk provider sync rather than by the universe seeder.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | `integer` | no | PK |
| `symbol` | `varchar(20)` | no | **Unique** — `uq_chinese_stock_names_symbol` |
| `code` | `varchar(10)` | no | The bare 6-digit code — `600519` |
| `name_cn` | `varchar(100)` | no | |
| `exchange` | `varchar(10)` | no | `SSE` or `SZSE` |
| `last_updated_by` | `varchar(50)` | yes | Which provider supplied it |
| `created_at` | `datetime` | no | |
| `updated_at` | `datetime` | no | |

**Constraints and indexes.**
- `uq_chinese_stock_names_symbol` on `symbol` — **unique**.
- `idx_chinese_stock_names_symbol` on `symbol`.
- `idx_chinese_stock_names_code` on `code` — the code lookup.

---

## 6. Domain: market intelligence

### 6.1 `market_news_items`

Raw news articles or events.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | `bigint` | no | PK |
| `source` | `varchar(50)` | no | The feed |
| `source_id` | `varchar(255)` | yes | The provider's own id |
| `title` | `text` | no | |
| `summary` | `text` | yes | |
| `url` | `text` | yes | |
| `published_at` | `datetime` | no | |
| `region` | `varchar(10)` | yes | `US`, `CN`, `HK`, `JP`, `KR`, `SG`, `TW`, `GLOBAL` |
| `language` | `varchar(5)` | no | Default `en` |
| `raw_sentiment` | `float` | yes | The provider's sentiment, if it supplies one |
| `is_processed` | `boolean` | no | Default `False` — has a signal been extracted? |
| `created_at` | `datetime` | no | |

**Constraints and indexes.**
- `uq_news_source_id` on `(source, source_id)` — **unique**. The dedup key.
- `ix_news_published_at` on `published_at` — the recency feed.
- `ix_news_is_processed` on `(is_processed, published_at)` — the work queue.

### 6.2 `market_signals`

The AI-extracted structure derived from a news item. One signal per news item.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | `bigint` | no | PK |
| `news_item_id` | `bigint` | no | Indexed. One signal per news item |
| `signal_type` | `varchar(30)` | no | `earnings`, `macro`, `geopolitical`, `sector`, `regulatory`, `corporate` |
| `sentiment` | `float` | yes | −1.0 (bearish) to +1.0 (bullish) |
| `confidence` | `float` | yes | 0.0 to 1.0 |
| `impact_horizon` | `varchar(10)` | yes | `intraday`, `short` (1–7d), `medium` (1–4w), `long` |
| `regions` | `varchar(10)[]` | yes | e.g. `['US','CN']` |
| `sectors_affected` | `varchar(50)[]` | yes | GICS sector names |
| `symbols_mentioned` | `varchar(20)[]` | yes | Directly mentioned tickers |
| `symbols_impacted` | `varchar(20)[]` | yes | Tickers the signal impacts |
| `impact_direction` | `varchar(10)[]` | yes | |
| `theme_tags` | `varchar(100)[]` | yes | The tags Pulse scores against |
| `summary_en` | `text` | yes | The English summary |
| `summary_zh` | `text` | yes | The Chinese summary |
| `processed_at` | `datetime` | no | |
| `model_used` | `varchar(50)` | yes | Which model extracted it |

**Constraints and indexes.**
- `uq_signal_news_item` on `news_item_id` — **unique**.
- `ix_market_signals_news_item_id` on `news_item_id`.
- `ix_signal_processed_at` on `processed_at` — Pulse's freshness window.

### 6.3 `sector_intelligence`

A daily sector aggregate.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | `bigint` | no | PK |
| `sector` | `varchar(50)` | no |  |
| `region` | `varchar(10)` | no | |
| `intel_date` | `date` | no |  |
| `signal_count` | `integer` | no | |
| `avg_sentiment` | `float` | yes | |
| `bullish_count` | `integer` | no | |
| `bearish_count` | `integer` | no | |
| `top_themes` | `varchar(100)[]` | yes | |
| `narrative` | `text` | yes | The generated narrative |
| `key_signal_ids` | `bigint[]` | yes |  |
| `created_at` | `datetime` | no | |
| `updated_at` | `datetime` | no | |

**Constraints and indexes.**
- `uq_sector_intel_date` on `(sector, region, intel_date)` — **unique**.
- `idx_sector_intel_date` on `intel_date`.

### 6.4 `sector_themes`

GICS sectors (`theme_type='static_gics'`) and AI-derived themes
(`'dynamic_ai'`).

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | `integer` | no | PK |
| `name` | `varchar(100)` | no | |
| `name_cn` | `varchar(100)` | yes | |
| `theme_type` | `varchar(20)` | no | `static_gics` or `dynamic_ai` |
| `description` | `text` | yes | |
| `description_cn` | `text` | yes | |
| `icon_key` | `varchar(30)` | yes | Maps to a frontend icon key |
| `stock_count` | `integer` | no | Default `0` |
| `avg_sentiment` | `float` | yes | From `sector_intelligence` |
| `top_symbols` | `varchar(20)[]` | yes | The top 5 by market cap |
| `top_themes` | `varchar(100)[]` | yes | The top theme tags |
| `region` | `varchar(10)` | no | Default `GLOBAL` |
| `is_active` | `boolean` | no | Default `True` |
| `created_at` | `datetime` | no | |
| `updated_at` | `datetime` | no | |

**Constraints and indexes.**
- `uq_sector_theme_name_type` on `(name, theme_type)` — **unique**.
- `ix_sector_theme_type` on `theme_type`.

### 6.5 `theme_stocks`

Membership for dynamic themes. Static GICS membership is derived from
`stocks.sector` at query time rather than stored.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | `integer` | no | PK |
| `theme_id` | `integer` | no | Indexed |
| `symbol` | `varchar(20)` | no | |
| `score` | `float` | yes | 0.0–1.0, from signal frequency and sentiment strength |
| `added_at` | `datetime` | no | |

**Constraints and indexes.**
- `uq_theme_stock` on `(theme_id, symbol)` — **unique**.
- `ix_theme_stocks_theme_id` on `theme_id`.
- `idx_theme_stock_symbol` on `symbol`.

### 6.6 `stock_relationships`

The peer and correlation graph.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | `bigint` | no | PK |
| `symbol_a` | `varchar(20)` | no | Indexed |
| `symbol_b` | `varchar(20)` | no | Indexed |
| `relationship_type` | `varchar(30)` | no | `peer`, `supplier`, `competitor`, … |
| `strength` | `float` | yes | |
| `correlation_30d` | `float` | yes | |
| `correlation_90d` | `float` | yes | |
| `direction` | `varchar(10)` | yes |  |
| `source` | `varchar(20)` | no |  |
| `computed_at` | `datetime` | no | |

**Constraints and indexes.**
- `uq_stock_rel` on `(symbol_a, symbol_b, relationship_type)` — **unique**.
- `ix_stock_rel_a` on `symbol_a`.
- `ix_stock_rel_b` on `symbol_b`.

---

## 7. Domain: user

### 7.1 `user_profiles`

| Column | Type | Null | Notes |
|---|---|---|---|
| `keycloak_id` | `uuid` | no | **PK** — one row per user |
| `default_exchange` | `varchar(20)` | yes | |
| `default_currency` | `varchar(5)` | yes | |
| `timezone` | `varchar(50)` | yes | IANA name |
| `locale` | `varchar(10)` | yes | `en`, `zh`, … |
| `bio` | `text` | yes | |
| `avatar` | `text` | yes | |
| `created_at` | `datetime` | no | |
| `updated_at` | `datetime` | no | |

### 7.2 `investor_profile`

The structured investing style that Pulse scoring consumes.

| Column | Type | Null | Notes |
|---|---|---|---|
| `keycloak_id` | `uuid` | no | **PK** |
| `risk_tolerance` | `varchar(20)` | yes | `low`, `medium`, `high` |
| `horizon` | `varchar(20)` | yes | `day`, `swing`, `long_term` |
| `style` | `varchar(30)` | yes | `value`, `growth`, `income`, `momentum`, `mixed` |
| `preferred_sectors` | `varchar(50)[]` | yes | Boosts matching signals by 1.15 |
| `avoided_sectors` | `varchar(50)[]` | yes | Suppresses matching signals by 0.4 |
| `constraints` | `text` | yes | |
| `goals` | `text` | yes | |
| `confidence` | `float` | yes | How well the profile is known |
| `source` | `varchar(20)` | no | How it was established |
| `updated_at` | `datetime` | no | |

### 7.3 `watchlists`

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | `integer` | no | PK |
| `keycloak_id` | `uuid` | no | Indexed |
| `symbol` | `varchar(20)` | no | |
| `sort_order` | `integer` | no | |
| `created_at` | `datetime` | no | |

**Constraints and indexes.**
- `uq_watchlist_user_symbol` on `(keycloak_id, symbol)` — **unique**.
- `ix_watchlists_keycloak_id` on `keycloak_id`.

### 7.4 `user_alerts`

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | `integer` | no | PK |
| `keycloak_id` | `uuid` | no | Indexed |
| `symbol` | `varchar(20)` | no | |
| `alert_type` | `varchar(30)` | no | `price_above`, `price_below`, `change_pct_above`, `change_pct_below` |
| `threshold` | `float` | no | The price or percentage that fires it |
| `is_active` | `boolean` | no | Default `True`. `False` once triggered |
| `triggered_at` | `datetime` | yes | |
| `created_at` | `datetime` | no | |

**Constraints and indexes.**
- `uq_user_alert_user_symbol_type` on `(keycloak_id, symbol, alert_type)` —
  **unique**. One alert of each type per symbol; a second `price_above` alert
  on the same symbol is rejected.
- `ix_user_alerts_keycloak_id` on `keycloak_id`.

### 7.5 `user_notifications`

The in-app notification log. The durable record behind the real-time delivery.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | `integer` | no | PK |
| `keycloak_id` | `uuid` | no | Indexed |
| `notification_type` | `varchar(50)` | no | `alert_triggered`, `volume_spike`, `sentiment_shift`, `news_signal`, `agent_brief`, `event_reminder` |
| `title` | `varchar(200)` | no | |
| `body` | `text` | yes | |
| `metadata` | `jsonb` | yes | The ORM attribute is `extra_data`; the column is `metadata` |
| `is_read` | `boolean` | no | Default `False` |
| `created_at` | `datetime` | no | Indexed |

**Indexes.** `ix_user_notifications_keycloak_id` on `keycloak_id`,
`ix_user_notifications_created_at` on `created_at`.

> The ORM attribute is `extra_data` because `metadata` is a reserved name in
> SQLAlchemy's declarative API. The **column** is `metadata`, so a raw SQL
> query must use `metadata`.

### 7.6 `user_memories`

Free-form key/value facts NOVA has been asked to remember.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | `integer` | no | PK |
| `keycloak_id` | `uuid` | no | Indexed |
| `memory_key` | `varchar(100)` | no | Truncated to 100 characters |
| `memory_value` | `text` | no | Truncated to 200 characters |
| `updated_at` | `datetime` | no | |

**Constraints and indexes.**
- `uq_user_memory_key` on `(keycloak_id, memory_key)` — **unique**. The write
  path is an `INSERT … ON CONFLICT DO UPDATE` against this constraint.
- `ix_user_memories_keycloak_id` on `keycloak_id`.

### 7.7 `notification_prefs`

The push fan-out toggles and quiet hours.

| Column | Type | Null | Notes |
|---|---|---|---|
| `keycloak_id` | `uuid` | no | **PK** |
| `push_alerts` | `boolean` | no | Default `True` |
| `push_volume` | `boolean` | no | Default `True` |
| `push_signals` | `boolean` | no | Default `True` |
| `push_agent` | `boolean` | no | Default `True` |
| `push_events` | `boolean` | no | Default `True` |
| `proactive_digest` | `boolean` | no | Default `False` — one daily digest instead of several pushes |
| `quiet_enabled` | `boolean` | no | Default `False` |
| `quiet_start` | `integer` | no | Hour 0–23, local. Default `22` |
| `quiet_end` | `integer` | no | Hour 0–23, local. Default `7` |
| `tz` | `varchar(64)` | no | Default `UTC` |

**Behaviour.** The `allows_push` method maps a notification type to its toggle
through `TYPE_TO_PREF`. It is **default-on**: only an explicit `False` blocks a
category. The quiet window is `[start, end)` in the user's own timezone, and
handles an overnight wrap such as 22 → 7.

In-app notifications are always written regardless of these preferences — the
toggles gate the *push* fan-out only.

### 7.8 `push_subscriptions`

The browser endpoints for Web Push.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | `integer` | no | PK |
| `keycloak_id` | `uuid` | no | Indexed |
| `endpoint` | `text` | no | **Unique** — `uq_push_subscription_endpoint` |
| `p256dh` | `text` | no | The browser's public key |
| `auth` | `text` | no | The auth secret |
| `user_agent` | `varchar(300)` | yes |  |
| `created_at` | `datetime` | no | |
| `last_used_at` | `datetime` | yes | |

**Indexes.** `ix_push_subscriptions_keycloak_id` on `keycloak_id`.

Endpoints the push service reports as gone (404 or 410) are deleted.

### 7.9 `chat_quotas`

The one-time free-trial ledger.

| Column | Type | Null | Notes |
|---|---|---|---|
| `keycloak_id` | `uuid` | no | **PK** |
| `trial_start` | `datetime` | no | Set once on the first message. **Never moves** |
| `messages_used` | `integer` | no | Increment-only. **Never resets** |
| `created_at` | `datetime` | no | |

**Constants.** `FREE_TRIAL_MESSAGE_LIMIT = 10`, `FREE_TRIAL_DAYS = 7`. The
trial ends permanently when *either* is reached. There is no reset path.

Admin and paid roles bypass this table entirely — the quota route returns an
unlimited state without reading or writing it.

### 7.10 `message_feedback`

A self-contained snapshot of each rated answer, so the eval golden set can grow
without joining live tables.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | `bigint` | no | PK |
| `keycloak_id` | `uuid` | no | Indexed |
| `conversation_id` | `uuid` | yes | |
| `rating` | `smallint` | no | `+1` (👍) or `−1` (👎) |
| `question` | `text` | yes | |
| `answer` | `text` | yes | |
| `agent` | `varchar(100)` | yes | |
| `model` | `varchar(60)` | yes | |
| `tools_used` | `varchar(50)[]` | yes | |
| `created_at` | `datetime` | no | Server default `now()` |

**Indexes.** `ix_message_feedback_keycloak_id` on `keycloak_id`,
`idx_feedback_rating` on `rating`, `idx_feedback_created` on `created_at`.

---

## 8. Domain: chat and agents

### 8.1 `conversations`

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | `uuid` | no | PK, generated by the application |
| `keycloak_id` | `uuid` | no | Indexed |
| `title` | `varchar(200)` | yes | Derived from the first user message |
| `agent` | `varchar(100)` | yes | The skill this thread runs as |
| `symbols` | `varchar(20)[]` | yes | The symbols in play |
| `rolling_summary` | `text` | yes | The folded-in older turns |
| `summary_turns` | `integer` | no | Default `0`. The message count at the last summary |
| `message_count` | `integer` | no | Default `0` |
| `created_at` | `datetime` | no | Server default `now()` |
| `updated_at` | `datetime` | no | Server default `now()`, auto-updates on write |

**Indexes.** `ix_conversations_keycloak_id` on `keycloak_id`,
`ix_conversations_user` on `(keycloak_id, updated_at)` — the history list,
newest first.

### 8.2 `messages`

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | `bigint` | no | PK |
| `conversation_id` | `uuid` | no | FK → `conversations.id`, `ON DELETE CASCADE` |
| `role` | `varchar(16)` | no | `user`, `assistant`, `tool` |
| `content` | `text` | yes | |
| `tools_used` | `varchar(50)[]` | yes | The assistant turn's tool list |
| `created_at` | `datetime` | no | Server default `now()` |

**Indexes.** `ix_messages_conv` on `(conversation_id, id)` — the ordered
conversation read.

### 8.3 `custom_agents`

A user-built agent. A row hydrates into the in-memory `Skill` dataclass and
runs through the same `run_skill` path as the native agents.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | `integer` | no | PK |
| `keycloak_id` | `uuid` | no | Indexed |
| `name` | `varchar(60)` | no | A slug, unique per owner |
| `title` | `varchar(80)` | no | |
| `category` | `varchar(40)` | no | Default `Custom` |
| `description` | `text` | yes | |
| `system_prompt` | `text` | no | The agent's instructions |
| `tools` | `varchar(50)[]` | no | Validated against the tool registry at write time |
| `model_tier` | `varchar(10)` | no | Default `auto` |
| `temperature` | `float` | no | Default `0.4` |
| `max_tokens` | `integer` | no | Default `1024` |
| `visibility` | `varchar(12)` | no | Default `private`. `public` puts it in the community catalogue |
| `clone_count` | `integer` | no | Default `0` |
| `icon` | `varchar(8)` | no | Default `🤖` |
| `created_at` | `datetime` | no | |
| `updated_at` | `datetime` | no | |

**Constraints and indexes.**
- `uq_custom_agent_owner_name` on `(keycloak_id, name)` — **unique**.
- `ix_custom_agents_keycloak_id` on `keycloak_id`.

**Write-time validation** (`api/routes/me_agents.py`): the name is slugified
and rejected if it is too short or collides with a native agent name; the
system prompt is required and capped at 4000 characters; at most 10 tools; every
tool must exist in the registry; the tier must be one of `auto`/`light`/`heavy`;
the temperature is clamped to `[0, 1]`; `max_tokens` is clamped to
`[128, 2000]`.

### 8.4 `agent_schedules`

A recurring, unattended run of an agent for one user.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | `integer` | no | PK |
| `keycloak_id` | `uuid` | no | Indexed |
| `agent_name` | `varchar(60)` | no | A native skill name or a custom-agent slug |
| `agent_title` | `varchar(80)` | no | Denormalised for the notification |
| `prompt` | `text` | no | |
| `symbols` | `varchar(20)[]` | yes | |
| `cadence` | `varchar(10)` | no | `daily` or `weekly` |
| `weekday` | `integer` | yes | 0 = Monday … 6 = Sunday. Weekly only |
| `hour` | `integer` | no | Local wall-clock hour |
| `minute` | `integer` | no | Local wall-clock minute |
| `tz` | `varchar(64)` | no | IANA timezone name |
| `is_active` | `boolean` | no | Default `True` |
| `last_run_at` | `datetime` | yes | UTC |
| `last_status` | `varchar(20)` | yes | `ok`, `empty`, `error` |
| `delivery_channel` | `varchar(64)` | no | Default `in_app`. Comma-joined |
| `webhook_url` | `varchar(500)` | yes | |
| `created_at` | `datetime` | no | |

**Indexes.** `ix_agent_schedules_keycloak_id` on `keycloak_id`.

**Time storage.** The scheduled time is stored as local wall-clock plus an IANA
timezone, not as a UTC instant. The dispatcher resolves "is it due now" in the
schedule's own timezone, which keeps "9am my time" correct across daylight
saving transitions. `last_run_at` is UTC.

### 8.5 `retrieval_chunks`

The pgvector retrieval index. Not tied to one source type.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | `bigint` | no | PK |
| `source_type` | `varchar(20)` | no | `news`, `signal`, `sector`, `filing` |
| `source_id` | `bigint` | no | The source row's id |
| `chunk_index` | `integer` | no | |
| `content` | `text` | no | The chunk text |
| `embedding` | `vector(384)` | no | **Must match `embedding_dim`** |
| `symbols` | `varchar(20)[]` | yes | Metadata filter |
| `sectors` | `varchar(50)[]` | yes | Metadata filter |
| `regions` | `varchar(10)[]` | yes | Metadata filter |
| `sentiment` | `float` | yes | |
| `published_at` | `datetime` | yes | The recency blend |
| `lang` | `varchar(5)` | yes |  |
| `model` | `varchar(100)` | no | The embedding model that produced the vector |
| `owner_id` | `uuid` | yes | `NULL` for global content |
| `source_ref` | `varchar(64)` | yes |  |
| `created_at` | `datetime` | no | |

**Constraints and indexes.**
- `uq_chunk_source_model` on `(source_type, source_id, chunk_index, model)` —
  **unique**. The model is part of the key so a re-index under a new model does
  not collide with the old vectors.
- `ix_retrieval_chunks_owner_id` on `owner_id`.
- `idx_chunks_published` on `published_at`.

**Owner scoping.** The `semantic_news_search` tool filters on
`owner_id IS NULL` — global content only. A user's private conversation chunks
can never surface in a global search.

### 8.6 `shared_analyses`

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | `integer` | no | PK |
| `slug` | `varchar(16)` | no | **Unique**, indexed |
| `title` | `varchar(200)` | no | |
| `symbol` | `varchar(20)` | yes | |
| `content` | `text` | no | Capped at 20000 characters on write |
| `created_by` | `uuid` | no | |
| `view_count` | `integer` | no | Default `0` |
| `created_at` | `datetime` | no | |

**Indexes.** `ix_shared_analyses_slug` on `slug` (**unique**),
`ix_shared_analyses_created_by` on `created_by`,
`ix_shared_analyses_created_at` on `created_at`.

The slug is a 12-character random token. The page is served as server-rendered
HTML at `/s/{slug}`.

### 8.7 `shadow_trades`

A simpler paper-trade log used by the portfolio tooling, distinct from the
simulator's order book.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | `integer` | no | PK |
| `keycloak_id` | `uuid` | no | Indexed |
| `symbol` | `varchar(20)` | no | |
| `action` | `varchar(10)` | no | `buy` or `sell` |
| `shares` | `numeric(12,4)` | no |  |
| `price` | `numeric(12,4)` | no |  |
| `note` | `text` | yes | |
| `trade_date` | `datetime` | no | |
| `created_at` | `datetime` | no | |

**Indexes.** `ix_shadow_trades_keycloak_id` on `keycloak_id`.

### 8.8 `proactive_insights_sent`

The dedup ledger that makes Pulse idempotent across collector restarts.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | `integer` | no | PK |
| `keycloak_id` | `uuid` | no | Indexed |
| `dedup_key` | `varchar(80)` | no | A stable key, e.g. `sig:123` |
| `symbol` | `varchar(20)` | yes | |
| `kind` | `varchar(20)` | no | |
| `score` | `float` | yes | The relevance score at push time |
| `sent_at` | `datetime` | no | |

**Constraints and indexes.**
- `uq_proactive_insight` on `(keycloak_id, dedup_key)` — **unique**.
- `ix_proactive_insights_sent_keycloak_id` on `keycloak_id`.
- `idx_proactive_sent_at` on `sent_at` — the daily-cap count.

The `dedup_key` is stable by design, so one signal touching several of a
user's holdings collapses into a single push.

### 8.9 `pulse_tuning`

A singleton row (`id = 1`) holding the auto-tuned thresholds.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | `integer` | no | PK, always `1` |
| `score_cutoff` | `float` | yes | The tuned relevance cutoff |
| `min_confidence` | `float` | yes | |
| `sample_size` | `integer` | yes | The votes behind the tuning |
| `approval_rate` | `float` | yes | |
| `rationale` | `varchar(300)` | yes | Why the cutoff moved |
| `updated_at` | `datetime` | yes | |

A `NULL` column means "use the configured default".

---

## 9. Domain: simulator

### 9.1 `sim_accounts`

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | `bigint` | no | PK |
| `keycloak_id` | `uuid` | no | Indexed |
| `name` | `varchar(80)` | no | |
| `currency` | `varchar(5)` | no | Must be a key in `MARKET_RULES` |
| `initial_balance` | `numeric(20,4)` | no | The starting balance |
| `cash_balance` | `numeric(20,4)` | no | The current cash |
| `is_active` | `boolean` | no | Default `True` |
| `created_at` | `datetime` | no | |
| `updated_at` | `datetime` | no | |

**Constraints and indexes.**
- `uq_sim_account_name` on `(keycloak_id, name)` — **unique**.
- `ix_sim_accounts_keycloak_id` on `keycloak_id`.

### 9.2 `sim_orders`

The order book.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | `bigint` | no | PK |
| `account_id` | `bigint` | no | Indexed |
| `keycloak_id` | `uuid` | no | Indexed |
| `symbol` | `varchar(20)` | no | |
| `side` | `varchar(4)` | no | `buy` or `sell` |
| `order_type` | `varchar(6)` | no | `market` or `limit` |
| `quantity` | `numeric(20,4)` | no | |
| `limit_price` | `numeric(20,6)` | yes | Required for a limit order |
| `tif` | `varchar(4)` | no | `day` |
| `status` | `varchar(10)` | no | `pending`, `filled`, `rejected`, `cancelled`, `expired` |
| `filled_quantity` | `numeric(20,4)` | no | |
| `avg_fill_price` | `numeric(20,6)` | yes |  |
| `reject_reason` | `varchar(140)` | yes | Why it was rejected |
| `idempotency_key` | `varchar(64)` | yes |  |
| `created_at` | `datetime` | no | |
| `updated_at` | `datetime` | no | |
| `filled_at` | `datetime` | yes | |
| `expires_at` | `datetime` | yes | End of the UTC day, for a day limit order |

**Constraints and indexes.**
- `uq_sim_order_idem` on `(account_id, idempotency_key)` — **unique**. A
  retried request with the same key returns the original order rather than
  placing a second one.
- `ix_sim_orders_account_id` on `account_id`.
- `ix_sim_orders_account_status` on `(account_id, status)` — the matcher's
  work queue.
- `ix_sim_orders_keycloak_id` on `keycloak_id`.
- `ix_sim_orders_status` on `status`.

### 9.3 `sim_positions`

The aggregate position per symbol.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | `bigint` | no | PK |
| `account_id` | `bigint` | no | Indexed |
| `symbol` | `varchar(20)` | no | |
| `quantity` | `numeric(20,4)` | no | |
| `avg_cost` | `numeric(20,6)` | no | The average execution price |
| `realized_pnl` | `numeric(20,4)` | no | |
| `updated_at` | `datetime` | no | |

**Constraints and indexes.**
- `uq_sim_position` on `(account_id, symbol)` — **unique**.
- `ix_sim_positions_account_id` on `account_id`.

The row is deleted when the position closes to zero.

### 9.4 `sim_fills`

The immutable execution ledger.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | `bigint` | no | PK |
| `order_id` | `bigint` | no | Indexed |
| `account_id` | `bigint` | no | Indexed |
| `symbol` | `varchar(20)` | no | |
| `side` | `varchar(4)` | no |  |
| `quantity` | `numeric(20,4)` | no | |
| `price` | `numeric(20,6)` | no | The execution price |
| `fee` | `numeric(20,4)` | no | |
| `cash_delta` | `numeric(20,4)` | no | The signed cash impact |
| `realized_pnl` | `numeric(20,4)` | no | |
| `created_at` | `datetime` | no | |

**Indexes.** `idx_sim_fills_account_id` on `account_id`,
`idx_sim_fills_order_id` on `order_id`,
`idx_sim_fills_account_created` on `(account_id, created_at)`.

Fills are never rewritten. The position can be recomputed from them, which is
what makes the account auditable.

### 9.5 `sim_snapshots`

The daily mark-to-market.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | `bigint` | no | PK |
| `account_id` | `bigint` | no | Indexed |
| `ts` | `datetime` | no | Midnight UTC of the snapshot day |
| `cash` | `numeric(20,4)` | no | |
| `positions_value` | `numeric(20,4)` | no | |
| `equity` | `numeric(20,4)` | no | `cash + positions_value` |

**Constraints and indexes.**
- `uq_sim_snapshot` on `(account_id, ts)` — **unique**. The write path uses
  `INSERT … ON CONFLICT DO UPDATE` against this constraint, so re-running the
  snapshot job for a day updates rather than duplicates.
- `ix_sim_snapshots_account_id` on `account_id`.
- `idx_sim_snapshots_account_ts` on `(account_id, ts)`.

---

## 10. Domain: platform

### 10.1 `provider_status`

Live quota counters and availability.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | `integer` | no | PK |
| `provider_name` | `varchar(50)` | no | **Unique** |
| `daily_limit` | `integer` | yes | `NULL` means unlimited |
| `daily_used` | `integer` | no | Default `0` |
| `minute_limit` | `integer` | yes | `NULL` means unlimited |
| `minute_used` | `integer` | no | Default `0` |
| `last_reset` | `datetime` | yes | |
| `is_available` | `boolean` | no | Default `True` |
| `priority` | `integer` | no | The fallback order |
| `updated_at` | `datetime` | no | |

The `can_make_request()` method returns `False` when the provider is
unavailable or either counter has reached its limit.

### 10.2 `provider_registry`

The descriptive catalogue of what each provider supports.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | `integer` | no | PK |
| `provider_name` | `varchar(50)` | no | **Unique**, indexed |
| `display_name` | `varchar(100)` | no | |
| `website_url` | `varchar(255)` | yes | |
| `api_endpoint` | `varchar(255)` | yes | |
| `free_daily_limit` | `integer` | yes | |
| `free_minute_limit` | `integer` | yes | |
| `free_monthly_limit` | `integer` | yes | |
| `supported_exchanges` | `varchar(255)` | yes | |
| `supported_data_types` | `varchar(255)` | yes | |
| `requires_api_key` | `boolean` | no | |
| `supports_realtime` | `boolean` | no | |
| `supports_historical` | `boolean` | no | |
| `supports_batch` | `boolean` | no | |
| `notes` | `text` | yes | |
| `is_active` | `boolean` | no | Default `True` |
| `created_at` | `datetime` | no | |
| `updated_at` | `datetime` | no | |

### 10.3 `crawl_coverage`

Which symbols were successfully collected on which date. This is what gap
detection reads.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | `integer` | no | PK |
| `symbol` | `varchar(20)` | no | Indexed |
| `coverage_date` | `date` | no | |
| `data_type` | `varchar(20)` | yes | `quote`, `historical`, `info` |
| `provider` | `varchar(50)` | yes | |
| `status` | `varchar(20)` | no | Default `success` |
| `records_fetched` | `integer` | no | Default `0` |
| `fetched_at` | `datetime` | yes | |
| `created_at` | `datetime` | no | |

**Constraints and indexes.**
- `uq_coverage_symbol_date_type` on `(symbol, coverage_date, data_type)` —
  **unique**.
- `ix_crawl_coverage_symbol` on `symbol`.
- `idx_coverage_date_status` on `(coverage_date, status)` — the coverage
  report.

### 10.4 `crawler_run_log`

Per-provider, per-run timing and throughput. One row per provider per job
invocation; `run_id` groups the rows belonging to one scheduler call.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | `integer` | no | PK |
| `run_id` | `varchar(36)` | no | The UUID grouping one invocation |
| `job_name` | `varchar(100)` | no | The scheduler job |
| `provider_name` | `varchar(50)` | no | |
| `exchange` | `varchar(20)` | yes | |
| `data_type` | `varchar(20)` | no | `quote`, `historical`, `eod_bulk`, `info`, `fundamental`, `macro` |
| `plan_date` | `date` | no | |
| `started_at` | `datetime` | no | |
| `ended_at` | `datetime` | yes | |
| `duration_seconds` | `numeric(10,2)` | yes | |
| `symbols_attempted` | `integer` | no | Default `0` |
| `symbols_succeeded` | `integer` | no | Default `0` |
| `symbols_failed` | `integer` | no | Default `0` |
| `records_fetched` | `integer` | no | Default `0` |
| `daily_quota_limit` | `integer` | yes | `NULL` means unlimited |
| `daily_quota_before` | `integer` | no | Default `0` |
| `daily_quota_after` | `integer` | no | Default `0` |
| `status` | `varchar(20)` | no | `running`, `completed`, `partial`, `failed`, `skipped` |
| `error_summary` | `text` | yes | |

**Indexes.** `idx_run_log_run_id` on `run_id`,
`idx_run_log_provider_date` on `(provider_name, plan_date)`,
`idx_run_log_job_started` on `(job_name, started_at)`.

### 10.5 `data_source`

The catalogue of external data sources.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | `bigint` | no | PK |
| `slug` | `varchar(40)` | no | **Unique**, indexed |
| `name` | `varchar(200)` | no |  |
| `description` | `text` | yes |  |
| `api_base` | `varchar(200)` | yes |  |
| `api_key_env_var` | `varchar(60)` | yes | Which environment variable holds the key |
| `requires_api_key` | `boolean` | no | |
| `rate_limit` | `varchar(60)` | yes |  |
| `status` | `varchar(20)` | no |  |
| `primary_domain` | `varchar(80)` | yes | Indexed |
| `secondary_domains` | `varchar(200)` | yes |  |
| `record_count` | `integer` | no | Default `0` |
| `curated_count` | `integer` | no | Default `0` |
| `last_updated` | `datetime` | yes | |
| `docs_url` | `varchar(200)` | yes |  |
| `portal_slug` | `varchar(80)` | yes | Indexed |
| `sort_order` | `integer` | no | Default `0` |
| `is_active` | `boolean` | no | Default `True` |
| `created_at` | `datetime` | no | |
| `updated_at` | `datetime` | no | |

**Indexes.** `ix_data_source_slug` on `slug` (**unique**),
`ix_data_source_primary_domain` on `primary_domain`,
`ix_data_source_portal_slug` on `portal_slug`,
`ix_data_source_is_active` on `is_active`.

### 10.6 The registry spine

Four tables that let the platform describe domains beyond finance.

**`domains`** — the taxonomy tree.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | `bigint` | no | PK |
| `parent_id` | `bigint` | yes | Self-FK → `domains.id` |
| `slug` | `varchar(40)` | no | Unique within the parent |
| `name` | `varchar(200)` | no |  |
| `name_cn` | `varchar(120)` | yes | |
| `path` | `varchar(255)` | no | **Unique** — `manufacturing/automotive/car-parts` |
| `depth` | `integer` | no | Default `0` — 0 is a root |
| `entity_noun` | `varchar(40)` | yes | The noun for this domain's entities |
| `entity_noun_cn` | `varchar(40)` | yes | |
| `category_slug` | `varchar(60)` | yes | |
| `description` | `text` | yes | |
| `description_cn` | `text` | yes | |
| `is_active` | `boolean` | no | Default `True` |
| `created_at` | `datetime` | no | |

The tree is an adjacency list (`parent_id`) plus a materialised `path`, so a
subtree query is a prefix match on `path` rather than a recursive traversal.

**`entities`** — the generic per-domain directory.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | `bigint` | no | PK |
| `domain_id` | `bigint` | no | Indexed |
| `slug` | `varchar(40)` | no | Unique within the domain |
| `name` | `varchar(200)` | no | Indexed |
| `identifiers` | `json` | yes | Sparse attribute map |
| `attributes` | `json` | yes | Sparse attribute map |
| `is_active` | `boolean` | no | Default `True` |
| `created_at` | `datetime` | no | |
| `updated_at` | `datetime` | no | |

**`entity_identifiers`** — the external identifiers for an entity.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | `bigint` | no | PK |
| `entity_id` | `bigint` | no | Indexed |
| `scheme` | `varchar(40)` | no | The identifier scheme |
| `value` | `varchar(200)` | no | |
| `created_at` | `datetime` | no | |

**`datasets`** — the catalogue of what each domain offers.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | `bigint` | no | PK |
| `domain_id` | `bigint` | no | Indexed |
| `slug` | `varchar(40)` | no | Unique within the domain |
| `name` | `varchar(200)` | no |  |
| `name_cn` | `varchar(160)` | yes | |
| `description` | `text` | yes | |
| `description_cn` | `text` | yes | |
| `scope` | `varchar(80)` | yes | |
| `cadence` | `varchar(40)` | yes | How often it refreshes |
| `source_table` | `varchar(80)` | yes | The backing table — drives the freshness report |
| `freshness_column` | `varchar(80)` | yes | |
| `warn_hours` | `integer` | yes | The staleness warning threshold |
| `source_feed` | `varchar(120)` | yes | |
| `row_filter` | `text` | yes | |
| `is_public` | `boolean` | no | Default `False` |
| `created_at` | `datetime` | no | |

**Indexes and constraints.**

| Table | Constraint | Columns | Unique |
|---|---|---|---|
| `domains` | `uq_domain_path` | `path` | yes |
| `domains` | `ix_domain_parent` | `parent_id` | no |
| `entities` | `uq_entity_domain_slug` | `(domain_id, slug)` | yes |
| `entities` | `ix_entity_domain` | `domain_id` | no |
| `entities` | `ix_entity_name` | `name` | no |
| `entity_identifiers` | `uq_entity_ident_scheme_value` | `(scheme, value)` | yes |
| `entity_identifiers` | `ix_entity_ident_entity` | `entity_id` | no |
| `datasets` | `uq_dataset_domain_slug` | `(domain_id, slug)` | yes |
| `datasets` | `idx_dataset_domain` | `domain_id` | no |

Finance is registered as a domain whose datasets point at the existing finance
tables — no data migration, and `stocks` stays its native spine.

### 10.7 `translations`

The translation cache.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | `bigint` | no | PK |
| `source_hash` | `varchar(32)` | no | A hash of the source text |
| `source_lang` | `varchar(5)` | no |  |
| `target_lang` | `varchar(5)` | no |  |
| `source_text` | `text` | no | |
| `translated_text` | `text` | no | |
| `engine` | `varchar(24)` | no | Which engine produced it |
| `created_at` | `datetime` | no | |

**Constraints and indexes.**
- `uq_translation_hash_lang` on `(source_hash, target_lang)` — **unique**.
- `idx_translation_hash` on `source_hash`.

---

## 11. Indexes and unique constraints

### 11.1 The unique constraints, and what each protects

| Constraint | Table | Columns | Protects |
|---|---|---|---|
| `uq_quotes_stock_timestamp` | `quotes` | `(stock_id, timestamp)` | One quote per symbol per instant |
| `uq_historical_stock_date` | `historical_prices` | `(stock_id, date)` | One bar per symbol per day |
| `uq_filing_accession` | `company_filings` | `(accession)` | The globally unique SEC accession |
| `uq_insider_txn` | `insider_transactions` | `(accession, line_index)` | One row per Form 4 transaction line |
| `uq_short_interest_symbol_date` | `short_interest` | `(symbol, settlement_date)` | One snapshot per settlement date |
| `uq_congress_trade_hash` | `congress_trades` | `(dedup_hash)` | The disclosure feed's repeated records |
| `uq_fundamental_symbol_concept_period_form` | `fundamental_data` | `(symbol, concept, period_end, form)` | One fact per concept per period per form |
| `uq_macro_series_date` | `macro_indicators` | `(series_id, indicator_date)` | One point per series per date |
| `uq_market_event` | `market_events` | `(symbol, kind, event_date)` | One event per symbol per kind per date |
| `uq_chinese_stock_names_symbol` | `chinese_stock_names` | `(symbol)` | One name per symbol |
| `uq_news_source_id` | `market_news_items` | `(source, source_id)` | The news feed's repeated articles |
| `uq_signal_news_item` | `market_signals` | `(news_item_id)` | One signal per news item |
| `uq_sector_intel_date` | `sector_intelligence` | `(sector, region, intel_date)` | One aggregate per sector per region per day |
| `uq_sector_theme_name_type` | `sector_themes` | `(name, theme_type)` | One theme per name per type |
| `uq_theme_stock` | `theme_stocks` | `(theme_id, symbol)` | One membership row |
| `uq_stock_rel` | `stock_relationships` | `(symbol_a, symbol_b, relationship_type)` | One relationship per pair per type |
| `uq_custom_agent_owner_name` | `custom_agents` | `(keycloak_id, name)` | One agent per name per owner |
| `uq_chunk_source_model` | `retrieval_chunks` | `(source_type, source_id, chunk_index, model)` | One chunk per source per index per model |
| `uq_watchlist_user_symbol` | `watchlists` | `(keycloak_id, symbol)` | One watchlist row per symbol |
| `uq_user_alert_user_symbol_type` | `user_alerts` | `(keycloak_id, symbol, alert_type)` | One alert of each type per symbol |
| `uq_user_memory_key` | `user_memories` | `(keycloak_id, memory_key)` | One memory per key |
| `uq_push_subscription_endpoint` | `push_subscriptions` | `(endpoint)` | One row per browser endpoint |
| `uq_proactive_insight` | `proactive_insights_sent` | `(keycloak_id, dedup_key)` | One push per insight |
| `uq_sim_account_name` | `sim_accounts` | `(keycloak_id, name)` | One account per name |
| `uq_sim_order_idem` | `sim_orders` | `(account_id, idempotency_key)` | Idempotent order placement |
| `uq_sim_position` | `sim_positions` | `(account_id, symbol)` | One position row per symbol |
| `uq_sim_snapshot` | `sim_snapshots` | `(account_id, ts)` | One snapshot per day |
| `uq_domain_path` | `domains` | `(path)` | A unique path in the taxonomy |
| `uq_entity_domain_slug` | `entities` | `(domain_id, slug)` | One entity per slug per domain |
| `uq_entity_ident_scheme_value` | `entity_identifiers` | `(scheme, value)` | One entity per external identifier |
| `uq_dataset_domain_slug` | `datasets` | `(domain_id, slug)` | One dataset per slug per domain |
| `uq_translation_hash_lang` | `translations` | `(source_hash, target_lang)` | One translation per source per language |

**The pattern.** Almost every unique constraint is a dedup key that makes a
collector re-run idempotent. The write path relies on the constraint rather
than on an application-level check, so a race between two runs cannot produce
a duplicate — the second insert simply conflicts.

### 11.2 The other unique constraints

| Constraint | Table | Columns |
|---|---|---|
| `ix_stocks_symbol` | `stocks` | `symbol` (unique) |
| `ix_shared_analyses_slug` | `shared_analyses` | `slug` (unique) |
| `ix_data_source_slug` | `data_source` | `slug` (unique) |
| `ix_provider_registry_provider_name` | `provider_registry` | `provider_name` (unique) |
| unnamed | `provider_status` | `provider_name` (unique) |

### 11.3 Index purposes

| Purpose | Indexes |
|---|---|
| **Latest quote per symbol** | `idx_quotes_stock_id`, `idx_quotes_timestamp` |
| **Price series** | `idx_historical_stock_date (stock_id, date)` |
| **Per-symbol lookups** | `ix_company_filings_symbol`, `ix_insider_transactions_symbol`, `ix_short_interest_symbol`, `ix_congress_trades_symbol`, `ix_market_events_symbol`, `ix_crawl_coverage_symbol`, `ix_theme_stock_symbol` |
| **Composite per-symbol** | `idx_filing_symbol_form`, `ix_insider_transactions_symbol_date`, `ix_congress_symbol_date`, `idx_market_event_date_kind` |
| **Owner scoping** | `ix_user_notifications_keycloak_id`, `ix_user_memories_keycloak_id`, `ix_watchlists_keycloak_id`, `ix_user_alerts_keycloak_id`, `ix_custom_agents_keycloak_id`, `ix_agent_schedules_keycloak_id`, `ix_shadow_trades_keycloak_id`, `ix_sim_accounts_keycloak_id`, `ix_sim_orders_keycloak_id`, `ix_proactive_insights_sent_keycloak_id`, `ix_push_subscriptions_keycloak_id`, `ix_message_feedback_keycloak_id`, `ix_retrieval_chunks_owner_id` |
| **User history lists** | `ix_conversations_user (keycloak_id, updated_at)`, `idx_sim_fills_account_created (account_id, created_at)`, `idx_sim_snapshots_account_ts (account_id, ts)` |
| **Work queues** | `ix_news_is_processed (is_processed, published_at)`, `idx_signal_processed_at`, `idx_coverage_date_status`, `idx_run_log_provider_date`, `idx_run_log_job_started`, `idx_run_log_run_id`, `idx_sim_orders_account_status` |
| **Recency feeds** | `ix_news_published_at`, `idx_chunks_published`, `idx_proactive_sent_at` |
| **Name search** | `idx_entity_name`, `ix_feedback_rating`, `idx_feedback_created`, `idx_chinese_stock_names_code` |

### 11.4 A note on index names

PostgreSQL index names are **schema-global**. Two tables cannot declare the
same index name, even in unrelated schemas. The migration therefore uses
table-qualified names where a collision is plausible — for example
`ix_insider_transactions_symbol_date` rather than `ix_insider_symbol_date`.
If you add an index, check that the name is not already taken in the database.

---

## 12. The soft-delete convention

`stocks.is_active` is the only soft-delete flag in the schema.

| Value | Meaning |
|---|---|
| `True` | The symbol is listed and actively collected. |
| `False` | The symbol is no longer collected. **Its row stays forever.** |

### 12.1 Why

Delisted companies still have history, quotes, filings, and insider
transactions that users may want to look up. Hard-deleting the row would
destroy the historical record and leave dangling references from `quotes`,
`historical_prices`, and the alternative-data tables.

### 12.2 What reads it

| Path | Filter |
|---|---|
| `GET /api/v1/stocks` | `Stock.is_active.is_(True)` |
| `GET /api/v1/showcase` | `Stock.is_active.is_(True)` |
| `GET /api/v1/status` (coverage by exchange) | `Stock.is_active == True` |
| `active_symbols()` in the collector | `Stock.is_active == True` |

The collectors only ever touch active symbols. The API's list endpoints filter
them out.

### 12.3 What writes it

Two paths, and both are deliberate:

1. **The universe seeder.** It updates the descriptive fields of an existing
   symbol but **never resurrects an inactive one** — the `is_active` flag is
   not in the list of fields it updates. Deactivating a symbol is a deliberate
   act: edit `universe.csv`, set `is_active` to `f`, and re-run the seeder.
2. **The symbol set itself.** A symbol absent from the CSV is never
   deactivated by the seeder — it is simply left alone. The CSV is a starting
   point, and the seeder only adds and updates.

### 12.4 The related soft states

Two other tables use a similar pattern for a different reason:

- `user_alerts.is_active` — `False` once the alert has fired. The row is
  kept so the user can re-arm it with `PATCH /api/v1/me/alerts/{id}/rearm`.
- `sim_accounts.is_active` — `False` when the account is deactivated. The row
  is kept so its history stays intact.

Neither is a delete. No code path in the application hard-deletes a row.

---

## 13. Schema drift detection

`backend/packages/flowdesk-core/flowdesk_core/schema_check.py`

**Purpose.** Alembic owns the schema; this is the safety net. On a shared
database, a `stamp` performed without the matching `upgrade` — or a manual
change — can leave the recorded `alembic_version` ahead of the actual DDL.
That drift is silent until a query finally hits the missing table or column.

**Public interface.**

```python
async def find_schema_drift() -> dict: ...
def has_drift(drift: dict) -> bool: ...
def format_drift(drift: dict) -> str: ...
```

The returned dict is `{"missing_tables": [...], "column_drift": {table: [cols]}}`.

**Direction.** Only model-declared tables and columns the database is
*missing* are reported — that is the failure mode that breaks reads. Extra
tables in the database are **intentionally ignored**, because a shared
database may legitimately contain tables owned by other applications.

**Running it.**

```bash
cd FlowDesktop/backend
python -m flowdesk_core.schema_check
```

```
schema OK — live DB matches all models
```

On drift:

```
SCHEMA DRIFT DETECTED (models declare these, DB lacks them):
  shadow_trades missing columns: icon
```

**Exit codes.** `0` — clean. `1` — drift detected, or the database is
unreachable.

> The module's own docstring refers to the command as
> `python -m flowdesk.schema_check`. The package was renamed to
> `flowdesk_core`, so `python -m flowdesk_core.schema_check` is the correct
> invocation.

---

## 14. Contributor workflow

### 14.1 Adding a table

1. **Write the model** in
   `backend/packages/flowdesk-core/flowdesk_core/models/`. Follow the
   conventions: an explicit `__tablename__`, a `__table_args__` block with the
   unique constraints and indexes, and `mapped_column` annotations throughout.

2. **Export it** from `flowdesk_core/models/__init__.py`. The import is what
   registers the table on `Base.metadata` — without it, `schema_check` will
   not see it and Alembic will not generate it.

3. **Generate the migration**:

   ```bash
   cd backend
   alembic revision --autogenerate -m "add_<table>"
   ```

4. **Review the generated file.** Autogenerate is a starting point, not an
   answer. Check the column types, the nullability, the server defaults, and
   the index and constraint names. Confirm the names do not collide with
   existing schema-global index names.

5. **Apply it**:

   ```bash
   alembic upgrade head
   ```

6. **Verify**:

   ```bash
   python -m flowdesk_core.schema_check
   ```

### 14.2 Never do this

```python
Base.metadata.create_all(engine)   # NO
```

It races with Alembic, produces `DuplicateTable` errors, and leaves the
recorded `alembic_version` out of sync with the actual DDL — which is exactly
the drift `schema_check` exists to catch.

`flowdesk_core.database.init_db()` runs `SELECT 1` and nothing else. That is
deliberate, and its docstring says so.

### 14.3 Before you push

```bash
cd backend
ruff check .
ruff format .
pyright
pytest tests/ -q
```

And from the repository root:

```bash
cd frontend && npm run lint && npm run build
```
