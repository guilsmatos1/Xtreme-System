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
3. For each candidate, open every occurrence and compare the exact differences before judging it.
4. Prefer an existing module, function, workflow, or macro as the consolidation target.
5. Create a new shared helper only when no suitable home exists and there are at least 2 real callers.
6. Tie every recommendation to all duplicate sites, with representative snippets when possible.
7. Avoid broad refactors unless the duplication is clearly causing correctness, reliability, or
   maintenance problems.
8. After preparing the final report, save the content to `.loop/running/improvements-consolidation.json` as JSON.

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

Deliver results as a JSON file with this comprehensive structure:

```json
{
  "analysis_timestamp": "ISO-8601 timestamp",
  "total_opportunities": 9,
  "opportunities": [
    {
      "id": "imp-YYYYMMDD-NNN",
      "short_title": "<short, actionable title>",
      "location": {
        "file": "path/to/file.py",
        "line_start": 120,
        "line_end": 135,
        "function": "function_name",
        "snippet": "<8-12 lines of the actual relevant code>"
      },
      "impact": "High",
      "category": "Parallel implementations",
      "estimated_effort": "Medium",
      "potential_savings": "<concrete estimated benefit, omit if not justifiable>",
      "description": "<specific explanation tied to the duplicated code>",
      "why_it_matters": "<correctness, risk, maintainability, or operational consequence>",
      "concrete_fix": "<specific behavior-preserving consolidation>",
      "example": "<code sample with before/after when useful>",
      "additional_fields": {
        "priority": "high|medium|low",
        "risk_level": "high|medium|low",
        "tags": ["tag1", "tag2"],
        "files_affected": ["path1", "path2"],
        "related_opportunities": ["imp-YYYYMMDD-NNN"],
        "duplicate_type": "literal duplication|near duplication|parallel implementation|reimplemented helper|redundant layer|template consolidation",
        "duplicate_sites": ["path/to/file.py:123", "path/to/other.py:45"],
        "differences_between_copies": "<line-by-line differences, or byte-identical>",
        "behavior_preservation": "<which behaviors survive and how>",
        "verification": ["<existing test/check>", "<new test needed>"]
      },
      "self_critique": {
        "confidence_score": 8.5,
        "strengths": ["<why this finding is solid, cite what was verified>"],
        "weaknesses": ["<what wasn't verified, assumptions made>"],
        "uncertain": false,
        "suggested_improvements": ["<how to raise confidence further>"]
      }
    }
  ],
  "discarded_candidates": [
    {
      "title": "<candidate considered and rejected>",
      "reason": "<why it is not a consolidation opportunity>"
    }
  ],
  "risks": ["<consolidation risks to watch>"]
}
```

## Persistence

- Write the final report to `.loop/running/improvements-duplicates.json`.
- If the directory does not exist, create it.
- If the file already exists, overwrite it with the latest report.
- `total_opportunities` must match the actual number of items in `opportunities` — do not hardcode it to 10.
- Include all analysis data in the JSON structure above, preserving all findings from the review.

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
`.loop/running/improvements-duplicates.json` ONLY.
