"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    model: str
    api_key: str
    base_url: str | None
    database_path: Path
    log_path: Path
    assistant_file: Path
    profile_file: Path
    max_steps: int = 6
    max_tool_calls: int = 8
    history_turns: int = 5
    request_timeout: float = 60.0


def load_settings() -> Settings:
    """Load settings from .env and the process environment."""
    load_dotenv()

    model = os.getenv("LLM_MODEL", "").strip()
    if not model:
        raise ValueError("LLM_MODEL is missing. Set it in your .env file.")

    api_key = os.getenv("LLM_API_KEY", "local").strip()
    base_url = os.getenv("LLM_BASE_URL", "").strip() or None

    return Settings(
        model=model,
        api_key=api_key,
        base_url=base_url,
        database_path=Path(os.getenv("HARNESS_DATABASE", "data/harness.sqlite3")),
        log_path=Path(os.getenv("HARNESS_LOG_FILE", "logs/runs.jsonl")),
        assistant_file=Path(os.getenv("HARNESS_ASSISTANT_FILE", "config/assistant.md")),
        profile_file=Path(os.getenv("HARNESS_PROFILE_FILE", "config/profile.md")),
        max_steps=max(1, int(os.getenv("HARNESS_MAX_STEPS", "6"))),
        max_tool_calls=max(1, int(os.getenv("HARNESS_MAX_TOOL_CALLS", "8"))),
        history_turns=max(1, int(os.getenv("HARNESS_HISTORY_TURNS", "5"))),
        request_timeout=max(5.0, float(os.getenv("HARNESS_REQUEST_TIMEOUT", "60"))),
    )
