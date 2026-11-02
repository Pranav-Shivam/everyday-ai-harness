import json
from pathlib import Path

from everyday_harness.store import Store
from everyday_harness.transcript import ingest_transcript, parse_transcript


def _line(**fields) -> str:
    return json.dumps(fields)


def _user(uuid: str, text: str, ts: str = "2026-11-02T10:00:00Z", **extra) -> str:
    return _line(type="user", uuid=uuid, timestamp=ts, message={"role": "user", "content": text}, **extra)


def _assistant(uuid: str, blocks: list[dict], ts: str = "2026-11-02T10:00:05Z", **extra) -> str:
    return _line(type="assistant", uuid=uuid, timestamp=ts, message={"role": "assistant", "content": blocks}, **extra)


def _tool_result(uuid: str, text: str, ts: str = "2026-11-02T10:00:06Z") -> str:
    block = {"type": "tool_result", "tool_use_id": "t1", "content": text}
    return _line(type="user", uuid=uuid, timestamp=ts, toolUseResult={}, message={"role": "user", "content": [block]})


def test_user_assistant_and_tool_roundtrip() -> None:
    lines = [
        _user("u1", "Remember my review is Friday"),
        _assistant("a1", [{"type": "tool_use", "name": "save_note", "input": {"content": "review Friday"}}]),
        _tool_result("r1", "saved"),
        _assistant("a2", [{"type": "text", "text": "Done, saved."}]),
    ]
    messages = parse_transcript(lines)
    assert [m.role for m in messages] == ["user", "tool_call", "tool_result", "assistant"]
    assert messages[0].content == "Remember my review is Friday"
    assert messages[1].content == 'save_note {"content": "review Friday"}'
    assert messages[2].content == "saved"
    assert messages[3].content == "Done, saved."
    assert messages[0].created_at == "2026-11-02T10:00:00Z"


def test_ignores_noise_types_sidechain_meta_and_thinking() -> None:
    lines = [
        _line(type="attachment", uuid="x1"),
        _line(type="queue-operation"),
        _user("u1", "sidechain prompt", isSidechain=True),
        _user("u2", "meta prompt", isMeta=True),
        _assistant("a1", [{"type": "thinking", "thinking": "secret thoughts"}, {"type": "text", "text": "hi"}]),
    ]
    messages = parse_transcript(lines)
    assert [(m.role, m.content) for m in messages] == [("assistant", "hi")]


def test_bad_json_and_truncated_last_line_are_skipped() -> None:
    lines = ["not json at all", _user("u1", "hello"), '{"type": "assistant", "uuid": "a1", "mess']
    assert [m.content for m in parse_transcript(lines)] == ["hello"]


def test_private_prompt_hides_whole_turn_then_resumes() -> None:
    lines = [
        _user("u1", "  #PRIVATE  my plan"),
        _assistant("a1", [{"type": "text", "text": "private reply"}]),
        _assistant("a2", [{"type": "tool_use", "name": "save_note", "input": {}}]),
        _tool_result("r1", "private result"),
        _user("u2", "normal question"),
        _assistant("a3", [{"type": "text", "text": "normal reply"}]),
    ]
    assert [m.content for m in parse_transcript(lines)] == ["normal question", "normal reply"]


def test_private_tag_mid_sentence_is_not_private() -> None:
    messages = parse_transcript([_user("u1", "this is not #private at all")])
    assert len(messages) == 1


def test_ingest_is_idempotent_and_incremental(store: Store, tmp_path: Path) -> None:
    path = tmp_path / "t.jsonl"
    path.write_text("\n".join([_user("u1", "one"), _assistant("a1", [{"type": "text", "text": "two"}])]) + "\n", encoding="utf-8")
    assert ingest_transcript(store, "s1", path) == 2
    assert ingest_transcript(store, "s1", path) == 0
    with path.open("a", encoding="utf-8") as file:
        file.write(_user("u2", "three") + "\n" + _assistant("a2", [{"type": "text", "text": "four"}]) + "\n")
    assert ingest_transcript(store, "s1", path) == 2
    assert len(store.get_chat_session("s1")) == 4


def test_ingest_missing_file_returns_zero(store: Store, tmp_path: Path) -> None:
    assert ingest_transcript(store, "s1", tmp_path / "missing.jsonl") == 0


def test_ingest_redacts_secret_in_prompt(store: Store, tmp_path: Path) -> None:
    path = tmp_path / "t.jsonl"
    path.write_text(_user("u1", "login with password=hunter2") + "\n", encoding="utf-8")
    ingest_transcript(store, "s1", path)
    assert store.get_chat_session("s1")[0]["content"] == "login with password=[REDACTED]"


def test_compact_summary_is_not_stored_and_does_not_end_private_mode() -> None:
    lines = [
        _user("u1", "#private my plan"),
        _assistant("a1", [{"type": "text", "text": "private reply part one"}]),
        _user("c1", "Summary of the whole earlier conversation including private plan", isCompactSummary=True),
        _assistant("a2", [{"type": "text", "text": "private reply part two"}]),
        _user("u2", "normal question"),
    ]
    assert [m.content for m in parse_transcript(lines)] == ["normal question"]


def test_compact_summary_outside_private_mode_is_still_not_stored() -> None:
    lines = [_user("c1", "Summary text", isCompactSummary=True), _user("u1", "hello")]
    assert [m.content for m in parse_transcript(lines)] == ["hello"]


def test_tool_call_and_tool_result_secrets_are_redacted_on_ingest(store: Store, tmp_path: Path) -> None:
    path = tmp_path / "t.jsonl"
    lines = [
        _assistant("a1", [{"type": "tool_use", "name": "Write", "input": {"content": '\npassword = "s3cr3t"'}}]),
        _tool_result("r1", "GITHUB_TOKEN=abc123xyz\nDB_PASSWORD=hunter2"),
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    ingest_transcript(store, "s1", path)
    stored = " ".join(m["content"] for m in store.get_chat_session("s1"))
    assert "s3cr3t" not in stored and "abc123xyz" not in stored and "hunter2" not in stored
