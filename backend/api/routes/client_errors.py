"""Client-side error reporting.

POST /api/v1/me/errors  — Authenticated users report frontend errors for server-side tracking.
Errors are written to the application logger (captured by Docker / log aggregation).
No sensitive payload is stored; message is capped to avoid log flooding.
"""

import logging

from fastapi import APIRouter
from pydantic import BaseModel

from flowdesk_core.auth import CurrentUser

logger = logging.getLogger("flowdesk.client_errors")

router = APIRouter(prefix="/me", tags=["errors"])

_MAX_MSG = 500
_MAX_CTX = 200


class ClientErrorReport(BaseModel):
    error_type: str  # e.g. "llm_stream", "keycloak_init", "api_error"
    message: str  # sanitised error description (already friendly on the client)
    context: str | None = None  # optional extra info (page, provider, model…)


@router.post("/errors", status_code=204)
async def report_client_error(
    body: ClientErrorReport,
    current_user: CurrentUser,
) -> None:
    """Receive a client-side error and log it server-side with the user id."""
    logger.warning(
        "client_error user=%s type=%s message=%r context=%r",
        current_user.get("sub", "unknown"),
        body.error_type[:64],
        body.message[:_MAX_MSG],
        (body.context or "")[:_MAX_CTX],
    )
