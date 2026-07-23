---
name: 0001-send-to-linear
description: Create Linear issues from chat requests, analyzed codebases, or from JSON batch data files.
---
# Send to Linear

Use `orca linear create` to create issues.

## Required Fields

- **Project**: Must be passed via `--project "<project-name>"` argument. Always required when creating issues.

## Defaults

- Assignee: `6b75d88f-389e-4bbb-bf7e-53528a774f93`
- State: `Backlog`
- Team: `GUI`

## When Sending from JSON Batch Files

A JSON file path must be provided via an argument. Iterate over the array of opportunities and create an issue for each item:

**Accepted paths:**
- Any JSON file path provided as argument
- Can be absolute or relative path

1. **Extract Linear issue metadata from each opportunity:**
  - `title` ← `short_title`
  - `body` ← entire opportunity object as JSON (raw JSON string)
  - `priority` ← `additional_fields.priority` (must be one of `none`, `low`, `medium`, `high`, `urgent`)
  - `label` ← infer from `additional_fields.tags` or `category`:
    - Use `Bug` if tags include "correctness", "security", "bug", or category is "Error handling"
    - Use `Feature` if tags include "feature" or category is "Features"
    - Use `Improvement` for all other cases (default)
  - `assignee` ← use default or from `additional_fields` if available
2. **Body strategy:**
  - Copy the entire opportunity JSON object as the issue body/description
  - This preserves all data (location, description, concrete_fix, example, files_affected, tags, self_critique, etc.) in structured format
  - No token waste on reformatting — the JSON is already structured and parseable
  - Implementing agent can parse and access any field directly
3. **Batch creation:**
  - Create one issue per opportunity without checking for duplicates
  - Log progress: "Creating issue N of M for {short_title}"

### Script automático (preferido)

Use o script `send_improvements.py` incluso nesta pasta:

```bash
python3 .claude/skills/0001-send-to-linear/send_improvements.py "<projeto>" <caminho-do-json>
```

O script lê o JSON, infere label/priority, cria as issues via `orca linear create` e loga o resultado de cada uma.

### Fallback manual

Se o script falhar (ex.: `orca` CLI indisponível, erro de permissão, JSON mal formatado), crie cada issue manualmente seguindo as regras de extração acima, um `orca linear create --project "<projeto>"` por oportunidade.

## Input: JSON File Path

You can receive the JSON file path via:
- **Skill argument**: Pass the file path as `args` parameter
- **Validation**: Check file exists and is valid JSON before processing

Process the `opportunities` array from the JSON file (or top-level if it's an array).

## When Sending from Chat Requests

- Set the title from the request, keeping it as close to the original source as possible.
- Set the body from the request context, preserving the original information verbatim whenever feasible.
- Não é necessário adicionar o caminho da fonte.
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

### From `.loop/running/improvements.json`

**Preferido** — usar o script incluso:

```bash
python3 .claude/skills/0001-send-to-linear/send_improvements.py "Xtreme System" .loop/running/improvements.json
```

**Fallback manual** — criar uma por uma:

```bash
orca linear create \
  --team GUI \
  --project "<project-name>" \
  --title "{short_title}" \
  --body "ID: {id} (rank {rank})\n\n## Description\n{description}\n\n## Why it matters\n{why_it_matters}\n\n## Files affected\n{files_affected}" \
  --assignee me \
  --state Backlog \
  --priority {priority} \
  --label {inferred_label} \
  --json
```

