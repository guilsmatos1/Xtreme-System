---
name: send-to-linear
description: Use when creating Linear issues from chat requests and issue metadata like priority or labels must be inferred from the request text.
---

# Send to Linear

Use `orca linear create` to create the issue.

## Defaults

- Assignee: `6b75d88f-389e-4bbb-bf7e-53528a774f93`
- State: `Backlog`
- Team: `GUI`
## What to fill

- Set the title from the request, keeping it as close to the original source as possible.
- Set the body from the request context, preserving the original information verbatim whenever feasible.
- Não é necessário adicionar o caminho da fonte.
- If the prompt specifies a project, pass `--project "<project-name>"`. If not specified, omit the flag.
- Always set `priority` and `label` on every issue.
- Set `priority` from the request if it is already explicit; otherwise infer it only from the task text and context. Use the lowest priority that still matches the request.
- Pass `priority` only as one of `none`, `low`, `medium`, `high`, or `urgent`.
- Set one label from the request type: `Bug`, `Feature`, or `Improvement`.
- Use `Bug` for defects, regressions, crashes, data loss, incorrect behavior, or broken invariants.
- Use `Feature` for new capabilities or user-facing additions.
- Use `Improvement` for refactors, performance work, cleanup, maintainability, and UX polish.
- Fill any other fields from the information already present in the conversation.
- Do not search the codebase.

## Example

```bash
orca linear create --team GUI --title "..." --body "..." --assignee me --state Backlog --priority medium --label Improvement --json
```
