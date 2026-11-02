from datetime import datetime, timezone

from everyday_harness.store import Store
from everyday_harness.tools import ToolRegistry


def _local_utc(day: str, hour: int, minute: int = 0) -> str:
    """UTC ISO timestamp for a local wall-clock time on `day`."""
    local = datetime.fromisoformat(day).replace(hour=hour, minute=minute).astimezone()
    return local.astimezone(timezone.utc).isoformat(timespec="seconds")


def _msg(external_id: str, created_at: str, content: str = "hi", role: str = "user") -> dict:
    return {"external_id": external_id, "role": role, "content": content, "created_at": created_at}


def _lesson_args(**overrides) -> dict:
    args = {
        "lesson_date": "2026-11-02",
        "who": "assistant",
        "category": "acted_without_asking",
        "summary": "Saved a note from a vague request",
        "evidence": "user: 'maybe note that down?'",
        "next_time": "Ask whether to save before saving",
    }
    return {**args, **overrides}


def test_get_chat_day_uses_local_calendar_day(store: Store) -> None:
    store.save_chat_messages(
        "s1",
        [
            _msg("late", _local_utc("2026-11-02", 23, 30), "late evening"),
            _msg("next", _local_utc("2026-11-03", 0, 30), "next day"),
            _msg("early", _local_utc("2026-11-02", 0, 15), "early morning"),
        ],
    )
    contents = [m["content"] for m in store.get_chat_day("2026-11-02")]
    assert sorted(contents) == ["early morning", "late evening"]


def test_get_chat_day_empty_and_capped(store: Store) -> None:
    assert store.get_chat_day("2026-11-02") == []
    stamp = _local_utc("2026-11-02", 12)
    store.save_chat_messages("s1", [_msg(f"m{i}", stamp, "x" * 100) for i in range(500)])
    assert len(store.get_chat_day("2026-11-02")) == 400
    store.save_chat_messages("s2", [_msg("long", stamp, "y" * 3000)])
    assert max(len(m["content"]) for m in store.get_chat_day("2026-11-02", limit=1000)) == 1500


def test_save_lesson_rejects_bad_who_category_and_date(store: Store) -> None:
    registry = ToolRegistry(store)
    assert "who" in registry.execute("save_lesson", _lesson_args(who="robot"))["error"]
    assert "category" in registry.execute("save_lesson", _lesson_args(category="bad"))["error"]
    assert "lesson_date" in registry.execute("save_lesson", _lesson_args(lesson_date="yesterday"))["error"]
    assert "summary" in registry.execute("save_lesson", _lesson_args(summary=" "))["error"]
    assert registry.execute("list_lessons", {})["lessons"] == []


def test_save_lesson_redacts_secrets_in_evidence(store: Store) -> None:
    registry = ToolRegistry(store)
    saved = registry.execute("save_lesson", _lesson_args(evidence="user pasted password=hunter2"))
    assert saved["status"] == "saved"
    assert registry.execute("list_lessons", {})["lessons"][0]["evidence"] == "user pasted password=[REDACTED]"


def test_list_lessons_filters_by_who_and_since_newest_first(store: Store) -> None:
    registry = ToolRegistry(store)
    registry.execute("save_lesson", _lesson_args(lesson_date="2026-10-01", who="user", category="unclear_prompt"))
    registry.execute("save_lesson", _lesson_args(lesson_date="2026-11-01"))
    registry.execute("save_lesson", _lesson_args(lesson_date="2026-11-02", who="user", category="missing_detail"))

    assert [l["lesson_date"] for l in registry.execute("list_lessons", {})["lessons"]] == [
        "2026-11-02",
        "2026-11-01",
        "2026-10-01",
    ]
    assert len(registry.execute("list_lessons", {"who": "user"})["lessons"]) == 2
    assert [l["lesson_date"] for l in registry.execute("list_lessons", {"since": "2026-11-01"})["lessons"]] == [
        "2026-11-02",
        "2026-11-01",
    ]
    assert "who" in registry.execute("list_lessons", {"who": "robot"})["error"]


def test_get_chat_day_tool_rejects_bad_date(store: Store) -> None:
    registry = ToolRegistry(store)
    assert "day" in registry.execute("get_chat_day", {"day": "today"})["error"]
    assert registry.execute("get_chat_day", {"day": "2026-11-02"}) == {
        "day": "2026-11-02",
        "count": 0,
        "messages": [],
        "truncated": False,
        "next_offset": None,
    }

