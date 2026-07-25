#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

MAX_OUTPUT_CHARS = 12000
# Bare `uv run pytest` always exits 4 here: the suite requires TEST_DATABASE_URL.
# `make test` would satisfy it, but it points every run at the single shared
# xtreme_test database on localhost:5432 -- parallel worktree agents would corrupt
# each other's runs and get blocked by failures that are not theirs. The SQLite
# fallback keeps each worktree isolated; `make test` in CI remains the real gate
# against the Alembic-migrated Postgres schema.
CHECKS = [
    ("ruff-fix", ["uv", "run", "ruff", "check", "--fix"], {}),
    ("ruff", ["uv", "run", "ruff", "check", "."], {}),
    ("ruff-format", ["uv", "run", "ruff", "format", ".", "--check"], {}),
    ("mypy", ["uv", "run", "mypy"], {}),
    (
        "pytest",
        ["env", "XTREME_ALLOW_SQLITE_TEST_DB=1", "uv", "run", "pytest"],
        {},
    ),
]


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


def state_path(root: Path, session_id: str) -> Path:
    safe_session = re.sub(r"[^A-Za-z0-9_.-]", "_", session_id or "unknown")
    return root / ".codex" / ".hook-state" / f"{safe_session}.json"


def run_checks(
    root: Path,
) -> tuple[str, list[str], subprocess.CompletedProcess[str]] | None:
    for name, command, env_overrides in CHECKS:
        result = subprocess.run(  # noqa: S603
            command,
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
            env={**os.environ, **env_overrides} if env_overrides else None,
        )
        if result.returncode != 0:
            return name, command, result
    return None


def block(reason: str) -> None:
    print(json.dumps({"decision": "block", "reason": reason}))


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0

    if payload.get("stop_hook_active"):
        return 0

    root = project_dir(payload)
    path = state_path(root, payload.get("session_id", ""))
    if path.exists():
        path.unlink(missing_ok=True)
        failed_check = run_checks(root)
        if failed_check is not None:
            name, command, result = failed_check
            output = (result.stdout + result.stderr)[-MAX_OUTPUT_CHARS:]
            block(
                "\n".join(
                    [
                        f'Post-edit check "{name}" failed.',
                        "",
                        f"Command: {' '.join(command)}",
                        "",
                        "```",
                        output or f"{name} failed without output.",
                        "```",
                        "",
                        "Fix failures, then stop again.",
                    ]
                )
            )
            return 0

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
    block(
        "Agent finish hook failed "
        "(scripts/agent-finish.sh):\n\n"
        f"{output}\n\nFix the failures, then stop again."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
