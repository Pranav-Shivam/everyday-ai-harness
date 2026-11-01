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
