import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from everyday_harness.store import Store

SCRIPT = Path(__file__).resolve().parents[1] / "claude-code" / ".claude" / "hooks" / "capture_chat.py"


def _run(stdin: str, database: Path) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "HARNESS_DATABASE": str(database)}
    return subprocess.run([sys.executable, str(SCRIPT)], input=stdin, env=env, capture_output=True, text=True)


def test_hook_stores_messages_and_prints_nothing(tmp_path: Path) -> None:
    transcript = tmp_path / "t.jsonl"
    entries = [
        {"type": "user", "uuid": "u1", "timestamp": "2026-11-02T10:00:00Z", "message": {"role": "user", "content": "hello"}},
        {
            "type": "assistant",
            "uuid": "a1",
            "timestamp": "2026-11-02T10:00:01Z",
            "message": {"role": "assistant", "content": [{"type": "text", "text": "hi there"}]},
        },
    ]
    transcript.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")
    database = tmp_path / "db.sqlite3"

    result = _run(json.dumps({"session_id": "sid", "transcript_path": str(transcript)}), database)

    assert result.returncode == 0
    assert result.stdout == ""
    assert len(Store(database).get_chat_session("sid")) == 2


@pytest.mark.parametrize(
    "stdin",
    ["", "not json", json.dumps({"session_id": "sid", "transcript_path": "missing-file.jsonl"})],
)
def test_hook_survives_bad_input(stdin: str, tmp_path: Path) -> None:
    result = _run(stdin, tmp_path / "db.sqlite3")
    assert result.returncode == 0
    assert result.stdout == ""
