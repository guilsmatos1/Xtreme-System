#!/usr/bin/env bash
set -euo pipefail

# Records how the agent finished its turn, for the Stop hook to act on.
#
# The agent does NOT report completion to the coordinator itself: it only states
# its own verdict here. After the turn ends, `.codex/hooks/verify-on-stop.py`
# runs the checks, commits and merges into master, and only then sends
# `worker_done`. Going through a file is what guarantees the merge happens
# BEFORE the coordinator is told the issue is finished -- an `orca orchestration
# send` from inside the turn always races the Stop hook.
#
# Written under .codex/.hook-state/ because that directory is gitignored:
# `agent-finish.sh` runs `git add -A`, and this file must never reach master.

phase="${1:-}"
summary="${2:-}"

case "${phase}" in
  success | failed) ;;
  *)
    printf '%s\n' "agent-report: phase must be 'success' or 'failed' (got '${phase}')" >&2
    exit 2
    ;;
esac

root="$(git rev-parse --show-toplevel)"
state_dir="${root}/.codex/.hook-state"
mkdir -p "${state_dir}"

OUT="${state_dir}/report.json" PHASE="${phase}" SUMMARY="${summary}" python3 -c '
import json
import os
import pathlib

pathlib.Path(os.environ["OUT"]).write_text(
    json.dumps({"phase": os.environ["PHASE"], "summary": os.environ["SUMMARY"]}),
    encoding="utf-8",
)
'

printf '%s\n' "agent-report: recorded ${phase}; the finish hook will commit, merge and report"
