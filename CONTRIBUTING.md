# Contributing to FlowDesktop

Thanks for taking the time. This document covers how to get set up, what the
project expects from a change, and how to get it reviewed.

## Getting set up

You need **Python 3.12+**, **Node 20+**, and a **PostgreSQL 17** instance with
the `vector` and `pg_trgm` extensions available.

```bash
git clone https://github.com/whereq/FlowDesktop.git
cd FlowDesktop

# Backend
cd backend
uv venv
uv sync --extra dev
uv run python -m alembic upgrade head

# Frontend
cd ../frontend
yarn install
```

Run the two dev servers:

```bash
cd backend && uv run uvicorn api.main:app --reload
cd frontend && yarn dev
```

Full setup instructions, including how to point the app at an identity
provider, are in [docs/setup.md](docs/setup.md).

## Before you open a pull request

Run the same checks CI runs:

```bash
# Backend
cd backend
uv run python -m pytest -q --no-cov
uv run python evals/run_evals.py
uv run ruff check .
uv run ruff format --check .

# Frontend
cd frontend
yarn lint
yarn build
```

All of them should pass. If a check fails, fix it before pushing — it is much
easier to review a green branch.

## Where things live

| Path | What goes there |
|---|---|
| `backend/api/routes/` | One module per resource group. |
| `backend/api/services/` | Business logic. A route should stay thin. |
| `backend/api/schemas/` | Pydantic request/response models. |
| `backend/packages/flowdesk-core/` | The data core — models, database, settings, auth. |
| `backend/packages/flowdesk-collector/` | Providers, collectors, the scheduler. |
| `backend/flowdesk/` | Tier entitlements. |
| `backend/tests/` | Unit tests. Fast, no database, no network. |
| `backend/evals/` | The deterministic router eval suite. |
| `frontend/src/` | React app. `pages/` for routes, `components/` for UI. |

## Adding a data provider

1. Write the provider in `backend/packages/flowdesk-collector/flowdesk_collector/providers/`.
   Subclass `BaseProvider` and return the normalised `QuoteData` / `HistoricalData`
   shapes — do not leak the provider's own field names.
2. Export it from `providers/__init__.py`.
3. Register it in `flowdesk_collector/provider_registry.py` so it shows up in
   `/providers/status`.
4. If it needs a credential, add a setting in `flowdesk_core/config.py` with an
   empty default, and document it in `docker/.env.example`.

## Adding a NOVA tool

1. Add the tool to the registry in `backend/api/services/tool_registry.py`. A
   tool declares a name, a description, a JSON schema for its arguments, and a
   handler.
2. Add it to the relevant skill's tool subset in
   `backend/api/services/skills.py` — a tool that no skill can reach will never
   be called.
3. Add a test in `backend/tests/`.

Tools run with the LLM's output, so validate every argument and never let a
tool's failure surface as a raw exception.

## Adding a skill

A skill is a named persona with its own system prompt, a curated tool subset
and a model tier. Add it to `SKILLS` in
`backend/api/services/skills.py`, then add keywords to the routing table so the
intent router can select it, and add cases to
`backend/evals/golden_set.json`.

## Database changes

The schema is owned by Alembic. **Never** edit the models without a migration.

```bash
cd backend

# 1. change the model
# 2. autogenerate the migration
uv run python -m alembic revision --autogenerate -m "describe the change"

# 3. apply it
uv run python -m alembic upgrade head

# 4. verify the schema still matches the models
uv run python -m flowdesk_core.schema_check
```

The schema check compares the live database against the models and reports
anything the database is missing. It is a safety net, not a substitute for
migrations.

Please never drop or rewrite a table to fix a problem — add a migration. Rows
in `stocks` are soft-deleted with `is_active = False`, never deleted.

## Tests

The test suite is deliberately fast and dependency-free: no database, no
network, no LLM. Anything that needs those belongs behind a marker or in a
manual script, not in `pytest`.

- Prefer testing pure functions directly.
- The router evals (`backend/evals/`) are deterministic and free — use them to
  guard behaviour that the LLM would otherwise make unpredictable.
- If you change the relevance scoring, the skill registry or the router
  thresholds, add a case to the eval suite. Those thresholds are easy to break
  silently.

## Style

- Python: `ruff format` and `ruff check` decide. Do not hand-format.
- TypeScript: `yarn lint` and `yarn build` decide.
- Comments explain *why*, not *what*. The code already says what it does.
- Keep the domain honest: FlowDesktop produces analysis, never financial
  advice, and web content is treated as untrusted input.

## Commits and pull requests

- One logical change per pull request. Split unrelated changes.
- Write the subject in the imperative: *"Fix short-interest column mapping"*.
- Explain the problem and the fix in the body, and say how you verified it.
- Reference the issue it closes, if there is one.

## Reporting bugs

Open an issue with what you did, what you expected, what happened, and the
relevant log output. If it involves a data problem, include the symbol and the
date.

Security issues should go through [SECURITY.md](SECURITY.md) instead of a
public issue.

## Code of conduct

By participating you agree to abide by the
[Code of Conduct](CODE_OF_CONDUCT.md).
