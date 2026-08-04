---
name: coding--analyze--llm-adherence
description: Analyze Python modularization for LLM-friendly, low-coupling edits. Use when asked to improve module boundaries or LLM editability.
metadata:
    skill-organizer:
        original-name: coding--analyze--llm-adherence
        source-relative-path: coding/analyze/llm-adherence
        disabled: false
        risk-score: 0
        risk-evaluated-at: ""
        risk-evaluator: ""
        risk-reason: ""
        risk-source-hash: ""
---

# Analyze LLM Adherence

Analyze this codebase thoroughly and identify the best modularization opportunities that make future
LLM-assisted edits smaller, safer, and easier to verify. Prioritize weak boundaries, implicit
contracts, mixed responsibilities, and hidden dependencies over simple file-size complaints.


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
8. After preparing the findings, hand them to the `coding--generate--issues-md` skill,
   which formats and writes `.loop/running/issues-llm-adherence.md`.

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

## Domain notes

- Prefer modularization that improves LLM editability without changing behavior.

## Shared harness

Follow [../references/analyze-harness.md](../references/analyze-harness.md) for ranking, graphify
orientation, reading budget, output fields, issues-md handoff, and review standard.

## Persistence

- The output path is `.loop/running/issues-llm-adherence.md`. Pass it to `coding--generate--issues-md` per the harness.
- Hand over every retained finding and discarded candidate from this review — do not summarize, drop,
  or re-rank them on the way in.
