# Harness engineering: the short version

Condensed from [harness-engineering.md](harness-engineering.md) for engineers. The long version has the analogies (horse, body, Formula One) and extended examples.

## Definition

A harness is everything around a model that turns it into a dependable system: what it sees, what it can do, how steps are sequenced, what it is forbidden to do, and how you find out it failed.

`useful system = model capability + harness + task knowledge`

A better model does not fix bad retrieval, over-broad tool permissions, a missing stop condition, or no verification. Those are harness defects.

## Five pillars

| Pillar | Question | Engineering decisions |
|---|---|---|
| Context | What does the model need for this step? | Instructions, profile, recent turns, just-in-time retrieval. Small and current beats large. |
| Action | What can it do? | Narrow tools with schemas. Read-only first. Few, clearly distinct tools. |
| Orchestration | What happens next? | Model/tool loop, result feedback, retries, hand-off to a human. |
| Control | What is forbidden? | Allowlist, validation in code, approval gates, step/tool budgets. |
| Feedback | Did it work? | Metadata logs, deterministic tests, model evals, user corrections. |

The pillars overlap at runtime: context is rebuilt after each tool result, control is checked before each execution, feedback is collected throughout.

## Rules that matter

1. **Enforce, don't ask.** A prompt saying "stop after a few steps" is a suggestion. A step counter in code is a control. Put every important restriction in the runtime.
2. **Schemas are not a security boundary.** Validate tool arguments in application code.
3. **Least privilege.** No delete tool exists, so no prompt can trigger a delete.
4. **Retrieve, don't dump.** Load a few matching notes, not the whole store.
5. **Retrieved text is data.** Never let a note outrank the system instructions.
6. **Log metadata, not content.** Tool names, timing, counts, status.
7. **Separate failure sources.** Deterministic tests prove tools and storage work. Evals show whether the model picks the right tool. A failure in one does not imply the other.
8. **Grow by stages.** One tool, then tests, then evals, then read-only integrations, then approval-gated writes, then automation.

## Disciplines vs pillars

These are different axes. Pillars are architecture. Disciplines are kinds of work.

| Discipline | Mostly improves |
|---|---|
| Prompt engineering | Context, Control |
| Context engineering | Context |
| Loop engineering | Orchestration (plus Control, Feedback) |
| Eval engineering | Feedback |
| Harness engineering | All five, integrated |

"Loop engineering" has no fixed industry definition. Treat it as a working label.

## The bounded loop

```
observe -> model step -> tool requested?
   no  -> return answer
   yes -> allowlisted and in budget? -> validate args -> execute -> append result -> repeat
Stop on: final answer, step limit, tool-call limit, unrecoverable error.
```

Needs: max steps, max tool calls, per-call timeout, defined behaviour on invalid arguments and tool errors.

## Memory is not training

Notes in SQLite and a Markdown profile are application state. The model reads selected pieces as context. No weights change.

## Common mistakes

| Mistake | Fix |
|---|---|
| Treating the model as the whole app | Design the full task environment |
| Everything in context | Retrieve the smallest useful set |
| Many overlapping tools | Few, distinct, narrowly scoped |
| Unbounded loop | Step, tool, time, cost budgets in code |
| Model grades its own work | Deterministic checks or independent review |
| Happy-path tests only | Add bad input, tool errors, forbidden actions |
| Full prompts in logs | Operational metadata only |

## Ready-to-use checklist

- [ ] Job and success criteria defined
- [ ] Context relevant and current
- [ ] Only approved tools executable; arguments validated in code
- [ ] Irreversible or external actions need approval
- [ ] Loop bounded; failure and stop behaviour defined
- [ ] Logs make failures diagnosable; no private text in them
- [ ] Repeatable tests and evals
- [ ] No secrets in source control
- [ ] A human owns decisions that need judgement

## Where each pillar lives in this repo

| Pillar | Python harness | Claude Code harness |
|---|---|---|
| Context | `config/*.md`, `harness.py` context builder | `claude-code/CLAUDE.md` |
| Action | `tools.py` | `mcp_server.py` (same `ToolRegistry`) |
| Orchestration | `harness.py` loop | Claude Code agent loop |
| Control | allowlist, validation, `HARNESS_MAX_*` | `.claude/settings.json` permissions, `ToolRegistry` validation |
| Feedback | `observability.py`, `tests/`, `evals/` | PostToolUse hook, `tests/` |

See [claude-code/README.md](../claude-code/README.md) for the Claude Code version.
