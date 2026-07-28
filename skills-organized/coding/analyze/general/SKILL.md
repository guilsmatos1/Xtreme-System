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
7. After preparing the final report, save the content to `.loop/running/improvements-codebase.json` as JSON.

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
      "category": "Performance",
      "estimated_effort": "Medium",
      "potential_savings": "<concrete estimated benefit, omit if not justifiable>",
      "description": "<specific explanation tied to the code>",
      "why_it_matters": "<correctness, risk, maintainability, or operational consequence>",
      "concrete_fix": "<specific change, ideally the smallest useful fix>",
      "example": "<code sample with before/after when useful>",
      "additional_fields": {
        "priority": "high|medium|low",
        "risk_level": "high|medium|low",
        "tags": ["tag1", "tag2"],
        "files_affected": ["path1", "path2"],
        "related_opportunities": ["imp-YYYYMMDD-NNN"]
      },
      "self_critique": {
        "confidence_score": 8.5,
        "strengths": ["<why this finding is solid, cite what was verified>"],
        "weaknesses": ["<what wasn't verified, assumptions made>"],
        "uncertain": false,
        "suggested_improvements": ["<how to raise confidence further, e.g. a measurement to take>"]
      }
    }
  ]
}
```

## Persistence

- Write the final report to `.loop/running/improvements-codebase.json`.
- If the directory does not exist, create it.
- If the file already exists, overwrite it with the latest report.
- `total_opportunities` must match the actual number of items in `opportunities` — do not hardcode it to 10.
- Include all analysis data in the JSON structure above, preserving all findings from the review.

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
`.loop/running/improvements-general.json` ONLY.
