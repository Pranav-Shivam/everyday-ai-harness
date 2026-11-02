import asyncio

import pytest

pytest.importorskip("mcp")

from everyday_harness import mcp_server  # noqa: E402
from everyday_harness.store import Store  # noqa: E402
from everyday_harness.tools import ToolRegistry  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_registry(store: Store, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mcp_server, "_registry", ToolRegistry(store))


def test_exposes_the_expected_tools() -> None:
    tools = asyncio.run(mcp_server.mcp.list_tools())
    assert {tool.name for tool in tools} == {
        "save_note",
        "search_notes",
        "add_task",
        "list_tasks",
        "update_task_status",
        "search_chats",
        "list_chat_sessions",
        "get_chat_session",
        "get_chat_day",
        "save_lesson",
        "list_lessons",
    }


def test_tools_share_python_validation() -> None:
    assert "error" in mcp_server.add_task("Bad date", "next Friday")
    task = mcp_server.add_task("Write docs", "2026-11-05")
    assert task["status"] == "open"
    assert mcp_server.update_task_status(task["id"], "done")["status"] == "done"
    assert "error" in mcp_server.update_task_status(task["id"], "deleted")


def test_note_round_trip() -> None:
    mcp_server.save_note("Weekly review is Friday afternoon", ["planning"])
    assert mcp_server.search_notes("weekly review")["count"] == 1


def test_chat_round_trip(store: Store) -> None:
    store.save_chat_messages(
        "s1",
        [{"external_id": "a", "role": "user", "content": "weekly review plan", "created_at": "2026-11-02T10:00:00Z"}],
    )
    assert mcp_server.search_chats("weekly review")["count"] == 1
    assert mcp_server.get_chat_session("s1")["messages"][0]["content"] == "weekly review plan"
    assert mcp_server.list_chat_sessions()["sessions"][0]["session_id"] == "s1"


def test_lesson_round_trip() -> None:
    saved = mcp_server.save_lesson(
        "2026-11-02", "user", "unclear_prompt", "Vague request", "user: 'do it'", "Say what 'it' is"
    )
    assert saved["status"] == "saved"
    assert mcp_server.list_lessons()["lessons"][0]["category"] == "unclear_prompt"
    assert "error" in mcp_server.save_lesson("2026-11-02", "robot", "other", "s", "e", "n")
