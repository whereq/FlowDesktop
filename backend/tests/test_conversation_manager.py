"""Conversation compaction (token optimization) — the long-chat cost guard."""

from api.services.conversation_manager import _HISTORY_SOFT_CAP_TOKENS, ConversationManager


def _cm():
    return ConversationManager()


def test_short_conversation_passes_through_untouched():
    msgs = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
        {"role": "user", "content": "thanks"},
    ]
    out = _cm().prepare_messages(msgs, context="SYS", model="minimax-01")
    assert out[0] == {"role": "system", "content": "SYS"}
    assert not any("Summary of earlier" in m["content"] for m in out)
    assert [m["content"] for m in out[1:]] == ["hi", "hello", "thanks"]


def test_long_conversation_is_compacted_under_soft_cap():
    msgs = []
    for i in range(40):
        msgs.append({"role": "user", "content": f"Q{i} " + "x" * 600})
        msgs.append({"role": "assistant", "content": f"A{i} " + "y" * 600})
    msgs.append({"role": "user", "content": "FINAL question"})

    out = _cm().prepare_messages(msgs, context="SYS", model="minimax-01", max_tokens=4096)

    # The current turn is always preserved verbatim.
    assert out[-1]["content"] == "FINAL question"
    # Older turns are collapsed into one summary block.
    assert any(m["role"] == "system" and "Summary of earlier" in m["content"] for m in out)
    # Forwarded history stays near the soft cap, not the full 1M window.
    approx_tokens = sum(len(m["content"]) for m in out) // 4
    assert approx_tokens <= _HISTORY_SOFT_CAP_TOKENS + 2000
    assert len(out) < len(msgs)


def test_oversized_final_message_is_never_dropped():
    huge = "x" * 100_000
    out = _cm().prepare_messages(
        [{"role": "user", "content": huge}], context="SYS", model="minimax-01"
    )
    assert out[-1]["content"] == huge


def test_empty_history():
    out = _cm().prepare_messages([], context="SYS", model="minimax-01")
    assert out == [{"role": "system", "content": "SYS"}]
