"""Replace likely secrets with a placeholder before text is stored.

This is a safety net based on pattern matching, not a guarantee.
"""

from __future__ import annotations

import re

PLACEHOLDER = "[REDACTED]"
CARD_PLACEHOLDER = "[REDACTED_CARD]"

_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.DOTALL),
        PLACEHOLDER,
    ),
    (re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{20,}"), PLACEHOLDER),
    (re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}"), PLACEHOLDER),
    (re.compile(r"AKIA[0-9A-Z]{16}"), PLACEHOLDER),
    (re.compile(r"AIza[0-9A-Za-z_-]{35}"), PLACEHOLDER),
    (re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"), PLACEHOLDER),
    (re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"), PLACEHOLDER),
    (re.compile(r"(Bearer\s+)[A-Za-z0-9._~+/=-]{16,}"), r"\1" + PLACEHOLDER),
    (re.compile(r"(://)[^\s/:@]+:[^\s/@]+@"), r"\1" + PLACEHOLDER + "@"),
    (
        re.compile(
            r"(?i)(password|passwd|pwd|secret|token|api[_-]?key|apikey|access[_-]?key|client[_-]?secret)"
            r"(_[A-Za-z0-9_]*)?"
            r"(\\?[\"']?\s*[:=]\s*\\?[\"']?)(?!\[REDACTED\])[^\s\"',\\]+"
        ),
        r"\1\2\3" + PLACEHOLDER,
    ),
]

_CARD = re.compile(r"\b\d(?:[ -]?\d){12,15}\b")


def _luhn_ok(digits: str) -> bool:
    total = 0
    for index, char in enumerate(reversed(digits)):
        value = int(char)
        if index % 2 == 1:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return total % 10 == 0


def _card_replacement(match: re.Match[str]) -> str:
    digits = re.sub(r"\D", "", match.group(0))
    return CARD_PLACEHOLDER if _luhn_ok(digits) else match.group(0)


def redact(text: str) -> str:
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return _CARD.sub(_card_replacement, text)
