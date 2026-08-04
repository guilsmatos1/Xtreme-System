---
name: coding--analyze--duplicates
description: Analyze the codebase for code consolidation opportunities — duplicated, near-duplicated, and redundant code that can be unified without losing any functionality. Use when asked to find duplication, copy-paste, repeated logic, parallel implementations of the same rule, redundant helpers/templates/queries, or a prioritized list of safe behavior-preserving merges.
metadata:
    skill-organizer:
        original-name: coding--analyze--duplicates
        source-relative-path: coding/analyze/duplicates
        disabled: false
        risk-score: 0
        risk-evaluated-at: ""
        risk-evaluator: ""
        risk-reason: ""
        risk-source-hash: ""
---

# Analyze Consolidation

Analyze this codebase thoroughly and identify the best opportunities to consolidate duplicated,
near-duplicated, or redundant code without removing, weakening, or changing existing behavior.
Prioritize duplicated business rules, divergent parallel implementations, and repeated workflow or
template patterns over cosmetic similarity.


## Review Dimensions

For each opportunity, evaluate the relevant dimensions below:

1. Literal duplication
  - byte-identical blocks
  - copy-pasted conditionals
  - repeated route/template fragments
2. Near duplication
  - same shape with renamed fields
  - repeated parsing, filtering, or pagination
  - similar form/table/modal templates
3. Parallel implementations
  - same business rule computed in multiple places
  - divergent validation or error handling
  - duplicated status transitions
4. Reimplemented helpers
  - existing function, macro, or workflow bypassed
  - ad hoc formatting/coercion
  - duplicate query construction
5. Redundant layers
  - wrappers that only forward
  - single-caller indirections
  - re-export-only components
6. Template consolidation
  - repeated Jinja blocks
  - macro bypasses
  - duplicated HTMX attributes and empty/error states
7. Behavior preservation
  - differences between copies
  - verification coverage
  - layer-boundary risks

## Process

1. Explore the project structure before diving into specific files.
2. Identify likely hotspots:
  - business rules repeated across `components/*/core.py`
  - multi-step validation chains in `workflows.py`
  - route handlers with repeated parsing, filtering, pagination, permission, and error handling
  - Jinja fragments that should be macros
  - transaction, formatting, coercion, and query patterns repeated per caller
3. For each candidate, compare every occurrence — but read them scoped, never whole. Establish the
   shape first with a signature sweep (`rg -n "^(def |@router|{% macro )" <files>`), then read only
   the line ranges that sweep points at, using `Read` with `offset`/`limit`. Pull a full file only
   when a finding genuinely depends on file-wide structure, and say why. See Reading Budget.
4. Prefer an existing module, function, workflow, or macro as the consolidation target.
5. Create a new shared helper only when no suitable home exists and there are at least 2 real callers.
6. Tie every recommendation to all duplicate sites, with representative snippets when possible.
7. Avoid broad refactors unless the duplication is clearly causing correctness, reliability, or
   maintenance problems.
8. After preparing the findings, hand them to the `coding--generate--issues-md` skill,
   which formats and writes `.loop/running/issues-duplicates.md`.

## What Strong Findings Look Like

Strong finding:

```text
Vehicle availability validation is implemented in two workflows with different status checks, so one path can sell a vehicle that the other path rejects.
```

Weak finding:

```text
These two route handlers look similar.
```

Do not report similar-looking code unless it represents one logical rule or reusable structure that
can be unified while preserving behavior. Do not lower the bar just to reach a round number of
findings.

## Domain notes

- Every finding must include **Consolidation details**: duplicate type, all sites, differences between copies, behavior preservation, and verification plan.
- Cite all duplicate sites, not just a representative one.

## Shared harness

Follow [../references/analyze-harness.md](../references/analyze-harness.md) for ranking, graphify
orientation, reading budget, output fields, issues-md handoff, and review standard.

## Persistence

- The output path is `.loop/running/issues-duplicates.md`. Pass it to `coding--generate--issues-md` per the harness.
- Hand over every retained finding and discarded candidate from this review — do not summarize, drop,
  or re-rank them on the way in.
