"""Data collection service.

Importing the package installs the JavaScript-context guard: akshare runs
some payloads through py_mini_racer (V8), and V8 cannot survive two live
contexts in one process. The collector fetches in worker threads, so without
the guard the historical backfill aborts the whole collector with SIGSEGV.
See `collector.js_guard` for the details.
"""

from flowdesk_collector.js_guard import install as _install_js_guard

_install_js_guard()
