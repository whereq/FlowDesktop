"""Tier entitlements — role → tier resolution and per-tier caps."""

from flowdesk.entitlements import limit_for, roles_from_claims, tier_key, tier_label


def test_role_priority_admin_wins():
    assert tier_key(["fd-tier-1", "fd-admin"]) == "admin"


def test_tier_resolution():
    assert tier_key(["fd-tier-unlimited"]) == "unlimited"
    assert tier_key(["fd-tier-2"]) == "tier2"
    assert tier_key(["fd-tier-1"]) == "tier1"
    assert tier_key(["fd-tier-byok"]) == "byok"
    assert tier_key([]) == "free"


def test_highest_tier_when_multiple():
    assert tier_key(["fd-tier-1", "fd-tier-2"]) == "tier2"


def test_schedules_are_paid_only():
    assert limit_for([], "schedules") == 0  # free
    assert limit_for(["fd-tier-byok"], "schedules") == 0  # byok: no platform AI
    assert limit_for(["fd-tier-1"], "schedules") >= 1
    assert limit_for(["fd-admin"], "schedules") >= 1


def test_custom_agent_caps_scale_with_tier():
    assert limit_for([], "custom_agents") < limit_for(["fd-tier-1"], "custom_agents")
    assert limit_for(["fd-tier-1"], "custom_agents") < limit_for(["fd-tier-2"], "custom_agents")


def test_unknown_resource_is_zero():
    assert limit_for(["fd-admin"], "nonexistent") == 0


def test_roles_from_claims():
    assert roles_from_claims({"realm_access": {"roles": ["fd-tier-1"]}}) == ["fd-tier-1"]
    assert roles_from_claims({}) == []


def test_labels():
    assert tier_label([]) == "Free"
    assert tier_label(["fd-tier-2"]) == "Pro"
