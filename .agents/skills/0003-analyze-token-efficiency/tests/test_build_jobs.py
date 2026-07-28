# ruff: noqa: S101

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "build_jobs.py"
SPEC = importlib.util.spec_from_file_location("build_jobs", MODULE_PATH)
assert SPEC is not None
assert SPEC.loader is not None
build_jobs = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = build_jobs
SPEC.loader.exec_module(build_jobs)


def write_rollout(
    path: Path,
    *,
    session_id: str,
    issue: str = "GUI-123",
    timestamp: str = "2026-07-20T10:00:00Z",
    originator: str = "codex-tui",
    with_tokens: bool = True,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    events = [
        {
            "type": "session_meta",
            "payload": {
                "session_id": session_id,
                "timestamp": timestamp,
                "cwd": f"/Users/test/orca/workspaces/xtreme-system/{issue}",
                "originator": originator,
            },
        }
    ]
    if with_tokens:
        events.append(
            {
                "type": "event_msg",
                "payload": {
                    "type": "token_count",
                    "info": {"total_token_usage": {"total_tokens": 10}},
                },
            }
        )
    path.write_text(
        "".join(json.dumps(event) + "\n" for event in events),
        encoding="utf-8",
    )


def make_old(path: Path, now: float, age: float = 3600) -> None:
    os.utime(path, (now - age, now - age))


def test_discover_pending_filters_and_orders_sessions(tmp_path: Path) -> None:
    now = 2_000_000_000.0
    sessions = tmp_path / "sessions"
    reports = tmp_path / "reports"
    reports.mkdir()

    later = sessions / "later.jsonl"
    earlier = sessions / "earlier.jsonl"
    current = sessions / "current.jsonl"
    recent = sessions / "recent.jsonl"
    no_tokens = sessions / "no-tokens.jsonl"
    wrong_origin = sessions / "wrong-origin.jsonl"
    write_rollout(
        later,
        session_id="session-later",
        issue="GUI-222",
        timestamp="2026-07-21T10:00:00Z",
    )
    write_rollout(
        earlier,
        session_id="session-earlier",
        timestamp="2026-07-20T10:00:00Z",
    )
    write_rollout(current, session_id="session-current")
    write_rollout(recent, session_id="session-recent")
    write_rollout(no_tokens, session_id="session-no-tokens", with_tokens=False)
    write_rollout(wrong_origin, session_id="session-other", originator="exec")
    for path in (later, earlier, current, no_tokens, wrong_origin):
        make_old(path, now)
    make_old(recent, now, age=60)

    (reports / "GUI-222--session-later.md").write_text(
        "_Codex: session-later · input: 1_\n",
        encoding="utf-8",
    )
    pending, counts = build_jobs.discover_pending(
        sessions,
        reports,
        "session-current",
        now,
    )

    assert [session.session_id for session in pending] == ["session-earlier"]
    assert counts["analyzed"] == 1
    assert counts["current"] == 1
    assert counts["recent"] == 1


def test_session_job_uses_isolated_luna_agent_in_current_worktree(
    tmp_path: Path,
) -> None:
    rollout = tmp_path / "rollout.jsonl"
    write_rollout(rollout, session_id="session-123", issue="GUI-987")
    session = build_jobs.inspect_rollout(rollout)
    assert session is not None

    job = build_jobs.session_job(tmp_path / "reports", session)
    arguments = json.loads(job["skill_args"])

    assert job["worktree"] == {"mode": "current"}
    assert job["skill"] == "0007-analyze-single-session-token-efficiency"
    assert "gpt-5.6-luna" in job["command"]
    assert 'model_reasoning_effort="medium"' in job["command"]
    assert "CODEX_TOKEN_EFFICIENCY_CHILD=1" in job["command"]
    assert arguments["report_path"].endswith("GUI-987--session-123.md")


def test_inspect_rollout_ignores_empty_token_info(tmp_path: Path) -> None:
    rollout = tmp_path / "rollout.jsonl"
    write_rollout(rollout, session_id="session-empty-info", with_tokens=False)
    with rollout.open("a", encoding="utf-8") as stream:
        stream.write(
            json.dumps(
                {
                    "type": "event_msg",
                    "payload": {"type": "token_count", "info": None},
                }
            )
            + "\n"
        )

    assert build_jobs.inspect_rollout(rollout) is None


def test_verify_requires_matching_report_session(tmp_path: Path, capsys) -> None:
    valid = tmp_path / "valid.md"
    invalid = tmp_path / "invalid.md"
    missing = tmp_path / "missing.md"
    valid.write_text("_Codex: session-valid · input: 1_\n", encoding="utf-8")
    invalid.write_text("_Codex: another-session · input: 1_\n", encoding="utf-8")
    jobs_file = tmp_path / "jobs.json"
    jobs_file.write_text(
        json.dumps(
            {
                "jobs": [
                    {
                        "skill_args": json.dumps(
                            {
                                "session_id": session_id,
                                "report_path": str(report),
                            }
                        )
                    }
                    for session_id, report in (
                        ("session-valid", valid),
                        ("session-invalid", invalid),
                        ("session-missing", missing),
                    )
                ]
            }
        ),
        encoding="utf-8",
    )

    result = build_jobs.verify(type("Args", (), {"jobs_file": str(jobs_file)})())
    payload = json.loads(capsys.readouterr().out)

    assert result == 1
    assert payload["completed"] == ["session-valid"]
    assert payload["invalid"] == ["session-invalid"]
    assert payload["missing"] == ["session-missing"]


def test_prepare_creates_and_reports_temporary_jobs_file(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    sessions = tmp_path / "sessions"
    reports = tmp_path / "reports"
    sessions.mkdir()
    monkeypatch.setattr(build_jobs.tempfile, "tempdir", str(tmp_path))
    args = type(
        "Args",
        (),
        {
            "sessions_dir": str(sessions),
            "reports_dir": str(reports),
            "current_session": "",
            "now": 2_000_000_000.0,
            "jobs_file": None,
        },
    )()

    assert build_jobs.prepare(args) == 0
    payload = json.loads(capsys.readouterr().out)
    jobs_file = Path(payload["jobs_file"])

    assert jobs_file.is_file()
    assert json.loads(jobs_file.read_text(encoding="utf-8")) == {"jobs": []}
