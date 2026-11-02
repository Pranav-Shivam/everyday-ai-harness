"""Stop hook: save the session transcript to the local database, secrets redacted.

Never prints to stdout and always exits 0, so it cannot disturb the chat.
"""

import json
import os
import sys
from pathlib import Path

try:
    from everyday_harness.store import Store
    from everyday_harness.transcript import ingest_transcript

    event = json.load(sys.stdin)
    default_database = Path(__file__).resolve().parents[3] / "data" / "harness.sqlite3"
    store = Store(os.getenv("HARNESS_DATABASE") or default_database)
    ingest_transcript(store, str(event["session_id"]), event["transcript_path"])
except Exception as exc:
    print(f"capture_chat: {type(exc).__name__}: {exc}", file=sys.stderr)
sys.exit(0)
