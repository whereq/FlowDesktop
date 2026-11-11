"""FastAPI application entry point."""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import (
    agents,
    ai_insights,
    alerts,
    calendar,
    chat,
    client_errors,
    intelligence,
    market_data,
    me_agents,
    me_conversations,
    me_data,
    me_entitlements,
    me_feedback,
    me_investor_profile,
    me_notification_prefs,
    me_push,
    me_schedules,
    payments,
    profile,
    public_pages,
    quotes,
    search,
    sectors,
    share,
    showcase,
    sim,
    status,
    stocks,
    watchlist,
)
from api.services.notification_manager import start_pg_listener
from flowdesk_core.config import get_settings
from flowdesk_core.database import init_db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    logger.info("Starting FlowDesktop API...")
    await init_db()
    logger.info("Database initialized")

    # Configuration check. FlowDesktop needs two things to be useful: a
    # whereq.cloud API key for the market data and a configured identity
    # provider for the authentication. Neither is bundled, so say so loudly
    # at boot instead of letting the first request fail obscurely.
    _report_configuration()

    # Start pg_notify listener for real-time WebSocket notifications
    _pg_listener_task = asyncio.create_task(start_pg_listener(settings.database_url))

    yield

    # Shutdown
    _pg_listener_task.cancel()
    try:
        await _pg_listener_task
    except asyncio.CancelledError:
        pass
    logger.info("Shutting down FlowDesktop API...")


def _report_configuration() -> None:
    """Log what is and is not configured. Never raises — a missing key is a
    setup problem the operator must fix, not a reason to refuse to boot."""
    from flowdesk_core.auth import auth_configured

    if not (settings.whereq_api_key or "").strip():
        logger.warning(
            "WHEREQ_API_KEY is not set. FlowDesktop reads all market data from "
            "the whereq.cloud Data API and will not serve data without a key. "
            "See docs/setup.md."
        )
    if not auth_configured():
        logger.warning(
            "KEYCLOAK_URL / KEYCLOAK_REALM / KEYCLOAK_CLIENT_ID are not "
            "configured. Every authenticated route will answer 503 until they "
            "point at your OpenID Connect provider. See docs/setup.md."
        )


app = FastAPI(
    title="FlowDesktop API",
    description="Multi-source stock data aggregation API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(stocks.router, prefix="/api/v1")
app.include_router(quotes.router, prefix="/api/v1")
app.include_router(search.router, prefix="/api/v1")
app.include_router(status.router, prefix="/api/v1")
app.include_router(showcase.router, prefix="/api/v1")
app.include_router(profile.router, prefix="/api/v1")
app.include_router(watchlist.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(payments.router, prefix="/api/v1")
app.include_router(client_errors.router, prefix="/api/v1")
app.include_router(ai_insights.router, prefix="/api/v1")
app.include_router(intelligence.router, prefix="/api/v1")
app.include_router(sectors.router, prefix="/api/v1")
app.include_router(alerts.router, prefix="/api/v1")
app.include_router(me_data.router, prefix="/api/v1")
app.include_router(agents.router, prefix="/api/v1")
app.include_router(me_agents.router, prefix="/api/v1")
app.include_router(me_push.router, prefix="/api/v1")
app.include_router(me_schedules.router, prefix="/api/v1")
app.include_router(me_notification_prefs.router, prefix="/api/v1")
app.include_router(me_entitlements.router, prefix="/api/v1")
app.include_router(me_conversations.router, prefix="/api/v1")
app.include_router(me_investor_profile.router, prefix="/api/v1")
app.include_router(me_feedback.router, prefix="/api/v1")
app.include_router(market_data.router, prefix="/api/v1")
app.include_router(sim.router, prefix="/api/v1")
app.include_router(calendar.router, prefix="/api/v1")
app.include_router(share.router, prefix="/api/v1")
app.include_router(public_pages.router)  # root-level: /s/{slug}, /sitemap.xml, /robots.txt


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "name": "FlowDesktop API",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/api/v1/health",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
    )
