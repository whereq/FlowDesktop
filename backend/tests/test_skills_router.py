"""Agent suggestion router — keyword classification used by the chat chip."""

from api.services.skills import SKILLS, classify_skill, get_skill, list_skills


def test_compare_intent_routes_to_comparator():
    assert classify_skill("Compare NVDA vs AMD") == "stock_comparator"


def test_portfolio_intent_routes_to_doctor():
    assert classify_skill("how's my portfolio doing?") == "portfolio_doctor"


def test_strategy_intent_routes_to_architect():
    assert classify_skill("build me a swing trade plan for TSLA") == "strategy_architect"


def test_research_intent_routes_to_analyst():
    assert classify_skill("give me a deep dive on AAPL") == "research_analyst"


def test_catalyst_intent_routes_to_tracker():
    assert classify_skill("when does NVDA report earnings?") == "catalyst_tracker"
    assert classify_skill("any upcoming dividends in my list") == "catalyst_tracker"


def test_unmatched_returns_none():
    assert classify_skill("hello there") is None
    assert classify_skill("") is None


def test_registry_is_well_formed():
    agents = list_skills()
    assert len(agents) == len(SKILLS) >= 4
    for a in agents:
        assert get_skill(a["name"]) is not None
        # every catalog tool list is non-empty and the tier is valid
        assert a["model_tier"] in {"auto", "light", "heavy"}
