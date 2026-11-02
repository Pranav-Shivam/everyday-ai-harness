"""A small allowlisted set of local tools."""

from __future__ import annotations

from datetime import date
from typing import Any, Callable

from .store import LESSON_WHO, Store


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


def _search_chats(store: Store, arguments: dict[str, Any]) -> dict[str, Any]:
    query = _required_text(arguments.get("query"), "query", 300)
    messages = store.search_chats(query, limit=5)
    return {"count": len(messages), "messages": messages}


def _list_chat_sessions(store: Store, arguments: dict[str, Any]) -> dict[str, Any]:
    return {"sessions": store.list_chat_sessions(limit=10)}


def _offset(arguments: dict[str, Any]) -> int:
    value = arguments.get("offset", 0)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ToolError("offset must be a non-negative integer")
    return value


def _page(rows: list[dict[str, Any]], page_size: int, offset: int) -> tuple[list[dict[str, Any]], bool, int | None]:
    """Split rows fetched with one extra item into (page, truncated, next_offset)."""
    truncated = len(rows) > page_size
    return rows[:page_size], truncated, offset + page_size if truncated else None


def _get_chat_session(store: Store, arguments: dict[str, Any]) -> dict[str, Any]:
    session_id = _required_text(arguments.get("session_id"), "session_id", 100)
    offset = _offset(arguments)
    rows = store.get_chat_session(session_id, limit=201, offset=offset)
    if not rows and offset == 0:
        raise ToolError("Session not found")
    messages, truncated, next_offset = _page(rows, 200, offset)
    return {"session_id": session_id, "messages": messages, "truncated": truncated, "next_offset": next_offset}


def _iso_date(value: Any, field: str) -> str:
    text = _required_text(value, field, 10)
    try:
        if len(text) != 10 or text[4] != "-" or text[7] != "-":
            raise ValueError("incorrect date shape")
        date.fromisoformat(text)
    except ValueError as exc:
        raise ToolError(f"{field} must use YYYY-MM-DD format") from exc
    return text


def _get_chat_day(store: Store, arguments: dict[str, Any]) -> dict[str, Any]:
    day = _iso_date(arguments.get("day"), "day")
    offset = _offset(arguments)
    messages, truncated, next_offset = _page(store.get_chat_day(day, limit=401, offset=offset), 400, offset)
    return {"day": day, "count": len(messages), "messages": messages, "truncated": truncated, "next_offset": next_offset}


def _save_lesson(store: Store, arguments: dict[str, Any]) -> dict[str, Any]:
    lesson_date = _iso_date(arguments.get("lesson_date"), "lesson_date")
    who = _required_text(arguments.get("who"), "who", 20)
    category = _required_text(arguments.get("category"), "category", 40)
    summary = _required_text(arguments.get("summary"), "summary", 300)
    evidence = _required_text(arguments.get("evidence"), "evidence", 1000)
    next_time = _required_text(arguments.get("next_time"), "next_time", 300)
    try:
        return store.save_lesson(lesson_date, who, category, summary, evidence, next_time)
    except ValueError as exc:
        raise ToolError(str(exc)) from exc


def _list_lessons(store: Store, arguments: dict[str, Any]) -> dict[str, Any]:
    since = arguments.get("since")
    if since is not None:
        since = _iso_date(since, "since")
    who = arguments.get("who")
    if who is not None and who not in LESSON_WHO:
        raise ToolError("who must be 'user' or 'assistant'")
    return {"lessons": store.list_lessons(since=since, who=who)}


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
            # Read-only chat history tools for Claude Code. Deliberately absent from `definitions`,
            # so the Python harness model is never offered them.
            "search_chats": lambda args: _search_chats(self.store, args),
            "list_chat_sessions": lambda args: _list_chat_sessions(self.store, args),
            "get_chat_session": lambda args: _get_chat_session(self.store, args),
            "get_chat_day": lambda args: _get_chat_day(self.store, args),
            "save_lesson": lambda args: _save_lesson(self.store, args),
            "list_lessons": lambda args: _list_lessons(self.store, args),
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

    def execute(self, name: str, arguments: dict[str, Any], *, advertised_only: bool = False) -> dict[str, Any]:
        """Run a tool. With advertised_only, refuse tools missing from `definitions` (the Python harness)."""
        advertised = {definition["function"]["name"] for definition in self.definitions}
        if name not in self._functions or (advertised_only and name not in advertised):
            return {"error": f"Tool '{name}' is not allowed."}
        if not isinstance(arguments, dict):
            return {"error": "Tool arguments must be a JSON object."}
        try:
            return self._functions[name](arguments)
        except ToolError as exc:
            return {"error": str(exc)}
        except Exception as exc:
            return {"error": f"Tool execution failed: {type(exc).__name__}"}
