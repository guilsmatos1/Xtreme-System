---
name: 0006-orca-dispatch-skill-runner
description: >-
  Dispatches a list of skill invocations to specific Orca agents (claude,
  codex, omp, pi, grok, ...), one job at a time, using Orca Orchestration to
  detect completion (`worker_done`/`escalation`) and closing each agent's
  terminal window once its job is done. Generic: which skills, which agents,
  and which worktrees come from a jobs JSON file, not from fixed defaults.
---

# Orca Dispatch Skill Runner

Runs a sequence of jobs, each meaning "invoke skill `/<skill>` on agent `<agent>`",
one at a time: create/reuse a worktree, launch the requested agent, dispatch the
work through Orca Orchestration, wait for the agent to report completion, then
close its terminal window before starting the next job.

## Normal use

Use the helper. Do not reimplement the loop by hand with individual `orca` calls.

Invoke it as a background/detached process, not a single blocking foreground call —
a run with several jobs, or a single job whose agent takes a while, can easily exceed
a foreground command's timeout. Killing the foreground wrapper would not stop the
agent it already dispatched, and nothing would be left to poll it for `worker_done`.

```bash
python3 .agents/skills/0006-orca-dispatch-skill-runner/run_jobs.py run-jobs --jobs-file <path> --json
```

Run it in the background and poll its output/log periodically. The helper refuses to
start a second instance while one is already active (see Invariants) — if it does,
confirm the recorded PID is actually gone before treating the lock as stale.

Output is JSONL: compact progress events (`jobs_loaded`, one `job` event per completed
job) and a final object with `event:"summary"`.

At the end, report:

- `processed`
- `done`
- `escalation`
- `stuck`
- `errors`
- `warnings`

If the final summary has `status:"error"`, stop and report `errors`/`warnings`.

## Jobs file

A JSON file, either a bare array or `{"jobs": [...]}`. Each job:

```json
{
  "name": "audit-api-layer",
  "agent": "claude",
  "skill": "0001-analyze-codebase",
  "skill_args": "focus on the api layer only",
  "worktree": {
    "mode": "new",
    "name": "audit-api-layer",
    "repo": "name:xtreme-system",
    "base_branch": "master"
  }
}
```

Fields:

- `name` (optional): label used in logs and terminal title. Defaults to `job-<index>`.
- `skill` + `skill_args` (optional args), OR `prompt` (a raw prompt used verbatim instead
  of a skill invocation) — one of the two is required.
- `agent`: an Orca agent id (`claude`, `codex`, `omp`, `pi`, `grok`, `opencode`, `gemini`,
  `droid`, `cursor`, or another installed TUI agent). Launched via `orca worktree create
  --agent <id>` (new worktree) or `orca terminal create --command <id>` (existing/current).
- `command` (optional): a raw shell command overriding `agent`, for cases the bare agent id
  can't express — e.g. a specific Codex model/effort (`codex --model gpt-5.5 -c
  model_reasoning_effort="xhigh"`). One of `agent`/`command` is required.
- `worktree.mode`: `"new"` (default), `"existing"`, or `"current"`.
  - `"new"` requires `worktree.name`; optional `worktree.repo`, `worktree.base_branch`,
    `worktree.parent_worktree` (defaults to `--no-parent`, i.e. a top-level worktree).
  - `"existing"` requires `worktree.selector` (any Orca worktree selector: `name:...`,
    `path:...`, `branch:...`, `id:...`).
  - `"current"` targets the calling agent's own worktree (`--worktree active`).
- `keep_open` (optional, default `false`): if `true`, never close the terminal window
  even after `worker_done`. Use for a job whose output you want to inspect manually.

## Completion and window-closing contract

| status       | meaning                                                                                   | window                    |
| ------------ | ------------------------------------------------------------------------------------------ | ------------------------- |
| `done`       | Agent sent `worker_done` for this job's `taskId`/`dispatchId`.                              | Closed (`terminal close --tab`), unless `keep_open`. |
| `escalation` | Agent asked for human intervention.                                                          | Left open on purpose.     |
| `stuck`      | Per-job wait cap (`--job-timeout-seconds`, default 2h) expired with no `worker_done`.        | Left open.                |
| `error`      | Unexpected failure (missing handle, TUI never reached idle, task/dispatch creation failed). | Whatever exists is left as-is; the whole run stops. |

`worker_done` closes the window regardless of whether the agent's own report inside that
message describes success or failure — the job is *finished* either way, which is the
signal this skill closes on. If a job's outcome (success vs. failure) needs to gate
anything downstream, read it from the `done` event's `detail` (the `worker_done` message
body/payload) after the run, not from the window-closing decision itself.

## How dispatch works under the hood

Each job goes through `orca orchestration dispatch --task <id> --to <handle> --inject`,
which injects Orca's own lifecycle preamble into the target agent — that preamble is what
tells the agent to send `worker_done` (or `escalation`) itself when it stops. This script
does not write custom hook files or a bespoke "report" protocol; it relies entirely on
Orca Orchestration's standard worker contract (see the `orchestration` skill).

The task `--spec` sent to the agent is either:

- `prompt` verbatim, if the job set one, or
- `Invoke the skill /<skill> with these arguments: <skill_args>. Follow that skill's own
  SKILL.md exactly. Before acting, judge whether the request actually makes sense for this
  repo; if not, explain the problem and report that as the outcome instead of forcing a
  change.`

## Invariants

- Use only `run_jobs.py` to run a job list; do not hand-roll the loop.
- Only one `run-jobs` process may run at a time per repo, enforced by a PID lock file
  (`.run-jobs.lock` next to `run_jobs.py`). If a second invocation is refused, verify the
  recorded PID is truly dead before retrying.
- Completion detection MUST use Orca Orchestration (`worker_done`/`escalation`). Never
  fall back to `orca terminal wait --for exit` — most agents are interactive TUIs that
  never exit on their own.
- Jobs run strictly sequentially: the next job is not started until the current one
  reaches `done`, `escalation`, or `stuck`. An `error` stops the whole run.
- This skill never deletes worktrees or branches, and never force-closes a window before
  `worker_done`/`escalation`/`stuck` — only `terminal close` on an already-finished job.
- If Orchestration is unavailable, stop and tell the user to enable Settings > Experimental
  > Orchestration.
- A `worker_done`/`escalation` only counts when its payload's `taskId`/`dispatchId` match
  the job currently being waited on; the helper enforces this the same way
  `0002-linear-sequential-worktree` does.

## Debug / resume only

Use these only to inspect or resume a specific job. The normal path is `run-jobs`.

### Validate / inspect the jobs file

```bash
python3 .agents/skills/0006-orca-dispatch-skill-runner/run_jobs.py list-jobs --jobs-file <path> --json
```

### Start one job

Find the coordinator terminal handle with `orca terminal list --json`, then:

```bash
python3 .agents/skills/0006-orca-dispatch-skill-runner/run_jobs.py start-job \
  --jobs-file <path> --index 0 --coordinator-handle <coordinator_handle> --json
```

If it returns `pending`, keep `detail.task_id`, `detail.dispatch_id`, `detail.worker_handle`.

### Wait for one pending job

```bash
python3 .agents/skills/0006-orca-dispatch-skill-runner/run_jobs.py wait-job \
  --task-id <task_id> --dispatch-id <dispatch_id> --coordinator-handle <coordinator_handle> \
  --worker-handle <worker_handle> --json
```

Repeat while status is `pending`.
