import pytest

from everyday_harness.redact import redact


@pytest.mark.parametrize(
    "secret",
    [
        "sk-" + "a1B2c3D4e5F6g7H8i9J0kLmN",
        "sk-ant-api03-" + "x" * 30,
        "ghp_" + "A" * 36,
        "AKIA" + "ABCDEFGHIJKLMNOP",
        "AIza" + "B" * 35,
        "xoxb-1234567890-abcdefghij",
        "eyJhbGciOiJIUzI1.eyJzdWIiOiIxMjM0NTY.SflKxwRJSMeKKF2QT4",
    ],
)
def test_known_key_formats_are_redacted(secret: str) -> None:
    result = redact(f"here is my key {secret} please keep it")
    assert secret not in result
    assert "[REDACTED]" in result


def test_bearer_header() -> None:
    assert redact("Authorization: Bearer abcdefghijklmnop1234") == "Authorization: Bearer [REDACTED]"


def test_labelled_secrets_keep_label() -> None:
    assert redact("password=hunter2") == "password=[REDACTED]"
    assert redact("api_key: abc123") == "api_key: [REDACTED]"
    assert redact("Token = xyz") == "Token = [REDACTED]"
    assert redact("password = 'hunter2'") == "password = '[REDACTED]'"
    assert redact('{"api_key": "abc123def456"}') == '{"api_key": "[REDACTED]"}'


def test_private_key_block() -> None:
    text = "before\n-----BEGIN RSA PRIVATE KEY-----\nMIIabc\ndef\n-----END RSA PRIVATE KEY-----\nafter"
    assert redact(text) == "before\n[REDACTED]\nafter"


def test_url_credentials() -> None:
    assert redact("postgres://bob:s3cret@db.local/app") == "postgres://[REDACTED]@db.local/app"


def test_credit_card_luhn() -> None:
    assert redact("card 4111 1111 1111 1111 ok") == "card [REDACTED_CARD] ok"
    assert redact("number 1234 5678 9012 3456 ok") == "number 1234 5678 9012 3456 ok"


def test_plain_text_untouched() -> None:
    text = "Meeting on 2026-11-05 about the token economy, 3 tasks"
    assert redact(text) == text


def test_idempotent() -> None:
    text = "password=hunter2 sk-" + "a" * 24 + " postgres://u:p@h/db 4111 1111 1111 1111"
    once = redact(text)
    assert redact(once) == once


@pytest.mark.parametrize(
    "text, expected",
    [
        ("DB_PASSWORD=hunter2", "DB_PASSWORD=[REDACTED]"),
        ("GITHUB_TOKEN=abc123xyz", "GITHUB_TOKEN=[REDACTED]"),
        ("AWS_SECRET_ACCESS_KEY=abcd/efg+hij", "AWS_SECRET_ACCESS_KEY=[REDACTED]"),
        ("export OPENAI_API_KEY=plain", "export OPENAI_API_KEY=[REDACTED]"),
        ('secret_key = "abc"', 'secret_key = "[REDACTED]"'),
        ("auth_token='abc'", "auth_token='[REDACTED]'"),
        ("dbPassword: hunter2", "dbPassword: [REDACTED]"),
    ],
)
def test_env_style_labels_are_redacted(text: str, expected: str) -> None:
    assert redact(text) == expected


def test_secret_inside_json_encoded_tool_input_is_redacted() -> None:
    import json

    encoded = json.dumps({"content": '\npassword = "s3cr3t"\napi_key="k3y123"'})
    result = redact(encoded)
    assert "s3cr3t" not in result and "k3y123" not in result
    assert redact(result) == result


@pytest.mark.parametrize("text", ["feat/task-capture-chat-transcript", "risk-assessment-template-2026-final"])
def test_sk_inside_words_is_not_redacted(text: str) -> None:
    assert redact(text) == text
