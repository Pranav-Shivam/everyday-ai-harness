"""Turn a Claude Code transcript (JSONL) into chat messages and store them."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

from .store import Store

PRIVATE_PREFIX = "#private"


@dataclass(frozen=True)
class ChatMessage:
    external_id: str
    role: str
    content: str
    created_at: str


def _text_of(content: Any) -> str:
    """Join the text parts of a string or a list of content blocks."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            block["text"] for block in content if isinstance(block, dict) and isinstance(block.get("text"), str)
        )
    return ""


def parse_transcript(lines: Iterable[str]) -> list[ChatMessage]:
    messages: list[ChatMessage] = []
    private = False

    for line in lines:
        try:
            entry = json.loads(line)
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(entry, dict) or entry.get("type") not in {"user", "assistant"}:
            continue
        if entry.get("isSidechain") or entry.get("isMeta") or entry.get("isCompactSummary") or entry.get("isVisibleInTranscriptOnly"):
            continue
        message = entry.get("message")
        uuid = entry.get("uuid")
        if not isinstance(message, dict) or not isinstance(uuid, str):
            continue
        created_at = str(entry.get("timestamp", ""))
        content = message.get("content")
        blocks = content if isinstance(content, list) else []

        if entry["type"] == "user":
            results = [b for b in blocks if isinstance(b, dict) and b.get("type") == "tool_result"]
            if results:
                if private:
                    continue
                for index, block in enumerate(blocks):
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        messages.append(
                            ChatMessage(f"{uuid}:{index}", "tool_result", _text_of(block.get("content")), created_at)
                        )
                continue
            text = _text_of(content)
            if not text.strip():
                continue
            private = text.strip().lower().startswith(PRIVATE_PREFIX)
            if not private:
                messages.append(ChatMessage(uuid, "user", text, created_at))
            continue

        if private:
            continue
        for index, block in enumerate(blocks):
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text" and isinstance(block.get("text"), str) and block["text"].strip():
                messages.append(ChatMessage(f"{uuid}:{index}", "assistant", block["text"], created_at))
            elif block.get("type") == "tool_use":
                call = f"{block.get('name', '')} {json.dumps(block.get('input', {}), ensure_ascii=False)}"
                messages.append(ChatMessage(f"{uuid}:{index}", "tool_call", call, created_at))

    return messages


def ingest_transcript(store: Store, session_id: str, transcript_path: Path | str) -> int:
    """Store new messages from a transcript file. Safe to run repeatedly."""
    path = Path(transcript_path)
    if not path.is_file():
        return 0
    with path.open(encoding="utf-8", errors="replace") as file:
        messages = parse_transcript(file)
    return store.save_chat_messages(session_id, [asdict(message) for message in messages])
