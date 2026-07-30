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

Quality over quantity. Target 8-12 opportunities, but only include findings with impact `High` or
`Medium`. It is better to return 6 excellent findings than to pad the list to hit a number. If you
cannot find 8 strong opportunities, return fewer and say so — do not invent or inflate weak findings
to fill the count.

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

## Suggested Workflow

Use `graphify` first to orient cheaply, then only read/grep what it can't answer:

- duplicated logic: `graphify query "duplicated or parallel implementations"`
- route/template duplication: `graphify query "repeated route handlers and jinja fragments"`
- a specific concept: `graphify explain "<business rule or workflow>"`
- relationship between duplicate sites: `graphify path "<A>" "<B>"`
- navigation without raw browsing: `graphify-out/wiki/index.md`, if present

Only fall back to `rg`/`find`/`wc -l`/reading full files for what graphify's scoped subgraph doesn't
surface, or to confirm exact line ranges before citing them in a finding. Never re-derive the whole
file tree or definition list by hand when graphify can answer the same question with a fraction of
the tokens.

## Reading Budget

Follow [../references/reading-budget.md](../references/reading-budget.md) — the shared cost
discipline for every `coding--analyze--*` skill (repo path:
`skills-organized/coding/analyze/references/reading-budget.md`).

It applies with full force here: a duplication survey needs shapes and call patterns across many
files, so it is the review most likely to load full route modules it never quotes. Sweep signatures
first, read only the ranges you will cite, and never re-read a file already in context.

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

## Output Requirements

Deliver 8-12 opportunities (fewer if that's all the evidence supports), ordered from highest to
lowest impact. Only include `High` or `Medium` impact findings — discard `Low` impact candidates
rather than padding the list with them.

For each opportunity, include:

- **ID**: unique identifier (format: `imp-YYYYMMDD-NNN`)
- **Short title**: actionable, specific to the duplication
- **Location**: representative file, line range, function, and a real code snippet (8-12 lines)
- **Impact**: `High` or `Medium`
- **Category**: primary dimension from review dimensions
- **Description**: specific explanation tied to the duplicated code
- **Why it matters**: correctness, risk, maintainability, or operational consequence
- **Concrete fix**: smallest behavior-preserving consolidation
- **Estimated effort**: `Low`, `Medium`, or `High`
- **Potential savings**: concrete, estimated benefit when it can be reasoned about — omit rather than guess
- **Priority**: `high`, `medium`, or `low` (may differ from impact)
- **Risk level**: `high`, `medium`, or `low` (implementation risk)
- **Tags**: searchable labels
- **Files affected**: list of all duplicate sites and consolidation targets
- **Related opportunities**: IDs of related findings from the same analysis
- **Self-critique**: per-opportunity honest assessment — confidence score, strengths, weaknesses, and uncertainty
- **Consolidation details**: duplicate type, all sites, differences between copies, behavior preservation, and verification plan

## Output Format

Do not format the report yourself. Invoke the `coding--generate--issues-md` skill and hand it the
retained opportunities in final ranked order, the discarded candidates with their reasons, every
analysis-specific field (including the consolidation details), and the output path below. That skill
owns the shared Issues Markdown contract and is the single definition of the format; it
preserves analysis-specific fields under `Domain details` and validates the finished document.

## Persistence

- The output path is `.loop/running/issues-duplicates.md`. Pass it to `coding--generate--issues-md`, which creates the
  directory when missing, overwrites any existing report, sets `Generated` and `Total` from the
  actual document, and validates it against the contract.
- Hand over every retained finding and discarded candidate from this review — do not summarize,
  drop, or re-rank them on the way in.

## Review Standard

- Be specific, surgical, and evidence-based.
- Prefer duplicate rules with real drift risk over visual similarity.
- Cite all duplicate sites, not just a representative one.
- State the differences between copies explicitly, even when there are none.
- If the copies diverge, preserve the union of behavior or explain which behavior intentionally wins.
- Name the tradeoff when consolidation crosses a layer boundary.
- If a suspected duplicate is uncertain, set `self_critique.uncertain: true`, list it in
  `weaknesses`, and lower its priority/confidence_score accordingly.
- Include all enriched metadata: tags, affected files, related opportunities, duplicate sites,
  behavior-preservation details, and self-assessment of confidence.
- Honesty over completeness: an accurate list of 7 is better than an inflated list of 10.



**IMPORTANT — DO NOT print the report or a summary of it in the terminal.**

The full report is the deliverable, and it goes to
`.loop/running/issues-duplicates.md` ONLY.
