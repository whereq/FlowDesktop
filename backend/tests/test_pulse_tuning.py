"""NOVA Pulse auto-tuning — pure decide_cutoff decision logic (no DB)."""

from flowdesk_collector.pulse import decide_cutoff

KW = {"min_votes": 8, "step": 0.03, "lo": 0.15, "hi": 0.5}


def test_below_quorum_holds():
    new, why = decide_cutoff(0.25, up=3, down=1, **KW)  # 4 < 8
    assert new == 0.25 and "insufficient" in why


def test_zero_votes_holds():
    new, why = decide_cutoff(0.25, up=0, down=0, **KW)
    assert new == 0.25 and "insufficient" in why


def test_low_approval_raises_cutoff():
    # 10 votes, 30% approval → be more selective
    new, why = decide_cutoff(0.25, up=3, down=7, **KW)
    assert new == 0.28 and "raise" in why


def test_high_approval_lowers_cutoff():
    # 10 votes, 90% approval → widen coverage
    new, why = decide_cutoff(0.25, up=9, down=1, **KW)
    assert new == 0.22 and "lower" in why


def test_mid_approval_holds():
    new, why = decide_cutoff(0.25, up=6, down=4, **KW)  # 60%
    assert new == 0.25 and "hold" in why


def test_raise_clamped_at_max():
    new, why = decide_cutoff(0.50, up=1, down=9, **KW)
    assert new == 0.50 and "max" in why


def test_lower_clamped_at_min():
    new, why = decide_cutoff(0.15, up=10, down=0, **KW)
    assert new == 0.15 and "min" in why
