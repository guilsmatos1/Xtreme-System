---
name: devops--linear--send
description: Create Linear issues from chat requests, analyzed codebases, or Markdown improvement batches. Supports legacy JSON batches by rendering each opportunity as Markdown before sending.
metadata:
    skill-organizer:
        original-name: devops--linear--send
        source-relative-path: devops/linear/send
        disabled: false
        risk-score: 0
        risk-evaluated-at: ""
        risk-evaluator: ""
        risk-reason: ""
        risk-source-hash: ""
---

# Send to Linear

Use `orca linear create` to create issues.

## Required Fields

- **Project**: Must be passed via `--project "<project-name>"` argument. Always required when creating issues.

## Defaults

- Assignee: `6b75d88f-389e-4bbb-bf7e-53528a774f93`
- State: `Backlog`
- Team: `GUI`

## When Sending from Markdown Batch Files

A Markdown file path (absolute or relative) must be provided via an argument. **There is no default file path** — never assume, guess, or fall back to a fixed location. Create one issue per `## imp-YYYYMMDD-NNN — Short title` section without checking for duplicates. Send that complete section as the issue body so headings, prose, lists, and code remain readable without JSON escaping.

### Automatic Script

```bash
python3 skills-organized/devops/linear/send/send_issues.py "<project>" <path-md>
```

Reads the Markdown, extracts the fixed metadata lines, infers `label`/`priority`, calls `orca linear create` for each, and logs progress. See `infer_label()` in that file for the exact label rules. If `Priority` is missing, it defaults to `none`.

Legacy `.json` batches remain accepted. The helper converts every legacy opportunity to Markdown before sending; it never uses raw JSON as a Linear description.

### Fallback manual

Use only if the script fails (`orca` CLI unavailable, permission error, malformed Markdown). Per opportunity, run `orca linear create --project "<project>"` with:

- `title` ← `short_title`
- `body` ← complete Markdown section for the opportunity
- `priority` ← the `Priority` metadata value, or `none` if absent
- `label` ← `Bug` if tags include "correctness"/"security"/"bug" or category is "Error handling"; `Feature` if tags include "feature" or category is "Features"; `Improvement` otherwise

The file path is received as the skill's `args` parameter. It can point to any Markdown file, in any location. Validate it exists and follows the improvement heading contract before processing.

### Post-Processing: Move Markdown to .loop

After successfully sending all opportunities to Linear:

1. **Create a loop folder** in `.loop` with format: `loop-{x}-{y}`
  - `{x}` = incremental loop number (find the highest existing `loop-*` folder, extract its number, and add 1)
  - `{y}` = today's date in ISO format (YYYY-MM-DD)
  - Example: `loop-5-2026-07-23`
2. **Move the Markdown file** into the newly created folder
  - Example: Move `.loop/running/issues.md` → `.loop/loop-5-2026-07-23/issues.md`

This creates an archive of completed opportunity batches, one per loop run.

## When Sending from Chat Requests

- Set the title from the request, keeping it as close to the original source as possible.
- Set the body from the request context, preserving the original information verbatim whenever feasible.
- **Project is required**: Always pass `--project "<project-name>"` argument. The project name must be specified in the request or prompt context.
- Always set `priority` and `label` on every issue.
- Set `priority` from the request if it is already explicit; otherwise infer it only from the task text and context. Use the lowest priority that still matches the request.
- Pass `priority` only as one of `none`, `low`, `medium`, `high`, or `urgent`.
- Set one label from the request type: `Bug`, `Feature`, or `Improvement`.
- Use `Bug` for defects, regressions, crashes, data loss, incorrect behavior, or broken invariants.
- Use `Feature` for new capabilities or user-facing additions.
- Use `Improvement` for refactors, performance work, cleanup, maintainability, and UX polish.
- Fill any other fields from the information already present in the conversation.
- Do not search the codebase.

## Examples

### From Chat Request

```bash
orca linear create --team GUI --title "..." --body "..." --assignee me --state Backlog --priority medium --label Improvement --json
```

### From Markdown Batch

```bash
python3 skills-organized/devops/linear/send/send_issues.py "Xtreme System" /absolute/path/to/issues.md
```
