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
