<div align="center">

# FlowDesktop

**A self-hostable AI stock-analysis desk — chat, agents, alerts and paper trading.**

[MIT licensed](LICENSE) · Python 3.12+ · React 19 · PostgreSQL 17

</div>

---

FlowDesktop is an AI analyst for your watchlist. Ask it about a ticker in plain
English (or Chinese) and it answers from real market data: quotes, price
history, insider Form 4 activity, short interest and congressional trades. It
can also run on a schedule, watch for catalysts, and let you paper trade the
whole thing.

Market data comes from the **whereq.cloud Data API**. FlowDesktop is a client
of it: every request carries your API key, and there is no bundled scraper and
no anonymous fallback. Authentication is delegated to **your own OpenID
Connect provider** — nothing about it is bundled either. So you can clone the
repo and have it building in a couple of minutes, but to actually *run* it you
need two secrets of your own: a whereq.cloud API key and your identity
provider's settings.

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

## What you need to run it

Two secrets, both yours:

| Secret | Why | Where it goes |
|---|---|---|
| **whereq.cloud API key** | Every piece of market data. The key is sent in the `X-API-Key` header; without it the app refuses to fetch anything. | `WHEREQ_API_KEY` |
| **Your OIDC provider** | Logins and roles. The shipped values are placeholders — point them at your own realm. | `KEYCLOAK_URL`, `KEYCLOAK_REALM`, `KEYCLOAK_CLIENT_ID` |

A whereq.cloud key with the `filings` scope unlocks the SEC filing endpoints.
Everything else works with a standard key.

## Quick start

### Docker Compose (recommended)

```bash
git clone https://github.com/whereq/FlowDesktop.git
cd FlowDesktop

cp docker/.env.example docker/.env
# edit docker/.env — set WHEREQ_API_KEY, POSTGRES_PASSWORD and your OIDC settings

docker compose -f docker/docker-compose.yml up -d --build
```

The API comes up on `:8000`, the web UI on `:8080`, and the database is
initialised with the `vector` and `pg_trgm` extensions it needs. The collector
then syncs the instrument universe and starts filling the database.

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

See **[docs/setup.md](docs/setup.md)** for the full guide — getting a
Data API key, identity provider setup, running the collector, BYOK mode and
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
│ universe,      │◀─▶│ 51 tables, pgvec │   │ platform or BYOK │
│ quotes, history│   └───────────────────┘   └──────────────────┘
└───────┬────────┘
        │  X-API-Key
┌───────▼─────────────────────────┐
│  whereq.cloud Data API         │
│  quotes · history · catalog ·   │
│  short interest · insider Form 4│
└─────────────────────────────────┘
```

Three processes, two of them optional to run separately:

- **`api`** — the FastAPI application. Serves the REST API, the NOVA chat
  stream, and the tool registry.
- **`collector`** — syncs the database from the whereq.cloud Data API using
  your key: the instrument universe, quotes, daily history, short interest and
  insider activity. It runs on a schedule and only pulls quotes while markets
  are open.
- **`frontend`** — the React app.

The two Python packages live in this repository under `backend/packages/`:

| Package | What it is |
|---|---|
| `flowdesk-core` | The data core: SQLAlchemy models, database engine, settings, auth, LLM gateway, and the Data API client. |
| `flowdesk-collector` | The sync layer: the scheduler, the collectors, and the payload-to-ORM mappings. |

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
│       ├── flowdesk-core/      models, database, settings, auth, Data API client
│       └── flowdesk-collector/ scheduler, collectors, payload mappings
├── frontend/                   React 19 + Vite + TypeScript
├── docker/                     Dockerfiles and Compose stack
└── docs/                       architecture and design documentation
```

## Documentation

| Document | What it covers |
|---|---|
| [docs/setup.md](docs/setup.md) | Getting it running. |
| [docs/architecture.md](docs/architecture.md) | The system, end to end, with diagrams. |
| [docs/design-high-level-design.md](docs/design-high-level-design.md) | Components, boundaries, subsystems, extension points. |
| [docs/design-low-level-design.md](docs/design-low-level-design.md) | Module-by-module implementation detail. |
| [docs/database.md](docs/database.md) | The schema, table by table. |
| [docs/data-sources.md](docs/data-sources.md) | What the Data API provides, and the two gaps it leaves. |

## Data sources

Everything comes from one place — the whereq.cloud Data API — with your key:

| Endpoint family | Used for |
|---|---|
| `/v1/catalog/*` | The instrument universe, exchange coverage, per-symbol profiles |
| `/v1/equities/*` | Quotes and daily OHLCV history |
| `/v1/alt/short-interest/*` | Short-interest snapshots |
| `/v1/alt/insider/*` | Insider Form 4 transactions |
| `/v1/edgar/filings` | SEC filing metadata (needs the `filings` scope) |

Two surfaces are **not** covered by the API and therefore stay empty until you
populate them yourself — SEC filing *narrative* (the grounding index) and
congressional trades. The tables, tools and UI panels are all still there.
See [docs/data-sources.md](docs/data-sources.md) for the details.

## Development

```bash
# Backend
cd backend
uv run python -m pytest -q --no-cov     # unit tests
uv run python evals/run_evals.py        # deterministic router evals
uv run python scripts/check_schema.py   # migrations vs models
uv run ruff check . && uv run ruff format --check .

# Frontend
cd frontend
yarn lint && yarn build
```

Four gates run in CI on every push and pull request:

| Gate | What it proves |
|---|---|
| **Backend** | The unit tests, the deterministic router evals and the linter. |
| **Schema** | The migrations produce exactly the schema the models declare — table names, column names, types and nullability. No database needed. |
| **Docker** | Both production images build, and the Compose stack is valid. |
| **Frontend** | The linter and the production bundle. |

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
