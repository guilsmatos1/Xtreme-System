#!/usr/bin/env python3
"""Build a compact token-efficiency profile from a Codex rollout."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

SESSIONS_DIR = Path.home() / ".codex" / "sessions"
MIN_DUPLICATE_CALLS = 2
FAILURE_PATTERNS = (
    re.compile(r"\bprocess exited with code [1-9]\d*\b", re.IGNORECASE),
    re.compile(r"\b(exit_code|exit code)[\"': =]+[1-9]\d*\b", re.IGNORECASE),
)


class ProfileError(Exception):
    """Raised when a rollout cannot produce a profile."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--session-id",
        default=os.environ.get("CODEX_THREAD_ID"),
        help="Codex session id; defaults to CODEX_THREAD_ID",
    )
    parser.add_argument("--rollout", type=Path, help="Explicit rollout JSONL")
    parser.add_argument("--limit", type=int, default=10)
    return parser.parse_args()


def find_rollout(session_id: str | None, explicit: Path | None) -> Path:
    if explicit:
        if not explicit.is_file():
            raise ProfileError(explicit)
        return explicit
    if not session_id:
        raise ProfileError(  # noqa: TRY003
            "--session-id or CODEX_THREAD_ID is required"
        )
    matches = list(SESSIONS_DIR.glob(f"**/*{session_id}*.jsonl"))
    if not matches:
        raise ProfileError(  # noqa: TRY003
            f"rollout not found for session {session_id}"
        )
    return max(matches, key=lambda path: path.stat().st_mtime)


def read_events(path: Path) -> list[dict[str, Any]]:
    events = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ProfileError(  # noqa: TRY003
                    f"invalid JSON on line {line_number}"
                ) from exc
    return events


def output_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"))


def parse_arguments(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {"value": raw}
    return parsed if isinstance(parsed, dict) else {"value": parsed}


def compact_argument(arguments: dict[str, Any], limit: int = 240) -> str:
    preferred = (
        "cmd",
        "path",
        "file_path",
        "query",
        "target",
        "ref_id",
        "workdir",
    )
    value = next((arguments[key] for key in preferred if key in arguments), arguments)
    text = output_text(value).replace("\n", " ")
    return text[:limit] + ("..." if len(text) > limit else "")


def message_text(payload: dict[str, Any]) -> str:
    chunks = [
        item["text"]
        for item in payload.get("content", [])
        if isinstance(item, dict) and isinstance(item.get("text"), str)
    ]
    return "\n".join(chunks)


def iso_key(timestamp: Any) -> str:
    return timestamp if isinstance(timestamp, str) else ""


def main() -> int:  # noqa: PLR0912
    args = parse_args()
    try:
        rollout = find_rollout(args.session_id, args.rollout)
        events = read_events(rollout)
    except ProfileError as exc:
        sys.stderr.write(f"{exc}\n")
        return 2

    token_events = [
        event
        for event in events
        if event.get("type") == "event_msg"
        and event.get("payload", {}).get("type") == "token_count"
        and event.get("payload", {}).get("info", {}).get("total_token_usage")
    ]
    if not token_events:
        sys.stderr.write("rollout has no token_count event\n")
        return 2

    cutoff_event = token_events[-1]
    cutoff = iso_key(cutoff_event.get("timestamp"))
    tokens = cutoff_event["payload"]["info"]["total_token_usage"]

    metadata: dict[str, Any] = {}
    calls: list[dict[str, Any]] = []
    outputs: dict[str, dict[str, Any]] = {}
    user_prompts: list[str] = []

    for event in events:
        timestamp = iso_key(event.get("timestamp"))
        if cutoff and timestamp > cutoff:
            continue
        payload = event.get("payload", {})
        if event.get("type") == "session_meta":
            metadata = payload
        elif event.get("type") == "response_item" and payload.get("type") in {
            "function_call",
            "custom_tool_call",
        }:
            arguments = parse_arguments(
                payload.get("arguments", payload.get("input"))
            )
            calls.append(
                {
                    "id": payload.get("call_id") or payload.get("id"),
                    "timestamp": timestamp,
                    "tool": payload.get("name", "unknown"),
                    "arguments": arguments,
                    "argument": compact_argument(arguments),
                }
            )
        elif (
            event.get("type") == "response_item"
            and payload.get("type")
            in {"function_call_output", "custom_tool_call_output"}
        ):
            text = output_text(payload.get("output", ""))
            outputs[str(payload.get("call_id"))] = {
                "timestamp": timestamp,
                "chars": len(text),
                "failed": any(pattern.search(text) for pattern in FAILURE_PATTERNS),
            }
        elif (
            event.get("type") == "response_item"
            and payload.get("type") == "message"
            and payload.get("role") == "user"
        ):
            text = message_text(payload).strip()
            if text:
                user_prompts.append(text)

    enriched = []
    for call in calls:
        output = outputs.get(str(call["id"]), {})
        enriched.append(
            {
                **call,
                "output_chars": output.get("chars", 0),
                "estimated_output_tokens": round(output.get("chars", 0) / 4),
                "failed": output.get("failed", False),
            }
        )

    signatures: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for call in enriched:
        normalized = json.dumps(
            call["arguments"], ensure_ascii=True, sort_keys=True, separators=(",", ":")
        )
        signatures[f"{call['tool']}\0{normalized}"].append(call)

    duplicates = []
    for group in signatures.values():
        if len(group) < MIN_DUPLICATE_CALLS:
            continue
        duplicates.append(
            {
                "tool": group[0]["tool"],
                "argument": group[0]["argument"],
                "count": len(group),
                "output_chars": sum(item["output_chars"] for item in group),
                "estimated_output_tokens": sum(
                    item["estimated_output_tokens"] for item in group
                ),
                "timestamps": [item["timestamp"] for item in group],
            }
        )

    def candidate(call: dict[str, Any]) -> dict[str, Any]:
        return {
            key: call[key]
            for key in (
                "timestamp",
                "tool",
                "argument",
                "output_chars",
                "estimated_output_tokens",
            )
        }

    largest = sorted(enriched, key=lambda item: item["output_chars"], reverse=True)
    failed = [candidate(call) for call in enriched if call["failed"]]
    task_prompt = user_prompts[-1] if user_prompts else ""

    profile = {
        "session": {
            "session_id": metadata.get("session_id") or metadata.get("id"),
            "cwd": metadata.get("cwd"),
            "originator": metadata.get("originator"),
            "cli_version": metadata.get("cli_version"),
            "rollout": str(rollout),
            "cutoff": cutoff,
        },
        "tokens": tokens,
        "task_prompt": task_prompt[:1200],
        "tool_counts": dict(Counter(call["tool"] for call in enriched).most_common()),
        "largest_outputs": [
            candidate(call) for call in largest[: args.limit] if call["output_chars"]
        ],
        "duplicate_calls": sorted(
            duplicates,
            key=lambda item: item["estimated_output_tokens"],
            reverse=True,
        )[: args.limit],
        "failed_calls": failed[: args.limit],
    }
    json.dump(profile, sys.stdout, ensure_ascii=False, separators=(",", ":"))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
