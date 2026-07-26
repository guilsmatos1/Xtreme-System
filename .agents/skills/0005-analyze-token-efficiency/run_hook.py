#!/usr/bin/env python3
"""Run the token-efficiency skill in a fresh, isolated Codex context."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

CHILD_ENV = "CODEX_TOKEN_EFFICIENCY_CHILD"
SESSION_ENV = "CODEX_THREAD_ID"
REPORT_ENV = "CODEX_TOKEN_REPORT_PATH"
BRANCH_ENV = "CODEX_SOURCE_BRANCH"
TIMEOUT_SECONDS = 900


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--source-branch", default="unknown")
    return parser.parse_args()


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", value) or "unknown"


def report_path(checkout: Path, branch: str) -> Path:
    return (
        checkout
        / "docs"
        / "0005-analyze-token-efficiency"
        / f"{safe_name(branch)}.md"
    )


def main() -> int:
    args = parse_args()
    checkout = Path.cwd()
    output = report_path(checkout, args.source_branch)
    output.parent.mkdir(parents=True, exist_ok=True)

    codex = shutil.which("codex")
    if codex is None:
        sys.stderr.write("codex executable not found\n")
        return 127

    env = {
        **os.environ,
        CHILD_ENV: "1",
        SESSION_ENV: args.session_id,
        REPORT_ENV: str(output),
        BRANCH_ENV: args.source_branch,
    }
    prompt = (
        "Use a skill 0005-analyze-token-efficiency. "
        "Analise somente a sessao indicada por CODEX_THREAD_ID, grave o relatorio "
        "em CODEX_TOKEN_REPORT_PATH e nao altere codigo do produto."
    )
    try:
        result = subprocess.run(  # noqa: S603
            [
                codex,
                "exec",
                "--ephemeral",
                "-C",
                str(checkout),
                "--sandbox",
                "workspace-write",
                "-a",
                "never",
                prompt,
            ],
            cwd=checkout,
            env=env,
            check=False,
            timeout=TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        sys.stderr.write(
            f"token-efficiency retrospective timed out after {TIMEOUT_SECONDS}s\n"
        )
        return 124
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
