"""A small allowlisted set of local tools."""

from __future__ import annotations

from datetime import date
from typing import Any, Callable

from .store import Store


class ToolError(ValueError):
    """Raised when a tool receives invalid input."""


def _required_text(value: Any, field: str, max_length: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ToolError(f"{field} must be a non-empty string")
    clean = value.strip()
    if len(clean) > max_length:
        raise ToolError(f"{field} must be {max_length} characters or fewer")
    return clean


def _save_note(store: Store, arguments: dict[str, Any]) -> dict[str, Any]:
    content = _required_text(arguments.get("content"), "content", 5000)
    tags = arguments.get("tags", [])
    if not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags):
        raise ToolError("tags must be a list of strings")
    if len(tags) > 8:
        raise ToolError("A note can have at most 8 tags")
    return store.save_note(content, tags)


def _search_notes(store: Store, arguments: dict[str, Any]) -> dict[str, Any]:
    query = _required_text(arguments.get("query"), "query", 300)
    notes = store.search_notes(query, limit=5)
    return {"count": len(notes), "notes": notes}


def _add_task(store: Store, arguments: dict[str, Any]) -> dict[str, Any]:
    title = _required_text(arguments.get("title"), "title", 300)
    due_date = arguments.get("due_date")
    if due_date is not None:
        if not isinstance(due_date, str):
            raise ToolError("due_date must be an ISO date string or null")
        try:
            if len(due_date) != 10 or due_date[4] != "-" or due_date[7] != "-":
                raise ValueError("incorrect date shape")
            date.fromisoformat(due_date)
        except ValueError as exc:
            raise ToolError("due_date must use YYYY-MM-DD format") from exc
    return store.add_task(title, due_date)


def _update_task_status(store: Store, arguments: dict[str, Any]) -> dict[str, Any]:
    task_id = arguments.get("task_id")
    if isinstance(task_id, bool) or not isinstance(task_id, int) or task_id < 1:
        raise ToolError("task_id must be a positive integer")
    status = arguments.get("status")
    if not isinstance(status, str) or status not in {"open", "done"}:
        raise ToolError("status must be 'open' or 'done'")
    try:
        return store.update_task_status(task_id, status)
    except ValueError as exc:
        raise ToolError(str(exc)) from exc


def _list_tasks(store: Store, arguments: dict[str, Any]) -> dict[str, Any]:
    status = arguments.get("status", "open")
    if not isinstance(status, str) or status not in {"open", "done", "all"}:
        raise ToolError("status must be 'open', 'done', or 'all'")
    return {"tasks": store.list_tasks(status=status), "status_filter": status}


class ToolRegistry:
    """Executes only explicitly registered functions."""

    def __init__(self, store: Store) -> None:
        self.store = store
        self._functions: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
            "save_note": lambda args: _save_note(self.store, args),
            "search_notes": lambda args: _search_notes(self.store, args),
            "add_task": lambda args: _add_task(self.store, args),
            "list_tasks": lambda args: _list_tasks(self.store, args),
            "update_task_status": lambda args: _update_task_status(self.store, args),
        }

    @property
    def definitions(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "save_note",
                    "description": "Save a note only when the user explicitly asks you to remember or record information.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "content": {"type": "string", "description": "The note to save."},
                            "tags": {"type": "array", "items": {"type": "string"}, "description": "Optional short tags."},
                        },
                        "required": ["content"],
                        "additionalProperties": False,
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "search_notes",
                    "description": "Search the user's saved notes when they ask about previously stored information.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Keywords to find in saved notes."}
                        },
                        "required": ["query"],
                        "additionalProperties": False,
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "add_task",
                    "description": "Add a task to the user's local task list when they explicitly ask.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string", "description": "A clear task title."},
                            "due_date": {"type": ["string", "null"], "description": "Optional due date in YYYY-MM-DD format."},
                        },
                        "required": ["title"],
                        "additionalProperties": False,
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "update_task_status",
                    "description": "Change a task between open and done only when the user explicitly asks to mark it complete or reopen it.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "task_id": {"type": "integer", "minimum": 1},
                            "status": {"type": "string", "enum": ["open", "done"]},
                        },
                        "required": ["task_id", "status"],
                        "additionalProperties": False,
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "list_tasks",
                    "description": "List tasks from the user's local task list.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "status": {"type": "string", "enum": ["open", "done", "all"]}
                        },
                        "required": [],
                        "additionalProperties": False,
                    },
                },
            },
        ]

    @property
    def names(self) -> set[str]:
        return set(self._functions)

    def execute(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name not in self._functions:
            return {"error": f"Tool '{name}' is not allowed."}
        if not isinstance(arguments, dict):
            return {"error": "Tool arguments must be a JSON object."}
        try:
            return self._functions[name](arguments)
        except ToolError as exc:
            return {"error": str(exc)}
        except Exception as exc:
            return {"error": f"Tool execution failed: {type(exc).__name__}"}
