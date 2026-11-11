"""Test bootstrap — put the backend root on sys.path so `flowdesk`/`api` import.

These are fast, dependency-light unit tests over pure logic (token budgeting,
notification gating, agent routing, validation guardrails). Route/DB integration
tests would need a test database and are intentionally out of scope here.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
