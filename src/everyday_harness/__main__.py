"""Interactive command-line interface."""

from __future__ import annotations

from .config import load_settings
from .harness import AgentHarness


def main() -> None:
    try:
        settings = load_settings()
        assistant = AgentHarness(settings)
    except Exception as exc:
        print(f"Configuration error: {exc}")
        print("Check your .env file and the paths configured there.")
        raise SystemExit(1) from exc

    history: list[dict[str, str]] = []
    print("Everyday AI Harness")
    print("Ask a question, save a note, or manage your tasks. Type exit to quit.")

    while True:
        try:
            user_input = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break

        if user_input.lower() in {"exit", "quit"}:
            print("Goodbye.")
            break
        if not user_input:
            continue

        result = assistant.run_turn(user_input, history)
        print(f"\nAssistant: {result.answer}")
        print(
            f"\n[steps={result.steps}, tools={result.tool_calls}, "
            f"latency={result.elapsed_ms} ms]"
        )
        history.extend(
            [
                {"role": "user", "content": user_input},
                {"role": "assistant", "content": result.answer},
            ]
        )


if __name__ == "__main__":
    main()
