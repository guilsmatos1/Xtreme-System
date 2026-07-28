#!/usr/bin/env python3
# ruff: noqa: T201
"""Discover pending Codex worker sessions and build Orca dispatch jobs."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_SESSIONS_DIR = Path.home() / ".codex" / "sessions"
DEFAULT_REPORTS_DIR = Path("docs/analyze-token-efficiency")
RECENT_SECONDS = 600
REPORT_SESSION_RE = re.compile(r"_Codex:\s*([A-Za-z0-9_.-]+)\s*·")
WORKER_CWD_RE = re.compile(
    r"(?:^|/)orca/workspaces/xtreme-system/(?P<issue>GUI-\d+)(?:/|$)",
    re.IGNORECASE,
)
ANALYZER_SKILL = "0007-analyze-single-session-token-efficiency"
ANALYZER_COMMAND = (
    "env CODEX_TOKEN_EFFICIENCY_CHILD=1 "
    'codex --model gpt-5.6-luna --config model_reasoning_effort="medium"'
)


@dataclass(frozen=True)
class Session:
    session_id: str
    issue: str
    rollout: Path
    timestamp: str
    mtime: float


def _metadata(payload: dict[str, Any]) -> dict[str, Any]:
    return payload if isinstance(payload, dict) else {}


def inspect_rollout(path: Path) -> Session | None:
    metadata: dict[str, Any] = {}
    has_tokens = False
    try:
        with path.open(encoding="utf-8") as stream:
            for line in stream:
                event = json.loads(line)
                if event.get("type") == "session_meta":
                    metadata = _metadata(event.get("payload", {}))
                elif (
                    event.get("type") == "event_msg"
                    and event.get("payload", {}).get("type") == "token_count"
                    and (event.get("payload", {}).get("info") or {}).get(
                        "total_token_usage"
                    )
                ):
                    has_tokens = True
    except (OSError, json.JSONDecodeError):
        return None

    if not metadata or not has_tokens or metadata.get("originator") != "codex-tui":
        return None
    match = WORKER_CWD_RE.search(str(metadata.get("cwd") or ""))
    session_id = str(metadata.get("session_id") or metadata.get("id") or "").strip()
    if not match or not session_id:
        return None
    stat = path.stat()
    return Session(
        session_id=session_id,
        issue=match.group("issue").upper(),
        rollout=path.resolve(),
        timestamp=str(metadata.get("timestamp") or ""),
        mtime=stat.st_mtime,
    )


def analyzed_session_ids(reports_dir: Path) -> set[str]:
    analyzed: set[str] = set()
    if not reports_dir.is_dir():
        return analyzed
    for report in reports_dir.glob("*.md"):
        try:
            match = REPORT_SESSION_RE.search(report.read_text(encoding="utf-8"))
        except OSError:
            continue
        if match:
            analyzed.add(match.group(1))
    return analyzed


def discover_pending(
    sessions_dir: Path,
    reports_dir: Path,
    current_session: str | None,
    now: float,
) -> tuple[list[Session], dict[str, int]]:
    analyzed = analyzed_session_ids(reports_dir)
    counts = {
        "rollouts": 0,
        "eligible": 0,
        "analyzed": 0,
        "current": 0,
        "recent": 0,
        "invalid": 0,
    }
    pending_by_id: dict[str, Session] = {}
    for rollout in sessions_dir.glob("**/*.jsonl"):
        counts["rollouts"] += 1
        session = inspect_rollout(rollout)
        if session is None:
            counts["invalid"] += 1
            continue
        counts["eligible"] += 1
        if session.session_id == (current_session or ""):
            counts["current"] += 1
            continue
        if now - session.mtime < RECENT_SECONDS:
            counts["recent"] += 1
            continue
        if session.session_id in analyzed:
            counts["analyzed"] += 1
            continue
        previous = pending_by_id.get(session.session_id)
        if previous is None or session.mtime > previous.mtime:
            pending_by_id[session.session_id] = session
    pending = sorted(
        pending_by_id.values(),
        key=lambda item: (item.timestamp, item.mtime, item.session_id),
    )
    return pending, counts


def report_path(reports_dir: Path, session: Session) -> Path:
    return (reports_dir / f"{session.issue}--{session.session_id}.md").resolve()


def session_job(reports_dir: Path, session: Session) -> dict[str, Any]:
    arguments = {
        "session_id": session.session_id,
        "issue": session.issue,
        "rollout": str(session.rollout),
        "report_path": str(report_path(reports_dir, session)),
    }
    return {
        "name": f"token-efficiency-{session.issue}-{session.session_id[:8]}",
        "command": ANALYZER_COMMAND,
        "skill": ANALYZER_SKILL,
        "skill_args": json.dumps(arguments, separators=(",", ":")),
        "worktree": {"mode": "current"},
    }


def prepare(args: argparse.Namespace) -> int:
    sessions_dir = Path(args.sessions_dir).expanduser()
    reports_dir = Path(args.reports_dir).expanduser()
    pending, counts = discover_pending(
        sessions_dir,
        reports_dir,
        args.current_session,
        args.now,
    )
    jobs = [session_job(reports_dir, session) for session in pending]
    if args.jobs_file:
        jobs_file = Path(args.jobs_file)
    else:
        descriptor, generated_path = tempfile.mkstemp(
            prefix="codex-token-efficiency-jobs-",
            suffix=".json",
        )
        os.close(descriptor)
        jobs_file = Path(generated_path)
    jobs_file.write_text(
        json.dumps({"jobs": jobs}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": "prepared",
                "jobs_file": str(jobs_file.resolve()),
                "pending": len(jobs),
                **counts,
            },
            separators=(",", ":"),
        )
    )
    return 0


def _job_arguments(job: dict[str, Any]) -> dict[str, Any]:
    raw = job.get("skill_args", "")
    parsed = json.loads(raw)
    return parsed if isinstance(parsed, dict) else {}


def verify(args: argparse.Namespace) -> int:
    data = json.loads(Path(args.jobs_file).read_text(encoding="utf-8"))
    jobs = data if isinstance(data, list) else data.get("jobs", [])
    completed: list[str] = []
    missing: list[str] = []
    invalid: list[str] = []
    for job in jobs:
        values = _job_arguments(job)
        session_id = str(values.get("session_id") or "")
        path = Path(str(values.get("report_path") or ""))
        if not path.is_file():
            missing.append(session_id)
            continue
        try:
            match = REPORT_SESSION_RE.search(path.read_text(encoding="utf-8"))
        except OSError:
            match = None
        if match is None or match.group(1) != session_id:
            invalid.append(session_id)
            continue
        completed.append(session_id)
    payload = {
        "status": "complete" if not missing and not invalid else "incomplete",
        "expected": len(jobs),
        "completed": completed,
        "missing": missing,
        "invalid": invalid,
    }
    print(json.dumps(payload, separators=(",", ":")))
    return 0 if payload["status"] == "complete" else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--jobs-file")
    prepare_parser.add_argument("--sessions-dir", default=str(DEFAULT_SESSIONS_DIR))
    prepare_parser.add_argument("--reports-dir", default=str(DEFAULT_REPORTS_DIR))
    prepare_parser.add_argument(
        "--current-session",
        default=os.environ.get("CODEX_THREAD_ID", ""),
    )
    prepare_parser.add_argument("--now", type=float, default=time.time())
    prepare_parser.set_defaults(func=prepare)

    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--jobs-file", required=True)
    verify_parser.set_defaults(func=verify)
    return parser


def main() -> int:
    try:
        args = build_parser().parse_args()
        return args.func(args)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"{type(exc).__name__}: {exc}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
