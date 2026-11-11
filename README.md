<div align="center">

# FlowDesktop

**A self-hostable AI stock-analysis desk — chat, agents, alerts and paper trading.**

[MIT licensed](LICENSE) · Python 3.12+ · React 19 · PostgreSQL 17

</div>

---

FlowDesktop is an AI analyst for your watchlist. Ask it about a ticker in plain
English (or Chinese) and it answers from real market data: quotes, price
history, SEC filings, insider Form 4 activity, short interest and congressional
trades. It can also run on a schedule, watch for catalysts, and let you paper
trade the whole thing.

The interesting part is that **it needs no API keys to work**. The bundled data
providers — Yahoo Finance, SEC EDGAR, AKShare — are free and keyless, so you can
clone it, point it at a database, and have live data in a couple of minutes.

## What you get

| | |
|---|---|
| **NOVA** | The AI analyst. 34 tools it can call, 5 specialist skills it can switch into. |
| **Agent schedules** | Ask it to brief you every morning at 08:00 in your own timezone. Delivered by Web Push. |
| **Proactive insights** | It watches for catalysts on your holdings and pushes only the ones that matter to *you*. |
| **Paper trading** | A full simulator — limit and market orders, board lots, per-market settlement rules, equity curves, no real money. |
| **Watchlist & alerts** | Price and event alerts, with a quiet-hours window so it does not wake you at 3am. |
| **Bilingual** | English and Simplified Chinese throughout, including the answers. |
| **Bring your own key** | Point it at any LLM provider, or let each user bring their own. |

## Quick start

### Docker Compose (recommended)

```bash
git clone https://github.com/whereq/FlowDesktop.git
cd FlowDesktop

cp docker/.env.example docker/.env
# edit docker/.env — at minimum set POSTGRES_PASSWORD and your OIDC settings

docker compose -f docker/docker-compose.yml up -d --build
```

The API comes up on `:8000`, the web UI on `:8080`, and the database is
initialised with the `vector` and `pg_trgm` extensions it needs.

### Local development

```bash
# Backend
cd backend
uv venv && uv sync --extra dev
createdb flowdesktop
uv run python -m alembic upgrade head
uv run uvicorn api.main:app --reload

# Frontend (in another shell)
cd frontend
yarn install
yarn dev
```

See **[docs/setup.md](docs/setup.md)** for the full guide — identity provider
setup, seeding the symbol universe, running the collector, BYOK mode and
troubleshooting.

## Architecture at a glance

```
                        ┌──────────────┐
    browser  ──────────▶│   frontend   │  React 19 + Vite (nginx in production)
                        └──────┬───────┘
                               │ /api/v1
                        ┌──────▼───────┐
                        │     api      │  FastAPI · NOVA chat · 34 tools
                        └──────┬───────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        │                      │                      │
┌───────▼────────┐   ┌─────────▼─────────┐   ┌────────▼─────────┐
│   collector    │   │    PostgreSQL 17  │   │   LLM gateway    │
│ quotes/history │◀─▶│ 51 tables, pgvec │   │ platform or BYOK │
│ SEC/insider/SI │   └───────────────────┘   └──────────────────┘
└────────────────┘
```

Three processes, two of them optional to run separately:

- **`api`** — the FastAPI application. Serves the REST API, the NOVA chat
  stream, and the tool registry.
- **`collector`** — fills the database. Quotes and history from Yahoo Finance,
  filings and insider activity from SEC EDGAR, short interest from Yahoo. Runs
  on a schedule and only collects while markets are open.
- **`frontend`** — the React app.

The two Python packages live in this repository under `backend/packages/`:

| Package | What it is |
|---|---|
| `flowdesk-core` | The data core: SQLAlchemy models, database engine, settings, auth, LLM gateway. |
| `flowdesk-collector` | The data layer: providers, market hours, the scheduler and the collectors. |

## Repository layout

```
FlowDesktop/
├── backend/
│   ├── api/                    FastAPI routes, services, schemas
│   ├── worker/                 product-job worker entrypoint
│   ├── flowdesk/               tier entitlements
│   ├── evals/                  deterministic router eval suite
│   ├── tests/                  unit tests
│   ├── alembic/                schema migrations
│   └── packages/
│       ├── flowdesk-core/      models, database, settings, auth
│       └── flowdesk-collector/ providers, scheduler, collectors
├── frontend/                   React 19 + Vite + TypeScript
├── docker/                     Dockerfiles and Compose stack
└── docs/                       architecture and design documentation
```

## Documentation

| Document | What it covers |
|---|---|
| [docs/architecture.md](docs/architecture.md) | The system, end to end, with diagrams. |
| [docs/design-high-level-design.md](docs/design-high-level-design.md) | Components, boundaries, subsystems, extension points. |
| [docs/design-low-level-design.md](docs/design-low-level-design.md) | Module-by-module implementation detail. |
| [docs/setup.md](docs/setup.md) | Getting it running. |
| [docs/database.md](docs/database.md) | The schema, table by table. |

## Data sources

Everything bundled works without an API key:

| Source | Used for | Key required |
|---|---|---|
| Yahoo Finance | Quotes, daily history, short interest | No |
| SEC EDGAR | 10-K / 10-Q filings, insider Form 4 | No |
| AKShare | Mainland China listings (SSE, SZSE) | No |
| Stooq | Historical prices (backup) | No |

Optional key-based providers (Alpha Vantage, Finnhub, Polygon, Tiingo, FMP,
FRED, TuShare) are supported as extension points — see
[docs/design-high-level-design.md](docs/design-high-level-design.md).

## Development

```bash
# Backend
cd backend
uv run python -m pytest -q --no-cov     # unit tests
uv run python evals/run_evals.py        # deterministic router evals
uv run ruff check . && uv run ruff format --check .

# Frontend
cd frontend
yarn lint && yarn build
```

Both suites run in CI on every push and pull request.

## Contributing

Pull requests are welcome. Please read
[CONTRIBUTING.md](CONTRIBUTING.md) first, and note that
[SECURITY.md](SECURITY.md) explains how to report a vulnerability privately
rather than in a public issue.

## License

MIT — see [LICENSE](LICENSE). Third-party notices are in [NOTICE](NOTICE).

## A note on the name

"NOVA" is the AI analyst inside FlowDesktop. It stands for *Networked
Observational Value Analyst*.

---

**Not financial advice.** FlowDesktop produces research and analysis, never
directives to buy, sell, hold or allocate. The simulator is paper trading —
no real money is involved.
