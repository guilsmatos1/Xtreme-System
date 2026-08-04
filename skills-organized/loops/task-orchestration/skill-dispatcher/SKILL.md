---
name: loops--task-orchestration--skill-dispatcher
description: Dispatch skill jobs to Orca agents one-at-a-time from a jobs JSON file.
disable-model-invocation: true
metadata:
    skill-organizer:
        original-name: loops--task-orchestration--skill-dispatcher
        source-relative-path: loops/task-orchestration/skill-dispatcher
        disabled: false
        risk-score: 0
        risk-evaluated-at: ""
        risk-evaluator: ""
        risk-reason: ""
        risk-source-hash: ""
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
# Run a single jobs file
python3 skills-organized/loops/task-orchestration/skill-dispatcher/run_jobs.py run-jobs --jobs-file <path> --json

# Run multiple workflows sequentially (E) — concatenates their jobs in order
python3 skills-organized/loops/task-orchestration/skill-dispatcher/run_jobs.py run-jobs --workflows ui-ux features duplicates --json
```

### Example job files (workflows)

Pre-built job configurations are available in the `workflow/` directory:

```bash
python3 skills-organized/loops/task-orchestration/skill-dispatcher/run_jobs.py run-jobs \
  --jobs-file skills-organized/loops/task-orchestration/skill-dispatcher/workflow/workflow-jobs-general.json \
  --json
```

Available workflows:
- `workflow-jobs-general.json` — general code analysis + Linear issue creation + Linear run
- `workflow-jobs-features.json` — feature analysis + Linear issue creation + Linear run
- `workflow-jobs-duplicates.json` — duplicate code analysis + Linear issue creation + Linear run
- `workflow-jobs-ui-ux.json` — UI/UX analysis + Linear issue creation + Linear run
- `workflow-jobs-llm-adherence.json` — LLM adherence analysis + Linear issue creation + Linear run

## E: Multi-Workflow Sequential Execution

Run multiple pre-built workflows back-to-back without manually merging JSON files.
Use `--workflows` followed by one or more bare workflow names (space-separated).
Jobs from each workflow are concatenated in the given order and run sequentially
as a single merged list. Duplicate job names across workflows are automatically
suffixed with the source workflow slug.

```bash
# Natural language equivalent: "Execute ui-ux, features, duplicates"
python3 skills-organized/loops/task-orchestration/skill-dispatcher/run_jobs.py \
  run-jobs --workflows ui-ux features duplicates --json

# Single workflow (equivalent to --jobs-file workflow/jobs-ui-ux.json)
python3 skills-organized/loops/task-orchestration/skill-dispatcher/run_jobs.py \
  run-jobs --workflows ui-ux --json
```

`--workflows` is mutually exclusive with `--jobs-file`. Accepted name formats:
- Bare slug: `ui-ux`, `features`, `duplicates`, `general`, `llm-adherence`
- With prefix: `jobs-ui-ux`, `workflow-jobs-ui-ux`
- Full path: `/absolute/path/to/jobs.json`

**When the user says something like** "Execute ui-ux, features, duplicates" **or** "Run the ui-ux and features workflows", translate it directly to `--workflows ui-ux features` (or whichever names were mentioned) and invoke `run-jobs` with that flag.

### Helper: resolve_workflow_path

The `run_jobs.py` script provides a helper function `resolve_workflow_path(workflow_name)` that resolves workflow files from the `workflow/` directory. It accepts:

- A bare name (e.g., `"general"`) — automatically prefixes with `workflow-` and adds `.json`
- A name with `.json` extension (e.g., `"general.json"`)
- A name with `workflow-` prefix (e.g., `"workflow-general"`)
- A full path

It searches relative to the repo root and the script's directory.

```bash
# Using the helper programmatically
python3 -c "
from run_jobs import resolve_workflow_path
print(resolve_workflow_path('general'))
print(resolve_workflow_path('workflow-jobs-features.json'))
"
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
  "skill": "coding--analyze--general",
  "skill_args": "focus on the api layer only",
  "retries": 2,
  "retry_delay_seconds": 10,
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
  Also suppresses worktree removal (see `remove_worktree`).
- `remove_worktree` (optional, default `true`): if the job's outcome is `done`, `worktree.mode`
  is `"new"` (i.e. this job created the worktree), and `keep_open` is not set, remove the
  worktree via `orca worktree rm --worktree <selector>` right after the terminal closes.
  Never applies to `"existing"` or `"current"` mode, since the job does not own those
  worktrees. Removal is best-effort: a dirty/unmergeable worktree is left in place with a
  warning rather than forced (`--force` is not passed).
- `retries` (optional, default `0`): how many times to retry the job on a transient
  `error` before propagating the failure. Does **not** retry `escalation` or `stuck`.
- `retry_delay_seconds` (optional, default `5`): seconds to wait between attempts.
  Set to `0` for immediate retries.

## Completion and window-closing contract

| status       | meaning                                                                                   | window                    |
| ------------ | ------------------------------------------------------------------------------------------ | ------------------------- |
| `done`       | Agent sent `worker_done` for this job's `taskId`/`dispatchId`.                              | Closed (`terminal close --tab`), unless `keep_open`. If `worktree.mode` is `"new"`, the worktree is also removed unless `keep_open` or `remove_worktree: false`. |
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

## Checkpointing and Resume (A)

After each job completes with `done`, its name is written to a sidecar file
`<jobs-file>.state.json` next to the jobs file. If the coordinator process crashes or is
killed mid-run, restart with `--resume` to skip all jobs already recorded as `done`:

```bash
python3 skills-organized/loops/task-orchestration/skill-dispatcher/run_jobs.py \
  run-jobs --jobs-file <path> --resume --json
```

If you want to re-run everything from scratch, delete (or rename) the `.state.json` file
before the next invocation.

## Retry Policy (B)

Add `"retries": N` and optionally `"retry_delay_seconds": M` to any job that may hit
transient errors (e.g. terminal startup races, orchestration timeouts). On each `error`
the helper emits a `{"event":"retry", ...}` JSONL event, waits the configured delay,
then tries again. `escalation` and `stuck` are **never** retried — they require human
attention.

## Static Skill Validation (D)

Before the first job starts, `run-jobs` scans `.agents/skills/` and `skills-organized/`
(relative to CWD and the script's own directory) and verifies that every `skill` name
declared in the jobs file exists as a directory. If any skill is unknown the run stops
immediately with an `error` summary, before any terminal or worktree is created:

```
{"event":"summary","status":"error","errors":[{"reason":"skill validation failed: Unknown skill(s): ['typo-skill']. ..."}], ...}
```

Jobs using `prompt` instead of `skill` are exempt from this check.

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
- This skill never force-closes a window before `worker_done`/`escalation`/`stuck` — only
  `terminal close` on an already-finished job. It removes a worktree only when it created
  that worktree itself (`worktree.mode: "new"`), the job reached `done`, and neither
  `keep_open` nor `remove_worktree: false` opted out; `"existing"`/`"current"` worktrees and
  branches are never touched. Removal never forces past a dirty worktree.
- If Orchestration is unavailable, stop and tell the user to enable Settings > Experimental
  > Orchestration.
- A `worker_done`/`escalation` only counts when its payload's `taskId`/`dispatchId` match
  the job currently being waited on; the helper enforces this the same way
  `loops--task-orchestration--linear-run` does.

## Debug / resume only

Use these only to inspect or resume a specific job. The normal path is `run-jobs`.

### Validate / inspect the jobs file

```bash
python3 skills-organized/loops/task-orchestration/skill-dispatcher/run_jobs.py list-jobs --jobs-file <path> --json
```

### Start one job

Find the coordinator terminal handle with `orca terminal list --json`, then:

```bash
python3 skills-organized/loops/task-orchestration/skill-dispatcher/run_jobs.py start-job \
  --jobs-file <path> --index 0 --coordinator-handle <coordinator_handle> --json
```

If it returns `pending`, keep `detail.task_id`, `detail.dispatch_id`, `detail.worker_handle`.

### Wait for one pending job

```bash
python3 skills-organized/loops/task-orchestration/skill-dispatcher/run_jobs.py wait-job \
  --task-id <task_id> --dispatch-id <dispatch_id> --coordinator-handle <coordinator_handle> \
  --worker-handle <worker_handle> --json
```

Repeat while status is `pending`.
