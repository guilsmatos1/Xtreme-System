#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

MAX_OUTPUT_CHARS = 12000


def project_dir(payload: dict) -> Path:
    return Path(payload.get("cwd") or ".")


def working_tree_dirty(root: Path) -> bool:
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    return bool(result.stdout.strip())


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0

    if payload.get("stop_hook_active"):
        return 0

    root = project_dir(payload)
    if not working_tree_dirty(root):
        return 0

    result = subprocess.run(
        ["scripts/agent-finish.sh"],
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
                    "Agent finish hook failed "
                    "(scripts/agent-finish.sh):\n\n"
                    f"{output}\n\nFix the failures, then stop again."
                ),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
