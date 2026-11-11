"""Notification push gating — per-type toggles + overnight-aware quiet hours."""

from datetime import UTC, datetime

from flowdesk_core.models.notification_prefs import NotificationPrefs, _in_quiet_window

UTC_NOON = datetime(2026, 1, 1, 12, tzinfo=UTC)
UTC_NIGHT = datetime(2026, 1, 1, 23, tzinfo=UTC)


def test_quiet_window_same_day():
    assert _in_quiet_window(10, 9, 17)
    assert not _in_quiet_window(8, 9, 17)
    assert not _in_quiet_window(17, 9, 17)  # end is exclusive


def test_quiet_window_overnight_wrap():
    assert _in_quiet_window(23, 22, 7)
    assert _in_quiet_window(3, 22, 7)
    assert not _in_quiet_window(12, 22, 7)


def test_quiet_window_equal_bounds_is_never_quiet():
    assert not _in_quiet_window(5, 8, 8)


def test_per_type_toggle_blocks_only_its_category():
    p = NotificationPrefs(
        keycloak_id=None,
        push_alerts=False,
        push_volume=True,
        push_signals=True,
        push_agent=True,
        quiet_enabled=False,
    )
    assert not p.allows_push("alert_triggered", UTC_NOON)
    assert p.allows_push("agent_brief", UTC_NOON)
    assert p.allows_push("volume_spike", UTC_NOON)


def test_signals_toggle_covers_news_and_sentiment():
    p = NotificationPrefs(keycloak_id=None, push_signals=False, quiet_enabled=False)
    assert not p.allows_push("news_signal", UTC_NOON)
    assert not p.allows_push("sentiment_shift", UTC_NOON)


def test_events_toggle_gates_event_reminders():
    p = NotificationPrefs(keycloak_id=None, push_events=False, quiet_enabled=False)
    assert not p.allows_push("event_reminder", UTC_NOON)
    on = NotificationPrefs(keycloak_id=None, push_events=True, quiet_enabled=False)
    assert on.allows_push("event_reminder", UTC_NOON)


def test_unknown_type_is_allowed():
    p = NotificationPrefs(keycloak_id=None, quiet_enabled=False)
    assert p.allows_push("some_future_type", UTC_NOON)


def test_unset_instance_defaults_to_allow():
    # Fresh instance has None fields (no DB insert); must not silently block.
    p = NotificationPrefs(keycloak_id=None)
    assert p.allows_push("alert_triggered", UTC_NOON)


def test_quiet_hours_suppresses_then_allows():
    p = NotificationPrefs(
        keycloak_id=None, quiet_enabled=True, quiet_start=22, quiet_end=7, tz="UTC"
    )
    assert not p.allows_push("agent_brief", UTC_NIGHT)
    assert p.allows_push("agent_brief", UTC_NOON)
