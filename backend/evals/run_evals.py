"""Lightweight NOVA eval runner (dev/CI — not in the serving path).

Run inside the api container (cwd /app):
    python evals/run_evals.py            # router evals only — free, deterministic
    python evals/run_evals.py --live     # also run live skill checks (uses the LLM)

Router evals guard the intent router against regressions as skills are added.
Live evals smoke a skill end-to-end (asserts the answer matches a pattern).
Exit code 0 = all passed, 1 = at least one failed (CI-friendly).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))  # ensure /app is importable when run as a script

from api.services.skills import classify_skill, get_skill, run_skill  # noqa: E402

CASES = json.loads((HERE / "golden_set.json").read_text())

# Merge curated cases ingested from real 👍 feedback (evals/ingest_feedback.py),
# so the regression gate grows with real-world routing examples.
_FEEDBACK = HERE / "golden_feedback.json"
if _FEEDBACK.exists():
    try:
        _fb = json.loads(_FEEDBACK.read_text())
        CASES["router"] = CASES.get("router", []) + _fb.get("router", [])
    except Exception as _exc:  # noqa: BLE001 — never let a bad feedback file break evals
        print(f"[warn] could not merge golden_feedback.json: {_exc}")


def run_router() -> tuple[int, int]:
    passed = failed = 0
    for c in CASES["router"]:
        got = classify_skill(c["q"])
        ok = got == c["expect"]
        print(f"[router] {'PASS' if ok else 'FAIL'}  {c['q']!r} -> {got} (expect {c['expect']})")
        passed += ok
        failed += not ok
    return passed, failed


async def run_skill_cases() -> tuple[int, int]:
    from flowdesk_core.database import AsyncSessionLocal

    passed = failed = 0
    async with AsyncSessionLocal() as db:
        for c in CASES["skill"]:
            skill = get_skill(c["skill"])
            if skill is None:
                print(f"[skill]  FAIL  unknown skill {c['skill']}")
                failed += 1
                continue
            text = ""
            async for ch in run_skill(
                skill,
                db=db,
                user_id=None,
                user_text=c["input"],
                symbols=c.get("symbols"),
                max_tokens=c.get("max_tokens", 120),
            ):
                if ch.get("delta"):
                    text += ch["delta"]
            ok = bool(re.search(c["must_match"], text))
            print(f"[skill]  {'PASS' if ok else 'FAIL'}  {c['skill']} :: {text[:80]!r}")
            passed += ok
            failed += not ok
    return passed, failed


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="also run live skill checks (uses the LLM)")
    args = ap.parse_args()

    p, f = run_router()
    if args.live:
        lp, lf = asyncio.run(run_skill_cases())
        p, f = p + lp, f + lf

    print(f"\n{p} passed, {f} failed")
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
