# Chat Capture, Search and Eval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automatically save every Claude Code chat to the local SQLite database with secrets redacted, let Claude search and reopen old chats, add an `/eval-chat` command that critiques a saved chat, and add a daily "Learn about today" review that records mistakes by both user and assistant as trackable lessons.

**Architecture:** A `Stop` hook reads Claude Code's own transcript file, parses it into messages, redacts secrets, and inserts new rows into a `chat_messages` table in the existing database (idempotent, so re-running never duplicates). Three read-only MCP tools expose search/list/read. `/eval-chat` is a prompt-only slash command that reads a session through those tools and grades it against a fixed rubric.

**Tech Stack:** Python 3.11 stdlib (`re`, `json`, `sqlite3`, `dataclasses`), existing `Store` / `ToolRegistry` / FastMCP server, pytest. No new dependencies.

**Spec:** None written. The user skipped the design questions ("just start"); requirements are the chat decisions restated in Global Constraints below.

## Global Constraints

- Redaction happens inside `Store.save_chat_messages`, so raw text never reaches the database from any caller.
- Placeholder for redacted secrets is exactly `[REDACTED]` (credit cards: `[REDACTED_CARD]`).
- A user prompt starting with `#private` (after stripping whitespace, case-insensitive) is not stored, and neither is anything Claude does until the next user prompt.
- The hook must never write to stdout (stdout of some hooks is fed back to Claude), must always exit 0, and reports problems on stderr only.
- Stored message roles are exactly `user`, `assistant`, `tool_call`, `tool_result`. Stored content is truncated to 8000 characters (`tool_result` to 500) with the suffix `…[truncated]`.
- Chat data lives in the same database file as notes (`../data/harness.sqlite3` from `claude-code/`), which is already git-ignored.
- The Python harness must keep exposing exactly its original five tools to the model (`ToolRegistry.definitions` unchanged).
- Chat tools are read-only. No tool can edit or delete stored chats.
- Out of scope (YAGNI): custom redaction patterns, semantic search, storing eval results, capturing chats from the Python harness, Claude Desktop/VS Code sessions outside `claude-code/`.
- No commits are made unless the user asks.
- The daily review is called **Learn about today**. It runs when the user types `/learn-today` or says "Learn about today" (any capitalisation, trailing punctuation ignored). It is a project skill, so both routes use the same instructions.
- A lesson is never saved without the user's approval: `save_lesson` stays in the `ask` permission list, one prompt per lesson.
- Lesson `who` is exactly `user` or `assistant`. Lesson `category` is exactly one of: `unclear_prompt`, `missing_detail`, `changed_mind`, `acted_without_asking`, `assumed_instead_of_checking`, `claimed_without_proof`, `invented_fact`, `other`.
- "Today" means the user's local calendar day, not UTC.

## Review Focus

1. Secret inside JSON-shaped text, e.g. `{"api_key": "abc123def456"}` and `password = 'hunter2'`: value hidden, label kept. (Task 1)
2. Redacting already-redacted text changes nothing, and ordinary text (dates, short numbers, 13+ digit numbers failing Luhn) is left alone. (Task 1)
3. Transcript last line is half-written / not valid JSON: skipped, no crash, other lines still ingested. (Task 3)
4. Hook runs twice on the same transcript, or after more turns were added: no duplicate rows, only new messages inserted. (Tasks 2, 3)
5. `#private` appearing mid-sentence does not trigger opt-out; `#PRIVATE  note` at the start does; the next normal prompt resumes saving. (Task 3)
6. Hook given empty stdin, bad JSON, or a missing transcript path: exit 0, empty stdout. (Task 4)
7. Search with an empty or oversized query, or `get_chat_session` with an unknown id: returns an error dict, never raises. A stop-words-only query returns an empty result. (Tasks 2, 5)
8. A chat at 23:30 local time (already the next day in UTC, or the reverse) lands in the correct local day. (Task 7)
9. A day with no chats: Learn about today says so plainly and saves nothing. A day with hundreds of messages is capped, not dumped whole. (Task 7)
10. Invalid `who`, `category` or date in `save_lesson`: error dict, nothing stored. (Task 7)

---

### Task 1: Redaction filter

**Files:**
- Create: `src/everyday_harness/redact.py`
- Test: `tests/test_redact.py`

**Interfaces:**
- Produces: `redact(text: str) -> str`

- [ ] **Step 1: Write failing tests** in `tests/test_redact.py`, one per case, asserting the exact output:
  - `test_known_key_formats_are_redacted`: parametrised over an OpenAI-style `sk-` + 24 chars, `sk-ant-` key, `ghp_` + 36 chars, `AKIA` + 16 chars, `AIza` + 35 chars, `xoxb-` Slack token, a three-part `eyJ...` JWT. Each placed in a sentence; assert the key text is gone and `[REDACTED]` is present.
  - `test_bearer_header`: `Authorization: Bearer abcdefghijklmnop1234` -> `Authorization: Bearer [REDACTED]`.
  - `test_labelled_secrets_keep_label`: `password=hunter2` -> `password=[REDACTED]`; `api_key: abc123` -> `api_key: [REDACTED]`; `Token = xyz` case-insensitive; `{"api_key": "abc123def456"}` -> `{"api_key": "[REDACTED]"}` (Review Focus 1).
  - `test_private_key_block`: multi-line PEM `-----BEGIN RSA PRIVATE KEY-----...-----END RSA PRIVATE KEY-----` -> `[REDACTED]`.
  - `test_url_credentials`: `postgres://bob:s3cret@db.local/app` -> `postgres://[REDACTED]@db.local/app`.
  - `test_credit_card_luhn`: `4111 1111 1111 1111` -> `[REDACTED_CARD]`; `1234 5678 9012 3456` (fails Luhn) unchanged.
  - `test_plain_text_untouched`: `"Meeting on 2026-11-05 about the token economy, 3 tasks"` is returned unchanged except nothing is hidden (the word `token` without `=` or `:` is not a label).
  - `test_idempotent`: `redact(redact(x)) == redact(x)` for a string containing several secret kinds.
- [ ] **Step 2: Run** `pytest tests/test_redact.py -v`. Expected: FAIL (module missing).
- [ ] **Step 3: Implement `redact(text: str) -> str`** in `src/everyday_harness/redact.py`. Module-level compiled pattern list applied in order, PEM block first. Patterns (exact):
  - `sk-[A-Za-z0-9_-]{20,}`, `gh[pousr]_[A-Za-z0-9]{36,}`, `AKIA[0-9A-Z]{16}`, `AIza[0-9A-Za-z_-]{35}`, `xox[baprs]-[A-Za-z0-9-]{10,}`, `eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}` -> `[REDACTED]`
  - `-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----` (DOTALL) -> `[REDACTED]`
  - `(Bearer\s+)[A-Za-z0-9._~+/=-]{16,}` -> `\1[REDACTED]`
  - `(://)[^\s/:@]+:[^\s/@]+@` -> `\1[REDACTED]@`
  - labelled: `(?i)\b(password|passwd|pwd|secret|token|api[_-]?key|apikey|access[_-]?key|client[_-]?secret)(["']?\s*[:=]\s*["']?)[^\s"',]+` -> `\1\2[REDACTED]`; skip the replacement when the value is already `[REDACTED]` (keeps idempotence).
  - Card numbers: find `\b(?:\d[ -]?){13,16}\b`, strip separators, replace with `[REDACTED_CARD]` only if the digits pass a Luhn check (private helper `_luhn_ok(digits: str) -> bool`).
- [ ] **Step 4: Run** `pytest tests/test_redact.py -v`. Expected: all PASS.

---

### Task 2: Chat tables and store methods

**Files:**
- Modify: `src/everyday_harness/store.py` (add table in `_initialise`, add methods, extract the term-splitting from `search_notes` into a module-level `_search_terms(query: str) -> list[str]` that `search_notes` also uses; behaviour of `search_notes` must not change)
- Test: `tests/test_chat_store.py`

**Interfaces:**
- Consumes: `redact(text: str) -> str` from Task 1
- Produces on `Store`:
  - `save_chat_messages(self, session_id: str, messages: list[dict[str, Any]]) -> int`: each dict has `external_id`, `role`, `content`, `created_at` (all str). Redacts and truncates content per Global Constraints. Returns the count of newly inserted rows.
  - `search_chats(self, query: str, limit: int = 5) -> list[dict[str, Any]]`: dicts with `session_id`, `role`, `content` (first 500 chars), `created_at`. Only `user`/`assistant` rows, newest 2000 rows scanned, scored by term hits like notes, `limit` clamped to 1..20. Empty list when no usable terms.
  - `list_chat_sessions(self, limit: int = 10) -> list[dict[str, Any]]`: dicts with `session_id`, `started_at`, `last_at`, `message_count`, `first_prompt` (first `user` content, 120 chars). Newest `last_at` first, `limit` clamped 1..50.
  - `get_chat_session(self, session_id: str, limit: int = 200) -> list[dict[str, Any]]`: dicts with `role`, `content`, `created_at`, oldest first, `[]` if unknown.
- Table: `chat_messages(id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL, external_id TEXT NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(session_id, external_id))`, plus an index on `session_id`.

- [ ] **Step 1: Write failing tests** in `tests/test_chat_store.py` using the `store` fixture:
  - `test_save_redacts_secrets`: save `"my key is sk-" + "a"*24`, read back via `get_chat_session`, assert no `sk-aaaa` and `[REDACTED]` present.
  - `test_save_is_idempotent`: same `external_id` twice -> first call returns 1, second returns 0, session has one message (Review Focus 4).
  - `test_truncates_long_content`: 9000-char content stored as 8000 chars ending in `…[truncated]` (total length 8000 including suffix); `tool_result` capped at 500 the same way.
  - `test_search_chats_finds_user_and_assistant_not_tool`: a `tool_call` row containing the search word is not returned; a `user` row is.
  - `test_search_chats_stop_words_only_returns_empty`.
  - `test_list_chat_sessions_orders_newest_first_with_first_prompt`.
  - `test_get_chat_session_unknown_returns_empty`.
  - `test_search_notes_unchanged`: existing `tests/test_tools.py` still passes (run it).
- [ ] **Step 2: Run** `pytest tests/test_chat_store.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** the table, `_search_terms`, and the four methods exactly as the Interfaces block specifies. Scoring and clamping mirror `search_notes`.
- [ ] **Step 4: Run** `pytest tests/test_chat_store.py tests/test_tools.py tests/test_harness.py -v`. Expected: all PASS.

---

### Task 3: Transcript parser and ingest

**Files:**
- Create: `src/everyday_harness/transcript.py`
- Test: `tests/test_transcript.py`

**Interfaces:**
- Consumes: `Store.save_chat_messages` from Task 2
- Produces:
  - `PRIVATE_PREFIX = "#private"`
  - `@dataclass(frozen=True) class ChatMessage: external_id: str; role: str; content: str; created_at: str`
  - `parse_transcript(lines: Iterable[str]) -> list[ChatMessage]`
  - `ingest_transcript(store: Store, session_id: str, transcript_path: Path | str) -> int` returns newly inserted count; returns 0 if the file does not exist.

**Transcript format (verified against a real Claude Code transcript on this machine):** JSONL. Relevant lines have `type` `"user"` or `"assistant"`, a `uuid`, a `timestamp`, `isSidechain`, and `message.content` that is a string or a list of blocks (`text`, `tool_use` with `name`/`input`, `tool_result` with `content`, `thinking`). All other `type` values (`attachment`, `queue-operation`, `api-request`, ...) are ignored.

**Parse rules:**
- Skip lines that are not valid JSON, entries with `isSidechain` true, and entries with `isMeta` true.
- `user` entry with string content or `text` blocks = a real prompt: role `user`. Its `external_id` is the entry `uuid`.
- `user` entry with `tool_result` blocks: role `tool_result`, content is the block text (join text parts if `content` is a list), `external_id` is `uuid:<block index>`.
- `assistant` entry: each `text` block -> role `assistant`; each `tool_use` block -> role `tool_call` with content `<name> <json.dumps(input)>`; `thinking` blocks ignored. `external_id` is `uuid:<block index>`.
- Private mode: a real prompt whose stripped, lower-cased text starts with `#private` turns private mode on and emits nothing; every later entry is skipped until the next real prompt, which resets the mode based on its own prefix.
- `created_at` is the entry `timestamp`.

- [ ] **Step 1: Write failing tests** in `tests/test_transcript.py`, using a small helper `_line(**fields) -> str` that builds JSON lines:
  - `test_user_assistant_and_tool_roundtrip`: lines for a user prompt, an assistant `tool_use` (`save_note`), a user `tool_result`, an assistant `text` -> parsed roles are `["user", "tool_call", "tool_result", "assistant"]` with the expected content.
  - `test_ignores_noise_types_sidechain_meta_and_thinking`.
  - `test_bad_json_and_truncated_last_line_are_skipped` (Review Focus 3).
  - `test_private_prompt_hides_whole_turn_then_resumes` (Review Focus 5): `#PRIVATE  plan` prompt + assistant reply + tool call produce nothing; the following normal prompt and reply are produced.
  - `test_private_tag_mid_sentence_is_not_private`.
  - `test_ingest_is_idempotent_and_incremental`: write 2 lines, ingest -> 2; ingest again -> 0; append 2 more lines, ingest -> 2 (Review Focus 4).
  - `test_ingest_missing_file_returns_zero`.
  - `test_ingest_redacts_secret_in_prompt`: prompt contains `password=hunter2`; stored text has `[REDACTED]`.
- [ ] **Step 2: Run** `pytest tests/test_transcript.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** the dataclass, `parse_transcript` and `ingest_transcript` per the rules above. `ingest_transcript` reads the file as UTF-8 with `errors="replace"` and passes `ChatMessage` fields as dicts to `store.save_chat_messages`.
- [ ] **Step 4: Run** `pytest tests/test_transcript.py -v`. Expected: all PASS.

---

### Task 4: Stop hook wiring

**Files:**
- Create: `claude-code/.claude/hooks/capture_chat.py`
- Modify: `claude-code/.claude/settings.json` (add a `Stop` hook entry with no matcher, command `python .claude/hooks/capture_chat.py`)
- Test: `tests/test_capture_hook.py`

**Interfaces:**
- Consumes: `Store`, `ingest_transcript` from Tasks 2-3
- Produces: script reading one JSON object from stdin with keys `session_id` and `transcript_path`. Database path: env `HARNESS_DATABASE` if set, else `<repo root>/data/harness.sqlite3` resolved from the script's own location (`Path(__file__).resolve().parents[3]`), so it does not depend on the working directory.

- [ ] **Step 1: Write failing tests** in `tests/test_capture_hook.py` running the script with `subprocess.run([sys.executable, str(script)], input=..., env={**os.environ, "HARNESS_DATABASE": str(tmp_db)}, capture_output=True, text=True)`:
  - `test_hook_stores_messages_and_prints_nothing`: write a 2-entry transcript, run the hook, assert `returncode == 0`, `stdout == ""`, and `Store(tmp_db).get_chat_session(sid)` has 2 messages.
  - `test_hook_survives_bad_input` (Review Focus 6): parametrised over empty stdin, `"not json"`, and a valid event with a missing `transcript_path` file; each gives `returncode == 0` and `stdout == ""`.
- [ ] **Step 2: Run** `pytest tests/test_capture_hook.py -v`. Expected: FAIL (script missing).
- [ ] **Step 3: Implement the script.** Read stdin, parse JSON, call `ingest_transcript`, wrap everything in `try/except Exception` that writes `capture_chat: <error type>: <message>` to stderr and exits 0. No stdout writes anywhere. Add the `Stop` entry to `settings.json` next to the existing `PostToolUse` entry, keeping valid JSON.
- [ ] **Step 4: Run** `pytest tests/test_capture_hook.py -v`. Expected: all PASS. Also run `python -c "import json; json.load(open('claude-code/.claude/settings.json'))"`; expected: no output.

---

### Task 5: Search tools for Claude

**Files:**
- Modify: `src/everyday_harness/tools.py` (three new validators and `_functions` entries; `definitions` stays at five entries)
- Modify: `src/everyday_harness/mcp_server.py` (three new tools)
- Modify: `claude-code/.claude/settings.json` (add the three tools to `permissions.allow`)
- Modify: `tests/test_mcp_server.py`, `tests/test_tools.py`

**Interfaces:**
- Consumes: `Store.search_chats`, `list_chat_sessions`, `get_chat_session` from Task 2
- Produces (registry names and MCP tool functions, same names):
  - `search_chats(query: str) -> dict`: `{"count": n, "messages": [...]}`; `query` non-empty string, max 300 chars, same `_required_text` rule as notes. A query with no usable terms returns `{"count": 0, "messages": []}`.
  - `list_chat_sessions() -> dict`: `{"sessions": [...]}` (latest 10).
  - `get_chat_session(session_id: str) -> dict`: `{"session_id": ..., "messages": [...]}`; `session_id` non-empty string max 100 chars; error dict `{"error": "Session not found"}` when the store returns no messages.
- Allow-list entries: `mcp__everyday__search_chats`, `mcp__everyday__list_chat_sessions`, `mcp__everyday__get_chat_session`.

- [ ] **Step 1: Write failing tests.**
  - In `tests/test_tools.py`: `test_chat_tools_validate_input` (empty query, 301-char query, non-string session_id -> `{"error": ...}`); `test_unknown_session_is_an_error_not_a_crash` (Review Focus 7); `test_python_harness_still_advertises_five_tools` asserting `{d["function"]["name"] for d in registry.definitions}` equals the original five names.
  - In `tests/test_mcp_server.py`: rename `test_exposes_exactly_the_five_tools` to `test_exposes_the_expected_tools` and assert the set is the original five plus `search_chats`, `list_chat_sessions`, `get_chat_session`; add `test_chat_round_trip` that saves messages through the store fixture's `save_chat_messages`, then asserts `mcp_server.search_chats("weekly review")["count"] == 1` and `mcp_server.get_chat_session(sid)["messages"]` has the saved messages.
- [ ] **Step 2: Run** `pytest tests/test_tools.py tests/test_mcp_server.py -v`. Expected: new tests FAIL.
- [ ] **Step 3: Implement** the validators in `tools.py` (reuse `_required_text`), register them in `ToolRegistry._functions` with a one-line comment that they are intentionally absent from `definitions`, add the three `@mcp.tool()` functions with docstrings telling Claude to use them only when the user asks about past conversations, and update the module docstring from "five" to "local". Add the three allow entries to `settings.json`.
- [ ] **Step 4: Run** `pytest -v`. Expected: the whole suite PASSES.

---

### Task 6: `/eval-chat` command and docs

**Files:**
- Create: `claude-code/.claude/commands/eval-chat.md`
- Modify: `claude-code/CLAUDE.md` (Tools section: add the three chat tools and the `#private` note; Safety section: one line that chats are saved with secrets redacted)
- Modify: `claude-code/README.md` (Mapping table Feedback row, "five tools" wording, Evals row in the differences table, short "Chat history and privacy" section)
- Modify: `README.md` only if it states the Claude Code version has no chat history (check with grep; otherwise leave it)

**Interfaces:**
- Consumes: the three MCP tools from Task 5.
- Produces: slash command `/eval-chat [session-id]`.

- [ ] **Step 1: Write `eval-chat.md`.** Frontmatter: `description: Review a saved chat for mistakes and suggest improvements` and `argument-hint: [session-id]`. Body instructs Claude to:
  1. Use `$ARGUMENTS` as the session id; if empty call `list_chat_sessions` and use the newest.
  2. Call `get_chat_session`, then judge only what the transcript shows.
  3. Check this fixed rubric, each as PASS / FAIL / NO EVIDENCE with a quoted line as proof: followed `CLAUDE.md` rules (saved a note or changed a task only when asked); never claimed an action succeeded without a matching `tool_result`; no invented notes, dates or tool results; answered what was actually asked; reported tool errors honestly; kept routine answers short.
  4. Finish with the top 3 concrete improvements (what to change in `CLAUDE.md`, the tools, or how the user phrases requests) and a one-line caveat that Claude is grading its own work, so the user should spot-check any FAIL.
  5. Make no changes and call no write tools.
- [ ] **Step 2: Update `CLAUDE.md` and `README.md`** per the Files list. Docs must state plainly: what is stored, where, that secrets matching known patterns are replaced by `[REDACTED]` but redaction is a safety net not a guarantee (for example "my pin is 4821" is not caught), that a prompt starting with `#private` is skipped, and that anything typed is still sent to Claude.
- [ ] **Step 3: Verify end to end, in this order.**
  - `pytest -v` -> all PASS.
  - Seed a throwaway database with the transcript from this machine's session, using the hook with `HARNESS_DATABASE` pointing at a temp path (scratchpad), then run a short Python snippet calling `Store.list_chat_sessions()` and `search_chats("harness")`; expect at least one session and one hit, and no stored line containing an obvious secret.
  - Report honestly in the final message that `/eval-chat` is a prompt file and could not be run non-interactively here; the user should run `/eval-chat` once in `claude-code/` and confirm the output.

---

### Task 7: Learn about today

**Files:**
- Modify: `src/everyday_harness/store.py` (new `lessons` table and methods)
- Modify: `src/everyday_harness/tools.py`, `src/everyday_harness/mcp_server.py` (three tools; `definitions` stays at five)
- Modify: `claude-code/.claude/settings.json` (`get_chat_day` and `list_lessons` in `allow`; `save_lesson` in `ask`)
- Create: `claude-code/.claude/skills/learn-today/SKILL.md`
- Modify: `claude-code/CLAUDE.md`, `claude-code/README.md`, `tests/test_mcp_server.py` (expected tool set grows by three)
- Test: `tests/test_lessons.py`

**Interfaces:**
- Consumes: `chat_messages` from Task 2.
- Produces on `Store`:
  - `get_chat_day(self, day: str, limit: int = 400) -> list[dict[str, Any]]`: `day` is `YYYY-MM-DD` in local time. Converts the local day's start and end to UTC (`datetime.fromisoformat(day).astimezone()` for the start, plus one day for the end) and returns rows in that window as dicts with `session_id`, `role`, `content` (cut to 1500 chars), `created_at`, oldest first, at most `limit`.
  - `save_lesson(self, lesson_date: str, who: str, category: str, summary: str, evidence: str, next_time: str) -> dict[str, Any]`: validates `who` and `category` against the Global Constraints sets, raises `ValueError` otherwise; returns the saved row with its `id`.
  - `list_lessons(self, since: str | None = None, who: str | None = None, limit: int = 50) -> list[dict[str, Any]]`: newest first, `limit` clamped 1..100.
- Table: `lessons(id INTEGER PRIMARY KEY AUTOINCREMENT, lesson_date TEXT NOT NULL, who TEXT NOT NULL, category TEXT NOT NULL, summary TEXT NOT NULL, evidence TEXT NOT NULL, next_time TEXT NOT NULL, created_at TEXT NOT NULL)`. Evidence and summary pass through `redact` before saving.
- Tools (registry and MCP, same names): `get_chat_day(day: str) -> {"day": ..., "count": n, "messages": [...]}` (error dict on a bad date), `save_lesson(lesson_date, who, category, summary, evidence, next_time) -> dict`, `list_lessons(since: str | None = None, who: str | None = None) -> {"lessons": [...]}`. Text fields are required non-empty strings, summary and next_time max 300 chars, evidence max 1000.

- [ ] **Step 1: Write failing tests** in `tests/test_lessons.py`:
  - `test_get_chat_day_uses_local_calendar_day` (Review Focus 8): build timestamps with the same local-to-UTC conversion the code uses, one at 23:30 local on the target day and one at 00:30 local on the next day; only the first is returned.
  - `test_get_chat_day_empty_and_capped` (Review Focus 9): empty day returns `[]`; 500 seeded messages with `limit=400` return 400; content longer than 1500 chars is cut.
  - `test_save_lesson_rejects_bad_who_category_and_date` (Review Focus 10), through the registry so errors come back as dicts.
  - `test_save_lesson_redacts_secrets_in_evidence`.
  - `test_list_lessons_filters_by_who_and_since_newest_first`.
  - In `tests/test_mcp_server.py`: update the expected tool set and add `test_lesson_round_trip`.
  - In `tests/test_tools.py`: `test_python_harness_still_advertises_five_tools` must still pass.
- [ ] **Step 2: Run** `pytest tests/test_lessons.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** the table, store methods, validators, registry entries and MCP tools per the Interfaces block. Update `settings.json` (`ask` gets `mcp__everyday__save_lesson`).
- [ ] **Step 4: Write `SKILL.md`.** Frontmatter `name: learn-today` and a `description` that says: use when the user types `/learn-today` or says "Learn about today" / "learn about today." / asks to review today's chats for mistakes. Body, in order:
  1. Use today's local date, or the date in `$ARGUMENTS` if given. Call `get_chat_day`. If `count` is 0, say there are no saved chats for that day and stop.
  2. Call `list_lessons` for the last 30 days so repeats are noticed.
  3. Find mistakes on both sides using the Global Constraints categories. User side: unclear or wrong prompt, missing detail, changed mind mid-task. Assistant side: acted without asking when the request was vague, assumed instead of checking, claimed success without a matching `tool_result`, invented a fact. Each finding needs a quoted line as evidence; no evidence means do not list it.
  4. Present two short lists, "Your mistakes" and "My mistakes", each item as: what happened, evidence quote, what to do next time. Say which items repeat earlier lessons. Keep the tone practical and neutral. If there are none, say so.
  5. Ask which items to save. Call `save_lesson` only for approved items (each call triggers a permission prompt).
  6. End with one line: how many lessons were saved, and, if the same category has now appeared 3 or more times, propose (not apply) a one-line rule for `CLAUDE.md`.
  7. Make no other changes.
- [ ] **Step 5: Update docs.** `CLAUDE.md`: one line saying that "Learn about today" or `/learn-today` triggers the `learn-today` skill, plus the three tools. `claude-code/README.md`: a short "Learn about today" section with an example session, the category list, and that lessons are only saved after approval.
- [ ] **Step 6: Verify.** `pytest -v` -> all PASS. Seed a temp database with two messages (a vague prompt and an assistant reply that acts on it), call `get_chat_day`, `save_lesson` and `list_lessons` from a Python snippet, and confirm the results. Report honestly that the skill's judgement quality could only be confirmed by the user running "Learn about today" in `claude-code/`.
