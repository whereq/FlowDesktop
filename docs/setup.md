# FlowDesktop — Setup Guide

A complete getting-started guide for running FlowDesktop on your own machine or
your own infrastructure.

FlowDesktop is self-hostable. Every piece of market data comes from the
**whereq.cloud Data API**, which requires an API key — there is no anonymous
path and no bundled scraper. A working installation needs a database, a
whereq.cloud API key, an identity provider, and one LLM credential (or none at
all, if every user brings their own).

**Contents**

1. [Prerequisites](#1-prerequisites)
2. [Install path A — Docker Compose](#2-install-path-a--docker-compose)
3. [Install path B — local backend and frontend](#3-install-path-b--local-backend-and-frontend-dev-servers)
4. [Install path C — local backend only](#4-install-path-c--local-backend-only)
5. [Configuration reference](#5-configuration-reference)
6. [Database setup](#6-database-setup)
7. [Syncing the symbol universe](#7-syncing-the-symbol-universe)
8. [Running the collector](#8-running-the-collector)
9. [Pointing at your own identity provider](#9-pointing-at-your-own-identity-provider)
10. [Choosing an LLM mode](#10-choosing-an-llm-mode-platform-vs-byok)
11. [Running the tests](#11-running-the-tests)
12. [Troubleshooting](#12-troubleshooting)

---

## 1. Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| **Python** | 3.12 or newer | The backend declares `requires-python = ">=3.12"`. |
| **Node.js** | 20 or newer | The frontend build uses Vite 8 and TypeScript 6. Node 22 is used in the production image. |
| **PostgreSQL** | 17 | With the `vector` and `pg_trgm` extensions available. |
| **A whereq.cloud API key** | Any | Required for every market-data request. See [§1.2](#12-the-whereqcloud-api-key). |
| **An OIDC provider** | Any | Must issue RS256 JWTs with a realm-roles claim. See [§9](#9-pointing-at-your-own-identity-provider). |
| **Docker** (path A only) | Any recent version | With the Compose plugin. |

### 1.1 PostgreSQL extensions

The schema needs two extensions:

| Extension | Used by | How to get it |
|---|---|---|
| `vector` (pgvector) | `retrieval_chunks.embedding` — NOVA's semantic search | A packaged PostgreSQL 17 image with pgvector, or the extension package for your platform. |
| `pg_trgm` | Trigram indexes for symbol and name search | In PostgreSQL's standard `contrib` package. |

If you use the bundled compose file, `docker/db/init-extensions.sql` creates
both automatically when the database is first initialised, and
`backend/alembic/env.py` creates them again (best-effort) before the first
migration runs.

For a self-managed PostgreSQL, install them once as a superuser:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

If the extension files are not installed on the server, PostgreSQL will refuse
the command with `could not open extension control file`. Install the
pgvector package for your distribution and restart PostgreSQL.

### 1.2 The whereq.cloud API key

FlowDesktop is a **client** of the whereq.cloud Data API at
`https://api.whereq.cloud`. Every quote, every daily bar, every short-interest
snapshot and every Form 4 transaction in the database was fetched from that API
with your key. There is no bundled scraper and no anonymous endpoint: the key
is what turns the data on, and the client refuses every request when one is
missing.

Get a key from your whereq.cloud dashboard, then put it in the environment.

For a local backend run — `backend/.env`:

```bash
WHEREQ_API_KEY=your-key-here
```

For the compose stack — `docker/.env`:

```bash
WHEREQ_API_KEY=your-key-here
```

The key is sent in the `X-API-Key` header on every request. A key may carry
scopes; the `filings` scope is required for the SEC endpoints. A rejected key
raises a clear authentication error rather than an empty result, and the API
logs a loud warning at boot when `WHEREQ_API_KEY` is missing — it never refuses
to start, so a missing key shows up as "no data", not as a crash.

Two further settings control the connection:

| Variable | Default | Purpose |
|---|---|---|
| `WHEREQ_API_URL` | `https://api.whereq.cloud` | The API base URL. Override only for a self-hosted or regional deployment. |
| `WHEREQ_API_TIMEOUT` | `30.0` | The per-request timeout, in seconds. |

Two data sets the Data API does not carry — SEC filing *narrative* and
congressional (STOCK Act) disclosures — are covered in
[§8.4](#84-the-two-data-gaps).

---

## 2. Install path A — Docker Compose

The fastest route to a running stack. Four containers: PostgreSQL, the API, the
collector, and the frontend.

### 2.1 Create the environment file

```bash
cd FlowDesktop
cp docker/.env.example docker/.env
```

Edit `docker/.env`. At minimum, change the database password and point the
identity provider settings at your own:

```bash
# ── Database ───────────────────────────────────────────────────────────────
POSTGRES_USER=flowdesktop
POSTGRES_PASSWORD=change-me
POSTGRES_DB=flowdesktop
DB_PORT=5432

# ── Ports ──────────────────────────────────────────────────────────────────
API_PORT=8000
FRONTEND_PORT=8080

# ── whereq.cloud Data API (required for market data) ──────────────────────
WHEREQ_API_KEY=your-key-here
WHEREQ_API_URL=https://api.whereq.cloud

# ── Identity provider (OIDC) ───────────────────────────────────────────────
KEYCLOAK_URL=https://auth.example.com
KEYCLOAK_REALM=flowdesktop
KEYCLOAK_CLIENT_ID=flowdesktop-spa
VITE_KEYCLOAK_URL=https://auth.example.com
VITE_KEYCLOAK_REALM=flowdesktop
VITE_KEYCLOAK_CLIENT_ID=flowdesktop-spa

# ── LLM (platform mode) — leave blank if every user brings their own key ──
OPENAI_API_KEY=
PLATFORM_LLM_PROVIDER=
```

> The `VITE_*` variables are read at **build** time and compiled into the
> JavaScript bundle. Changing them requires rebuilding the frontend image.

### 2.2 Start the stack

```bash
docker compose -f docker/docker-compose.yml up -d --build
```

The first build takes a while: it installs the Python dependencies from the
lockfile and bakes the local embedding model into the image.

### 2.3 Watch it come up

```bash
docker compose -f docker/docker-compose.yml logs -f api
docker compose -f docker/docker-compose.yml logs -f collector
```

The API container applies the schema before it starts serving:

```
python -m alembic upgrade head && uvicorn api.main:app --host 0.0.0.0 --port 8000
```

Check that it is healthy:

```bash
curl http://localhost:8000/api/v1/health
```

```json
{"status": "healthy", "timestamp": "...", "service": "flowdesk-api"}
```

Then open the frontend at `http://localhost:8080`.

### 2.4 Sync the universe

The compose stack starts the collector, which syncs the instrument universe from
the whereq.cloud catalog at 00:01 UTC. To do it immediately instead, run the
sync once:

```bash
docker compose -f docker/docker-compose.yml exec api python -c "
import asyncio
from flowdesk_core.database import AsyncSessionLocal
from flowdesk_collector.collectors.universe import sync_universe

async def main():
    async with AsyncSessionLocal() as s:
        print(await sync_universe(s))

asyncio.run(main())
"
```

The command needs `WHEREQ_API_KEY` in the environment of the container, or it
fails with an authentication error. See [§7](#7-syncing-the-symbol-universe) for
what the sync does.

### 2.5 Verify the schema

```bash
docker compose -f docker/docker-compose.yml exec api python -m flowdesk_core.schema_check
```

```
schema OK — live DB matches all models
```

Exit code `0` means clean, `1` means drift.

### 2.6 Stopping

```bash
docker compose -f docker/docker-compose.yml down
```

Add `-v` to drop the database volume as well. This destroys all collected data.

### 2.7 Notes on the compose topology

- The compose file is a **starting point, not a production topology**. Put a
  TLS-terminating reverse proxy in front of the `frontend` service so the SPA,
  the API, and the SSE stream are served from one origin.
- The `db` service publishes its port for local inspection only. Remove that
  line for a real deployment.
- The collector and the API use the same image (`docker/api/Dockerfile`); they
  differ only in their `command`.

---

## 3. Install path B — local backend and frontend dev servers

For development, with hot reload on both sides.

### 3.1 Backend

```bash
cd FlowDesktop/backend

# Create the virtual environment and install everything.
# Both packages are local path dependencies — nothing is fetched over the network.
uv venv
uv pip install -e ".[dev]"
```

If you prefer `pip`:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 3.2 Configure the environment

Create `backend/.env`:

```bash
cd FlowDesktop/backend
cp ../docker/.env.example .env
```

Edit it. The critical setting for a local run is the database URL — the
defaults point at `localhost:5432` with the credentials `flowdesktop:flowdesktop`:

```bash
DATABASE_URL=postgresql+asyncpg://flowdesktop:flowdesktop@localhost:5432/flowdesktop
DATABASE_URL_SYNC=postgresql://flowdesktop:flowdesktop@localhost:5432/flowdesktop
```

And the whereq.cloud API key, without which there is no market data at all
([§1.2](#12-the-whereqcloud-api-key)):

```bash
WHEREQ_API_KEY=your-key-here
```

The other settings the backend reads — `WHEREQ_API_URL`, `KEYCLOAK_URL`,
`KEYCLOAK_REALM`, `KEYCLOAK_CLIENT_ID`, `OPENAI_API_KEY`, and so on — are
documented in [§5](#5-configuration-reference).

> `backend/.env` is git-ignored. Never commit credentials.

### 3.3 Create the database

```bash
createdb flowdesktop
psql -d flowdesktop -c "CREATE EXTENSION IF NOT EXISTS vector;"
psql -d flowdesktop -c "CREATE EXTENSION IF NOT EXISTS pg_trgm;"
```

Or with Docker:

```bash
docker run -d --name flowdesktop-db \
  -e POSTGRES_USER=flowdesktop \
  -e POSTGRES_PASSWORD=flowdesktop \
  -e POSTGRES_DB=flowdesktop \
  -p 5432:5432 \
  postgres:17
```

### 3.4 Apply the migrations

```bash
cd FlowDesktop/backend
source .venv/bin/activate
alembic upgrade head
```

`alembic.ini` sets `script_location = alembic` and `prepend_sys_path = .`, so
run it from the `backend/` directory.

Verify:

```bash
python -m flowdesk_core.schema_check
```

### 3.5 Run the API

```bash
cd FlowDesktop/backend
source .venv/bin/activate
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

The interactive API documentation is at `http://localhost:8000/docs`.

### 3.6 Run the collector

In a second terminal:

```bash
cd FlowDesktop/backend
source .venv/bin/activate
python -m flowdesk_collector.scheduler
```

### 3.7 Run the frontend

In a third terminal:

```bash
cd FlowDesktop/frontend
cp .env.example .env
```

Edit `frontend/.env`:

```
VITE_KEYCLOAK_URL=https://auth.example.com
VITE_KEYCLOAK_REALM=flowdesktop
VITE_KEYCLOAK_CLIENT_ID=flowdesktop-spa
```

Then:

```bash
npm install
npm run dev
```

The dev server listens on port 5173 and proxies `/api` to
`http://api:8000` by default. If the API is running on the host rather than in
a container, point the proxy at it:

```bash
API_PROXY_TARGET=http://localhost:8000 npm run dev
```

Open `http://localhost:5173`.

> The API's CORS default allows `http://localhost:5173` and
> `http://localhost:3000`. If you run the dev server on a different port, add
> it to `CORS_ORIGINS` in `backend/.env`:
> `CORS_ORIGINS='["http://localhost:5173","http://localhost:3000","http://localhost:4173"]'`

### 3.8 Frontend build

```bash
cd FlowDesktop/frontend
npm run build     # tsc && vite build → frontend/dist
npm run lint      # eslint --max-warnings 0
```

---

## 4. Install path C — local backend only

For a headless deployment: the API and collector run on your server and the
frontend is served as static files by whatever you already use, or by the
bundled nginx image.

```bash
cd FlowDesktop/backend
uv venv && uv pip install -e ".[dev]"
cp ../docker/.env.example .env    # then edit it
alembic upgrade head
```

Run the API:

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

Run the collector:

```bash
python -m flowdesk_collector.scheduler
```

Build the frontend elsewhere and serve `frontend/dist` as static files,
proxying `/api` to the API. If you use the bundled nginx configuration, it
expects the API at `http://api:8000` — change `proxy_pass` to match your
topology.

If you run the API and the collector as two separate services, the collector
can run product jobs only:

```bash
python -m worker.main
```

or, equivalently:

```bash
python -m flowdesk_collector.scheduler --product-only
```

Both register the same three product jobs (scheduled agents, the simulator
order matcher, daily equity snapshots) and skip all data collection.

---

## 5. Configuration reference

Every setting is a field on `flowdesk_core.config.Settings`. Pydantic Settings
reads them from the environment and from a `.env` file in the working directory.
Names map case-insensitively: `keycloak_url` ← `KEYCLOAK_URL`.

### 5.1 Required

Strictly speaking, nothing is required to boot — the API starts without a
database connection check passing only if it can reach the database, and the
LLM can run in BYOK mode. These are the settings you will normally set:

| Variable | Setting | Default | Purpose |
|---|---|---|---|
| `DATABASE_URL` | `database_url` | `postgresql+asyncpg://flowdesktop:flowdesktop@localhost:5432/flowdesktop` | The asyncpg connection string. **Must be set for a non-default database.** |
| `DATABASE_URL_SYNC` | `database_url_sync` | `postgresql://flowdesktop:flowdesktop@localhost:5432/flowdesktop` | The synchronous connection string, used by Alembic and sync tooling. |
| `WHEREQ_API_KEY` | `whereq_api_key` | `""` | The whereq.cloud Data API key. **Required for market data.** Without it every data request fails with an authentication error and the app serves no quotes, history, insider activity or short interest. |
| `KEYCLOAK_URL` | `keycloak_url` | `https://auth.example.com` | The OIDC issuer root — the base URL, without the realm path. |
| `KEYCLOAK_REALM` | `keycloak_realm` | `flowdesktop.local` | The realm that holds your users and roles. |
| `KEYCLOAK_CLIENT_ID` | `keycloak_client_id` | `flowdesk-spa` | The public (SPA) client the frontend authenticates against. The backend validates the `azp` claim against this value. |
| `KEYCLOAK_CLIENT_SECRET` | `keycloak_client_secret` | `""` | The client secret, when your realm uses a confidential client. Leave blank for a public client with PKCE. |
| `VITE_KEYCLOAK_URL` | — | — | The same issuer root, for the **frontend build**. |
| `VITE_KEYCLOAK_REALM` | — | — | The same realm, for the frontend build. |
| `VITE_KEYCLOAK_CLIENT_ID` | — | — | The same client id, for the frontend build. |

### 5.2 Database and collection

| Variable | Default | Purpose |
|---|---|---|
| `COLLECTION_INTERVAL_MINUTES` | `5` | How often the quote collector runs. |
| `HISTORICAL_DAYS` | `365` | The history backfill window. |
| `SYNC_MAX_SYMBOLS` | `200` | Symbols synced per alternative-data run (insider, short interest). |
| `WHEREQ_API_URL` | `https://api.whereq.cloud` | The whereq.cloud Data API base URL. |
| `WHEREQ_API_TIMEOUT` | `30.0` | The Data API per-request timeout, in seconds. |
| `COLLECTOR_SOCKET_TIMEOUT` | `60` | Seconds before a blocking socket times out. Read directly from the environment, not from `Settings`. |
| `SERVICE_NAME` | a legacy collector label | The service label in log output. Set it to `flowdesktop-collector` for clarity. |
| `ENV` | `dev` | `production` hard-disables the development auth shortcuts. |

### 5.3 LLM providers

Set at least one to use platform mode. All default to empty.

| Variable | Setting | Notes |
|---|---|---|
| `OPENAI_API_KEY` | `openai_api_key` | |
| `ANTHROPIC_API_KEY` | `anthropic_api_key` | |
| `GOOGLE_AI_API_KEY` | `google_ai_api_key` | |
| `DEEPSEEK_API_KEY` | `deepseek_api_key` | |
| `QWEN_API_KEY` | `qwen_api_key` | |
| `MINIMAX_API_KEY` | `minimax_api_key` | |
| `MINIMAX_GROUP_ID` | `minimax_group_id` | Optional. |
| `PLATFORM_LLM_PROVIDER` | `platform_llm_provider` | Pin the provider (`openai`, `anthropic`, `google`, `deepseek`, `qwen`, `minimax`) to avoid auto-detection ambiguity when more than one key is set. |

### 5.4 Identity provider — administration

Only needed if you run the subscription flow. Leave the secret blank to
disable it.

| Variable | Setting | Default | Purpose |
|---|---|---|---|
| `KEYCLOAK_ADMIN_CLIENT_ID` | `keycloak_admin_client_id` | `flowdesk-backend` | A confidential client with the service account enabled and the `manage-users` realm role. |
| `KEYCLOAK_ADMIN_CLIENT_SECRET` | `keycloak_admin_client_secret` | `""` | Its client secret. |
| `ADMIN_ROLE` | `admin_role` | `fd-admin` | The realm role for admin-only surfaces. See the caveat below. |

> **Caveat.** The admin check in `api/routes/status.py` and
> `api/routes/payments.py` compares against the literal `"fd-admin"` rather
> than reading `ADMIN_ROLE`. Setting `ADMIN_ROLE` to a different value
> therefore has no effect on those two endpoints today.

### 5.5 Payments — optional

Leave blank to disable the subscription flow entirely.

| Variable | Purpose |
|---|---|
| `STRIPE_SECRET_KEY` | The Stripe secret key. |
| `STRIPE_WEBHOOK_SECRET` | The signing secret for the webhook endpoint. |

The frontend's plan definitions in `frontend/src/config/plans.ts` hold the
Stripe Product and Price ids. Set them to your own — the file ships with
placeholder values, and a null `stripePriceId` keeps the upgrade button in a
"coming soon" state.

### 5.6 Web Push — optional

| Variable | Default | Purpose |
|---|---|---|
| `VAPID_PRIVATE_KEY` | `""` | A base64-encoded PKCS8 PEM on a single line. Empty disables Web Push; notifications stay in-app and over the WebSocket. |
| `VAPID_SUBJECT` | `mailto:admin@example.com` | The contact address in the VAPID claims. |

Generate a key pair:

```bash
python -c "
from py_vapid import Vapid02
import base64
v = Vapid02()
print(base64.b64encode(v.private_pem_bytes_raw).decode())
"
```

### 5.7 Market data

Market data comes from one source: the whereq.cloud Data API. There is no
per-provider key to configure and no provider fallback chain — the bundled
scrapers are gone.

| Variable | Setting | Default | Purpose |
|---|---|---|---|
| `WHEREQ_API_KEY` | `whereq_api_key` | `""` | The Data API key, sent as `X-API-Key` on every request. Mandatory. |
| `WHEREQ_API_URL` | `whereq_api_url` | `https://api.whereq.cloud` | The API base URL. |
| `WHEREQ_API_TIMEOUT` | `whereq_api_timeout` | `30.0` | The per-request timeout, in seconds. |
| `SYNC_MAX_SYMBOLS` | `sync_max_symbols` | `200` | Symbols synced per alternative-data run. |

The earlier per-provider variables — `ALPHA_VANTAGE_API_KEY`,
`FINNHUB_API_KEY`, `TWELVE_DATA_API_KEY`, `POLYGON_API_KEY`, `TIINGO_API_KEY`,
`ALPACA_API_KEY`, `ALPACA_API_SECRET`, `FMP_API_KEY`, `FRED_API_KEY`,
`TUSHARE_TOKEN`, `JQUANTS_*`, `STOOQ_REQUEST_DELAY`, `CONGRESS_SENATE_URL`,
`CONGRESS_HOUSE_URL` and `SEC_USER_AGENT` — have been removed with the
providers they belonged to. Setting them has no effect.

### 5.8 Feature flags

| Variable | Default | Effect |
|---|---|---|
| `SIM_ENABLED` | `True` | The paper-trading simulator. When false, its routes return 404 and the matcher and snapshot jobs no-op. |
| `LAZY_MARKET_DATA_ENABLED` | `True` | On-view fetching of insider and short-interest data. |
| `FILINGS_ENABLED` | `False` | The filings grounding pipeline. **Off by default** — the Data API does not carry the filing narrative. See [§8.4](#84-the-two-data-gaps). |
| `INSIDER_ENABLED` | `True` | The insider Form 4 collector. |
| `SHORT_INTEREST_ENABLED` | `True` | The short-interest collector. |
| `CONGRESS_TRADES_ENABLED` | `True` | The congressional-disclosure surface. The table is not populated out of the box — see [§8.4](#84-the-two-data-gaps). |
| `PROACTIVE_INSIGHTS_ENABLED` | `False` | NOVA Pulse proactive insight delivery. Opt-in. |
| `PULSE_TUNE_ENABLED` | `True` | Auto-tuning the Pulse relevance cutoff from feedback. |

### 5.9 Simulator tuning

| Variable | Default |
|---|---|
| `SIM_MAX_INITIAL_BALANCE` | `10000000` |
| `SIM_DEFAULT_INITIAL_BALANCE` | `100000` |
| `SIM_COMMISSION_BPS` | `0.0` |
| `SIM_SLIPPAGE_BPS` | `0.0` |
| `SIM_QUOTE_MAX_AGE_MINUTES` | `30` |
| `SIM_MATCHER_INTERVAL_MINUTES` | `5` |

### 5.10 Database pool and logging

These are read directly from the environment rather than through `Settings`:

| Variable | Default | Purpose |
|---|---|---|
| `DB_POOL_SIZE` | `10` | The SQLAlchemy connection pool size. |
| `DB_MAX_OVERFLOW` | `20` | The pool's overflow allowance. |
| `SLOW_QUERY_MS` | `250` | The slow-query log threshold. |
| `SLOW_QUERY_LOG` | `1` | Set to `0` to disable slow-query logging. |

### 5.11 Development-only auth shortcuts

Both are **hard-gated off when `ENV=production`**, regardless of the flag.

| Variable | Effect |
|---|---|
| `DEV_BEARER` | Set to `1` to accept `Authorization: Bearer DEV:<username>` as a synthetic identity, without contacting the identity provider. |
| `DEV_AZP_OVERRIDE` | A comma-separated list of extra `azp` values to accept, for development clients such as `admin-cli`. |

### 5.12 CORS

| Variable | Default |
|---|---|
| `CORS_ORIGINS` | `["http://localhost:5173","http://localhost:3000"]` |

The value must be a JSON array.

---

## 6. Database setup

### 6.1 Create the role and database

```bash
sudo -u postgres psql <<'SQL'
CREATE ROLE flowdesktop LOGIN PASSWORD 'flowdesk';
CREATE DATABASE flowdesktop OWNER flowdesktop;
SQL
```

### 6.2 Create the extensions

```bash
psql -d flowdesktop -c "CREATE EXTENSION IF NOT EXISTS vector;"
psql -d flowdesktop -c "CREATE EXTENSION IF NOT EXISTS pg_trgm;"
```

The migrations attempt this too, but creating them yourself as a superuser
avoids a permission failure on a managed instance.

### 6.3 Apply the migrations

```bash
cd FlowDesktop/backend
alembic upgrade head
```

This applies the migration tree. `0001_initial_schema` creates all 51 tables,
78 indexes, and the unique constraints; `0002_insider_api_sync` relaxes the two
insider-transaction columns the Data API does not fill.

### 6.4 Verify

```bash
python -m flowdesk_core.schema_check
```

The output should be:

```
schema OK — live DB matches all models
```

`schema_check` compares the live database against the ORM metadata and reports
tables and columns the models declare but the database lacks. It reports drift
in one direction only — extra tables are ignored, because a shared database may
legitimately contain tables owned by other applications.

Exit code `0` means clean, `1` means drift. If it reports drift, the recorded
`alembic_version` is probably ahead of the applied DDL — run `alembic upgrade
head` again, or reconcile the schema.

---

## 7. Syncing the symbol universe

The instrument universe is **not** bundled. It comes from the whereq.cloud Data
API catalog, and the `stocks` table is a projection of that catalog.

There is no CSV to edit any more — the one that used to ship with the collector
was removed together with the bundled providers.

The sync walks the catalog **exchange by exchange**. That order matters: the
catalog's exchange list carries each exchange's market and currency, and the
per-symbol listing does not, so the symbol rows would otherwise have no market
or currency.

The fields it writes are:

```
symbol, name, name_cn, exchange, sector, industry, market_cap, market, currency, priority_tier, is_active
```

`market` and `currency` come from the exchange entry; everything else comes
from the instrument's own catalog row. Symbols are stored in the catalog's
canonical ticker format — a bare ticker for US markets, `600519.SS` for
Shanghai, `000858.SZ` for Shenzhen.

### 7.1 Sync

```bash
cd FlowDesktop/backend
python -c "
import asyncio
from flowdesk_core.database import AsyncSessionLocal
from flowdesk_collector.collectors.universe import sync_universe

async def main():
    async with AsyncSessionLocal() as s:
        print(await sync_universe(s))

asyncio.run(main())
"
```

```
{'inserted': 6107, 'updated': 0, 'deactivated': 0, 'total': 6107}
```

The command reads the Data API, so `WHEREQ_API_KEY` must be set. The
collector's `sync_universe` job does the same thing at 00:01 UTC, so you only
need to run it by hand if you want the data immediately.

### 7.2 What the sync does and does not do

- It **inserts** instruments that are not in the database.
- It **updates** the descriptive fields of existing instruments — name, Chinese
  name, exchange, sector, market, currency, market cap.
- It **soft-deletes** instruments the catalog no longer lists: they are marked
  `is_active = False` and their rows stay.
- It **never resurrects an inactive symbol** — an instrument you deactivated by
  hand stays deactivated.
- It **never hard-deletes** a row. Quotes, history and insider transactions
  still reference it, and the historical record has value.

### 7.3 The soft-delete convention

`stocks.is_active = False` means the symbol is no longer collected. The row is
never deleted: quotes, history, filings, and insider transactions all reference
it, and the historical record has value.

Every read path filters on `is_active`. To deactivate a symbol by hand, set
`is_active = false` on its `stocks` row:

```sql
UPDATE stocks SET is_active = false WHERE symbol = 'AAPL';
```

The sync updates the descriptive fields of an existing symbol but never
touches `is_active`, so a symbol you deactivate by hand stays deactivated —
deactivation is a deliberate decision, not a side effect of the next run.

---

## 8. Running the collector

```bash
cd FlowDesktop/backend
python -m flowdesk_collector.scheduler
```

### 8.1 The job catalogue

All schedules are UTC.

| Job | Schedule | What it does |
|---|---|---|
| `sync_universe` | 00:01 daily | Syncs the instrument universe from the Data API catalog, and seeds the source-status table. |
| `collect_quotes` | Every 5 minutes | Fetches the latest quote for every active symbol. Skipped entirely when all markets are closed. |
| `collect_history` | Every 4 hours | Backfills daily OHLCV for symbols whose data is older than 7 days. Capped at 200 symbols per run. |
| `collect_insider` | 02:30 daily | Fetches recent Form 4 insider transactions. |
| `collect_short_interest` | 03:00 daily | Fetches short-interest snapshots. |

Product jobs, registered by the collector in all-in-one mode and by
`worker.main` in split mode:

| Job | Schedule | What it does |
|---|---|---|
| `run_due_agent_schedules` | Every 5 minutes | Runs due user agent schedules and delivers the brief as a notification. |
| `run_sim_order_matcher` | Every 5 minutes | Fills resting simulator orders that crossed; expires day orders. |
| `run_sim_snapshots` | 22:00 daily | Marks every active simulator account to market. |

### 8.2 Running a single collection by hand

```bash
cd FlowDesktop/backend
python -c "
import asyncio
from flowdesk_core.database import AsyncSessionLocal
from flowdesk_collector.collectors.quotes import collect_quotes

async def main():
    async with AsyncSessionLocal() as s:
        print(await collect_quotes(s, symbols=['AAPL', 'MSFT']))

asyncio.run(main())
"
```

### 8.3 Collection etiquette

Every collection job talks to one metered service, the whereq.cloud Data API,
so the pacing lives in the client rather than in each collector:

- Quotes are fetched in batches of 50 — the API's per-request cap — one
  request per batch.
- The client retries a transient failure (a 5xx, a 429 or a network error) up
  to three attempts, and honours the `Retry-After` header on a 429.
- A failed batch is logged and the remaining batches continue; the symbols in
  it are counted as failed.

If you add a collector against the same API, keep the batching and let the
client handle the retries.

### 8.4 The two data gaps

Two data sets that older FlowDesktop releases collected are **not** available
through the Data API. Both are stated here plainly, because the tables and the
UI panels for them still exist and will simply be empty.

**SEC filing narrative.** The Data API exposes SEC filing *metadata* — form,
filing date, accession, document URL — and it addresses filings by **CIK**, not
by ticker. It does not expose a ticker→CIK mapping, and it does not return the
10-K/10-Q document text that FlowDesktop's filing-grounding index embeds.
Therefore FlowDesktop **does not populate `company_filings` out of the box**.
The table, the `search_filings` tool, the embedding chunker and the UI panel
are all still there — **populate the table yourself** (or point the collector
at your own source) and the feature works. `FILINGS_ENABLED` defaults to
`False` for that reason.

**Congressional trades.** The Data API does not expose congressional (STOCK
Act) disclosures at all. The `congress_trades` table, the `get_congress_trades`
tool and the UI panel remain; the table is simply not populated. Populate it
yourself to turn the panel on.

The `/filings` route in `api/routes/market_data.py` still exists and reads the
`company_filings` table — it serves whatever is in there.

`docs/data-sources.md` covers the same two gaps from the API's side.

---

## 9. Pointing at your own identity provider

FlowDesktop expects a Keycloak-style OIDC provider. The requirement is
generic; any provider that satisfies it works.

**The identity provider is yours.** FlowDesktop ships no provider and no
accounts: the shipped values (`https://auth.example.com`, realm
`flowdesktop`, client `flowdesk-spa`) are **placeholders**, and they are
recognised as such. While they are still in place, every authenticated route
answers **503** with a clear "Authentication is not configured" message instead
of an opaque error, and the API logs a warning at boot. Replace all three
values — `KEYCLOAK_URL`, `KEYCLOAK_REALM` and `KEYCLOAK_CLIENT_ID` — with your
own before serving traffic. The API never refuses to boot on this; it warns,
and the 503s tell you what is wrong.

### 9.1 What the backend requires

1. **A JWKS endpoint** at
   `{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/certs`
   returning the realm's public signing keys.
2. **RS256-signed JWTs** with:
   - `iss` — exactly `{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}`.
   - `exp` — a future expiry.
   - `sub` — a stable UUID for the user. This is the owner key on every
     user-scoped table.
   - `azp` — the client id the token was issued for. The backend rejects a
     token whose `azp` is not `KEYCLOAK_CLIENT_ID`, so a token minted for
     another client in the same realm is refused.
   - `realm_access.roles` — an array of role names. The tier model reads from
     here.
   - Optional display claims: `preferred_username`, `email`, `given_name`,
     `family_name`, `avatar`.
3. **A token endpoint** at
   `{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/token`
   accepting the `client_credentials` grant — only needed for the optional
   subscription flow.
4. **An admin REST API** at `{KEYCLOAK_URL}/admin/realms/{KEYCLOAK_REALM}` —
   also only needed for the optional subscription flow.

Audience verification is **disabled** in the backend, because public-client
access tokens do not always carry the client id in `aud`. The `azp` claim is
used instead. If you want strict audience checking, add an audience mapper in
the identity provider and re-enable it in `flowdesk_core/auth.py`.

### 9.2 What the frontend requires

The frontend uses the `keycloak-js` adapter, which expects the standard
endpoints under `{issuer}/realms/{realm}/protocol/openid-connect/`. It needs a
**public (SPA) client** with the standard authorization-code flow and CORS
configured for your frontend origin.

### 9.3 The role model

Create these realm roles. Only `fd-admin` is needed to start; the rest control
the free trial and the paid tiers.

| Role | Meaning |
|---|---|
| `fd-admin` | Admin bypass — unlimited chat, access to the admin dashboard and the system-status surfaces. |
| `fd-tier-unlimited` | Unlimited paid tier. |
| `fd-tier-2` | Pro tier. |
| `fd-tier-1` | Basic tier. |
| `fd-tier-byok` | BYOK-only tier: the user must supply their own LLM key and gets no platform AI. |
| *(no role)* | Free trial: 10 messages or 7 days, whichever comes first, with no reset. |

`PAID_ROLES` is the set the payment webhook is permitted to assign.

### 9.4 Configuring it

Backend (`backend/.env`) — the three values below are the shipped placeholders,
so replace them with your own provider's issuer, realm and client id:

```bash
KEYCLOAK_URL=https://auth.example.com
KEYCLOAK_REALM=flowdesktop
KEYCLOAK_CLIENT_ID=flowdesktop-spa
```

Frontend (`frontend/.env`, or the compose build args):

```
VITE_KEYCLOAK_URL=https://auth.example.com
VITE_KEYCLOAK_REALM=flowdesktop
VITE_KEYCLOAK_CLIENT_ID=flowdesktop-spa
```

### 9.5 The optional subscription flow

To let users buy a tier through a payment provider:

1. Create a **confidential** client with the service account enabled, and grant
   its service account the `manage-users` realm role.
2. Set `KEYCLOAK_ADMIN_CLIENT_ID` and `KEYCLOAK_ADMIN_CLIENT_SECRET`.
3. Create a Product and a recurring Price for each tier in your payment
   provider's dashboard.
4. Put the Product and Price ids into `frontend/src/config/plans.ts`.
5. Point the payment provider's webhook at `POST /api/v1/payments/webhook` and
   set `STRIPE_WEBHOOK_SECRET` to the endpoint's signing secret.
6. Check the wiring with `GET /api/v1/payments/health` (admin only).

The webhook assigns the role named in the session metadata. The assignable set
is pinned to `PAID_ROLES`, so a tampered metadata value cannot grant an
arbitrary role.

---

## 10. Choosing an LLM mode — platform vs BYOK

### 10.1 Platform mode

The server holds the provider key. Users do not need one.

```bash
# backend/.env
OPENAI_API_KEY=sk-...
# Optional, to avoid ambiguity when several keys are present:
PLATFORM_LLM_PROVIDER=openai
```

The backend picks the first configured provider in a fixed order (`openai`,
`anthropic`, `google`, `deepseek`, `qwen`, `minimax`) unless you pin one.

Platform mode is the only mode in which:
- The chat quota is enforced (10 messages or 7 days for a free user).
- The model tier is chosen automatically — a light model for lookups, a heavy
  model for analytical questions.
- The scheduled agents and the AI-insights endpoints work.

### 10.2 BYOK mode

Each user supplies their own key. The server holds no key and incurs no cost.

The frontend stores the key locally and sends it in the `X-LLM-Api-Key` header
on every request. Platform mode ignores that header; BYOK mode requires it.

`POST /api/v1/chat/validate-key` checks a key with a one-token completion
before the user relies on it. It returns `valid: true` when the key
authenticates (including when it is merely rate-limited), `valid: false` when
the provider rejects it, and `valid: null` when the network failed — a
connection error never marks a key invalid.

The `fd-tier-byok` role gets no platform AI at all: a platform-mode request
from that role returns 403.

### 10.3 Embeddings

Semantic search uses the **local** ONNX embedding model by default
(`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, 384
dimensions). It needs no API key and no quota. The model files are baked into
the API image, so there is no runtime download.

If you change `EMBEDDING_MODEL`, `EMBEDDING_DIM` must match the
`vector(N)` column width on `retrieval_chunks`, and the index must be rebuilt
under the new model id. A model name containing `/` routes to the local path;
a flat name routes to an API provider and requires that provider's key.

---

## 11. Running the tests

### 11.1 Backend

```bash
cd FlowDesktop/backend
source .venv/bin/activate
pytest tests/ -q
```

The suite is fast and dependency-light — 162 tests over pure logic: token
budgeting, notification gating, agent routing, validation guardrails, the
simulator matcher, valuation, ordering, and the backtest engine. It does not
need a database or a network.

With coverage:

```bash
pytest --cov=flowdesk --cov=api --cov-report=html
```

The HTML report is written to `backend/htmlcov/`.

Lint and type-check:

```bash
ruff check .
ruff format .
pyright
```

### 11.2 The NOVA eval suite

The router evals are deterministic and need no database or LLM:

```bash
cd FlowDesktop/backend
python evals/run_evals.py
```

They assert that `classify_skill` maps each golden-set question to the expected
agent. The live skill cases call the LLM and need both a database and a
provider key:

```bash
python evals/run_evals.py --live
```

The golden set lives in `backend/evals/golden_set.json`.
`backend/evals/ingest_feedback.py` grows it from real 👍/👎 feedback collected
in `message_feedback`.

### 11.3 Frontend

```bash
cd FlowDesktop/frontend
npm run lint
npm run build
```

---

## 12. Troubleshooting

### The API will not start

**`ConnectionRefusedError` on port 5432.** The database is not reachable.
Check that PostgreSQL is running and that `DATABASE_URL` matches. Inside the
compose stack the hostname is `db`, not `localhost`:

```bash
DATABASE_URL=postgresql+asyncpg://flowdesktop:flowdesktop@db:5432/flowdesktop
```

**`password authentication failed for user`.** The credentials in
`DATABASE_URL` do not match the role. In the compose stack they come from
`POSTGRES_USER` and `POSTGRES_PASSWORD` in `docker/.env`.

**`could not open extension control file` for `vector`.** The pgvector
extension files are not installed on the server. Install the package for your
PostgreSQL version and restart, or use an image that ships pgvector.

**`relation "stocks" does not exist`.** The migrations have not been applied:

```bash
cd FlowDesktop && alembic upgrade head
```

Run it from `backend/` — `alembic.ini` sets `script_location = alembic`
relative to the working directory.

### Schema drift

```
SCHEMA DRIFT DETECTED (models declare these, DB lacks them):
  shadow_trades missing columns: ...
```

The recorded `alembic_version` is ahead of the applied DDL. Run
`alembic upgrade head` again, then re-check:

```bash
python -m flowdesk_core.schema_check
```

### Authentication

**401 on every request.** The token is missing, expired, or invalid. Check the
`Authorization: Bearer` header and the token's `exp`.

**401 "Invalid token" on a token you believe is valid.** The `azp` claim does
not match `KEYCLOAK_CLIENT_ID`. The token was issued for a different client in
the same realm — for example a command-line client. In development, set
`DEV_AZP_OVERRIDE` to the extra client id. In production, issue the token for
the SPA client.

**503 "Authentication is not configured".** `KEYCLOAK_URL`, `KEYCLOAK_REALM` or
`KEYCLOAK_CLIENT_ID` still carries the shipped placeholder
(`https://auth.example.com`). Point all three at your own provider — see
[§9](#9-pointing-at-your-own-identity-provider).

**503 "Authentication service temporarily unavailable".** The identity
provider is unreachable and no JWKS is cached. The backend caches keys for an
hour and serves stale ones when a refresh fails, so this only happens on a cold
start with the provider down.

**The frontend is stuck on the login screen.** `VITE_KEYCLOAK_URL`,
`VITE_KEYCLOAK_REALM`, and `VITE_KEYCLOAK_CLIENT_ID` are compiled into the
bundle at build time. Changing them requires rebuilding the frontend.

### Chat

**503 "No platform LLM provider configured."** No provider key is set. Either
set one, or have the user switch to BYOK mode in Settings.

**429 "Your 7-day free trial has expired."** The free trial ended —
permanently. The quota has no reset by design.

**403 "Your BYOK plan does not include FlowDesk AI."** (the message text the
backend sends today) The user has the
`fd-tier-byok` role and is trying platform mode. They must supply their own
key.

**"Semantic search unavailable (embeddings unconfigured)."** The embedding
model needs a key that is not set. With the default local model this should
not happen — if it does, check that `fastembed` is installed and that
`FASTEMBED_CACHE_PATH` points at the baked model directory.

**The chat streams the first sentence, then stops and shows a spinner.** The
model began a tool call. The frontend clears the pre-tool text and shows a
progress indicator; the answer resumes when the tools return.

**The chat works locally but the answer is cut off in production.** A
buffering reverse proxy is holding the SSE frames. Set `proxy_buffering off`
and a long `proxy_read_timeout` on the `/api` location.

### The collector and market data

**"All markets closed — skipping quote collection".** Working as intended. The
quote job checks the market-hours table and skips when every exchange is
closed.

**Every request fails with "No whereq.cloud API key configured".**
`WHEREQ_API_KEY` is not set in the environment the process reads. Put it in
`backend/.env` (local) or `docker/.env` (compose) and restart the API and the
collector. See [§1.2](#12-the-whereqcloud-api-key).

**"whereq.cloud rejected the API key (401)".** The key is wrong, expired, or
lacks the scope the endpoint needs. The `filings` scope is required for the SEC
endpoints.

**"whereq.cloud rate limit reached".** The API is throttling this account. The
client already retries a 429 three times and honours `Retry-After`; if it still
fails, raise `COLLECTION_INTERVAL_MINUTES` and lower `SYNC_MAX_SYMBOLS`.

**No quotes are collected.** Check that the symbol is in the `stocks` table
with `is_active = True`, and that the collector has been running long enough
for a cycle. Note that the market-hours check is a weekday-and-UTC-hour test,
not a holiday calendar — it does not know about public holidays.

**The filings or congressional panels are always empty.** That is expected: the
Data API does not carry filing narratives or congressional disclosures. See
[§8.4](#84-the-two-data-gaps).

**The collector logs "Job ... failed" repeatedly.** The traceback in the log
names the failing collector. Most common causes are a network failure to the
Data API, a missing API key, or a schema mismatch.

### The simulator

**"symbol trades in EUR; not tradable in a USD account".** The simulator does
not convert currencies. A simulator account's currency must match the
symbol's currency.

**"quantity must be a multiple of 100 (board lot)".** The account currency is
`CNY`, `JPY`, `SGD`, or `TWD`, which use board lots. Use a lot-sized
quantity, or use a `USD` account.

**"no recent price available for this symbol".** There is no fresh quote. The
collector may not have run, the market may be closed, or the quote may be
older than `SIM_QUOTE_MAX_AGE_MINUTES`.

**Orders never fill.** The matcher runs every
`SIM_MATCHER_INTERVAL_MINUTES` and only fills when the market is open, the
quote is fresh, and a limit order has crossed. Check the collector's log for
`Sim matcher: filled=... expired=... rejected=...`.

### The frontend

**`npm run build` fails with a TypeScript error.** Run `npm run lint` for the
detail. The build runs `tsc && vite build`, so type errors fail the build
before Vite runs.

**API calls return 404 in development.** The dev server proxies `/api` to
`http://api:8000`, the compose service name. Running the API on the host
instead requires `API_PROXY_TARGET=http://localhost:8000 npm run dev`.

**A CORS error in the browser console.** The frontend's origin is not in
`CORS_ORIGINS`. The value must be a JSON array.

**The build succeeds but the site shows the previous version.** The HTML entry
point must revalidate. The bundled nginx config sets
`Cache-Control: no-cache, must-revalidate` on `index.html`; hashed assets
under `/assets` are immutable for a year.

### Docker

**`docker compose up` fails with "could not find env file .env".** Copy the
template: `cp docker/.env.example docker/.env`.

**The frontend shows the API's errors.** Check that the `api` service name
resolves — the nginx configuration proxies to `http://api:8000` by name.

**The build fails on a stale lockfile.** The API image installs from
`uv.lock` with `uv export --locked`, which fails loudly when `pyproject.toml`
and `uv.lock` have drifted. Re-sync the lockfile.

---

## Where to go next

| Document | Contents |
|---|---|
| [architecture.md](architecture.md) | The running shape: processes, schema, external sources, request flows, trust boundaries, design decisions. |
| [design-high-level-design.md](design-high-level-design.md) | Component boundaries, the data model, subsystem designs, deployment topologies, extension points. |
| [design-low-level-design.md](design-low-level-design.md) | File-by-file implementation detail with signatures and failure behaviour. |
| [database.md](database.md) | The table catalogue with column-level detail, indexes, constraints, and the migration workflow. |
