"""Local SQLite persistence for notes and tasks."""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class Store:
    def __init__(self, database_path: Path | str) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialise()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialise(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    tags TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    due_date TEXT,
                    status TEXT NOT NULL DEFAULT 'open',
                    created_at TEXT NOT NULL
                );
                """
            )

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def save_note(self, content: str, tags: list[str] | None = None) -> dict[str, Any]:
        clean_tags = [str(tag).strip()[:40] for tag in (tags or []) if str(tag).strip()]
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO notes (content, tags, created_at) VALUES (?, ?, ?)",
                (content, json.dumps(clean_tags), self._now()),
            )
            note_id = int(cursor.lastrowid)
        return {"id": note_id, "content": content, "tags": clean_tags, "status": "saved"}

    def search_notes(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        stop_words = {"about", "after", "again", "also", "and", "are", "for", "from", "find", "have", "help", "into", "just", "list", "look", "more", "note", "notes", "please", "show", "that", "the", "their", "this", "what", "when", "where", "with", "your", "you"}
        terms = [term for term in dict.fromkeys(re.findall(r"[a-zA-Z0-9]{3,}", query.lower())) if term not in stop_words]
        if not terms:
            return []

        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id, content, tags, created_at FROM notes ORDER BY id DESC LIMIT 500"
            ).fetchall()

        scored: list[tuple[int, int, dict[str, Any]]] = []
        for row in rows:
            haystack = f"{row['content']} {' '.join(json.loads(row['tags']))}".lower()
            score = sum(1 for term in terms if term in haystack)
            if score:
                scored.append(
                    (
                        score,
                        int(row["id"]),
                        {
                            "id": int(row["id"]),
                            "content": row["content"],
                            "tags": json.loads(row["tags"]),
                            "created_at": row["created_at"],
                        },
                    )
                )

        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [item[2] for item in scored[: max(1, min(limit, 20))]]

    def relevant_notes(self, query: str, limit: int = 3) -> list[dict[str, Any]]:
        """Retrieve a few relevant notes for context, not the entire memory store."""
        return self.search_notes(query, limit=limit)

    def add_task(self, title: str, due_date: str | None = None) -> dict[str, Any]:
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO tasks (title, due_date, status, created_at) VALUES (?, ?, 'open', ?)",
                (title, due_date, self._now()),
            )
            task_id = int(cursor.lastrowid)
        return {"id": task_id, "title": title, "due_date": due_date, "status": "open"}

    def update_task_status(self, task_id: int, status: str) -> dict[str, Any]:
        if status not in {"open", "done"}:
            raise ValueError("status must be 'open' or 'done'")
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE tasks SET status = ? WHERE id = ?",
                (status, task_id),
            )
            if cursor.rowcount == 0:
                raise ValueError(f"Task {task_id} was not found")
            row = connection.execute(
                "SELECT id, title, due_date, status, created_at FROM tasks WHERE id = ?",
                (task_id,),
            ).fetchone()
        return dict(row)

    def list_tasks(self, status: str = "open", limit: int = 50) -> list[dict[str, Any]]:
        if status not in {"open", "done", "all"}:
            raise ValueError("status must be 'open', 'done', or 'all'")

        query = "SELECT id, title, due_date, status, created_at FROM tasks"
        parameters: tuple[Any, ...]
        if status == "all":
            parameters = (max(1, min(limit, 100)),)
            query += " ORDER BY CASE status WHEN 'open' THEN 0 ELSE 1 END, id DESC LIMIT ?"
        else:
            parameters = (status, max(1, min(limit, 100)))
            query += " WHERE status = ? ORDER BY id DESC LIMIT ?"

        with self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [dict(row) for row in rows]
