"""NOVA Skill registry + runner (provider-agnostic).

A Skill is declarative config — a focused system prompt, a curated tool subset,
and a model tier — executed by the shared LLMGateway over whatever model is
configured (LiteLLM). No provider-specific code lives here, so skills are reusable
across MiniMax / OpenAI / Anthropic / etc.

Phase A registers the four v1 skills and fully wires `research_analyst`
(the /ai/analyze route). The remaining routes are converted in Phase B; see
docs/architecture/AGENTS_ROADMAP.md.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass

from api.services.llm_gateway import (
    LLMGateway,
    provider_api_base,
    resolve_platform_provider,
)

_gateway = LLMGateway()


@dataclass(frozen=True)
class Skill:
    """A reusable, model-agnostic NOVA capability."""

    name: str  # stable id, e.g. "research_analyst"
    title: str  # persona name for the catalog
    category: str  # Research | Compare | Strategy | Portfolio | ...
    description: str  # one-line purpose (catalog + router)
    system_prompt: str  # focused instructions appended to NOVA's base prompt
    tools: tuple[str, ...]  # curated subset of ToolRegistry tool names
    model_tier: str = "auto"  # "light" | "heavy" | "auto"
    temperature: float = 0.4
    max_tokens: int = 1024
    example_prompts: tuple[str, ...] = ()
    maturity: str = "beta"  # "stable" | "beta" | "planned"
    icon: str = "✦"

    def public(self) -> dict:
        """Serializable view for the (future) GET /agents catalog endpoint."""
        return {
            "name": self.name,
            "title": self.title,
            "category": self.category,
            "description": self.description,
            "tools": list(self.tools),
            "model_tier": self.model_tier,
            "example_prompts": list(self.example_prompts),
            "maturity": self.maturity,
            "icon": self.icon,
        }


# ---------------------------------------------------------------------------
# v1 skill catalog (persona-named)
# ---------------------------------------------------------------------------

RESEARCH_ANALYST = Skill(
    name="research_analyst",
    title="Research Analyst",
    category="Research",
    description="Full one-stock brief: price, technicals, fundamentals, news, peers, and risks.",
    icon="🔬",
    maturity="stable",
    model_tier="heavy",
    temperature=0.4,
    max_tokens=1200,
    tools=(
        "get_stock_quote",
        "fetch_live_quote",
        "get_price_history",
        "get_technical_indicators",
        "get_fundamentals",
        "get_news_and_signals",
        "semantic_news_search",
        "get_peers_and_correlations",
        "get_calendar_events",
        "render_chart",
    ),
    example_prompts=(
        "Give me a full analysis of NVDA",
        "Research 600519.SS",
        "Is AAPL a buy right now?",
    ),
    system_prompt=(
        "You are running NOVA's **Research Analyst** skill. Produce a structured, "
        "data-grounded single-stock brief. Use your tools to fill any gaps "
        "(technicals, fundamentals, recent news/sentiment, peers) before concluding. "
        "Organize as: Snapshot → Technical read → Fundamentals/valuation → "
        "News & catalysts → Peers/context → Risks → Bottom line. Cite concrete "
        "numbers, never invent data, and clearly state anything unavailable. "
        "Keep it tight and skimmable; end with a balanced takeaway and a risk "
        "caveat — never a guarantee."
    ),
)

STOCK_COMPARATOR = Skill(
    name="stock_comparator",
    title="Stock Comparator",
    category="Compare",
    description="Rank and contrast 2–5 stocks on valuation, growth, momentum, and risk, with a verdict.",
    icon="⚖️",
    maturity="beta",
    model_tier="heavy",
    temperature=0.4,
    max_tokens=1200,
    tools=(
        "compare_stocks",
        "get_fundamentals",
        "get_technical_indicators",
        "get_peers_and_correlations",
        "get_stock_quote",
        "render_chart",
    ),
    example_prompts=(
        "Compare NVDA vs AMD vs AVGO",
        "KO or PEP for a dividend portfolio?",
    ),
    system_prompt=(
        "You are running NOVA's **Stock Comparator** skill. Compare the requested "
        "names side by side using fetched data (quote, valuation, growth, momentum, "
        "risk). Present a compact comparison table, then a short verdict that says "
        "which fits which goal and why. Cite numbers; flag where data is missing; "
        "never guarantee outcomes."
    ),
)

PORTFOLIO_DOCTOR = Skill(
    name="portfolio_doctor",
    title="Portfolio Doctor",
    category="Portfolio",
    description="Reviews your paper portfolio: exposure, P/L, concentration, gaps, and suggested alerts.",
    icon="💼",
    maturity="beta",
    model_tier="heavy",
    temperature=0.4,
    max_tokens=1200,
    tools=(
        "get_portfolio",
        "get_peers_and_correlations",
        "get_macro_indicators",
        "get_news_and_signals",
        "semantic_news_search",
        "get_stock_quote",
        "propose_create_alert",
    ),
    example_prompts=(
        "How's my portfolio doing?",
        "What are the risks in my holdings?",
    ),
    system_prompt=(
        "You are running NOVA's **Portfolio Doctor** skill. Review the user's "
        "holdings: total and per-position P/L, sector/name concentration, "
        "correlation/overlap risk, and notable news on holdings. Surface concrete "
        "observations and, where helpful, propose alerts for the user to confirm. "
        "Be candid about risks; this is analysis, not advice; never guarantee returns."
    ),
)

STRATEGY_ARCHITECT = Skill(
    name="strategy_architect",
    title="Strategy Architect",
    category="Strategy",
    description="Proposes and justifies entry/exit/sizing strategies for a thesis, with risk framing.",
    icon="🧠",
    maturity="beta",
    model_tier="heavy",
    temperature=0.5,
    max_tokens=1400,
    tools=(
        "get_technical_indicators",
        "get_fundamentals",
        "get_macro_indicators",
        "get_news_and_signals",
        "semantic_news_search",
        "get_price_history",
        "get_stock_quote",
        "run_backtest",
    ),
    example_prompts=(
        "Build me a swing-trade plan for TSLA",
        "Backtest an SMA 20/50 crossover on AAPL",
        "How would I hedge a tech-heavy book?",
    ),
    system_prompt=(
        "You are running NOVA's **Strategy Architect** skill. Given a thesis or "
        "stock, propose 1–3 concrete strategy options with rationale grounded in "
        "fetched technicals, fundamentals, and macro context. For each: setup, "
        "entry/exit logic, position sizing/risk controls, and what would invalidate "
        "it. When a rules-based idea can be tested (e.g. an SMA crossover or RSI "
        "mean-reversion), call run_backtest to ground it in real historical "
        "performance vs buy & hold, and cite the metrics. Present trade-offs "
        "honestly; a backtest is illustrative, not predictive. Educational only — "
        "not financial advice; never promise profits."
    ),
)

CATALYST_TRACKER = Skill(
    name="catalyst_tracker",
    title="Catalyst Tracker",
    category="Research",
    description="Surfaces upcoming catalysts — earnings, dividends, and fresh news — for a stock or your watchlist, with what to watch.",
    icon="📅",
    maturity="beta",
    model_tier="heavy",
    temperature=0.4,
    max_tokens=1100,
    tools=(
        "get_calendar_events",
        "get_news_and_signals",
        "semantic_news_search",
        "get_stock_quote",
        "get_watchlist",
        "get_fundamentals",
    ),
    example_prompts=(
        "What catalysts are coming up for NVDA?",
        "Any earnings or dividends in my watchlist this week?",
        "Who reports earnings in the next few days?",
    ),
    system_prompt=(
        "You are running NOVA's **Catalyst Tracker** skill. Identify upcoming "
        "catalysts for the requested stock(s) or the user's watchlist: earnings "
        "dates (with EPS estimates), ex-dividend dates and amounts, and notable "
        "recent news/signals. Use get_calendar_events for dates and "
        "get_news_and_signals for context. Organize by date (soonest first), say "
        "what each catalyst could move and what to watch, and flag when no events "
        "are scheduled. Be concise and concrete; never speculate beyond the data."
    ),
)

SKILLS: dict[str, Skill] = {
    s.name: s
    for s in (
        RESEARCH_ANALYST,
        STOCK_COMPARATOR,
        PORTFOLIO_DOCTOR,
        STRATEGY_ARCHITECT,
        CATALYST_TRACKER,
    )
}


def get_skill(name: str) -> Skill | None:
    return SKILLS.get(name)


# ---------------------------------------------------------------------------
# Custom (user-built) agents — hydrate a DB row into a Skill (Phase F1)
# ---------------------------------------------------------------------------


def hydrate_custom_agent(row) -> Skill:
    """Turn a CustomAgent DB row into a runnable Skill. Tools are validated at
    write time, so they're a trusted subset here."""
    return Skill(
        name=f"custom:{row.name}",
        title=row.title,
        category=row.category or "Custom",
        description=row.description or "",
        system_prompt=row.system_prompt,
        tools=tuple(row.tools or ()),
        model_tier=row.model_tier or "auto",
        temperature=float(row.temperature),
        max_tokens=int(row.max_tokens),
        maturity="custom",
        icon=row.icon or "🤖",
    )


async def resolve_agent(db, user_id: str | None, name: str) -> Skill | None:
    """Resolve an agent reference to a runnable Skill: native first, then the
    caller's own custom agents. Returns None if unknown."""
    native = get_skill(name)
    if native:
        return native
    if not user_id:
        return None
    from uuid import UUID

    from sqlalchemy import select

    from flowdesk_core.models.custom_agent import CustomAgent

    try:
        row = await db.scalar(
            select(CustomAgent).where(
                CustomAgent.keycloak_id == UUID(user_id),
                CustomAgent.name == name,
            )
        )
    except Exception:
        return None
    return hydrate_custom_agent(row) if row else None


def list_skills() -> list[dict]:
    """Catalog view (for a future GET /agents endpoint)."""
    return [s.public() for s in SKILLS.values()]


# ---------------------------------------------------------------------------
# Orchestration — lightweight intent router
# ---------------------------------------------------------------------------

# Keyword cues per skill, checked most-specific first. Used to suggest the right
# agent for a free-text request (the catalog/chat can surface this).
_ROUTER_CUES: list[tuple[str, tuple[str, ...]]] = [
    (
        "catalyst_tracker",
        (
            "earnings",
            "ex-dividend",
            "ex dividend",
            "dividend",
            "catalyst",
            "report date",
            "when does",
            "reports earnings",
            "upcoming events",
            "earnings calendar",
        ),
    ),
    (
        "portfolio_doctor",
        ("my portfolio", "my holdings", "my positions", "how am i doing", "my book", "rebalance"),
    ),
    (
        "stock_comparator",
        ("compare", " vs ", " versus ", "better buy", "head to head", "head-to-head"),
    ),
    (
        "strategy_architect",
        (
            "strategy",
            "trade plan",
            "swing",
            "entry",
            "exit",
            "hedge",
            "position sizing",
            "backtest",
        ),
    ),
    (
        "research_analyst",
        (
            "analyze",
            "analysis",
            "research",
            "deep dive",
            "deep-dive",
            "should i buy",
            "is it a buy",
            "thesis",
        ),
    ),
]


def classify_skill(text: str) -> str | None:
    """Return the best-matching skill name for a free-text request, or None.

    Conservative keyword routing — a suggestion aid, not an auto-dispatch.
    """
    t = f" {(text or '').lower()} "
    for name, cues in _ROUTER_CUES:
        if any(c in t for c in cues):
            return name
    return None


# ---------------------------------------------------------------------------
# Sub-agent primitive — token-isolated data gathering
# ---------------------------------------------------------------------------


async def run_subagent(
    task: str,
    *,
    db,
    user_id: str | None = None,
    tool_names: list[str] | None = None,
    symbols: list[str] | None = None,
    tier: str = "light",
    max_tokens: int = 400,
) -> str:
    """Run a focused sub-task on a cheap model with a scoped tool set and return
    a COMPACT text summary (non-streaming).

    This is the token-isolation building block for composite agents: a sub-agent
    does the heavy tool calls and returns a short digest, so the parent
    synthesizer never ingests raw tool dumps. Returns "" on failure.
    """
    from flowdesk_core.llm_platform import strip_thinking

    provider_name, model, api_key = resolve_platform_provider()
    api_base = provider_api_base(provider_name)
    parts: list[str] = []
    try:
        async for chunk in _gateway.stream_chat(
            provider_name=provider_name,
            model=model,
            api_key=api_key,
            messages=[{"role": "user", "content": task}],
            db=db,
            user_id=user_id,
            symbols=symbols,
            temperature=0.2,
            max_tokens=max_tokens,
            api_base=api_base,
            allow_routing=True,
            tool_names=tool_names or [],
            system_suffix=(
                "You are a focused data sub-agent. Use your tools to gather "
                "exactly what is asked, then reply with a concise, factual "
                "summary — no preamble, no caveats, just the findings."
            ),
            force_tier=tier,
        ):
            if chunk.get("delta"):
                parts.append(chunk["delta"])
    except Exception:
        return ""
    return strip_thinking("".join(parts)).strip()


# ---------------------------------------------------------------------------
# Runner — executes a skill through the shared gateway (platform mode)
# ---------------------------------------------------------------------------


async def run_skill(
    skill: Skill,
    *,
    db,
    user_id: str | None,
    user_text: str,
    symbols: list[str] | None = None,
    locale: str | None = None,
    max_tokens: int | None = None,
) -> AsyncIterator[dict]:
    """Run a skill and stream gateway chunks.

    Applies the skill's tool subset, focused system prompt, and model tier on top
    of NOVA's base context. Uses the platform provider (same proven path as chat).
    """
    provider_name, model, api_key = resolve_platform_provider()
    api_base = provider_api_base(provider_name)

    async for chunk in _gateway.stream_chat(
        provider_name=provider_name,
        model=model,
        api_key=api_key,
        messages=[{"role": "user", "content": user_text}],
        db=db,
        user_id=user_id,
        symbols=symbols,
        locale=locale,
        temperature=skill.temperature,
        max_tokens=max_tokens or skill.max_tokens,
        api_base=api_base,
        allow_routing=True,
        tool_names=list(skill.tools),
        system_suffix=skill.system_prompt,
        force_tier=skill.model_tier,
    ):
        yield chunk
