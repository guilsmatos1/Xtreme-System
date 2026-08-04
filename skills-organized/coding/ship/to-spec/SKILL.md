---
name: coding--ship--to-spec
description: Turn the current conversation into a spec — no interview, synthesis only.
disable-model-invocation: true
metadata:
    skill-organizer:
        original-name: coding--ship--to-spec
        source-relative-path: coding/ship/to-spec
        disabled: false
        risk-score: 0
        risk-evaluated-at: ""
        risk-evaluator: ""
        risk-reason: ""
        risk-source-hash: ""
---

# To Spec

Synthesize the current conversation into a spec (PRD). Do **not** interview — use what is already known.

Do **not** invoke `devops--linear--send`. Publishing to Linear (optional) uses `orca linear create` directly below.

## Process

1. Orient with `CONTEXT.md` vocabulary and any ADRs. Use graphify if the codebase state is unclear.
2. Sketch **test seams** (prefer existing, highest seam; fewer is better — ideal is one). Confirm seams with the user before writing the spec body.
3. Write the spec with the template below to `.loop/running/specs/<feature-slug>.md`.
4. Ask whether to also publish as a Linear Issue. If yes, run (team GUI defaults):

```bash
orca linear create \
  --project "<project-name>" \
  --title "<spec title>" \
  --body "$(cat .loop/running/specs/<feature-slug>.md)" \
  --priority high \
  --state Todo \
  --label Feature
```

`--project` is required. Priority `urgent`/`high` → state `Todo`; otherwise prefer `Backlog`. Record the returned Issue key (GUI-*) in the local spec file header.

## Spec template

```markdown
## Problem Statement

{User-facing problem.}

## Solution

{User-facing solution.}

## User Stories

1. As a <actor>, I want a <feature>, so that <benefit>
{Long, exhaustive numbered list.}

## Implementation Decisions

- Bricks / interfaces touched (no fragile file paths unless a prototype snippet encodes a decision)
- Schema / API / authz decisions
- Architectural choices

## Testing Decisions

- What a good test is here (external behavior only)
- Agreed seams
- Prior art in the test suite

## Out of Scope

{Explicit non-goals.}

## Further Notes

{Anything else.}
```
