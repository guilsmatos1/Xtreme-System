# Harness Improvements — Accumulated Ranking

_Last updated: 2026-07-26. Processed sources: loop-2-2026-07-24, docs/loops--loop-runner--token-efficiency/GUI-108.md, docs/loops--loop-runner--token-efficiency/GUI-109.md, docs/loops--loop-runner--token-efficiency/GUI-120.md, docs/loops--loop-runner--token-efficiency/GUI-159.md, docs/loops--loop-runner--token-efficiency/GUI-168.md, docs/loops--loop-runner--token-efficiency/GUI-349.md, docs/loops--loop-runner--token-efficiency/GUI-360.md, docs/loops--loop-runner--token-efficiency/GUI-361.md, docs/loops--loop-runner--token-efficiency/GUI-362.md, docs/loops--loop-runner--token-efficiency/GUI-363.md, docs/loops--loop-runner--token-efficiency/GUI-365.md, docs/loops--loop-runner--token-efficiency/GUI-366.md, docs/loops--loop-runner--token-efficiency/GUI-367.md, docs/loops--loop-runner--token-efficiency/GUI-368.md, docs/loops--loop-runner--token-efficiency/GUI-369.md._

_5 improvements (24 mentions) have already been applied to the harness by skill `loops--loop-runner--apply-harness` and removed from this ranking. See `../loops--loop-runner--apply-harness/implementations.md`._

## Improvements

### 6. Stair-step verification / avoid duplicate suite runs
- **Problem:** Focused tests + full suite + rerun after lint, while commit hooks run pytest again: duplicated and slow validation.
- **Solution:** After a small final change, run only impacted tests/lint; leave the full suite for hooks/CI; rerun the full suite only if the change touches central logic or the user requires it.
- **Estimated savings:** ~500-3k tokens + execution time.
- **Sources:** loop-2/GUI-267.md, loop-2/GUI-302.md, loop-2/GUI-323.md

### 7. Deterministic and safe devops--deploy--commit-merge
- **Problem:** The skill recommends `git add .` and `git commit -am`, which is redundant/incorrect for new files and dangerous in a dirty worktree.
- **Solution:** Explicit flow: `git status --short`; explicitly stage files changed by the task; `git commit -m`; never use `git add .` in a possibly dirty repo; handle the "no changes" case clearly.
- **Estimated savings:** ~500-1k tokens from fewer defensive checks.
- **Sources:** loop-2/GUI-268.md, loop-2/GUI-323.md

### 8. Precheck master-worktree merge blockers
- **Problem:** The skill discovers that the master worktree is dirty, or that there is file overlap, only after committing, even though the merge blocker was predictable earlier.
- **Solution:** Before merge, check `git status --short` in the master worktree and compare `git diff --name-only master...HEAD` with the target; if there is overlap/dirty state, stop/ask before committing.
- **Estimated savings:** ~1k-2k tokens + 4-6 calls.
- **Sources:** loop-2/GUI-302.md, loop-2/GUI-323.md

### 9. Fixed repo command shortcuts (test/lint)
- **Problem:** The agent reads the entire README to discover test/lint commands that are already standard in this workspace.
- **Solution:** Add fixed harness shortcuts for this repo (`uv run rtk pytest [<path>]`, `uv run rtk ruff check <paths>`) and/or a `verify_changed_python` macro (ruff+mypy+relevant tests in compact output).
- **Estimated savings:** ~800-4k tokens.
- **Sources:** loop-2/GUI-274.md, loop-2/GUI-304.md

### 10. Pre-task impact-analysis subagent
- **Problem:** The main agent spends many tokens reading files only to confirm they do not use a symbol, or to map protected vs unprotected paths manually.
- **Solution:** Lightweight subagent that receives a symbol/import to remove, or a target, and returns only: callers (grep), files that need rollback guard, dependent fixtures. Nothing else.
- **Estimated savings:** ~13k tokens.
- **Sources:** loop-2/GUI-Others.md (x2: impact-analysis, impact-scan)

### 11. Lint before commit
- **Problem:** The commit fails due to ruff/format/focused-test rules, creating another patch/stage/commit cycle with large hook output.
- **Solution:** In Python tasks with new tests or code edits, run `ruff check`, `ruff format --check`, and the focused test before committing.
- **Estimated savings:** ~1k-18k tokens + 2-3 calls.
- **Sources:** loop-2/GUI-302.md, docs/loops--loop-runner--token-efficiency/GUI-349.md

### 12. Linear auto-context (injected summary)
- **Problem:** Reading the ticket requires loading a skill and running `orca status`, spending tokens on long instructions and large JSON.
- **Solution:** For linked worktrees, automatically inject a short issue summary: title, description, state, branch, and labels.
- **Estimated savings:** ~2k-4k tokens.
- **Sources:** loop-2/GUI-267.md

### 13. Use RTK only for voluminous outputs
- **Problem:** `rtk git ...` adds a layer and extra rules with no benefit for short-output commands such as `status --short`.
- **Solution:** Use RTK only for potentially voluminous commands (diff, large log, grep); for `status --porcelain`, `merge-base`, and `branch`, use direct `git`.
- **Estimated savings:** ~5-10% of task tokens.
- **Sources:** loop-2/GUI-268.md

### 14. Summarize git worktree list automatically
- **Problem:** `git worktree list` returns dozens of worktrees, taking a lot of context, when only the master location matters.
- **Solution:** Instruct RTK/harness to summarize to "current worktree + master worktree + target branch", omitting others unless there is a conflict.
- **Estimated savings:** ~1k-2k tokens.
- **Sources:** loop-2/GUI-304.md

### 15. Compact no-op response
- **Problem:** Even no-op cases leave room for redundant explanation.
- **Solution:** Fixed template: "No pending changes; master already contains HEAD. No action taken."
- **Estimated savings:** ~3-8% of tokens.
- **Sources:** loop-2/GUI-268.md

### 16. Required ticket template
- **Problem:** Ambiguous tickets hide the real gap; missing standardized fields increase exploration.
- **Solution:** Required `send-to-linear` template with "Affected files", "Test that reproduces the bug", and "Acceptance criteria".
- **Estimated savings:** Reduces ambiguity and initial exploration.
- **Sources:** loop-2/GUI-Others.md

### 17. test-impact skill (diff -> affected tests)
- **Problem:** Discovering which tests depend on changed behavior is done manually, or with a subagent, and still lets files slip through.
- **Solution:** `test-impact` skill that, given a diff, scans and lists all tests affected by changed functions/symbols.
- **Estimated savings:** Avoids manual subagent + reduces missed regressions.
- **Sources:** loop-2/GUI-Others.md

### 18. Pytest hook: "0 failures = success"
- **Problem:** RTK filters pytest output to show only failures; empty output means success, but that is not obvious, causing redundant confirmation calls.
- **Solution:** Hook that intercepts empty `rtk pytest` output and emits inline "All tests passed (N passed, 0 failed)".
- **Estimated savings:** Avoids ~3 redundant calls per task.
- **Sources:** loop-2/GUI-Others.md

### 19. Lean agent for trivial bug fixes
- **Problem:** The thinking loop spends ~8k tokens evaluating alternatives when the ticket already says what the problem is.
- **Solution:** Specialized subagent that receives `{file}:{line}` and produces the diff without deliberating over alternatives (~1k tokens).
- **Estimated savings:** ~7k tokens per trivial bug fix.
- **Sources:** loop-2/GUI-Others.md

### 20. Post-merge inspection without detailed diff
- **Problem:** During merge convergence, opening a detailed diff only to confirm staged files reinjects large content at the end of the session.
- **Solution:** Use `merge-base`, `diff --cached --name-only`, and `diff --cached --stat`; open a full diff only if there is an unexpected file or real conflict.
- **Estimated savings:** ~2.5k tokens.
- **Sources:** docs/loops--loop-runner--token-efficiency/GUI-349.md

## Ranking by mentions

| # | Improvement | Mentions | Sources |
|---|-------------|----------|---------|
| 5 | Stair-step verification / avoid duplicate suite runs | 3 | loop-2 |
| 6 | Deterministic and safe devops--deploy--commit-merge | 2 | loop-2 |
| 7 | Fixed repo command shortcuts (test/lint) | 2 | loop-2 |
| 8 | Lint before commit | 2 | loop-2, GUI-349 |
| 9 | Pre-task impact-analysis subagent | 2 | loop-2 |
| 10 | Precheck master-worktree merge blockers | 2 | loop-2 |
| 11 | Compact no-op response | 1 | loop-2 |
| 12 | Lean agent for trivial bug fixes | 1 | loop-2 |
| 13 | Linear auto-context (injected summary) | 1 | loop-2 |
| 14 | Post-merge inspection without detailed diff | 1 | GUI-349 |
| 15 | Pytest hook: "0 failures = success" | 1 | loop-2 |
| 16 | Required ticket template | 1 | loop-2 |
| 17 | Summarize git worktree list automatically | 1 | loop-2 |
| 18 | test-impact skill (diff -> affected tests) | 1 | loop-2 |
| 19 | Use RTK only for voluminous outputs | 1 | loop-2 |

_Total: 22 mentions -> 15 improvements in the ranking. 10 improvements (84 mentions) already applied. See `../loops--loop-runner--apply-harness/implementations.md`._
