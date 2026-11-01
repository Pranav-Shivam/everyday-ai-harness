"""Expose the same five local tools to Claude Code over MCP (stdio).

Validation lives in ToolRegistry, so the Python harness and the Claude Code
harness share one set of rules and one SQLite schema.
"""

from __future__ import annotations

import os
from typing import Any

from dotenv import find_dotenv, load_dotenv
from mcp.server.fastmcp import FastMCP

from .store import Store
from .tools import ToolRegistry

# Claude Code starts this server from claude-code/, so search upward for the repo-root .env.
load_dotenv(find_dotenv(usecwd=True))

mcp = FastMCP("everyday")
_registry: ToolRegistry | None = None


def registry() -> ToolRegistry:
    global _registry
    if _registry is None:
        _registry = ToolRegistry(Store(os.getenv("HARNESS_DATABASE", "data/harness.sqlite3")))
    return _registry


@mcp.tool()
def save_note(content: str, tags: list[str] | None = None) -> dict[str, Any]:
    """Save a note only when the user explicitly asks you to remember or record information."""
    return registry().execute("save_note", {"content": content, "tags": tags or []})


@mcp.tool()
def search_notes(query: str) -> dict[str, Any]:
    """Search the user's saved notes when they ask about previously stored information."""
    return registry().execute("search_notes", {"query": query})


@mcp.tool()
def add_task(title: str, due_date: str | None = None) -> dict[str, Any]:
    """Add a task to the user's local task list when they explicitly ask. due_date is YYYY-MM-DD."""
    return registry().execute("add_task", {"title": title, "due_date": due_date})


@mcp.tool()
def list_tasks(status: str = "open") -> dict[str, Any]:
    """List tasks from the user's local task list. status is open, done, or all."""
    return registry().execute("list_tasks", {"status": status})


@mcp.tool()
def update_task_status(task_id: int, status: str) -> dict[str, Any]:
    """Mark a task open or done only when the user explicitly asks to complete or reopen it."""
    return registry().execute("update_task_status", {"task_id": task_id, "status": status})


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
