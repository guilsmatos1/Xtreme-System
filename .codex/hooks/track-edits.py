#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

EDIT_COMMAND_RE = re.compile(
    r"\b(apply_patch|cat\s*>|tee\b|sed\s+-i|python\b|mv\b|cp\b|rm\b|touch\b)\b"
)


def state_path(cwd: str, session_id: str) -> Path:
    safe_session = re.sub(r"[^A-Za-z0-9_.-]", "_", session_id or "unknown")
    return Path(cwd) / ".codex" / ".hook-state" / f"{safe_session}.json"


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0

    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input") or {}
    command = str(tool_input.get("command", ""))

    edited = tool_name == "apply_patch" or (
        tool_name == "Bash" and bool(EDIT_COMMAND_RE.search(command))
    )
    if not edited:
        return 0

    cwd = payload.get("cwd") or "."
    path = state_path(cwd, payload.get("session_id", ""))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"edited": True}), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
