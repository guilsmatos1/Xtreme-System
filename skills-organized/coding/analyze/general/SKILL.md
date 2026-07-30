---
name: coding--analyze--general
description: Analyze a codebase thoroughly and identify the highest-impact improvement opportunities, prioritized by impact. Use when asked for a code review, technical debt audit, architecture critique, performance review, testing gap analysis, or a prioritized list of concrete improvements tied to specific files and snippets.
metadata:
    skill-organizer:
        original-name: analyze-codebase
        source-relative-path: coding/analyze/general
        disabled: false
        risk-score: 0
        risk-evaluated-at: ""
        risk-evaluator: ""
        risk-reason: ""
        risk-source-hash: ""
---

# Analyze Codebase

Analyze this codebase thoroughly and identify the best opportunities for improvement, prioritized by impact.
Prioritize issues affecting correctness, reliability, security, and operational risk over stylistic preferences.

Quality over quantity. Target 8-12 opportunities, but only include findings with impact `High` or `Medium`. It is better to return 6 excellent findings than to pad the list to hit a number. If you cannot find 8 strong opportunities, return fewer and say so — do not invent or inflate weak findings to fill the count.

## Review Dimensions

For each opportunity, evaluate the relevant dimensions below:

1. Code quality
  - duplication
  - complexity
  - readability
2. Architecture and design
  - coupling
  - separation of concerns
  - misapplied patterns
3. Performance
  - inefficient queries
  - unnecessary loops
  - missing caching
  - N+1 queries
4. Testing
  - weak coverage
  - brittle tests
  - missing tests
  - untested edge cases
5. Maintainability
  - technical debt
  - change risk
  - unclear ownership
6. Error handling and logging
  - swallowed exceptions
  - inconsistent errors
  - weak observability
7. Security
  - authorization/authentication gaps
  - injection risks (SQL, command, template)
  - data exposure / leakage
  - unsafe defaults, trust boundaries, secrets handling

## Process

1. Explore the project structure before diving into specific files.
2. Identify likely hotspots:
  - large or central modules
  - files with frequent cross-module dependencies
  - persistence, API, auth, background jobs, and orchestration flows
  - areas with complex branching or duplicated logic
3. Read enough surrounding context to understand each issue before judging it.
4. Prefer high-confidence findings over generic review advice.
5. Tie every recommendation to a specific file, function, and line range, with a real code snippet when possible.
6. Avoid broad refactors unless the current design is clearly causing correctness, reliability, or maintenance problems.
7. After preparing the findings, hand them to the `coding--generate--issues-md` skill,
   which formats and writes `.loop/running/improvements-general.md`.

## Suggested Workflow

Use `graphify` first to orient cheaply, then only read/grep what it can't answer:

- hotspots and god nodes: `graphify query "largest or most central modules"` (or read `graphify-out/GRAPH_REPORT.md` for the full architecture pass)
- a specific dimension: `graphify query "<dimension, e.g. N+1 queries, swallowed exceptions>"`
- a concept in isolation: `graphify explain "<concept>"`
- relationship between two areas: `graphify path "<A>" "<B>"`
- navigation without raw browsing: `graphify-out/wiki/index.md`, if present

Only fall back to `rg`/`find`/`wc -l`/reading full files for what graphify's scoped subgraph doesn't
surface, or to confirm exact line ranges before citing them in a finding. Never re-derive the whole
file tree or definition list by hand when graphify can answer the same question with a fraction of
the tokens.

## What Strong Findings Look Like

Strong finding:

```text
Repeated permission checks across three endpoints drifted apart and already disagree on admin fallback behavior, creating correctness risk and making new endpoint work error-prone.
```

Weak finding:

```text
This file is a bit long and could be split.
```

Do not report cosmetic findings unless they materially affect correctness, maintenance, or velocity. Do not lower the bar just to reach a round number of findings.

## Output Requirements

Deliver 8-12 opportunities (fewer if that's all the evidence supports), ordered from highest to lowest impact. Only include `High` or `Medium` impact findings — discard `Low` impact candidates rather than padding the list with them.

For each opportunity, include:

- **ID**: unique identifier (format: `imp-YYYYMMDD-NNN`)
- **Short title**: actionable, specific to the issue
- **Location**: file, line range, function, and a real code snippet (8-12 lines)
- **Impact**: `High` or `Medium`
- **Category**: primary dimension from review dimensions (including Security)
- **Description**: specific explanation tied to the code
- **Why it matters**: correctness, risk, maintainability, or operational consequence
- **Concrete fix**: smallest useful fix with example (before/after when applicable)
- **Estimated effort**: `Low`, `Medium`, or `High`
- **Potential savings**: concrete, estimated benefit when it can be reasoned about (e.g., "cuts listing query time ~40% under load", "closes a data-exposure path for non-admin users") — omit rather than guess a number you can't justify
- **Priority**: `high`, `medium`, or `low` (may differ from impact)
- **Risk level**: `high`, `medium`, or `low` (implementation risk)
- **Tags**: searchable labels (e.g., "performance", "frontend", "database")
- **Files affected**: list of all files involved in the fix
- **Related opportunities**: IDs of related findings from the same analysis
- **Self-critique**: per-opportunity honest assessment — confidence score, strengths, weaknesses, and whether this finding is uncertain (see schema below)

## Output Format

Do not format the report yourself. Invoke the `coding--generate--issues-md` skill and hand it the
retained opportunities in final ranked order, the discarded candidates with their reasons, every
analysis-specific field, and the output path below. That skill owns the shared Improvements Markdown
contract and is the single definition of the format; it preserves analysis-specific fields under
`Domain details` and validates the finished document.

## Persistence

- The output path is `.loop/running/improvements-general.md`. Pass it to `coding--generate--issues-md`, which creates the
  directory when missing, overwrites any existing report, sets `Generated` and `Total` from the
  actual document, and validates it against the contract.
- Hand over every retained finding and discarded candidate from this review — do not summarize,
  drop, or re-rank them on the way in.

## Review Standard

- Be specific, surgical, and evidence-based.
- Prefer concrete defects and real risks over style opinions.
- Name the tradeoff when a fix is larger than the immediate issue.
- If multiple files share the same problem, cite the best representative examples instead of repeating yourself.
- If a suspected issue is uncertain, set `self_critique.uncertain: true`, list it in `weaknesses`, and lower its priority/confidence_score accordingly — never silently upgrade an uncertain hunch to a confident finding.
- Include all enriched metadata: tags, affected files, related opportunities, and self-assessment of confidence.
- Ensure each finding is actionable and traceable to specific code locations with a real snippet.
- Honesty over completeness: an accurate list of 7 is better than an inflated list of 10.



**IMPORTANT — DO NOT print the report or a summary of it in the terminal.**

The full report is the deliverable, and it goes to
`.loop/running/improvements-general.md` ONLY.
