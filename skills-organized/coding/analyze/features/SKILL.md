---
name: coding--analyze--features
description: Analyze the system from the product/functionality angle and identify the 10 highest-impact functional improvements, prioritized by value to the end user. Use when asked what features are missing, what workflows are incomplete or awkward, what business rules are unenforced, or for a prioritized roadmap of functional improvements tied to specific routes, components, and screens.
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
over cosmetic or purely technical improvements.

Quality over quantity. Target 8-12 opportunities, but only include findings with impact `High` or
`Medium`. It is better to return 6 excellent findings than to pad the list to hit a number. If you
cannot find 8 strong opportunities, return fewer and say so — do not invent or inflate weak findings
to fill the count.

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
8. After preparing the final report, save the content to `.loop/running/improvements-features.md` as Markdown.

## Suggested Workflow

Use `graphify` first to orient cheaply, then only read/grep what it can't answer:

- route inventory: `graphify query "ui routes and the actions they expose"`
- domain workflow: `graphify explain "<domain workflow, e.g. fechamento de venda>"`
- schema-to-UI gaps: `graphify query "model fields not exposed in templates or routes"`
- relationship between domains: `graphify path "<A>" "<B>"`
- navigation without raw browsing: `graphify-out/wiki/index.md`, if present

Only fall back to `rg`/`find`/`wc -l`/reading full files for what graphify's scoped subgraph doesn't
surface, or to confirm exact line ranges before citing them in a finding. Never re-derive the whole
file tree or definition list by hand when graphify can answer the same question with a fraction of
the tokens.

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

## Output Requirements

Deliver 8-12 opportunities (fewer if that's all the evidence supports), ordered from highest to
lowest impact. Only include `High` or `Medium` impact findings — discard `Low` impact candidates
rather than padding the list with them.

For each opportunity, include:

- **ID**: unique identifier (format: `imp-YYYYMMDD-NNN`)
- **Short title**: actionable, specific to the functional gap
- **Location**: representative file, line range, function, and a real code snippet (8-12 lines)
- **Impact**: `High` or `Medium`
- **Category**: primary dimension from review dimensions
- **Description**: specific explanation tied to the product behavior
- **Why it matters**: user value, correctness, trust, operational risk, or frequency
- **Concrete fix**: smallest useful end-to-end behavior
- **Estimated effort**: `Low`, `Medium`, or `High`
- **Potential savings**: concrete, estimated benefit when it can be reasoned about — omit rather than guess
- **Priority**: `high`, `medium`, or `low` (may differ from impact)
- **Risk level**: `high`, `medium`, or `low` (implementation risk)
- **Tags**: searchable labels
- **Files affected**: list of all files involved in the fix
- **Related opportunities**: IDs of related findings from the same analysis
- **Self-critique**: per-opportunity honest assessment — confidence score, strengths, weaknesses, and uncertainty
- **Feature details**: domain, frequency, schema-change requirement, proposed behavior, and acceptance criteria

## Output Format

Follow the shared [Improvements Markdown contract](references/improvements-markdown-format.md). Preserve every analysis-specific field under descriptive Markdown sections.

## Persistence

- Write the final report to `.loop/running/improvements-features.md`.
- If the directory does not exist, create it.
- If the file already exists, overwrite it with the latest report.
- `total_opportunities` must match the actual number of items in `opportunities` — do not hardcode it to 10.
- Include all analysis data in the Markdown contract above, preserving all findings from the review.

## Review Standard

- Be specific, surgical, and evidence-based.
- Describe the user's blocked job first, then the code or schema evidence.
- Prefer high-value daily workflow gaps over nice-to-have ideas.
- Search before claiming a feature is missing.
- If a proposal needs a schema change, name the table/column and migration cost.
- Do not propose rewrites, refactors, or code-quality cleanups as feature findings.
- If a suspected gap is uncertain, set `self_critique.uncertain: true`, list it in `weaknesses`,
  and lower its priority/confidence_score accordingly.
- Include all enriched metadata: tags, affected files, related opportunities, acceptance criteria,
  schema impact, and self-assessment of confidence.
- Honesty over completeness: an accurate list of 7 is better than an inflated list of 10.



**IMPORTANT — DO NOT print the report or a summary of it in the terminal.**

The full report is the deliverable, and it goes to
`.loop/running/improvements-features.md` ONLY.
