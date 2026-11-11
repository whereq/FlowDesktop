"""One JavaScript context at a time.

akshare decrypts some payloads (Sina, CNINFO) by running JavaScript through
`py_mini_racer`, which embeds V8. Every akshare call builds its own context:

    ctx = MiniRacer()
    ctx.eval(js)

V8's PartitionAlloc can only be set up once per process, and a context is
bound to the thread that created it. The collector fetches A-share history in
worker threads — `asyncio.to_thread(ak.stock_zh_a_daily, ...)` — so two
symbols can hold a context at the same time, and the second one aborts the
WHOLE collector:

    [FATAL:partition_address_space.cc(243)] Check failed: !IsConfigurablePoolInitialized()
    #09 ... libffi.so.8.1.2
    → SIGSEGV, exit 139

There is no Python traceback and no exception: the process is simply gone.
Because the startup catch-up re-runs the overdue historical backfill, every
restart hit the same crash — an endless crash loop that stopped all
collection (the 2026-11-07 outage).

This guard holds one process-wide lock for the whole life of a MiniRacer
context, so only one context is ever alive. akshare creates and drops its
context inside a single call, so the lock is held for milliseconds and only
the JavaScript-backed endpoints queue behind each other.

Locking only the *creation* is not enough — the crash happens when two
contexts are *used* at the same time, so the lock covers creation, use and
destruction.
"""

from __future__ import annotations

import logging
import os
import threading
import weakref

logger = logging.getLogger(__name__)

# One context at a time, process-wide.
_context_lock = threading.Lock()

# Whether THIS thread is the one holding the lock. A second context on the
# same thread is safe (V8 allows it), so a nested creation skips the lock.
_local = threading.local()

# How long to wait for the previous context to be released before giving up.
# A leaked context would otherwise block every later JavaScript call forever;
# failing loudly beats hanging the collector.
_ACQUIRE_TIMEOUT = float(os.getenv("COLLECTOR_JS_LOCK_TIMEOUT", "30"))


def _release() -> None:
    """Release the process-wide lock, from whichever thread the context died on."""
    try:
        _context_lock.release()
    except RuntimeError:
        # Already released (close() and the finalizer can both fire).
        pass


def install() -> bool:
    """Serialise MiniRacer contexts. Returns True when the guard is in place."""
    try:
        from py_mini_racer import MiniRacer
    except Exception:  # pragma: no cover - py_mini_racer is an akshare dependency
        logger.info("js_guard: py_mini_racer is not installed — nothing to guard")
        return False

    if getattr(MiniRacer.__init__, "_flowdesktop_js_guarded", False):
        return True

    original_init = MiniRacer.__init__
    original_close = getattr(MiniRacer, "close", None)
    if original_close is None:  # pragma: no cover - unexpected mini-racer build
        logger.warning("js_guard: MiniRacer has no close() — not guarding")
        return False

    def guarded_init(self, *args, **kwargs):
        owns = getattr(_local, "owns", False)
        if owns and not _context_lock.locked():
            # The previous context on this thread died without releasing.
            owns = False
            _local.owns = False

        if owns:
            # A nested context on the same thread — V8 allows two of those,
            # and the outer one already keeps other threads out.
            original_init(self, *args, **kwargs)
            return

        if not _context_lock.acquire(timeout=_ACQUIRE_TIMEOUT):
            raise RuntimeError(
                "js_guard: another JavaScript context has been alive for more "
                f"than {_ACQUIRE_TIMEOUT:.0f}s — refusing to build a second one "
                "(py_mini_racer/V8 cannot survive two live contexts)"
            )
        try:
            original_init(self, *args, **kwargs)
        except BaseException:
            _release()
            raise
        _local.owns = True
        # akshare drops its context at the end of the call without closing it,
        # so the lock is released when the object is collected.
        self._flowdesktop_js_release = weakref.finalize(self, _release)

    def guarded_close(self, *args, **kwargs):
        try:
            original_close(self, *args, **kwargs)
        finally:
            release = getattr(self, "_flowdesktop_js_release", None)
            if release is not None:
                release()
                self._flowdesktop_js_release = None
                _local.owns = False

    guarded_init._flowdesktop_js_guarded = True
    MiniRacer.__init__ = guarded_init
    MiniRacer.close = guarded_close
    logger.info(
        "js_guard: py_mini_racer contexts are serialised (one at a time)",
        extra={"operation": "js_guard"},
    )
    return True
