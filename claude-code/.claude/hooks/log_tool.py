"""PostToolUse hook: log tool name and outcome only, never message or note text."""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

event = json.load(sys.stdin)
response = event.get("tool_response")
failed = isinstance(response, dict) and bool(response.get("is_error"))

record = {
    "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    "session_id": event.get("session_id"),
    "tool": event.get("tool_name"),
    "status": "error" if failed else "ok",
}

log_path = Path("../logs/claude-code-runs.jsonl")
log_path.parent.mkdir(parents=True, exist_ok=True)
with log_path.open("a", encoding="utf-8") as file:
    file.write(json.dumps(record) + "\n")
