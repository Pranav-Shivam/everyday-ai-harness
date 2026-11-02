# Everyday AI Harness on Claude Code

Same assistant, same five tools plus read-only chat history tools, same SQLite database. Claude Code supplies the model loop, so this version has no `llm.py` or `harness.py` to maintain. You configure the harness with files instead of Python.

## Mapping

| Pillar | File | Role |
|---|---|---|
| Context | `CLAUDE.md` (imports `../config/profile.md`) | Role, tool rules, safety, your profile |
| Action | `.mcp.json` -> `src/everyday_harness/mcp_server.py` | Exposes the five tools over MCP |
| Orchestration | Claude Code | Model/tool loop |
| Control | `.claude/settings.json` | Allows the 4 safe tools, prompts on `update_task_status`, denies shell, file edit, web, subagents |
| Control | `ToolRegistry` | Argument validation, shared with the Python version |
| Feedback | `.claude/hooks/log_tool.py` | Logs tool name and status to `../logs/claude-code-runs.jsonl`. No content |
| Feedback | `.claude/hooks/capture_chat.py` | Saves chats (redacted) to the database for search, `/eval-chat` and `Learn about today` |

## Setup

Full instructions: [../SETUP.md](../SETUP.md). Short version, from the repository root:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev,claude-code]"
Copy-Item .env.example .env
```

macOS or Linux: `source .venv/bin/activate` instead of the Activate script.

Keep the venv activated, then start Claude Code from this folder:

```bash
cd claude-code
claude
```

Approve the project MCP server `everyday` when prompted. The first launch may also ask to approve the `@../config/profile.md` import.

Try: `Remember that my weekly review is Friday afternoon`, `What did I save about my review?`, `Add a task: draft the article, due 2026-11-05`, `Mark task 1 done` (this one asks for permission).

## Chat history, review and privacy

Every time Claude finishes answering, the `Stop` hook (`.claude/hooks/capture_chat.py`) copies the session transcript into the shared SQLite database (`chat_messages` table). Only new messages are added, so running it twice never duplicates anything.

| You say | What happens |
|---|---|
| `What did we decide about the review last week?` | Claude searches saved chats (`search_chats`, `list_chat_sessions`, `get_chat_session`) |
| `/eval-chat` or `/eval-chat <session-id>` | Claude grades one saved chat against a fixed checklist and suggests improvements |
| `Learn about today` or `/learn-today` | Claude lists mistakes by you and by itself from today's chats, with quoted evidence. Only lessons you approve are saved (`lessons` table) |

Lesson categories: `unclear_prompt`, `missing_detail`, `changed_mind` (yours); `acted_without_asking`, `assumed_instead_of_checking`, `claimed_without_proof`, `invented_fact` (Claude's); `other`.

Privacy:

- Stored text goes through `src/everyday_harness/redact.py` first. Known key formats, tokens, passwords after labels like `password=`, private keys, passwords inside URLs, and card numbers become `[REDACTED]`. This is pattern matching, a safety net and not a guarantee: something like "my pin is 4821" is not caught.
- Start a message with `#private` and neither it nor Claude's reply to it is saved.
- Redaction protects what is stored. Everything you type is still sent to Claude.
- The database is under `data/`, which Git ignores.
- Claude's own grading in `/eval-chat` and "Learn about today" is self-review. Spot-check what it flags.

## Differences from the Python version

| | Python harness | Claude Code harness |
|---|---|---|
| Model | Any OpenAI-compatible endpoint | Claude |
| Loop limits | `HARNESS_MAX_STEPS`, `HARNESS_MAX_TOOL_CALLS` | None by default. In non-interactive mode use `claude -p --max-turns 6` |
| Recent-note retrieval into context | Automatic per turn | Model calls `search_notes` when `CLAUDE.md` tells it to |
| Evals | `evals/run_evals.py` | `/eval-chat` and `Learn about today` review saved chats |
| Moving parts | 8 Python modules | 1 MCP server, 1 hook, 2 config files |

The database is shared (`../data/harness.sqlite3`), so notes and tasks created in one version are visible in the other.

## Keep the boundary

The deny list in `.claude/settings.json` is what keeps this a notes-and-tasks assistant. Do not remove `Bash`, `Edit`, or `Write` from it without a plan: the assistant would then be able to modify the repository it runs from. Add integrations by registering a new MCP server and allowing only its read-only tools first.
