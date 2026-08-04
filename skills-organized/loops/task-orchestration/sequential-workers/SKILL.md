---
name: loops--task-orchestration--sequential-workers
description: Run a numbered task list sequentially in isolated subagents.
disable-model-invocation: true
metadata:
    skill-organizer:
        original-name: loops--task-orchestration--sequential-workers
        source-relative-path: loops/task-orchestration/sequential-workers
        disabled: false
        risk-score: 0
        risk-evaluated-at: ""
        risk-evaluator: ""
        risk-reason: ""
        risk-source-hash: ""
---

# Sequential Orchestrator with Workers

You are the ORCHESTRATOR. Your function is to execute a list of tasks sequentially, each in an isolated subagent worker.

## Main Flow

1. **Receive the list** of tasks from the user.
2. **For each item**, execute the cycle below.
3. **At the end**, deliver the general validation report.

## Cycle per Item

For each task `N` in the list:

### 1. State Collection
Before launching the worker, collect the current repository state:
- `git status --short`
- `git diff --stat`
- List of recent commits: `git log --oneline -5`

### 2. Create Subagent Worker
Launch a subagent of type `general` with a prompt containing:

```
Task: [description of the current item]

Repository state:
[git status]

Changes already applied in previous items:
[cumulative summary of items 1..N-1, with modified files]

Instructions:
- Implement ONLY the task described above.
- Do not modify unrelated code.
- Follow the project conventions (AGENTS.md, CONTEXT.md).
- For build/fix tasks, follow coding--ship--tdd at pre-agreed seams
  (red before green; vertical slices). Prefer coding--ship--implement
  discipline when the item is a ticket/spec slice.
- Once finished, run relevant tests and linters to validate.
- Return: (a) summary of what was done, (b) list of modified files,
  (c) test/lint commands executed and their results.
```

Rules:
- **Always** use a new subagent (task_id absent). Never reuse context from a previous worker.
- The worker must return exactly what was requested: summary, files, tests.

### 3. Post-Worker Validation
After the worker finishes:
- Check the modified files with `git diff --stat`
- Run the tests/lints indicated by the worker (supplement if necessary)
- If there are failures, fix them or request adjustments before committing

### 4. Commit
```bash
git add [modified files]
git commit -m "[concise task description]"
```
Capture the commit hash.

### 5. Update Cumulative State
Append to the cumulative summary:
```
Item N: [description]
  Files: [list]
  Commit: [hash]
  Summary: [1-2 lines]
```

### 6. Close and Advance
The subagent worker terminates automatically. Proceed to the next item.

## Conflict Resolution

If item `N` conflicts with changes from previous items:
- Adjust the worker prompt to consider the current state of the files.
- If necessary, provide specific snippets of the already modified code.
- If the conflict is unavoidable (e.g., two tasks modify the same function in incompatible ways), report to the user and stop.

## Final Report

Upon completing all items, perform a general validation:
```bash
git diff --stat HEAD~N   # all changes of the session
uv run ruff check .
uv run pytest -q
```

Deliver:

```
=== EXECUTION REPORT ===

Items completed: N/N
Total time: Xmin

Commits:
  [hash1] Item 1: description
  [hash2] Item 2: description
  ...

Files modified:
  src/foo.py
  src/bar.py
  tests/test_foo.py

Tests executed:
  ruff check .  -> Passed
  pytest -q     -> XX passed

Pending risks:
  [list only if any]
```
