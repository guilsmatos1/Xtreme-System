---
name: coding--analyze--features
description: Analyze product/workflow gaps and rank the highest-impact functional issues. Use when asked what features are missing or which workflows are incomplete.
metadata:
    skill-organizer:
        original-name: coding--analyze--features
        source-relative-path: coding/analyze/features
        disabled: false
        risk-score: 0
        risk-evaluated-at: ""
        risk-evaluator: ""
        risk-reason: ""
        risk-source-hash: ""
---

# Analyze Features

Analyze this system thoroughly as a product and identify the best functional improvement
opportunities, prioritized by value delivered to the people who use it. Prioritize incomplete
workflows, missing business-rule enforcement, and missing reads/actions that affect daily operation
over cosmetic or purely technical issues.


## Review Dimensions

For each opportunity, evaluate the relevant dimensions below:

1. Workflow completeness
  - dead-end flows
  - manual work outside the system
  - missing end-to-end actions
2. Business rules
  - unenforced invariants
  - inconsistent state transitions
  - bad data the system currently allows
3. Dead schema
  - fields never surfaced
  - relationships never used
  - enum states without UI/API behavior
4. Missing reads and reporting
  - stored data never shown back
  - missing operational summaries
  - weak traceability of calculated values
5. Automation
  - repeated manual recalculations
  - status changes users must remember
  - missing generated documents or notifications
6. Permissions and collaboration
  - limited profiles blocked from needed work
  - excessive access
  - concurrent-edit risks
7. Error recovery and trust
  - no cancel/reopen/reversal path
  - weak auditability
  - unclear financial traceability

## Process

1. Explore the product structure before diving into specific files.
2. Identify likely hotspots:
  - user-facing routes and templates
  - core business operations in `components/*/core.py`
  - multi-step operations in `workflows.py`
  - schema fields that are not exposed in UI/API
  - permissions, audit, reporting, and export paths
3. Trace complete user workflows where possible, such as compra → estoque → custos → venda →
   fechamento → caixa.
4. Read enough surrounding context to verify whether a proposed feature is truly missing.
5. Prefer high-confidence, user-visible gaps over generic roadmap ideas.
6. Tie every recommendation to concrete evidence: route, template, model field, function, or API contract.
7. Avoid code-quality refactors unless the functional gap cannot be fixed without them.
8. After preparing the findings, hand them to the `coding--generate--issues-md` skill,
   which formats and writes `.loop/running/issues-features.md`.

## What Strong Findings Look Like

Strong finding:

```text
The sale workflow stores financing fields but never exposes a review step that reconciles expected receivables with caixa entries, leaving staff to audit money in a spreadsheet.
```

Weak finding:

```text
Add a dashboard because dashboards are useful.
```

Do not report generic product ideas unless they are grounded in existing workflows, schema, or user
actions. Do not lower the bar just to reach a round number of findings.

## Shared harness

Follow [../references/analyze-harness.md](../references/analyze-harness.md) for ranking, graphify
orientation, reading budget, output fields, issues-md handoff, and review standard.

## Persistence

- The output path is `.loop/running/issues-features.md`. Pass it to `coding--generate--issues-md` per the harness.
- Hand over every retained finding and discarded candidate from this review — do not summarize, drop,
  or re-rank them on the way in.
