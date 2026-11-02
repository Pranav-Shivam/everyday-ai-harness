from everyday_harness.store import Store


def _msg(external_id: str, role: str, content: str, created_at: str = "2026-11-02T10:00:00+00:00") -> dict:
    return {"external_id": external_id, "role": role, "content": content, "created_at": created_at}


def test_save_redacts_secrets(store: Store) -> None:
    store.save_chat_messages("s1", [_msg("a", "user", "my key is sk-" + "a" * 24)])
    stored = store.get_chat_session("s1")[0]["content"]
    assert "sk-aaaa" not in stored
    assert "[REDACTED]" in stored


def test_save_is_idempotent(store: Store) -> None:
    messages = [_msg("a", "user", "hello")]
    assert store.save_chat_messages("s1", messages) == 1
    assert store.save_chat_messages("s1", messages) == 0
    assert len(store.get_chat_session("s1")) == 1


def test_truncates_long_content(store: Store) -> None:
    store.save_chat_messages(
        "s1",
        [_msg("a", "assistant", "x" * 9000), _msg("b", "tool_result", "y" * 900)],
    )
    first, second = store.get_chat_session("s1")
    assert len(first["content"]) == 8000 and first["content"].endswith("…[truncated]")
    assert len(second["content"]) == 500 and second["content"].endswith("…[truncated]")


def test_search_chats_finds_user_and_assistant_not_tool(store: Store) -> None:
    store.save_chat_messages(
        "s1",
        [
            _msg("a", "user", "what about the weekly review"),
            _msg("b", "tool_call", "search_notes weekly review"),
        ],
    )
    results = store.search_chats("weekly review")
    assert [r["role"] for r in results] == ["user"]
    assert results[0]["session_id"] == "s1"


def test_search_chats_stop_words_only_returns_empty(store: Store) -> None:
    store.save_chat_messages("s1", [_msg("a", "user", "show me the notes")])
    assert store.search_chats("the and show") == []


def test_list_chat_sessions_orders_newest_first_with_first_prompt(store: Store) -> None:
    store.save_chat_messages("old", [_msg("a", "user", "older question", "2026-11-01T09:00:00+00:00")])
    store.save_chat_messages(
        "new",
        [
            _msg("a", "assistant", "preamble", "2026-11-02T09:00:00+00:00"),
            _msg("b", "user", "newer question", "2026-11-02T09:01:00+00:00"),
        ],
    )
    sessions = store.list_chat_sessions()
    assert [s["session_id"] for s in sessions] == ["new", "old"]
    assert sessions[0]["first_prompt"] == "newer question"
    assert sessions[0]["message_count"] == 2
    assert sessions[0]["started_at"] == "2026-11-02T09:00:00+00:00"
    assert sessions[0]["last_at"] == "2026-11-02T09:01:00+00:00"


def test_get_chat_session_unknown_returns_empty(store: Store) -> None:
    assert store.get_chat_session("nope") == []
