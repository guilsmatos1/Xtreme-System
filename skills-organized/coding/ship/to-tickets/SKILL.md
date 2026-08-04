---
name: coding--ship--to-tickets
description: Break a plan or spec into tracer-bullet tickets with blocking edges.
disable-model-invocation: true
metadata:
    skill-organizer:
        original-name: coding--ship--to-tickets
        source-relative-path: coding/ship/to-tickets
        disabled: false
        risk-score: 0
        risk-evaluated-at: ""
        risk-evaluator: ""
        risk-reason: ""
        risk-source-hash: ""
---

# To Tickets

Break a plan, spec, or conversation into **tracer-bullet** tickets — vertical slices with blocking edges.

Do **not** invoke `devops--linear--send`. Publish via local files and/or `orca linear create` as below.

## Process

### 1. Gather context

Use conversation context. If the user passes a spec path or GUI-* key, read it (`orca linear issue GUI-XXX --full` when needed). Use `CONTEXT.md` vocabulary.

### 2. Explore (optional)

Prefactor opportunities: "make the change easy, then make the easy change."

### 3. Draft vertical slices

- Narrow complete path through layers (schema → API/UI → tests) — not horizontal one-layer slices
- Demoable/verifiable alone; sized for one fresh context window
- Prefactors first
- Each ticket lists **Blocked by** (or none)

**Wide refactors** (blast radius too big for a green vertical slice): use expand → migrate batches → contract, not forced tracer bullets.

### 4. Quiz the user

Present numbered list: Title, Blocked by, What it delivers. Iterate until approved.

### 5. Publish

**Always** write local files (source of truth for agents):

`.loop/running/tickets/<feature-slug>/<NN>-<slug>.md` — dependency order, blockers first.

```markdown
# <NN> — <Ticket title>

**What to build:** end-to-end behaviour from the user's perspective.

**Blocked by:** <NN/titles> or "None — can start immediately".

**Status:** ready-for-agent

- [ ] Acceptance criterion 1
- [ ] Acceptance criterion 2
```

**Optional Linear publish** (ask first). Create Issues in dependency order so blockers exist before dependents reference them:

```bash
orca linear create \
  --project "<project-name>" \
  --title "<ticket title>" \
  --body "<markdown body with What to build, Acceptance criteria, Blocked by>" \
  --priority high \
  --state Todo \
  --label Feature
```

Put parent GUI-* / blocking GUI-* keys in each body. Do not close or rewrite a parent Issue. Do not call `devops--linear--send`.

Work the **frontier**: tickets whose blockers are done.
