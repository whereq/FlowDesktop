"""User price alert model — per-user stock price triggers."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Float, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from flowdesk_core.database import Base

# Supported alert types
ALERT_TYPE_PRICE_ABOVE = "price_above"
ALERT_TYPE_PRICE_BELOW = "price_below"
ALERT_TYPE_CHANGE_PCT_ABOVE = "change_pct_above"
ALERT_TYPE_CHANGE_PCT_BELOW = "change_pct_below"

VALID_ALERT_TYPES = {
    ALERT_TYPE_PRICE_ABOVE,
    ALERT_TYPE_PRICE_BELOW,
    ALERT_TYPE_CHANGE_PCT_ABOVE,
    ALERT_TYPE_CHANGE_PCT_BELOW,
}


class UserAlert(Base):
    """A price or change-percentage alert for a single stock symbol.

    Constraints:
    - One alert per (user, symbol, alert_type) — e.g. you can have one
      price_above and one price_below for the same symbol, but not two
      price_above alerts for the same symbol.
    - Alerts are soft-disabled (is_active=False) once triggered.
    - Users can re-enable (PATCH /me/alerts/{id}/rearm) to reset.
    """

    __tablename__ = "user_alerts"
    __table_args__ = (
        UniqueConstraint(
            "keycloak_id",
            "symbol",
            "alert_type",
            name="uq_user_alert_user_symbol_type",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    keycloak_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), index=True)
    symbol: Mapped[str] = mapped_column(String(20))
    # One of VALID_ALERT_TYPES
    alert_type: Mapped[str] = mapped_column(String(30))
    # The price/pct threshold that fires the alert
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    # False once the alert has fired (or user manually disables it)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Set when the alert fires
    triggered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return (
            f"<UserAlert {self.keycloak_id} {self.symbol} "
            f"{self.alert_type}@{self.threshold} active={self.is_active}>"
        )
