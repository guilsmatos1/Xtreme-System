---
name: code-review-simple
description: Quick, lightweight code review of the current diff or a set of files — reports findings inline in chat, no report file, no code changes. Use when asked for a fast code review, a sanity check on a diff before commit, or "review this" without needing a full audit.
---

# Code Review (Simple)

A fast, no-frills review. No report file, no JSON, no code changes — findings only, printed directly in chat.

## Scope

Default to reviewing the current uncommitted diff (`git diff` + `git diff --staged`). If the user names specific files or a PR/branch instead, review that.

## Process

1. Determine scope:
   - No target named → `git status` then `git diff HEAD`
   - Files named → read those files
   - Branch/PR named → `git diff <base>...<branch>`
2. Read enough surrounding context (not just the diff hunk) to judge each change correctly.
3. Check each changed piece of code against:
   - **Correctness** — logic errors, edge cases, off-by-one, null/None handling, wrong assumptions
   - **Security** — injection (SQL/command/template), auth/authorization gaps, secrets, unsafe input handling
   - **Error handling** — swallowed exceptions, missing rollback, unhandled failure paths
   - **Consistency** — deviates from existing patterns in the same file/module without reason
   - **Tests** — missing coverage for new logic or edge cases introduced
4. Skip pure style/formatting nitpicks unless they cause a real bug.

## Output

Print directly in chat — do not write a file. For each finding:

- **file:line** — one-line summary of the problem
- Why it matters (concrete failure scenario, not hypothetical)
- Suggested fix (describe it — do not apply it)

Order findings by severity: correctness/security first, then error handling, then consistency/tests.

If no meaningful issues are found, say so plainly — don't invent findings to pad the review.

**Do not edit files.** This skill reports findings only; it does not implement fixes.
