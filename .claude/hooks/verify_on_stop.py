#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

MAX_OUTPUT_CHARS = 12000
SOURCE_SUFFIXES = (".py", ".ts", ".js", ".tsx", ".jsx")


def project_dir(payload: dict) -> Path:
    return Path(os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or ".")


def changed_source_files(root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    return [
        path for path in result.stdout.splitlines() if path.endswith(SOURCE_SUFFIXES)
    ]


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0

    # Safety valve: never block a stop that is itself the result of a
    # previous block, or we could loop forever on checks Claude can't fix.
    if payload.get("stop_hook_active"):
        return 0

    root = project_dir(payload)
    changed = changed_source_files(root)
    if not changed:
        return 0

    result = subprocess.run(  # noqa: S603
        ["uv", "run", "pre-commit", "run", "--files", *changed],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        return 0

    output = (result.stdout + result.stderr)[-MAX_OUTPUT_CHARS:]
    print(
        json.dumps(
            {
                "decision": "block",
                "reason": (
                    "Post-edit checks failed "
                    "(uv run pre-commit run --files ...):\n\n"
                    f"{output}\n\nFix the failures, then stop again."
                ),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
