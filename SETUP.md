# Setup

Two ways to run the same assistant. Both store notes and tasks in one local SQLite file (`data/harness.sqlite3`), so they share data. No database server and no Docker needed.

| | Python harness | Claude Code harness |
|---|---|---|
| Model | Any OpenAI-compatible endpoint | Claude (through Claude Code) |
| Needs `LLM_*` values in `.env` | Yes | No |
| Needs Claude Code installed | No | Yes |
| Start from | repo root | `claude-code/` |

Do steps 1 to 4 for both. Then follow part A, part B, or both.

## 1. Requirements

- Python 3.11 or newer
- Python version only: a model endpoint and a model name
- Claude Code version only: [Claude Code](https://claude.com/claude-code) installed and logged in

## 2. Install

Windows PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev,claude-code]"
Copy-Item .env.example .env
```

If PowerShell blocks activation, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` first.

macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev,claude-code]"
cp .env.example .env
```

Use `".[dev]"` instead if you only want the Python version. The `claude-code` extra adds the MCP library.

## 3. Fill in `.env`

| Variable | Needed by | Value |
|---|---|---|
| `LLM_BASE_URL` | Python | Endpoint URL. Example is a local one |
| `LLM_API_KEY` | Python | Provider key, or any text for a local endpoint |
| `LLM_MODEL` | Python | Model name your endpoint serves |
| `HARNESS_DATABASE` | Python | SQLite file path. Default `data/harness.sqlite3`, created automatically |
| `HARNESS_MAX_STEPS`, `HARNESS_MAX_TOOL_CALLS` | Python | Loop limits. Defaults are fine |

The Claude Code version ignores the `LLM_*` values and uses `../data/harness.sqlite3`, set in `claude-code/.mcp.json`. `.env` is ignored by Git. Never commit it.

## 4. Check the install

```bash
pytest
```

All tests should pass. They use temporary databases, not your real data.

## Part A: Python harness

From the repo root:

```bash
python -m everyday_harness
```

Try:

```text
Remember that my weekly review is on Friday afternoon.
Find my note about the weekly review.
Add a task titled Review the harness repository.
Show me my open tasks.
```

Type `exit` to quit. Optional model check: `python evals/run_evals.py`. It uses a temporary database.

Personalise by editing `config/assistant.md` (behaviour) and `config/profile.md` (your preferences).

## Part B: Claude Code harness

With the venv activated:

```bash
cd claude-code
claude
```

1. Approve the project MCP server `everyday` when asked.
2. Approve the `@../config/profile.md` import if asked.
3. Run `/mcp` and confirm `everyday` is connected with 5 tools.
4. Try the same example requests as above. `Mark task 1 done` asks for permission each time by design.

Claude Code must be started from a shell where the venv is active, so that `python` resolves to the venv.

Tool-call log (names and status only): `logs/claude-code-runs.jsonl`.

Do not remove the `deny` list in `claude-code/.claude/settings.json`. It is what stops the assistant from running shell commands or editing files.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `LLM_MODEL is missing` | Python version only. Set `LLM_MODEL` in `.env` |
| `everyday` MCP server fails or `No module named everyday_harness` | Venv not active when `claude` started, or step 2 skipped |
| Tools not listed in `/mcp` | Approve the project server, then restart `claude` |
| Python and Claude Code show different data | `HARNESS_DATABASE` in `.env` points somewhere other than `data/harness.sqlite3` |

## Backup and reset

- Backup: copy `data/harness.sqlite3`.
- Reset: stop the app and delete that file. A new one is created on next start.

## If you outgrow SQLite

Switch to PostgreSQL only if you need several users, a shared remote database, or semantic search. Only `src/everyday_harness/store.py` would change.
