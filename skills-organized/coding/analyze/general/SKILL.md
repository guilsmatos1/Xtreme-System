---
name: coding--analyze--general
description: Analyze a codebase thoroughly and identify the highest-impact improvement opportunities, prioritized by impact. Use when asked for a code review, technical debt audit, architecture critique, performance review, testing gap analysis, or a prioritized list of concrete issues tied to specific files and snippets.
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
   which formats and writes `.loop/running/issues-general.md`.

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

## Shared harness

Follow [../references/analyze-harness.md](../references/analyze-harness.md) for ranking, graphify
orientation, reading budget, output fields, issues-md handoff, and review standard.

## Persistence

- The output path is `.loop/running/issues-general.md`. Pass it to `coding--generate--issues-md` per the harness.
- Hand over every retained finding and discarded candidate from this review — do not summarize, drop,
  or re-rank them on the way in.
