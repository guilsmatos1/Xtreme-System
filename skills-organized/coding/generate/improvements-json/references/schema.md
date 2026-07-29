# Improvements Markdown contract

Write one UTF-8 Markdown document:

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

Correctness, risk, maintenance, or operational consequence.

### Concrete fix

Smallest useful implementation change.

### Example

Optional implementation example.

### Potential savings

Optional concrete supported benefit.

### Self-critique

- **Confidence:** 8.5/10
- **Uncertain:** No
- **Strengths:**
  - Evidence that was verified.
- **Weaknesses:**
  - Unverified detail or assumption.
- **Suggested checks:**
  - Further check that would raise confidence.
````

## Validation rules

- `Generated` is an ISO-8601 timestamp with timezone.
- `Total` equals the number of opportunity headings.
- Opportunity headings match `^## imp-[0-9]{8}-[0-9]{3} — .+$` and IDs are unique.
- `Impact` is `High` or `Medium`.
- `Estimated effort` is `Low`, `Medium`, or `High`.
- `Priority` and `Risk level` are `high`, `medium`, or `low`.
- `Confidence` is from `0` through `10`.
- Verified locations contain positive line numbers and an actual 8-12 line snippet.
- For unverified locations, write `Not verified`, set `Uncertain` to `Yes`, and explain the
  missing evidence under `Weaknesses`.
- Omit unsupported optional sections instead of filling them with placeholders.
- Use Markdown lists for files, tags, relationships, criteria, and critique details. Never embed
  JSON or YAML in the document.
