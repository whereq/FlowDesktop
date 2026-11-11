"""Fold NOVA 👍/👎 feedback into the eval golden set.

Run inside the api container (needs DB):
    python evals/ingest_feedback.py            # dry-run: print what would change
    python evals/ingest_feedback.py --write     # write evals/golden_feedback.json

Logic:
- A 👍 on a turn that auto-ran a NATIVE agent is evidence the router was right:
  it becomes a router case {q: question, expect: <agent>}. (Custom agents aren't
  router targets, so they're skipped.)
- 👎 cases are recorded under "review" (NOT used as ground truth — a thumbs-down
  means the answer was poor, which doesn't tell us the correct route/skill).
- Dedups against golden_set.json and any existing golden_feedback.json.

run_evals.py merges golden_feedback.json into the router suite, so the CI eval
gate grows with curated, real-world cases. Regenerate periodically (prod has the
DB), then commit golden_feedback.json so CI picks it up.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from sqlalchemy import select  # noqa: E402

from api.services.skills import SKILLS  # noqa: E402
from flowdesk_core.database import AsyncSessionLocal  # noqa: E402
from flowdesk_core.models.message_feedback import MessageFeedback  # noqa: E402

GOLDEN = HERE / "golden_set.json"
FEEDBACK_OUT = HERE / "golden_feedback.json"


def _norm(q: str) -> str:
    return " ".join((q or "").lower().split())


async def collect() -> dict:
    golden = json.loads(GOLDEN.read_text())
    existing_qs = {_norm(c["q"]) for c in golden.get("router", [])}
    if FEEDBACK_OUT.exists():
        prev = json.loads(FEEDBACK_OUT.read_text())
        existing_qs |= {_norm(c["q"]) for c in prev.get("router", [])}

    router_cases: list[dict] = []
    review: list[dict] = []
    seen: set[str] = set()

    async with AsyncSessionLocal() as db:
        rows = (
            (
                await db.execute(
                    select(MessageFeedback).order_by(MessageFeedback.id.desc()).limit(2000)
                )
            )
            .scalars()
            .all()
        )

    for f in rows:
        q = (f.question or "").strip()
        if not q:
            continue
        nq = _norm(q)
        if f.rating > 0:
            # Positive + native agent → a router ground-truth case.
            if f.agent and f.agent in SKILLS and nq not in existing_qs and nq not in seen:
                router_cases.append({"q": q[:200], "expect": f.agent})
                seen.add(nq)
        else:
            review.append({"q": q[:200], "agent": f.agent, "answer": (f.answer or "")[:160]})

    return {"router": router_cases, "review": review[:200]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="write golden_feedback.json")
    args = ap.parse_args()

    data = asyncio.run(collect())
    print(
        f"Derived {len(data['router'])} new router case(s) from 👍 feedback; "
        f"{len(data['review'])} 👎 case(s) recorded for review."
    )
    for c in data["router"]:
        print(f"  + {c['expect']:18s} <- {c['q']!r}")

    if args.write:
        FEEDBACK_OUT.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        print(f"\nWrote {FEEDBACK_OUT.relative_to(HERE.parent)}")
    else:
        print("\n(dry-run — pass --write to persist golden_feedback.json)")


if __name__ == "__main__":
    main()
