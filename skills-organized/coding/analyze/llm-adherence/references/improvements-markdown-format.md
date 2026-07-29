# Improvements Markdown contract

Write one UTF-8 Markdown document with this structure:

````md
# Improvement opportunities

- **Generated:** 2026-07-29T12:00:00-03:00
- **Total:** 1

## imp-20260729-001 — Actionable title

- **Impact:** High
- **Category:** Security
- **Estimated effort:** Medium
- **Priority:** high
- **Risk level:** medium
- **Tags:** security, api
- **Files affected:** `path/to/file.py`
- **Related opportunities:** None

### Location

`path/to/file.py:120` — `function_name`

```python
8-12 lines copied from the current file
```

### Description

Specific explanation tied to the task and evidence.

### Why it matters

Correctness, risk, maintenance, user, or operational consequence.

### Concrete fix

Smallest useful implementation change.

### Example

Optional implementation example.

### Potential savings

Optional concrete supported benefit.

### Domain details

Optional analysis-specific fields such as acceptance criteria, proposed behavior,
LLM risk, suggested interface, tests, screens, or success metric. Use descriptive
Markdown subheadings and lists rather than serialized JSON.

### Self-critique

- **Confidence:** 8.5/10
- **Uncertain:** No
- **Strengths:**
  - Evidence that was verified.
- **Weaknesses:**
  - Unverified detail or assumption.
- **Suggested checks:**
  - Further check that would raise confidence.

## Discarded candidates

### Candidate title

Reason it was not retained.
````

## Validation rules

- Use exactly one level-two heading per retained opportunity in the form
  `## imp-YYYYMMDD-NNN — Short title`.
- Keep the metadata labels exactly as shown. `Estimated effort` must be `Low`,
  `Medium`, or `High`; `Impact` must be `High` or `Medium`; `Priority` and
  `Risk level` must be `high`, `medium`, or `low`.
- Make IDs unique and ordered. Set `Total` to the actual number of opportunity
  headings.
- Put narrative and code in Markdown sections, never in JSON, YAML, or an escaped
  string.
- Include an actual 8-12 line snippet for verified locations. If no location can
  be verified, write `Not verified`, mark the finding uncertain, and explain the
  missing evidence under `Weaknesses`.
- Omit optional sections instead of inventing content.
- Keep related IDs reciprocal when they represent the same direct dependency or
  root cause.
