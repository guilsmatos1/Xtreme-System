---
name: loops--state-management--consolidate-harness
description: Consolidates harness-improvement suggestions produced by worktree runs. Reads versioned GUI-*.md reports in docs/analyze-token-efficiency/ and, for legacy runs, the latest .loop folder; groups equivalent improvements through semantic deduplication and maintains an accumulated ranking (improvements-harness.md, inside this skill). Use when asked to consolidate harness suggestions, rank run improvements, or feed the continuous-improvement loop.
metadata:
    skill-organizer:
        original-name: loops--state-management--consolidate-harness
        source-relative-path: loops/state-management/consolidate-harness
        disabled: false
        risk-score: 0
        risk-evaluated-at: ""
        risk-evaluator: ""
        risk-reason: ""
        risk-source-hash: ""
---

# Consolidate Harness Improvements

Consolidate, into one accumulated ranking, the harness-improvement suggestions that each worktree run leaves in `docs/analyze-token-efficiency/GUI-*.md`. For legacy reports, the latest `.loop` folder can also be used. Equivalent improvements, even with different names, count as **one** item, and the mention count shows which harness changes should have the highest return in future runs.

The deliverable is **`improvements-harness.md`**, written **inside this skill folder**. It **accumulates history** across runs: each new source adds mentions to the existing state.

## Efficiency Rule

- Preserve raw reports; **do not delete or move** `docs/analyze-token-efficiency/GUI-*.md`.
- Consolidate incrementally: list filenames first, compare them with `Processed sources`, and read content **only** from new sources.
- Do not reread old reports for deduplication. Use only the compact state already summarized in `improvements-harness.md`.
- To discover new sources, use listing commands (`find`, `rg --files`, `git ls-files`) and filter by path; do not open `.md` content at this stage.

## Done

- `improvements-harness.md` contains one explanatory section per unique improvement plus a final ranking table sorted by mentions desc.
- No duplicate improvements: semantic equivalents become one entry with summed mentions.
- Each processed source is recorded; rerunning on the same sources **does not** duplicate counts.

## Flow

### 1. Locate Target Sources

- Read `improvements-harness.md` first, if it exists, and extract only the accumulated state and the `Processed sources` line.
- List `docs/analyze-token-efficiency/GUI-*.md` by name/path.
- If files exist there, process **all reports not yet recorded** in `improvements-harness.md`.
- If there are no new versioned reports, use the legacy fallback: list `.loop/loop-*`, choose the **latest** by date in the name (`loop-N-YYYY-MM-DD` or similar), break ties with the higher number, and process its `GUI-*.md` files that are not yet recorded.
- **Require at least one new source.** If all reports are already listed as processed, tell the user and stop.
- Tell the user which sources will be processed before continuing.

### 2. Load Accumulated State

- If `improvements-harness.md` exists in this skill folder, use the read from step 1 to obtain:
  - the canonical list of already registered improvements, titles, and counts;
  - the **`Processed sources`** list (already counted `docs/.../GUI-*.md` or `.loop/.../GUI-*.md` files).
- Remove from the queue any source already listed as processed. Avoiding reprocessing prevents double counting. If the user insists on reprocessing, remove that source from the list before recounting.
- If the file does not exist, start from an empty state.

### 3. Extract Improvements From Current Sources

- Read **only** the new `GUI-*.md` files selected in step 1.
- Numbered `GUI-NNN.md` format: blocks like
  ```text
  Improvement #N: <Title>
  - Problem: ...
  - Solution: ...
  - Estimated savings: <tokens>
  ```
  Extract each block as `{title, problem, solution, savings, source}`.
- Free-text `GUI-Others.md` format: extract each distinct suggestion (subagents, skills, AGENTS.md/hooks rules) as one item, synthesizing problem/solution/savings when present.
- `source` = full relative path, for example `docs/analyze-token-efficiency/GUI-360--<session-id>.md` or `.loop/loop-4-2026-07-24/GUI-350.md`.

### 4. Consolidate By Semantic Deduplication

For each extracted improvement, compare **by meaning**, not exact string, against existing canonical entries. Examples of equivalence that must collapse into one entry:

- "Docs On Demand" == "blind docs reading" == "read ARCHITECTURE/API only when changing contracts".
- "Full Diff Only Once" == "Lean Diff Flow" == "git diff --stat by default".
- "Compact Commit-Merge Skill" == "Leaner Commit Flow" == "small clean change mode".
- "Reduce Intermediate Comments" == "fewer progress updates".
- "Linear Auto-Context" == "inject issue summary" == "read only files referenced by the issue".

Rules:

- **Matched existing entry**: increment its counter and append `source`. **Do not** rewrite its explanation or create a new entry.
- **New entry**: create a canonical entry with a **short, stable title**, synthesized explanation (problem, proposed solution, typical savings), and mentions = 1.
- When rewriting the file, **reuse canonical titles already recorded** so entries are not renamed across runs.
- Two mentions of the same improvement in different GUI files count as **2**.

### 5. Rewrite `improvements-harness.md`

Write the file in this skill folder with this structure:

```markdown
# Harness Improvements — Accumulated Ranking

_Last updated: <date>. Processed sources: <relative-path list>._

## Improvements

### <Canonical title 1>
- **Problem:** ...
- **Solution:** ...
- **Estimated savings:** ...
- **Sources:** <run/file>, <run/file>, ...

### <Canonical title 2>
...

## Ranking by mentions

| # | Improvement | Mentions | Sources |
|---|----------|---------|---------|
| 1 | <Title> | 5       | GUI-360, GUI-361 |
| 2 | ...     | 3       | ... |
```

- The table is sorted by **mentions desc** (tie: alphabetical). The top item is the highest priority for upcoming runs.
- Use `Processed sources` in the header to list processed relative paths. If updating an old file that still uses a legacy processed-source header, migrate that field to `Processed sources` while preserving existing entries.
- In the table, the `Sources` column must show distinct source identifiers extracted from sources, for example `GUI-360`, `GUI-361`, `loop-4-2026-07-24/GUI-350`.

### 6. Report

When done, tell the user: processed sources, number of new improvements added, number of mentions incremented in existing entries, and the ranking top 3.
