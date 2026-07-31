import importlib.util
import json
import subprocess
from pathlib import Path
from types import ModuleType

import pytest


def _load_verify_hook() -> ModuleType:
    path = Path(__file__).parents[1] / ".codex/hooks/verify-on-stop.py"
    spec = importlib.util.spec_from_file_location("verify_on_stop", path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_failed_checks_block_before_finish(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hook = _load_verify_hook()
    report = {"phase": "success", "summary": "done"}
    payload = {"cwd": str(tmp_path), "session_id": "session-1"}
    blocked: list[str] = []
    finished = False

    (tmp_path / ".codex/.hook-state").mkdir(parents=True)
    (tmp_path / ".codex/.hook-state/report.json").write_text(
        json.dumps(report), encoding="utf-8"
    )

    def fail_checks(
        _root: Path,
    ) -> tuple[str, list[str], subprocess.CompletedProcess[str]]:
        return (
            "pre-commit",
            [],
            subprocess.CompletedProcess(["pre-commit"], 1, "failed", ""),
        )

    def must_not_finish(_root: Path) -> tuple[bool, str]:
        nonlocal finished
        finished = True
        return True, ""

    monkeypatch.setattr(hook, "run_checks", fail_checks)
    monkeypatch.setattr(hook, "run_agent_finish", must_not_finish)
    monkeypatch.setattr(hook, "block", blocked.append)

    result = hook.checks_stage(tmp_path, payload, report, None, True)

    assert result is False
    assert blocked
    assert not finished


def test_missing_edit_marker_does_not_bypass_checks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hook = _load_verify_hook()
    payload = {"cwd": str(tmp_path), "session_id": "session-1"}
    blocked: list[str] = []

    def fail_checks(
        _root: Path,
    ) -> tuple[str, list[str], subprocess.CompletedProcess[str]]:
        return (
            "pre-commit",
            [],
            subprocess.CompletedProcess(["pre-commit"], 1, "failed", ""),
        )

    monkeypatch.setattr(hook, "working_tree_dirty", lambda _root: True)
    monkeypatch.setattr(hook, "run_checks", fail_checks)
    monkeypatch.setattr(hook, "block", blocked.append)

    result = hook.checks_stage(tmp_path, payload, None, None, True)

    assert result is False
    assert blocked


def test_finish_failure_blocks_before_reporting_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hook = _load_verify_hook()
    blocked: list[str] = []
    finalized = False

    def fail_finish(_root: Path) -> tuple[bool, str]:
        return False, "pre-commit failed"

    def must_not_finalize(*_args: object, **_kwargs: object) -> bool:
        nonlocal finalized
        finalized = True
        return True

    monkeypatch.setattr(hook, "run_agent_finish", fail_finish)
    monkeypatch.setattr(hook, "block", blocked.append)
    monkeypatch.setattr(hook, "finalize", must_not_finalize)

    result = hook.integrate_reported(
        tmp_path,
        {"phase": "success", "summary": "done"},
        None,
        True,
    )

    assert result is False
    assert blocked
    assert not finalized
