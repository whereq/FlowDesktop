"""Shared cooldown for the East Money (东方财富) endpoints.

East Money rate-limits by source IP, and the ban is *sticky*.  The upstream
error says so explicitly:

    东方财富 push2 行情服务器断开了连接，通常是短时间内请求过多，当前 IP 被
    临时限流。首次限流一般约 5 分钟后恢复，反复触发后可能需要 40 分钟以上；
    等待期间不要重复调用东方财富的行情接口，否则会延长限流。

    ("…the connection was dropped because too many requests were made in a
    short time; this IP is temporarily rate-limited.  A first ban lasts
    about five minutes, but repeated triggers may need 40+ minutes, and
    calling the quote interface again while waiting only extends it.")

We call East Money from six places:

* the global news flash feed (``stock_info_global_em``)
* the A-share index spot table (``stock_zh_index_spot_em``)
* the index sparklines (``stock_zh_index_daily_em``)
* the sector fund-flow table (``stock_sector_fund_flow_rank``)
* the hot-stock ranking (``stock_hot_rank_em``)
* the HKEX spot feed (``stock_hk_spot_em``)

Each of them used to retry on its own schedule — every two to five minutes —
so the ban was refreshed before it could expire.  Measured on 2026-11-04:
**85 consecutive East Money failures over 48 hours and not one success.**

That single failure is what starves the Hong Kong quote feed: with East
Money blocked, the HK provider falls back to Sina, which carries ~2 800 of
the ~4 600 HK listings, and the remaining ~1 800 listings had nobody else to
ask.

The cooldown is therefore *shared and explicit*: the first rate-limit error
opens it, every caller stays out until it expires, and the ban finally gets
the chance to run its course.

The gate is advisory — a caller that is blocked falls back to its non-East
Money source instead of failing.
"""

from __future__ import annotations

import logging
import time
from typing import ClassVar

logger = logging.getLogger(__name__)

# A first East Money ban lasts ~5 minutes, but repeated triggers push it to
# 40+ minutes.  We stay out long enough for the worst case so the ban can
# actually expire instead of being extended by our own retries.
COOLDOWN_SECONDS: float = 45 * 60.0

# Fallback cooldown for failures that are not explicit rate-limit errors
# (connection resets, read timeouts).  A few of those in a row usually mean
# the same thing, so we cool down briefly rather than hammering.
TRANSIENT_FAILURE_THRESHOLD: int = 3
TRANSIENT_COOLDOWN_SECONDS: float = 10 * 60.0

# Substrings that identify an explicit upstream rate-limit rejection.
# The upstream message is Chinese; the English markers cover the same error
# arriving through a proxy or a library that translates it.
_RATE_LIMIT_MARKERS: tuple[str, ...] = (
    "限流",
    "请求过多",
    "too many requests",
    "rate limit",
    "rate-limit",
    "ratelimit",
)


def is_rate_limited(exc: BaseException) -> bool:
    """Return True if *exc* is an upstream rate-limit rejection."""
    try:
        text = str(exc).lower()
    except Exception:  # noqa: BLE001 — a broken __str__ must not break the gate
        return False
    return any(marker.lower() in text for marker in _RATE_LIMIT_MARKERS)


class EastMoneyGate:
    """Process-wide gate that keeps every East Money caller out during a ban."""

    _blocked_until: ClassVar[float] = 0.0
    _consecutive_failures: ClassVar[int] = 0
    _last_error: ClassVar[str] = ""
    _opened_at: ClassVar[float | None] = None
    _total_blocks: ClassVar[int] = 0

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    @classmethod
    def is_blocked(cls) -> bool:
        """True while an East Money cooldown is in force."""
        return not cls._blocked_until <= time.monotonic()

    @classmethod
    def cooldown_remaining(cls) -> float:
        """Seconds left on the current cooldown (0 when open)."""
        return max(0.0, cls._blocked_until - time.monotonic())

    @classmethod
    def last_error(cls) -> str:
        """The error that opened the current cooldown."""
        return cls._last_error

    @classmethod
    def total_blocks(cls) -> int:
        """How many cooldowns this process has opened (diagnostic)."""
        return cls._total_blocks

    # ------------------------------------------------------------------
    # Transitions
    # ------------------------------------------------------------------

    @classmethod
    def record_success(cls) -> None:
        """A call went through — East Money is reachable again."""
        if cls._consecutive_failures or cls.is_blocked():
            logger.info(
                "East Money reachable again — cooldown cleared",
                extra={
                    "operation": "eastmoney_gate",
                    "consecutive_failures_cleared": cls._consecutive_failures,
                },
            )
        cls._consecutive_failures = 0
        cls._blocked_until = 0.0
        cls._opened_at = None
        cls._last_error = ""

    @classmethod
    def record_failure(cls, exc: BaseException) -> bool:
        """Record a failed East Money call; open a cooldown when appropriate.

        Returns True if a cooldown is now in force.
        """
        cls._consecutive_failures += 1
        cls._last_error = str(exc)[:400]

        if is_rate_limited(exc):
            cls._open(COOLDOWN_SECONDS, "rate limited")
            return True

        if cls._consecutive_failures >= TRANSIENT_FAILURE_THRESHOLD:
            cls._open(TRANSIENT_COOLDOWN_SECONDS, "repeated failures")
            return True

        return cls.is_blocked()

    @classmethod
    def _open(cls, seconds: float, reason: str) -> None:
        now = time.monotonic()
        # Never shorten an existing cooldown.
        if cls._blocked_until > now:
            return
        cls._blocked_until = now + seconds
        cls._opened_at = now
        cls._total_blocks += 1
        logger.warning(
            f"East Money {reason} — pausing every East Money caller for "
            f"{int(seconds // 60)} minutes. Repeated calls extend the ban, "
            f"so the fallback sources are used until it expires.",
            extra={
                "operation": "eastmoney_gate",
                "reason": reason,
                "cooldown_seconds": seconds,
                "consecutive_failures": cls._consecutive_failures,
            },
        )

    @classmethod
    def reset(cls) -> None:
        """Clear the gate (tests / manual recovery)."""
        cls._blocked_until = 0.0
        cls._consecutive_failures = 0
        cls._last_error = ""
        cls._opened_at = None


def eastmoney_allowed() -> bool:
    """True when an East Money call may be attempted."""
    return not EastMoneyGate.is_blocked()


class EastMoneyCoolingDown(RuntimeError):
    """Raised instead of calling East Money while its cooldown is in force.

    Callers treat this like any other East Money failure and fall back to
    their non-East Money source — the point is that no HTTP request is made.
    """
