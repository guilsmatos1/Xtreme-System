---
name: coding--ship--implement
description: Implement work from a spec or tickets using TDD, then Standards+Spec review.
disable-model-invocation: true
metadata:
    skill-organizer:
        original-name: coding--ship--implement
        source-relative-path: coding/ship/implement
        disabled: false
        risk-score: 0
        risk-evaluated-at: ""
        risk-evaluator: ""
        risk-reason: ""
        risk-source-hash: ""
---

# Implement

Implement the work in the given spec, ticket file, or Linear Issue.

1. Read `CONTEXT.md` and the ticket/spec acceptance criteria.
2. Confirm **seams** with the user if not already agreed (from `coding--ship--to-spec`).
3. Drive `coding--ship--tdd` at those seams — one vertical slice at a time.
4. Run targeted tests often; full relevant suite once at the end.
5. Run `coding--review--standards-spec` against the fixed point (branch base / merge-base) and the originating Issue/spec.
6. Commit on the current branch when the user wants a commit (do not push unless asked).

If this session is analysis-only (Claude), stop after a written plan and hand off via `devops--handoff` to an implement worker — do not edit application code.
