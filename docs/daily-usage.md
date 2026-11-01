# Configure the harness for everyday use

This guide shows how to make the starter project useful without turning it into a complex autonomous system.

## 1. First-run checklist

1. Install Python 3.11 or newer.
2. Create and activate a virtual environment.
3. Install the project and development dependencies.
4. Copy `.env.example` to `.env`.
5. Set a model endpoint and model name.
6. Run the assistant.
7. Save one test note and add one test task.
8. Close and reopen the assistant, then retrieve the note and task.

This checks that both the model connection and persistent storage work.

## 2. Tune the assistant's permanent behaviour

Edit `config/assistant.md` when a rule should apply every time. Keep the file focused on stable behaviour, tool-use conditions, and safety boundaries.

Good permanent rules:

- Do not invent dates or owners.
- Separate confirmed facts from assumptions.
- Use a saved note only when it is relevant to the current request.
- Do not save information unless the user asks.
- Ask before external or irreversible actions.

Avoid adding a long list of instructions for rare one-off tasks. Put one-time requirements in the user's message.

## 3. Tune personal context

Edit `config/profile.md` for stable preferences. Useful entries include preferred language, response style, recurring work context, or formats you use often.

Keep sensitive and temporary information out of the profile. Use saved notes for information the user explicitly asks to retain. Remove stale notes from the SQLite database through a database utility you control, or start a fresh database by changing `HARNESS_DATABASE`.

## 4. How memory works in this starter

The harness also includes the computer-reported local date and time in each turn so relative dates can be interpreted more reliably.

There are two memory-like sources:

1. The profile file is always added to the system context.
2. Saved notes live in SQLite. The context builder retrieves up to three potentially relevant notes for each request. The `search_notes` tool can retrieve up to five results on demand.

This is not automatic model training. The model does not rewrite its weights or silently rewrite its own instructions. Memory is application data that the harness stores and selectively retrieves.

The simple keyword retrieval is appropriate for a small collection. It is not semantic search. If your note collection grows, replace it with SQLite FTS5 or a retrieval system with embeddings and metadata filtering.

## 5. Daily examples

| What you type | Expected behaviour |
|---|---|
| `Remember that I prefer concise status updates.` | Store a note. |
| `Find the note about status updates.` | Search saved notes. |
| `Add a task titled Prepare Monday's project update.` | Add a task. |
| `Show my open tasks.` | List open tasks. |
| `Mark task 3 as done.` | Change the selected task status only because you explicitly requested it. |
| `Explain how a tool-calling loop works.` | Answer normally without a tool call. |

## 6. Make it part of a routine

A useful manual routine is:

**Morning:** ask for open tasks, add any new tasks, and request a prioritised plan.

**During the day:** save decisions or facts that you explicitly want to retrieve later. Add follow-up tasks when needed.

**End of day:** ask for the open task list and compare it with what you completed. This starter does not mark tasks complete automatically. That keeps task state under your control.

Start with manual use. Only add a scheduled trigger after you know that the workflow behaves correctly and you understand what it can access.

## 7. Extending the tool set safely

For each new tool, document:

- The exact action it performs.
- The data it can read.
- The data it can change.
- Its input schema and output schema.
- Its permission requirement.
- Its expected failure modes.
- How it is tested.

Prefer read-only tools first. For any tool that sends, publishes, deletes, purchases, or changes external records, add an approval step enforced by application code. Do not rely only on an instruction in `assistant.md`.

## 8. GitHub workflow

1. Create a new empty GitHub repository.
2. Copy the contents of this project into the repository.
3. Check that `.env`, `data/`, and `logs/` are not staged.
4. Commit the source, documentation, and tests.
5. Add a clear repository description, such as `A small local-first harness for everyday AI notes and tasks`.
6. Keep personal notes and API credentials on your own machine, not in the public repository.

A clean repository makes the harness easier to understand and allows you to version instructions, tools, tests, and architecture decisions independently from private data.
