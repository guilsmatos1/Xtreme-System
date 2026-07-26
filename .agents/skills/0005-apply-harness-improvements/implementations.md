# Harness Improvement Implementations

Record of what skill `0005-apply-harness-improvements` actually applied to the Codex worker harness. Each block corresponds to an improvement removed from the ranking in `improvements-harness.md`.

---

### Minimal, on-demand docs/files reading — 2026-07-24
- **Risk level:** low
- **Changed files:** `AGENTS.md`
- **What changed:** New "Minimal, on-demand reading" block in the "Agent-Readable Workspace Map" section, right after "Shortcuts by intent:": grep/graphify first and open only files cited by the issue; read the 4 docs (README/ARCHITECTURE/API/DATABASE) only when the change is ambiguous about contract/architecture/auth/schema; a bug fix with `file:line` does not trigger doc reading; when `file:line` is provided, read `line-30..line+30` in a single call.
- **How to verify:** `git diff AGENTS.md` shows the 6 added lines between "Shortcuts by intent:" and "## 1. Think Before Coding". Codex reads `AGENTS.md` natively.
- **How to revert:** remove the "Minimal, on-demand reading" block from `AGENTS.md`.
- **Source:** improvements-harness.md #1 (6 mentions)
- **Process note:** a subagent applied this improvement and improperly committed it to `master` (`bf26ddd`); the commit was undone with `git reset HEAD~1` (recoverable through reflog), leaving the change only in the working tree.

### Lean diff by default — 2026-07-24
- **Risk level:** low
- **Changed files:** `AGENTS.md`
- **What changed:** New "## 4. Lean Diff by Default" section between Surgical Changes and Goal-Driven Execution: inspect with `git diff --stat` + `--name-only` by default; read the full diff at most once (before a sensitive commit or when genuinely in doubt); skip `diff`/`log` when `git status` is clean. Following sections were renumbered to keep 1-7 contiguous.
- **How to verify:** `grep -n "^## " AGENTS.md` shows 1..7 with no gaps, including "## 4. Lean Diff by Default".
- **How to revert:** remove "## 4. Lean Diff by Default" and restore the previous numbering (Goal-Driven -> 4, RTK -> 6, etc.).
- **Source:** improvements-harness.md #2 (5 mentions)

### Direct command mode / appropriate Linear verbosity — 2026-07-24
- **Risk level:** low
- **Changed files:** `AGENTS.md`
- **What changed:** New "## 8. Direct Commands & Linear Verbosity" section at the end: if the user gives an exact command (for example `orca linear issue GUI-XXX --full`), run it exactly and skip `orca status`/discovery and skill loading, except when it mutates Linear; unspecified reads default to `--json`, and `--full` is used only when comments/attachments are needed.
- **How to verify:** `grep -n "^## 8" AGENTS.md` shows the section at the end of the file.
- **How to revert:** remove "## 8. Direct Commands & Linear Verbosity".
- **Source:** improvements-harness.md #3 (5 mentions)

### Reduce intermediate comments/updates — 2026-07-24
- **Risk level:** low
- **Changed files:** `AGENTS.md`
- **What changed:** New "## 9. Fewer Intermediate Updates" section at the end: silent-unless-blocked for small/medium tasks; limit progress updates to 2-4 (start/criteria, before substantial edit, when blocked, final verification); do not emit updates for non-blocking read/test/status steps.
- **How to verify:** `grep -n "^## 9" AGENTS.md` shows the section at the end.
- **How to revert:** remove "## 9. Fewer Intermediate Updates".
- **Source:** improvements-harness.md #5 (4 mentions)

### Lean commit-merge / fast path — 2026-07-24
- **Risk level:** medium
- **Changed files:** `.agents/skills/commit-merge/SKILL.md`
- **What changed:** New "## Fast path (check first)" section at the top of the flow, after the intro and before "## Triggers": run `git status --porcelain --branch` first; if there is nothing to commit and `git merge-base --is-ancestor HEAD master` is true, treat it as no-op, respond compactly, and stop without `git worktree list`/diff/log; fall through to the full flow only when there is a real change.
- **How to verify:** the `commit-merge` `SKILL.md` has "## Fast path (check first)" before "## Triggers"; Triggers/Flow sections are intact.
- **How to revert:** remove "## Fast path (check first)" from `commit-merge/SKILL.md`.
- **Source:** improvements-harness.md #4 (4 mentions)
