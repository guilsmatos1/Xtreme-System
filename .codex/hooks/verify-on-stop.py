#!/usr/bin/env python3
"""Post-turn gate for codex agents in this repo.

Runs the post-edit checks, integrates the work into master, and -- for workers
driven by the 0002-linear-sequential-worktree skill -- reports completion to the
coordinator. The report is sent HERE, after the merge, on purpose: an agent that
sends `worker_done` from inside its own turn always races this hook, and the
coordinator would start the next issue from a master missing the previous one.

The agent only states its verdict, via `scripts/agent-report.sh`. Two files in
the gitignored .codex/.hook-state/ drive this:
  report.json        written by the agent: {"phase": "success"|"failed", "summary": ...}
  orchestration.json written by process_issue.py at dispatch: the ids to report to

No report.json means "not a worker, or the agent stopped mid-task": the hook
stays silent so a coordinator keeps waiting instead of reading an unfinished
turn as a result.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

MAX_OUTPUT_CHARS = 12000
BODY_LIMIT = 1200
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


def hook_state_dir(root: Path) -> Path:
    return root / ".codex" / ".hook-state"


def read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


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
    return hook_state_dir(root) / f"{safe_session}.json"


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


def run_agent_finish(root: Path) -> tuple[bool, str]:
    """Commit and merge into master. Idempotent: a second call on an already
    merged branch is a no-op (`git merge` reports "Already up to date")."""
    result = subprocess.run(
        ["scripts/agent-finish.sh"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0, (result.stdout + result.stderr)[-MAX_OUTPUT_CHARS:]


def block(reason: str) -> None:
    print(json.dumps({"decision": "block", "reason": reason}))


def send_worker_done(context: dict, phase: str, body: str) -> str | None:
    """Report completion to the coordinator. Returns an error string, or None."""
    missing = [
        key
        for key in ("coordinatorHandle", "taskId", "dispatchId")
        if not context.get(key)
    ]
    if missing:
        return f"orchestration context is missing {', '.join(missing)}"

    orca = shutil.which("orca") or "/opt/homebrew/bin/orca"
    identifier = context.get("identifier", "issue")
    result = subprocess.run(  # noqa: S603
        [
            orca,
            "orchestration",
            "send",
            "--to",
            context["coordinatorHandle"],
            "--type",
            "worker_done",
            "--task-id",
            context["taskId"],
            "--dispatch-id",
            context["dispatchId"],
            "--phase",
            phase,
            "--subject",
            f"{identifier} finished",
            "--body",
            (body or phase)[:BODY_LIMIT],
            "--json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return (result.stdout + result.stderr)[-MAX_OUTPUT_CHARS:]
    return None


def finalize(
    root: Path,
    context: dict | None,
    phase: str,
    body: str,
    can_block: bool,
) -> None:
    """Send the verdict exactly once, then consume the agent's report.

    Consuming only after a successful send is what makes a retry possible: while
    report.json exists the next stop tries again. When retrying is no longer
    possible (`can_block` is false), the file is dropped and the failure is left
    on disk -- the coordinator falls back to its own merge verification.
    """
    report = hook_state_dir(root) / "report.json"
    if context is None:
        report.unlink(missing_ok=True)
        return

    error = send_worker_done(context, phase, body)
    if error is None:
        report.unlink(missing_ok=True)
        return

    if can_block:
        block(
            "Could not report completion to the coordinator "
            f"(orca orchestration send, phase={phase}):\n\n{error}\n\n"
            "The work is already committed and merged. Stop again to retry the report."
        )
        return

    report.unlink(missing_ok=True)
    (hook_state_dir(root) / "report-error.log").write_text(error, encoding="utf-8")


def checks_stage(
    root: Path,
    payload: dict,
    report: dict | None,
    context: dict | None,
    can_block: bool,
) -> bool:
    """Run the post-edit checks. Returns True when the turn is already resolved."""
    session_state = state_path(root, payload.get("session_id", ""))
    if not session_state.exists():
        return False

    session_state.unlink(missing_ok=True)
    failed_check = run_checks(root)
    if failed_check is None:
        return False

    name, command, result = failed_check
    output = (result.stdout + result.stderr)[-MAX_OUTPUT_CHARS:]
    if can_block:
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
        return True

    # Second failure in a row, with no block left to ask for a fix. A red tree
    # must not reach master, so report the failure instead: the coordinator
    # resets the issue for a later retry, rather than waiting out its 2h cap on
    # a worker that will never report.
    if report is not None:
        finalize(
            root,
            context,
            "failed",
            f'post-edit check "{name}" still failing:\n{output}',
            can_block,
        )
    return True


def integrate_unreported(root: Path, can_block: bool) -> None:
    """No verdict on disk: not a worker, or an agent that stopped mid-task.

    Keeps the historical behaviour -- integrate whatever is pending -- and
    reports nothing, so a coordinator keeps waiting instead of reading an
    unfinished turn as a result.
    """
    if not working_tree_dirty(root):
        return
    ok, output = run_agent_finish(root)
    if not ok and can_block:
        block(
            "Agent finish hook failed "
            "(scripts/agent-finish.sh):\n\n"
            f"{output}\n\nFix the failures, then stop again."
        )


def integrate_reported(
    root: Path,
    report: dict,
    context: dict | None,
    can_block: bool,
) -> None:
    phase = str(report.get("phase", "")).strip().lower()
    summary = str(report.get("summary", ""))

    # Fails closed: only an explicit success is allowed to reach master. A failed
    # attempt must never be merged -- the coordinator deletes its branch
    # afterwards, but a merge commit would outlive that cleanup and leave the
    # broken work in master forever.
    if phase != "success":
        body = summary or "worker reported failure"
        finalize(root, context, "failed", body, can_block)
        return

    ok, output = run_agent_finish(root)
    if not ok:
        # Implementation is fine, integration is not. `merge_failed` stops the
        # whole run with the worktree and branch intact, instead of discarding
        # work that only needs a human to resolve a conflict.
        finalize(
            root,
            context,
            "merge_failed",
            f"{summary}\n\nscripts/agent-finish.sh failed:\n{output}",
            can_block,
        )
        return

    finalize(root, context, "success", summary, can_block)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0

    root = project_dir(payload)
    # `stop_hook_active` means this stop already follows a block of ours.
    # Blocking again risks an endless loop, so from here the hook has to resolve
    # the turn itself instead of asking the agent for another pass.
    can_block = not payload.get("stop_hook_active")

    report = read_json(hook_state_dir(root) / "report.json")
    context = read_json(hook_state_dir(root) / "orchestration.json")

    if checks_stage(root, payload, report, context, can_block):
        return 0

    if report is None:
        integrate_unreported(root, can_block)
        return 0

    integrate_reported(root, report, context, can_block)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
