import pytest

from everyday_harness.store import Store
from everyday_harness.tools import ToolRegistry


def test_save_and_search_note(store: Store) -> None:
    registry = ToolRegistry(store)

    saved = registry.execute(
        "save_note",
        {"content": "My weekly planning review is on Friday afternoon.", "tags": ["planning"]},
    )
    assert saved["status"] == "saved"
    assert saved["id"] > 0

    found = registry.execute("search_notes", {"query": "weekly planning review"})
    assert found["count"] == 1
    assert "Friday afternoon" in found["notes"][0]["content"]


def test_add_and_list_tasks(store: Store) -> None:
    registry = ToolRegistry(store)

    task = registry.execute(
        "add_task",
        {"title": "Review the harness README", "due_date": "2026-11-05"},
    )
    assert task["status"] == "open"
    assert task["due_date"] == "2026-11-05"

    listed = registry.execute("list_tasks", {"status": "open"})
    assert len(listed["tasks"]) == 1
    assert listed["tasks"][0]["title"] == "Review the harness README"


def test_invalid_date_is_rejected(store: Store) -> None:
    registry = ToolRegistry(store)
    result = registry.execute("add_task", {"title": "Test date", "due_date": "next Friday"})
    assert "error" in result
    assert "YYYY-MM-DD" in result["error"]
    alternate = registry.execute("add_task", {"title": "Bad ISO week date", "due_date": "2026-W44-5"})
    assert "error" in alternate


def test_unknown_tool_is_blocked(store: Store) -> None:
    registry = ToolRegistry(store)
    result = registry.execute("delete_everything", {})
    assert "error" in result
    assert "not allowed" in result["error"]


def test_note_size_limit_is_enforced(store: Store) -> None:
    registry = ToolRegistry(store)
    result = registry.execute("save_note", {"content": "x" * 5001})
    assert "error" in result
    assert "5000" in result["error"]


def test_task_status_changes_only_for_valid_task(store: Store) -> None:
    registry = ToolRegistry(store)
    task = registry.execute("add_task", {"title": "Prepare weekly review"})

    updated = registry.execute(
        "update_task_status",
        {"task_id": task["id"], "status": "done"},
    )
    assert updated["status"] == "done"

    done_tasks = registry.execute("list_tasks", {"status": "done"})
    assert len(done_tasks["tasks"]) == 1
    assert done_tasks["tasks"][0]["title"] == "Prepare weekly review"


def test_unknown_task_status_update_is_rejected(store: Store) -> None:
    registry = ToolRegistry(store)
    result = registry.execute("update_task_status", {"task_id": 999, "status": "done"})
    assert "error" in result
    assert "not found" in result["error"]


def test_chat_tools_validate_input(store: Store) -> None:
    registry = ToolRegistry(store)
    assert "query" in registry.execute("search_chats", {"query": ""})["error"]
    assert "query" in registry.execute("search_chats", {"query": "x" * 301})["error"]
    assert "session_id" in registry.execute("get_chat_session", {"session_id": 5})["error"]
    assert "session_id" in registry.execute("get_chat_session", {"session_id": "s" * 101})["error"]


def test_unknown_session_is_an_error_not_a_crash(store: Store) -> None:
    result = ToolRegistry(store).execute("get_chat_session", {"session_id": "nope"})
    assert result == {"error": "Session not found"}


def test_chat_search_and_list_round_trip(store: Store) -> None:
    store.save_chat_messages(
        "s1",
        [{"external_id": "a", "role": "user", "content": "weekly review plan", "created_at": "2026-11-02T10:00:00Z"}],
    )
    registry = ToolRegistry(store)
    assert registry.execute("search_chats", {"query": "weekly review"})["count"] == 1
    assert registry.execute("search_chats", {"query": "the and"}) == {"count": 0, "messages": []}
    assert registry.execute("list_chat_sessions", {})["sessions"][0]["session_id"] == "s1"
    assert registry.execute("get_chat_session", {"session_id": "s1"})["messages"][0]["role"] == "user"


def test_python_harness_still_advertises_five_tools(store: Store) -> None:
    names = {d["function"]["name"] for d in ToolRegistry(store).definitions}
    assert names == {"save_note", "search_notes", "add_task", "update_task_status", "list_tasks"}


def _seed(store: Store, count: int, day_stamp: str = "2026-11-02T12:00:00+00:00") -> None:
    store.save_chat_messages(
        "big",
        [{"external_id": f"m{i}", "role": "user", "content": f"msg {i}", "created_at": day_stamp} for i in range(count)],
    )


def test_get_chat_session_reports_truncation_and_pages(store: Store) -> None:
    _seed(store, 250)
    registry = ToolRegistry(store)
    first = registry.execute("get_chat_session", {"session_id": "big"})
    assert len(first["messages"]) == 200 and first["truncated"] is True and first["next_offset"] == 200
    second = registry.execute("get_chat_session", {"session_id": "big", "offset": first["next_offset"]})
    assert len(second["messages"]) == 50 and second["truncated"] is False and second["next_offset"] is None
    assert second["messages"][0]["content"] == "msg 200"
    assert "offset" in registry.execute("get_chat_session", {"session_id": "big", "offset": -1})["error"]


def test_get_chat_day_reports_truncation_and_pages(store: Store) -> None:
    from datetime import datetime, timezone

    local_noon = datetime.fromisoformat("2026-11-02").replace(hour=12).astimezone().astimezone(timezone.utc)
    _seed(store, 450, local_noon.isoformat(timespec="seconds"))
    registry = ToolRegistry(store)
    first = registry.execute("get_chat_day", {"day": "2026-11-02"})
    assert first["count"] == 400 and first["truncated"] is True and first["next_offset"] == 400
    second = registry.execute("get_chat_day", {"day": "2026-11-02", "offset": 400})
    assert second["count"] == 50 and second["truncated"] is False and second["next_offset"] is None
