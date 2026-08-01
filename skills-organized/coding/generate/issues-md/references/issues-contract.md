# Issues Markdown Contract

Canonical issues-document contract. This file is the single source of truth for
every analysis skill. Do not copy it into another skill; reference it.

Write one UTF-8 Markdown document with this structure:

```md
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
10-15 lines copied from the current file
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
LLM risk, suggested interface, tests, screens, duplicate sites, line delta, or
success metric. Use descriptive Markdown subheadings and lists rather than
serialized JSON.

When the caller supplies consolidation data (e.g. `coding--analyze--duplicates`),
render it as a named `#### Consolidation details` subsection with these five
labeled bullets, not folded into free prose:

```md
#### Consolidation details

- **Duplicate type:** Literal duplication | Near duplication | Parallel
  implementation | Reimplemented helper | Redundant layer | Template
  consolidation
- **All sites:** every duplicate location, `path:line` — not just the
  representative one
- **Differences between copies:** explicit, even when there are none
- **Behavior preservation:** which behavior wins, or that the union is preserved
- **Verification plan:** how the consolidation would be checked safe
```

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
```

## Validation rules

- `Generated` is an ISO-8601 timestamp with timezone, built at write time.
- Use exactly one level-two heading per retained opportunity in the form
`## imp-YYYYMMDD-NNN — Short title`, matching `^## imp-[0-9]{8}-[0-9]{3} — .+$`.
- Keep the metadata labels exactly as shown. `Estimated effort` must be `Low`,
`Medium`, or `High`; `Impact` must be `High` or `Medium`; `Priority` and
`Risk level` must be `high`, `medium`, or `low`; `Confidence` is `0` through `10`.
- Make IDs unique and ordered. Set `Total` to the actual number of opportunity
headings — never hardcode it.
- Put narrative and code in Markdown sections, never in JSON, YAML, or an escaped
string. Use Markdown lists for files, tags, relationships, criteria, and
critique details.
- Include an actual 10-15 line snippet for verified locations, copied verbatim from
the file — never fabricated or paraphrased. If no location can be verified,
write `Not verified`, set `Uncertain` to `Yes`, and explain the missing evidence
under `Weaknesses`.
- Omit optional sections instead of inventing content.
- Keep related IDs reciprocal when they represent the same direct dependency or
root cause.
- When `Consolidation details` is present, all five labels (`Duplicate type`,
`All sites`, `Differences between copies`, `Behavior preservation`,
`Verification plan`) must appear — never a partial subset.

