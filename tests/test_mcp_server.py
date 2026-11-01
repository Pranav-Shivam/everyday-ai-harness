import asyncio

import pytest

pytest.importorskip("mcp")

from everyday_harness import mcp_server  # noqa: E402
from everyday_harness.store import Store  # noqa: E402
from everyday_harness.tools import ToolRegistry  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_registry(store: Store, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mcp_server, "_registry", ToolRegistry(store))


def test_exposes_exactly_the_five_tools() -> None:
    tools = asyncio.run(mcp_server.mcp.list_tools())
    assert {tool.name for tool in tools} == {
        "save_note",
        "search_notes",
        "add_task",
        "list_tasks",
        "update_task_status",
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
