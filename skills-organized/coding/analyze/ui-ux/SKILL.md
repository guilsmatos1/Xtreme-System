---
name: coding--analyze--ui-ux
description: Analyze UI/UX friction and rank the highest-impact interface issues. Use when asked for a UX review, design audit, or daily-user friction list.
metadata:
    skill-organizer:
        original-name: coding--analyze--ui-ux
        source-relative-path: coding/analyze/ui-ux
        disabled: false
        risk-score: 0
        risk-evaluated-at: ""
        risk-evaluator: ""
        risk-reason: ""
        risk-source-hash: ""
---

# Analyze UI/UX

Analyze this system thoroughly as an interface and identify the best UI/UX improvement opportunities,
prioritized by how much friction each one removes for people who use the system every day. Prioritize
hesitation, misreads, mis-clicks, retyping, inaccessible controls, and unclear system state over
pure visual preference.


## Review Dimensions

For each opportunity, evaluate the relevant dimensions below:

1. Information hierarchy
  - important values hidden
  - overloaded tables
  - weak visual priority
2. Form ergonomics
  - poor field order
  - missing input modes or masks
  - unclear required fields
3. Feedback and system state
  - missing loading/success/error states
  - HTMX swaps without indicators
  - destructive actions without confirmation
4. Error presentation
  - errors far from fields
  - lost user input
  - generic or inconsistent messages
5. Consistency
  - macro bypasses
  - divergent button/table/modal patterns
  - terminology drift
6. Density and scanability
  - hard-to-scan rows
  - poor alignment for numbers/statuses
  - overflow or truncation hiding meaning
7. Accessibility and responsiveness
  - weak focus states
  - missing labels or semantics
  - broken tablet/smaller desktop layouts

## Process

1. Explore the interface structure before diving into specific templates.
2. Identify likely hotspots:
  - `base.html` global layout and navigation
  - `_macros.html` design-system primitives
  - long forms for veículo, compra, venda, fechamento, and caixa
  - table rows/fragments and modal flows
  - `app.css`, `columns.js`, `filters.js`, and HTMX attributes
3. Read enough template/CSS/route context to understand each issue before judging it.
4. If the app can be run, render key screens at desktop and smaller widths; if it cannot, say so
   and rely only on template/CSS evidence.
5. Prefer fixes in shared macros and CSS over per-template patches when the issue repeats.
6. Tie every recommendation to a specific template, selector, macro, route, or JS behavior.
7. Avoid feature requests or code-quality refactors unless the interface issue cannot be fixed without them.
8. After preparing the findings, hand them to the `coding--generate--issues-md` skill,
   which formats and writes `.loop/running/issues-ui-ux.md`.

## What Strong Findings Look Like

Strong finding:

```text
Money-changing HTMX forms submit without disabled/loading state or nearby error recovery, so staff can double-submit or lose confidence during slow saves.
```

Weak finding:

```text
The page would look nicer with more spacing.
```

Do not report subjective visual polish unless it materially affects comprehension, task speed,
accessibility, or error rate. Do not lower the bar just to reach a round number of findings.

## Shared harness

Follow [../references/analyze-harness.md](../references/analyze-harness.md) for ranking, graphify
orientation, reading budget, output fields, issues-md handoff, and review standard.

## Persistence

- The output path is `.loop/running/issues-ui-ux.md`. Pass it to `coding--generate--issues-md` per the harness.
- Hand over every retained finding and discarded candidate from this review — do not summarize, drop,
  or re-rank them on the way in.
