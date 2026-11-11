# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Nothing yet.

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

[Unreleased]: https://github.com/whereq/FlowDesktop/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/whereq/FlowDesktop/releases/tag/v1.0.0
