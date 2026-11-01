"""Thin client for OpenAI-compatible chat completions endpoints."""

from __future__ import annotations

from typing import Any

from .config import Settings


class ChatModel:
    def __init__(self, settings: Settings) -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError(
                "The OpenAI Python SDK is not installed. Run python -m pip install -e ."
            ) from exc

        client_options: dict[str, Any] = {
            "api_key": settings.api_key,
            "timeout": settings.request_timeout,
        }
        if settings.base_url:
            client_options["base_url"] = settings.base_url
        self.client = OpenAI(**client_options)
        self.model = settings.model

    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> Any:
        return self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=0.2,
        )
