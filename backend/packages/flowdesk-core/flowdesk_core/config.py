"""Application configuration management.

Every setting can be supplied as an environment variable (case-insensitive) or
placed in a ``.env`` file next to the process. Nothing here has a secret
default — an unset credential simply disables the feature that needs it.
"""

from decimal import Decimal
from functools import lru_cache

from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # ── Database ──────────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://flowdesk:flowdesk@localhost:5432/flowdesk"
    database_url_sync: str = "postgresql://flowdesk:flowdesk@localhost:5432/flowdesk"

    # ── Data providers (all optional) ────────────────────────────────────
    # The bundled providers (Yahoo Finance, Stooq, AKShare, SEC EDGAR) need
    # no key at all. These keys are only for the optional extra providers you
    # can plug in — see docs/design-high-level-design.md.
    alpha_vantage_api_key: str = ""
    finnhub_api_key: str = ""
    twelve_data_api_key: str = ""
    polygon_api_key: str = ""
    tiingo_api_key: str = ""
    alpaca_api_key: str = ""
    alpaca_api_secret: str = ""
    fmp_api_key: str = ""
    fred_api_key: str = ""
    tushare_token: str = ""
    jquants_api_key: str = ""
    jquants_email: str = ""
    jquants_password: str = ""
    jquants_refresh_token: str = ""

    # ── Collection settings ───────────────────────────────────────────────
    collection_interval_minutes: int = 5
    historical_days: int = 365
    stooq_request_delay: float = 2.0

    # ── Authentication (OIDC) ─────────────────────────────────────────────
    # A generic OpenID Connect provider. The SPA is a public client; the
    # backend verifies the bearer token against the provider's JWKS endpoint.
    keycloak_url: str = "https://auth.example.com"
    keycloak_realm: str = "flowdesktop"
    keycloak_client_id: str = "flowdesktop-spa"
    # Realm role required for admin-only surfaces.
    admin_role: str = "fd-admin"

    # Service account used to assign roles after a subscription purchase.
    # Only needed when you run the paid-tier flow; leave blank to disable it.
    keycloak_admin_client_id: str = "flowdesktop-backend"
    keycloak_admin_client_secret: str = ""

    # ── Payments (optional) ───────────────────────────────────────────────
    # Leave both blank to disable the subscription flow entirely.
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""

    # ── API settings ──────────────────────────────────────────────────────
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]
    # The public origin of this deployment. Used for canonical links, the
    # sitemap, robots.txt and the server-rendered share pages.
    site_url: str = "http://localhost:8080"

    # ── LLM providers (platform mode) ─────────────────────────────────────
    # In platform mode the backend uses these keys. In BYOK mode each request
    # carries the user's own key instead and none of these are needed.
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_ai_api_key: str = ""
    deepseek_api_key: str = ""
    qwen_api_key: str = ""
    minimax_api_key: str = ""
    minimax_group_id: str = ""

    # Explicit platform provider override — set this to avoid key auto-detection
    # ambiguity. Must be one of: openai, anthropic, google, deepseek, qwen, minimax
    platform_llm_provider: str = ""

    # ── Semantic retrieval / embeddings ──────────────────────────────────
    # The default is a LOCAL CPU model via fastembed (ONNX, no API key, no
    # quota) — multilingual (en/zh), 384-dim. Models with a "/" route to the
    # local path; flat names route to an API.
    #
    # IMPORTANT: embedding_dim MUST match the vector(N) column in
    # retrieval_chunks. Changing the model or the dimension requires a
    # re-index under the new model id.
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    embedding_dim: int = 384

    # ── Proactive insights ("NOVA Pulse") ────────────────────────────────
    # Push-driven, per-user signal delivery. Off by default (opt-in). The job
    # matches fresh market signals against each user's watchlist and
    # portfolio, scores relevance against their investor profile, dedups, and
    # pushes the top few.
    proactive_insights_enabled: bool = False
    proactive_freshness_hours: int = 6  # only signals processed within this window
    proactive_min_confidence: float = 0.55  # drop low-conviction signals before scoring
    proactive_score_cutoff: float = 0.25  # minimum relevance score to push
    proactive_top_k: int = 3  # max insights considered per user per run
    proactive_daily_cap: int = 3  # max proactive pushes per user per day
    proactive_narrate: bool = True  # use the LLM for "why it matters"
    proactive_narrate_max_tokens: int = 400  # per-user batched narration budget
    proactive_digest_top_k: int = 6  # max insights in one daily digest push

    # Auto-tuning: adjust the effective score cutoff from thumbs up/down
    # feedback, but only once a vote quorum is met. Bounded, small steps.
    pulse_tune_enabled: bool = True
    pulse_tune_window_days: int = 30  # feedback lookback window
    pulse_tune_min_votes: int = 8  # quorum before any adjustment
    pulse_tune_step: float = 0.03  # cutoff step per tuning run
    pulse_cutoff_min: float = 0.15  # never push below this relevance
    pulse_cutoff_max: float = 0.5  # never require more than this

    # ── Filings grounding ─────────────────────────────────────────────────
    # SEC 10-K/10-Q narrative indexed into pgvector for semantic search.
    # Free/no-key (SEC EDGAR). Scoped to held (watchlist + portfolio) symbols.
    filings_enabled: bool = True
    filings_max_symbols: int = 200  # cap symbols processed per collect run
    filings_chunk_chars: int = 1500  # chars per embedded chunk
    filings_max_chunks_per_doc: int = 40  # cap embedded chunks per filing

    # ── Lazy on-view population ───────────────────────────────────────────
    # Fetch a symbol's insider activity, short interest and filings live on
    # the first StockDetail view (universe-only, cached, timeout-guarded).
    lazy_market_data_enabled: bool = True

    # ── Insider activity ──────────────────────────────────────────────────
    # SEC Form 4 transactions for held US symbols. Free/no-key.
    insider_enabled: bool = True
    insider_max_symbols: int = 200  # cap symbols processed per collect run
    insider_max_filings_per_symbol: int = 8  # recent Form 4 filings parsed per symbol

    # ── Short interest ────────────────────────────────────────────────────
    # Yahoo Finance snapshots for held symbols. Free/no-key.
    short_interest_enabled: bool = True
    short_interest_max_symbols: int = 300  # cap symbols processed per collect run

    # ── Congressional trades ───────────────────────────────────────────────
    # Community STOCK Act datasets, filtered to the symbol universe.
    congress_trades_enabled: bool = True
    congress_lookback_days: int = 400  # only keep disclosures within this window
    congress_senate_url: str = "https://senate-stock-watcher-data.s3-us-west-2.amazonaws.com/aggregate/all_transactions.json"
    congress_house_url: str = (
        "https://house-stock-watcher-data.s3-us-west-2.amazonaws.com/data/all_transactions.json"
    )

    # ── Trading simulator (paper trading) ─────────────────────────────────
    # Money knobs are Decimal; friction is off by default (a clean learning
    # tool).
    sim_enabled: bool = True
    sim_max_initial_balance: Decimal = Decimal("10000000")
    sim_default_initial_balance: Decimal = Decimal("100000")
    sim_commission_bps: float = 0.0  # commission in basis points (0 = none)
    sim_slippage_bps: float = 0.0  # execution slippage in bps (0 = none)
    sim_quote_max_age_minutes: int = 30  # stale-quote guard when the market is open
    sim_matcher_interval_minutes: int = 5  # limit/queued-order matcher cadence

    # ── Web Push (VAPID) ──────────────────────────────────────────────────
    # vapid_private_key is a base64-encoded PKCS8 PEM on a single line
    # (environment-variable safe); the public applicationServerKey is derived
    # from it at runtime. Empty = Web Push disabled (notifications stay
    # in-app / websocket).
    vapid_private_key: str = ""
    vapid_subject: str = "mailto:admin@example.com"

    # Pydantic v2 model config — replaces the deprecated inner `class Config`.
    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    """Get the cached settings instance."""
    return Settings()
