---
name: analyze-codebase
description: Analyze a codebase thoroughly and identify the 10 highest-impact improvement opportunities, prioritized by impact. Use when asked for a code review, technical debt audit, architecture critique, performance review, testing gap analysis, or a prioritized list of concrete improvements tied to specific files and snippets.
trigger: /analyze-codebase
---
# /analyze-codebase

Analyze this codebase thoroughly and identify the 10 best opportunities for improvement, prioritized by impact.

Prioritize issues affecting correctness, reliability, and operational risk over stylistic preferences.

## Review Dimensions

For each opportunity, evaluate the relevant dimensions below:

1. Code quality
  - duplication
  - complexity
  - readability
  - naming
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

## Process

1. Explore the project structure before diving into specific files.
2. Identify likely hotspots:
  - large or central modules
  - files with frequent cross-module dependencies
  - persistence, API, auth, background jobs, and orchestration flows
  - areas with complex branching or duplicated logic
3. Read enough surrounding context to understand each issue before judging it.
4. Prefer high-confidence findings over generic review advice.
5. Tie every recommendation to a specific file, function, and snippet when possible.
6. Avoid broad refactors unless the current design is clearly causing correctness, reliability, or maintenance problems.
7. After preparing the final report, save the same content to `docs/codebase-analysis.md` as Markdown.

## Suggested Workflow

Use lightweight inspection first, then deeper reading:

- project structure: `rg --files`
- hotspots by size: `find . -name '*.py' -o -name '*.js' -o -name '*.ts' | xargs wc -l | sort -n`
- definitions: `rg '^(def|class|async def)|function |const .* = \\('`
- cross-cutting patterns: `rg 'TODO|FIXME|except:|print\\(|logger\\.|raise |selectinload|joinedload|session\\.query|requests\\.|httpx\\.'`
- test coverage map: `rg --files | rg '(^|/)(test|tests)/|_test\\.|test_.*\\.'`

Adjust commands to the stack in the repository.

## What Strong Findings Look Like

Strong finding:

```text
Repeated permission checks across three endpoints drifted apart and already disagree on admin fallback behavior, creating correctness risk and making new endpoint work error-prone.
```

Weak finding:

```text
This file is a bit long and could be split.
```

Do not report cosmetic findings unless they materially affect correctness, maintenance, or velocity.

## Output Requirements

Deliver exactly 10 opportunities, ordered from highest to lowest impact.

For each opportunity, include:

- **Short title** of the issue
- **Location**: file, function, and line when applicable
- **Description**: what is wrong and why it matters
- **Impact**: `High`, `Medium`, or `Low`
- **Category**: choose the primary dimension that best fits the issue
- **Concrete fix suggestion**: include a code example when it helps
- **Estimated effort**: `Low`, `Medium`, or `High`

## Output Format

Use this structure for every item:

```text
## Opportunity N: <short title>

Location: path/to/file.py:123
Impact: High
Category: Performance
Estimated effort: Medium

Description:
<specific explanation tied to the code>

Why it matters:
<correctness, risk, maintainability, or operational consequence>

Concrete fix suggestion:
<specific change, ideally the smallest useful fix>

Example:
<short code sample when useful>
```

## Persistence

- Write the final 10-opportunity report to `docs/codebase-analysis.md`.
- Keep the file in Markdown and make it match the assistant output as closely as possible.
- If the file already exists, overwrite it with the latest report unless the user explicitly asks for a different filename.

## Review Standard

- Be specific, surgical, and evidence-based.
- Prefer concrete defects and real risks over style opinions.
- Name the tradeoff when a fix is larger than the immediate issue.
- If multiple files share the same problem, cite the best representative examples instead of repeating yourself.
- If a suspected issue is uncertain, say so explicitly and lower its priority.
