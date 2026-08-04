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

Runs jobs ("invoke skill `/<skill>` on agent `<agent>`") one at a time: worktree →
launch agent → Orchestration dispatch → wait → close terminal → next job.

Follow [../../references/orchestration-harness.md](../../references/orchestration-harness.md)
for background runs, PID locks, `worker_done` matching, sequencing, and window/worktree rules.
Do not reimplement the loop with hand-rolled `orca` calls.

## Normal use

```bash
python3 skills-organized/loops/task-orchestration/skill-dispatcher/run_jobs.py run-jobs --jobs-file <path> --json

python3 skills-organized/loops/task-orchestration/skill-dispatcher/run_jobs.py run-jobs \
  --workflows ui-ux features duplicates --json
```

`--workflows` is mutually exclusive with `--jobs-file`. Names: bare slug (`ui-ux`),
`jobs-ui-ux`, `workflow-jobs-ui-ux`, or an absolute path. When the user says
"Execute ui-ux, features, duplicates", map to `--workflows ui-ux features duplicates`.

Pre-built files live under `workflow/` (`workflow-jobs-general.json`, `features`,
`duplicates`, `ui-ux`, `llm-adherence`).

Output is JSONL; final `event:"summary"`. Report: `processed`, `done`, `escalation`,
`stuck`, `errors`, `warnings`. Stop on `status:"error"`.

## Jobs file

JSON array or `{"jobs": [...]}`. Each job:

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

- `name` (optional): log/terminal label; default `job-<index>`.
- `skill` + optional `skill_args`, **or** `prompt` (verbatim) — one required.
- `agent`: Orca agent id (`claude`, `codex`, `omp`, `pi`, `grok`, …). Optional `command`
  overrides `agent` for raw TUI flags (e.g. Codex model/effort). One of `agent`/`command` required.
- `worktree.mode`: `"new"` (default; needs `name`), `"existing"` (needs `selector`), or `"current"`.
- `keep_open` (default `false`): leave terminal open after `worker_done`; also skips worktree removal.
- `remove_worktree` (default `true`): on `done` + mode `"new"` + not `keep_open`, best-effort
  `orca worktree rm` (never `--force`; never for existing/current).
- `retries` / `retry_delay_seconds`: retry transient `error` only — never `escalation`/`stuck`.

Task `--spec` is `prompt` verbatim, or: invoke `/<skill>` with args, follow that SKILL.md,
and refuse nonsensical requests instead of forcing a change.

## Status → window (this skill)

| status | meaning | window |
| ------ | ------- | ------ |
| `done` | `worker_done` for this job's ids | Close unless `keep_open`; may remove new worktree |
| `escalation` | Human intervention | Leave open |
| `stuck` | Job wait cap (default 2h) | Leave open |
| `error` | Unexpected failure | Leave as-is; **stop the run** |

`worker_done` closes the window whether the agent's report was success or failure — the job
is *finished*. Gate downstream work on `detail`, not on the close decision.

## Checkpoint / resume / validate

- After each `done`, name is recorded in `<jobs-file>.state.json`. Restart with `--resume`
  to skip completed jobs; delete the state file to rerun from scratch.
- Before the first job, unknown `skill` names fail the run (jobs with only `prompt` are exempt).
- Debug only: `list-jobs`, `start-job`, `wait-job` (see harness). Normal path is `run-jobs`.

## Skill-specific invariants

- Use only `run_jobs.py`; lock file `.run-jobs.lock` next to it.
- This skill closes windows only after finish; removes worktrees only when it created them
  (`mode: "new"`) and policy allows — see harness for the shared rules.
