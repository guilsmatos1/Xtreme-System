---
name: devops--ask-xtreme
description: Router over xtreme-system skills — which flow fits the current situation.
disable-model-invocation: true
metadata:
    skill-organizer:
        original-name: devops--ask-xtreme
        source-relative-path: devops/ask-xtreme
        disabled: false
        risk-score: 0
        risk-evaluated-at: ""
        risk-evaluator: ""
        risk-reason: ""
        risk-source-hash: ""
---

# Ask Xtreme

You don't remember every skill, so ask. Map the user's situation to a **flow**, then name the skills to run. Do not start the work until they pick a path (unless they already named a skill).

Read `CONTEXT.md` for domain vocabulary when explaining options.

## Main flows

### Idea → ship (default for new work)

Keep grilling → spec → tickets in **one** context window; clear context before each implement.

1. **`coding--ship--grill-with-docs`** (codebase present) or **`coding--ship--grill-me`** — alignment first. Both drive `coding--ship--grilling`; with-docs also runs `coding--ship--domain-modeling`.
2. **`coding--ship--to-spec`** — synthesize a spec under `.loop/running/specs/` (optional `orca linear create`; never `devops--linear--send`).
3. Multi-session? **`coding--ship--to-tickets`** — tracer bullets under `.loop/running/tickets/` (optional Linear create).
4. Per ticket / small change: **`coding--ship--implement`** → drives **`coding--ship--tdd`**, then **`coding--review--standards-spec`**.

### Audit (find issues, don't ship)

Use when they want a review, debt list, or risk scan.

1. Pick the matching `coding--analyze--*` skill (security, concurrency, duplicates, performance, …). Prefer the narrowest skill; use `coding--analyze--general` only when the ask is broad.
2. That skill hands findings to `coding--generate--issues-md`.
3. Optional: `devops--linear--send` to turn analysis Markdown into Linear Issues (audit batches only — not the ship flow).

### Ship a known change

Use when the work is already clear (Issue GUI-*, numbered ticket file, or agreed plan) — skip grilling if already aligned.

1. Prefer an existing Linear Issue or `.loop/running/tickets/...` file.
2. **`coding--ship--implement`** in a fresh context (worktree / subagent). Clear context between tickets.
3. Close with `coding--review--standards-spec` against the Issue + fixed point before merge.
4. Deploy path: `devops--deploy--commit-merge` → `devops--deploy--git-push` (user-invoked).

### Drain the Linear queue

Use when they want the backlog emptied automatically.

→ `loops--task-orchestration--linear-run` (user-invoked).

### Dispatch many skills across agents

1. `loops--task-orchestration--job-generator` → jobs JSON
2. `loops--task-orchestration--skill-dispatcher` (user-invoked)

### Run a numbered checklist

→ `loops--task-orchestration--sequential-workers` (user-invoked).

## On-ramps

| Situation | Skill |
|-----------|--------|
| Sharpen an idea before building | `coding--ship--grill-with-docs` / `coding--ship--grill-me` |
| Something broken / flaky / slow | `coding--debug--diagnosing-bugs` (HTMX UI → also `coding--debug--playwright-cli`) |
| Duplicate Linear tickets | `devops--linear--duplicate-triage` |
| Compact this chat for another agent | `devops--handoff` |
| Sync skill trees after editing skills | `devops--skill-organizer` |
| Token-efficiency / harness loop | `loops--loop-runner--token-efficiency` → `loops--state-management--consolidate-harness` → `loops--loop-runner--apply-harness` |
| Compare against another repo | `coding--analyze--reference-repo` |
| UX / product gaps | `coding--analyze--ui-ux` / `coding--analyze--features` |

## Vocabulary layer

- Domain terms: `CONTEXT.md`
- Architecture / API / DB contracts: `ARCHITECTURE.md`, `API.md`, `DATABASE.md` (on-demand)
- Graph orientation: `graphify query` / `explain` / `path`

## Invocation note

Skills marked user-invoked (`disable-model-invocation: true`) only run when the human names them — including this router, queue drains, and deploy skills. Model-invoked skills (analyze, diagnosing-bugs, standards-spec) can be reached automatically when the task fits.
