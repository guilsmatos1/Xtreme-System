# Orca Orchestration Harness

Shared contract for loop skills that drive Orca workers via helpers
(`run_jobs.py`, `process_issue.py`, …). Each skill keeps its CLI, schema, and
domain status table; this file is the single source for how you *run* and *wait*.

## Background / detached

Always start the helper as a **background/detached** process. Never block a
foreground shell on the whole run.

A multi-job or multi-issue run routinely exceeds foreground timeouts. Killing the
wrapper does **not** stop workers already dispatched — they keep running with
nothing left to poll `worker_done` / `escalation`.

Poll the helper's log / JSONL periodically. Prefer redirecting stdout/stderr to a
log file under `.loop/` when the run is long.

## One instance + PID lock

Only one instance of a given helper may run per repo. Helpers enforce this with a
PID lock file next to the script (e.g. `.run-jobs.lock`, `.run-queue.lock`).

If a second start is refused: verify the recorded PID is **actually dead** before
treating the lock as stale. Never restart blindly on a failed liveness check.

## Completion detection

Completion **MUST** use Orca Orchestration (`worker_done` / `escalation`).

Never fall back to `orca terminal wait --for exit` — interactive TUIs usually do
not exit on their own.

A `worker_done` / `escalation` only counts when payload ids match the job being
waited on:

- `worker_done`: both `taskId` and `dispatchId` must match (unless the skill
  documents a hook-owned `worker_done` path).
- `escalation`: typically `taskId` only (pre-completion; may lack `dispatchId`).

If Orchestration is unavailable, stop and tell the user to enable
**Settings → Experimental → Orchestration**.

## Sequencing

Jobs / issues run **strictly sequentially**: do not start the next until the
current one reaches a terminal skill status (`done` / `escalation` / `stuck` /
skill-specific success|failure). An unexpected `error` usually stops the whole
run — see the calling skill.

## Windows and worktrees (generic)

- Do **not** force-close a terminal before `worker_done` / `escalation` / `stuck`.
  Close only finished jobs (`terminal close`), unless the skill leaves them open
  on purpose (`keep_open`, escalation, stuck).
- Remove a worktree only when the skill/helper **created** it and the skill's
  success path allows removal. Never force-remove dirty/unmergeable trees unless
  the skill explicitly documents a failed-path cleanup.
- Do not hand-roll `orca worktree create` / `orca terminal create` around a
  running helper — the helper owns lifecycle.

## Dispatch contract

Helpers that inject work use `orca orchestration dispatch` (or equivalent) so
Orca's lifecycle preamble tells the worker to emit `worker_done` / `escalation`.
Prefer the standard Orchestration worker contract (see the `orchestration`
skill) over bespoke hook protocols — unless the skill documents a Stop-hook
owned path (e.g. linear-run merge gate).

Acknowledge (`--ack`) consumed `check --wait` batches when the helper does; an
unacked batch replays and starves later `worker_done` messages.

## JSONL progress

Helpers emit JSONL progress events and a final object with `event:"summary"`.
Report the summary counters the skill lists. If `status:"error"`, stop and
surface `errors` / `warnings` — do not blindly retry.

## Debug / resume

Use per-skill `list-*` / `start-*` / `wait-*` helpers only to inspect or resume
one unit. Normal path is the bulk command (`run-jobs`, `run-queue`, …).
