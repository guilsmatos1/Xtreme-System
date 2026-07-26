---
name: 0001-analyze-llm-adherence
description: Analyze Python codebases for real modularization opportunities that improve maintainability, reduce coupling, clarify contracts, and help LLMs make small safe edits. Use when asked to review Python architecture, find refactoring opportunities, split large files/functions/classes, detect weak module boundaries, identify duplicated logic, circular imports, global dependencies, private API access, untyped dict/Any contracts, mixed CLI/API/UI/domain logic, or propose modularization work for safer AI-assisted maintenance.
---

# Analyze LLM Adherence

Analyze this codebase thoroughly and identify the best modularization opportunities that make future
LLM-assisted edits smaller, safer, and easier to verify. Prioritize weak boundaries, implicit
contracts, mixed responsibilities, and hidden dependencies over simple file-size complaints.

Quality over quantity. Target 8-12 opportunities, but only include findings with impact `High` or
`Medium`. It is better to return 6 excellent findings than to pad the list to hit a number. If you
cannot find 8 strong opportunities, return fewer and say so — do not invent or inflate weak findings
to fill the count.

## Review Dimensions

For each opportunity, evaluate the relevant dimensions below:

1. Boundary clarity
  - mixed route/workflow/core responsibilities
  - persistence mixed with domain computation
  - UI/API logic inside reusable domain code
2. Contract strength
  - raw `dict`/`Any` payloads
  - magic keys
  - ambiguous return structures
3. Locality of change
  - changes requiring broad context
  - functions with many unrelated stages
  - modules with unrelated responsibilities
4. Dependency control
  - global configuration reads
  - mutable singletons
  - hard-to-mock clients or sessions
5. Encapsulation
  - external access to private members
  - leaking internal representations
  - unclear public APIs
6. Coupling and import shape
  - circular imports
  - bidirectional service dependencies
  - generic utility dumps
7. Testability
  - important logic only reachable through routes
  - extraction opportunities with focused tests
  - fragile integration-only coverage

## Process

1. Explore the project structure before diving into specific files.
2. Identify likely hotspots:
  - large or central Python modules
  - route files mixing parsing, validation, persistence, and rendering
  - workflows with implicit dict contracts or many state transitions
  - generic `utils.py`, `helpers.py`, `common.py`, or low-cohesion modules
  - modules with circular imports, globals, or hidden dependency reads
3. Read candidate modules before judging them. Do not rely on line count alone.
4. Prefer opportunities that let a future agent change one small module and one focused test.
5. Recommend the smallest useful extraction with a clear public interface.
6. Tie every recommendation to a specific file, function, and line range, with a real code snippet when possible.
7. Avoid cosmetic splitting unless the current shape clearly increases maintenance or correctness risk.
8. After preparing the final report, save the content to `.loop/running/improvements-llm-adherence.json` as JSON.

## Suggested Workflow

Use `graphify` first to orient cheaply, then only read/grep what it can't answer:

- hotspots and god nodes: `graphify query "largest or most central python modules"`
- boundary risks: `graphify query "business logic mixed with routes persistence or templates"`
- circular imports: `graphify query "circular imports and bidirectional dependencies"`
- a specific module: `graphify explain "<module>"`
- relationship between two modules: `graphify path "<A>" "<B>"`
- navigation without raw browsing: `graphify-out/wiki/index.md`, if present

Only fall back to `rg`/`find`/`wc -l`/reading full files for what graphify's scoped subgraph doesn't
surface, or to confirm exact line ranges before citing them in a finding. Useful targeted searches:
`rg '\\._[A-Za-z]'`, `rg 'dict\\[|: dict|Any|Mapping\\[str, Any\\]'`, `rg 'os\\.getenv|global '`,
and `rg 'FastAPI|render|sqlalchemy|jinja'`.

## What Strong Findings Look Like

Strong finding:

```text
The sale workflow passes loosely typed dicts through validation, pricing, persistence, and template rendering, so adding a new sale field requires auditing every layer instead of updating one contract.
```

Weak finding:

```text
This file is 220 lines and should be split.
```

Do not report modularization findings unless the proposed boundary reduces real change risk,
clarifies a contract, or unlocks focused tests. Do not lower the bar just to reach a round number of
findings.

## Output Requirements

Deliver 8-12 opportunities (fewer if that's all the evidence supports), ordered from highest to
lowest impact. Only include `High` or `Medium` impact findings — discard `Low` impact candidates
rather than padding the list with them.

For each opportunity, include:

- **ID**: unique identifier (format: `imp-YYYYMMDD-NNN`)
- **Short title**: actionable, specific to the modularity risk
- **Location**: file, line range, function, and a real code snippet (8-12 lines)
- **Impact**: `High` or `Medium`
- **Category**: primary dimension from review dimensions
- **Description**: specific explanation tied to the code
- **Why it matters**: LLM edit risk, correctness, maintenance, or testability consequence
- **Concrete fix**: smallest useful extraction, contract, or boundary improvement
- **Estimated effort**: `Low`, `Medium`, or `High`
- **Potential savings**: concrete, estimated benefit when it can be reasoned about — omit rather than guess
- **Priority**: `high`, `medium`, or `low` (may differ from impact)
- **Risk level**: `high`, `medium`, or `low` (implementation risk)
- **Tags**: searchable labels
- **Files affected**: list of all files involved in the fix
- **Related opportunities**: IDs of related findings from the same analysis
- **Self-critique**: per-opportunity honest assessment — confidence score, strengths, weaknesses, and uncertainty
- **Modularity details**: LLM risk, suggested interface, new structure, tests, and success metric

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
      "category": "Contract strength",
      "estimated_effort": "Medium",
      "potential_savings": "<concrete estimated benefit, omit if not justifiable>",
      "description": "<specific explanation tied to the code>",
      "why_it_matters": "<LLM edit risk, correctness, maintenance, or testability consequence>",
      "concrete_fix": "<smallest useful extraction, contract, or boundary improvement>",
      "example": "<interface or before/after when useful>",
      "additional_fields": {
        "priority": "high|medium|low",
        "risk_level": "high|medium|low",
        "tags": ["tag1", "tag2"],
        "files_affected": ["path1", "path2"],
        "related_opportunities": ["imp-YYYYMMDD-NNN"],
        "llm_risk": "<why edits become broad, ambiguous, or fragile>",
        "suggested_interface": "<function/class/protocol signature or public API>",
        "new_structure": "<optional tree, only if structure matters>",
        "tests": ["<test files/cases>"],
        "success_metric": "<observable improvement>"
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
      "reason": "<why it is not a strong modularity opportunity>"
    }
  ]
}
```

## Persistence

- Write the final report to `.loop/running/improvements-llm-adherence.json`.
- If the directory does not exist, create it.
- If the file already exists, overwrite it with the latest report.
- `total_opportunities` must match the actual number of items in `opportunities` — do not hardcode it to 10.
- Include all analysis data in the JSON structure above, preserving all findings from the review.

## Execution

This skill can be run in an isolated subagent when combined with other `0001-analyze-*` skills, so
the raw exploration (graphify queries, file reads, `rg` output) stays out of the caller's context.
The subagent should write the report to the path above and reply with only the file path and item
count — never paste the report or exploration output back into the parent conversation.

## Review Standard

- Be specific, surgical, and evidence-based.
- Judge modularity by boundaries and contracts, not file count.
- Prefer concrete risks to future LLM edit locality over broad architecture opinions.
- Recommend abstractions only when they remove real ambiguity or make tests meaningfully smaller.
- Name the tradeoff when a fix is larger than the immediate issue.
- If a suspected issue is uncertain, set `self_critique.uncertain: true`, list it in `weaknesses`,
  and lower its priority/confidence_score accordingly.
- Include all enriched metadata: tags, affected files, related opportunities, suggested interface,
  tests, success metric, and self-assessment of confidence.
- Honesty over completeness: an accurate list of 7 is better than an inflated list of 10.



**IMPORTANT — DO NOT print the report or a summary of it in the terminal.**

The full report is the deliverable, and it goes to
`.loop/running/improvements-llm-adherence.json` ONLY.
