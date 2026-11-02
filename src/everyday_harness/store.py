"""Local SQLite persistence for notes and tasks."""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .redact import redact

_STOP_WORDS = {"about", "after", "again", "also", "and", "are", "for", "from", "find", "have", "help", "into", "just", "list", "look", "more", "note", "notes", "please", "show", "that", "the", "their", "this", "what", "when", "where", "with", "your", "you"}
_TRUNCATED = "…[truncated]"
_CHAT_LIMITS = {"tool_result": 500}
_CHAT_DEFAULT_LIMIT = 8000
LESSON_WHO = ("user", "assistant")
LESSON_CATEGORIES = (
    "unclear_prompt",
    "missing_detail",
    "changed_mind",
    "acted_without_asking",
    "assumed_instead_of_checking",
    "claimed_without_proof",
    "invented_fact",
    "other",
)


def _search_terms(query: str) -> list[str]:
    return [term for term in dict.fromkeys(re.findall(r"[a-zA-Z0-9]{3,}", query.lower())) if term not in _STOP_WORDS]


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - len(_TRUNCATED)] + _TRUNCATED


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

                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    external_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(session_id, external_id)
                );
                CREATE TABLE IF NOT EXISTS lessons (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lesson_date TEXT NOT NULL,
                    who TEXT NOT NULL,
                    category TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    evidence TEXT NOT NULL,
                    next_time TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON chat_messages(session_id);
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
        terms = _search_terms(query)
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

    def save_chat_messages(self, session_id: str, messages: list[dict[str, Any]]) -> int:
        """Redact, clip and insert messages. Returns how many were new."""
        rows = [
            (
                session_id,
                message["external_id"],
                message["role"],
                _clip(redact(message["content"]), _CHAT_LIMITS.get(message["role"], _CHAT_DEFAULT_LIMIT)),
                message["created_at"],
            )
            for message in messages
        ]
        with self._connect() as connection:
            before = connection.total_changes
            connection.executemany(
                "INSERT OR IGNORE INTO chat_messages (session_id, external_id, role, content, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                rows,
            )
            return connection.total_changes - before

    def search_chats(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        terms = _search_terms(query)
        if not terms:
            return []

        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id, session_id, role, content, created_at FROM chat_messages "
                "WHERE role IN ('user', 'assistant') ORDER BY id DESC LIMIT 2000"
            ).fetchall()

        scored: list[tuple[int, int, dict[str, Any]]] = []
        for row in rows:
            score = sum(1 for term in terms if term in row["content"].lower())
            if score:
                scored.append(
                    (
                        score,
                        int(row["id"]),
                        {
                            "session_id": row["session_id"],
                            "role": row["role"],
                            "content": row["content"][:500],
                            "created_at": row["created_at"],
                        },
                    )
                )

        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [item[2] for item in scored[: max(1, min(limit, 20))]]

    def list_chat_sessions(self, limit: int = 10) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT session_id,
                       MIN(created_at) AS started_at,
                       MAX(created_at) AS last_at,
                       COUNT(*) AS message_count,
                       (SELECT substr(content, 1, 120) FROM chat_messages u
                         WHERE u.session_id = m.session_id AND u.role = 'user'
                         ORDER BY u.id LIMIT 1) AS first_prompt
                FROM chat_messages m
                GROUP BY session_id
                ORDER BY last_at DESC, MAX(id) DESC
                LIMIT ?
                """,
                (max(1, min(limit, 50)),),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_chat_session(self, session_id: str, limit: int = 200, offset: int = 0) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT role, content, created_at FROM chat_messages WHERE session_id = ? ORDER BY id LIMIT ? OFFSET ?",
                (session_id, max(1, min(limit, 1000)), max(0, offset)),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_chat_day(self, day: str, limit: int = 400, offset: int = 0) -> list[dict[str, Any]]:
        """Messages from one local calendar day (YYYY-MM-DD), oldest first, content clipped."""
        local_start = datetime.fromisoformat(day).astimezone()
        local_end = (datetime.fromisoformat(day) + timedelta(days=1)).astimezone()
        # Stored timestamps are UTC strings in mixed formats, so narrow by date prefix, then compare exactly.
        low = local_start.astimezone(timezone.utc).date().isoformat()
        high = (local_end.astimezone(timezone.utc).date() + timedelta(days=1)).isoformat()
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT session_id, role, content, created_at FROM chat_messages "
                "WHERE created_at >= ? AND created_at < ? ORDER BY id",
                (low, high),
            ).fetchall()

        cap = max(1, min(limit, 1000))
        skip = max(0, offset)
        selected: list[dict[str, Any]] = []
        for row in rows:
            try:
                moment = datetime.fromisoformat(row["created_at"])
            except ValueError:
                continue
            if moment.tzinfo is None:
                moment = moment.replace(tzinfo=timezone.utc)
            if local_start <= moment < local_end:
                if skip:
                    skip -= 1
                    continue
                selected.append({**dict(row), "content": _clip(row["content"], 1500)})
                if len(selected) >= cap:
                    break
        return selected

    def save_lesson(
        self, lesson_date: str, who: str, category: str, summary: str, evidence: str, next_time: str
    ) -> dict[str, Any]:
        if who not in LESSON_WHO:
            raise ValueError("who must be 'user' or 'assistant'")
        if category not in LESSON_CATEGORIES:
            raise ValueError(f"category must be one of: {', '.join(LESSON_CATEGORIES)}")
        summary, evidence, next_time = redact(summary), redact(evidence), redact(next_time)
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO lessons (lesson_date, who, category, summary, evidence, next_time, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (lesson_date, who, category, summary, evidence, next_time, self._now()),
            )
            lesson_id = int(cursor.lastrowid)
        return {
            "id": lesson_id,
            "lesson_date": lesson_date,
            "who": who,
            "category": category,
            "summary": summary,
            "evidence": evidence,
            "next_time": next_time,
            "status": "saved",
        }

    def list_lessons(self, since: str | None = None, who: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id, lesson_date, who, category, summary, evidence, next_time FROM lessons "
                "WHERE (? IS NULL OR lesson_date >= ?) AND (? IS NULL OR who = ?) "
                "ORDER BY lesson_date DESC, id DESC LIMIT ?",
                (since, since, who, who, max(1, min(limit, 100))),
            ).fetchall()
        return [dict(row) for row in rows]

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
