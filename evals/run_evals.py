"""Run a small model-backed tool-use evaluation set."""

from __future__ import annotations

import json
import tempfile
from dataclasses import replace
from pathlib import Path

from everyday_harness.config import load_settings
from everyday_harness.harness import AgentHarness
from everyday_harness.store import Store


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    settings = load_settings()
    cases = json.loads((ROOT / "evals" / "cases.json").read_text(encoding="utf-8"))

    with tempfile.TemporaryDirectory(prefix="everyday-harness-evals-") as temp_dir:
        eval_settings = replace(
            settings,
            database_path=Path(temp_dir) / "eval.sqlite3",
            log_path=Path(temp_dir) / "eval-runs.jsonl",
        )
        assistant = AgentHarness(eval_settings, store=Store(eval_settings.database_path))
        history: list[dict[str, str]] = []
        passed = 0

        print("Model-backed harness evaluations")
        print("=" * 38)

        for case in cases:
            result = assistant.run_turn(case["input"], history)
            expected = case["expected_tool"]
            success = expected in result.tool_names
            passed += int(success)
            label = "PASS" if success else "FAIL"
            print(f"{label} | {case['name']} | expected tool: {expected}")
            if not success:
                print(f"  observed tools: {result.tool_names}")
                print(f"  response: {result.answer[:240]}")
            history.extend(
                [
                    {"role": "user", "content": case["input"]},
                    {"role": "assistant", "content": result.answer},
                ]
            )

        print("=" * 38)
        print(f"Result: {passed}/{len(cases)} passed")
        return 0 if passed == len(cases) else 1


if __name__ == "__main__":
    raise SystemExit(main())
