# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Nothing yet.

## [1.0.2] — 2026-11-11

Fixes the production image build, and adds the gates that would have caught it.

### Fixed

- **The API image built without the embedding model and failed.** The
  Dockerfile baked the local ONNX embedding model into the image, but
  `fastembed` is an optional extra that the locked runtime install does not
  include — so `docker build` died with `ModuleNotFoundError: No module named
  'fastembed'`. The backend project now declares an `embeddings` extra and
  the image installs it explicitly.
- The runtime image now also installs `libgomp1`, which `onnxruntime` needs.
- Baking the model into the image no longer fails the build when the model
  hub is unreachable. The embedding model is loaded lazily, so a build behind
  a firewall still produces a working image; semantic search downloads the
  model on first use instead.

### Added

- `backend/scripts/check_schema.py` — a static schema check that compares the
  migrations against the models (table names, column names, types and
  nullability) without needing a database or the pgvector extension.
- Two new CI gates: **Schema** runs that check, and **Docker** builds both
  production images and validates the Compose stack. The image build is its
  own gate because a dependency that is only an optional extra breaks the
  build in a way no unit test would catch.

## [1.0.1] — 2026-11-11

FlowDesktop becomes a client of the whereq.cloud Data API.

### Changed

- **Market data now comes from the whereq.cloud Data API**, called with your own
  API key in the `X-API-Key` header. The bundled scrapers — Yahoo Finance,
  SEC EDGAR, AKShare, Stooq, FMP — have been removed, and there is no anonymous
  fallback: without a key the app fetches nothing.
- **The instrument universe is synced from the Data API catalog** instead of a
  CSV bundled in the repository. Instruments the catalog stops listing are
  soft-deleted, never removed.
- **Authentication is delegated to your own OpenID Connect provider.** The
  shipped values are placeholders; until you replace them, every authenticated
  route answers `503` with a clear "Authentication is not configured" message.
- The per-provider key settings (`ALPHA_VANTAGE_API_KEY`, `FINNHUB_API_KEY`,
  `POLYGON_API_KEY`, `TIINGO_API_KEY`, `FMP_API_KEY`, `TUSHARE_TOKEN`, …) are
  gone, along with `SEC_USER_AGENT`.
- New settings: `WHEREQ_API_KEY`, `WHEREQ_API_URL`, `WHEREQ_API_TIMEOUT`,
  `SYNC_MAX_SYMBOLS`, `KEYCLOAK_CLIENT_SECRET`.

### Added

- `WhereqCloudClient` — an async client for the Data API, with retries on
  5xx/429, `Retry-After` handling and a hard refusal to make a request without
  a key.
- Pure payload → ORM mapping functions, unit tested against the real column
  names.
- `docs/data-sources.md` — what the API provides, and the two gaps it leaves.

### Fixed

- The `X-API-Key` header is attached per request, so the key is sent even when
  the HTTP client was constructed elsewhere.

### Known limitations

- **SEC filing narrative is not populated.** The Data API exposes filing
  metadata by CIK, not the 10-K/10-Q text the grounding index embeds, and it
  does not map a ticker to a CIK. The table, the chunker, the search tool and
  the UI panel are all still there — populate `company_filings` yourself.
- **Congressional trades are not populated.** The Data API does not expose
  STOCK Act disclosures. The table, the tool and the panel remain.

## [1.0.0] — 2026-11-10

The first public release.

### Added

- **NOVA**, the AI analyst: 34 LLM-callable tools across market data, filings,
  insider activity, short interest, congressional trades, watchlist, portfolio,
  news, web search and the simulator.
- Five specialist skills — `research_analyst`, `stock_comparator`,
  `portfolio_doctor`, `strategy_architect`, `catalyst_tracker` — each with a
  curated tool subset, its own system prompt and a model tier.
- **Proactive insights** ("NOVA Pulse"): deterministic relevance scoring of
  market signals against each user's investor profile, with feedback-driven
  cutoff tuning.
- **Agent schedules**: run an agent on a cadence in your own timezone and
  receive the brief by Web Push.
- **Paper-trading simulator**: market and limit orders, board lots,
  per-market settlement rules, stale-quote guards, daily equity snapshots and
  account valuation.
- **Watchlist, alerts and a quiet-hours window** so notifications do not
  arrive at 3am.
- **Collector**: quotes and daily history from Yahoo Finance, 10-K/10-Q filings
  and insider Form 4 from SEC EDGAR, short interest from Yahoo, and a bundled
  symbol universe — all without an API key.
- **BYOK mode**: every user can bring their own LLM key; the backend falls
  back to platform keys when they do not.
- **Semantic retrieval** over SEC filings using pgvector and a local multilingual
  embedding model.
- **Bilingual interface**: English and Simplified Chinese.
- A complete **database schema** (51 tables) with a single Alembic migration
  and a schema drift check.
- **Docker Compose** stack for the API, the collector, the frontend and
  PostgreSQL.

[Unreleased]: https://github.com/whereq/FlowDesktop/compare/v1.0.2...HEAD
[1.0.2]: https://github.com/whereq/FlowDesktop/compare/v1.0.1...v1.0.2
[1.0.1]: https://github.com/whereq/FlowDesktop/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/whereq/FlowDesktop/releases/tag/v1.0.0
