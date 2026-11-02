from pathlib import Path
from types import SimpleNamespace

from everyday_harness.config import Settings
from everyday_harness.harness import AgentHarness
from everyday_harness.store import Store


class FakeModel:
    def __init__(self) -> None:
        self.call_count = 0

    def complete(self, messages, tools):
        self.call_count += 1
        if self.call_count == 1:
            tool_call = SimpleNamespace(
                id="call-1",
                function=SimpleNamespace(
                    name="save_note",
                    arguments='{"content":"Harness tests should be repeatable.","tags":["engineering"]}',
                ),
            )
            message = SimpleNamespace(content=None, tool_calls=[tool_call])
        else:
            message = SimpleNamespace(content="The note was saved.", tool_calls=[])
        choice = SimpleNamespace(message=message)
        usage = SimpleNamespace(prompt_tokens=100, completion_tokens=20)
        return SimpleNamespace(choices=[choice], usage=usage)


def test_agent_loop_executes_tool_then_returns_answer(tmp_path: Path) -> None:
    settings = Settings(
        model="fake-model",
        api_key="fake",
        base_url=None,
        database_path=tmp_path / "db.sqlite3",
        log_path=tmp_path / "logs" / "runs.jsonl",
        assistant_file=Path("config/assistant.md"),
        profile_file=Path("config/profile.md"),
        max_steps=4,
        max_tool_calls=4,
        history_turns=3,
        request_timeout=10,
    )
    store = Store(settings.database_path)
    assistant = AgentHarness(settings, model=FakeModel(), store=store)

    result = assistant.run_turn("Save a note about repeatable tests.")

    assert result.answer == "The note was saved."
    assert result.tool_names == ["save_note"]
    assert result.steps == 2
    assert result.tool_calls == 1
    matches = store.search_notes("repeatable tests")
    assert len(matches) == 1


class SnoopModel:
    """Asks for a chat-history tool the Python harness never advertised."""

    def __init__(self) -> None:
        self.call_count = 0
        self.tool_message = ""

    def complete(self, messages, tools):
        self.call_count += 1
        if self.call_count == 1:
            call = SimpleNamespace(id="c1", function=SimpleNamespace(name="search_chats", arguments='{"query": "private plans"}'))
            message = SimpleNamespace(content=None, tool_calls=[call])
        else:
            self.tool_message = next(m["content"] for m in messages if m.get("role") == "tool")
            message = SimpleNamespace(content="done", tool_calls=[])
        return SimpleNamespace(
            choices=[SimpleNamespace(message=message)],
            usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1),
        )


def test_harness_refuses_tools_it_did_not_advertise(tmp_path: Path) -> None:
    settings = Settings(
        model="fake",
        api_key="fake",
        base_url=None,
        database_path=tmp_path / "db.sqlite3",
        log_path=tmp_path / "logs" / "runs.jsonl",
        assistant_file=Path("config/assistant.md"),
        profile_file=Path("config/profile.md"),
        max_steps=4,
        max_tool_calls=4,
        history_turns=3,
        request_timeout=10,
    )
    store = Store(settings.database_path)
    store.save_chat_messages(
        "s1", [{"external_id": "a", "role": "user", "content": "private plans here", "created_at": "2026-11-02T10:00:00Z"}]
    )
    model = SnoopModel()
    AgentHarness(settings, model=model, store=store).run_turn("what did we discuss?")
    assert "not allowed" in model.tool_message
    assert "private plans here" not in model.tool_message
