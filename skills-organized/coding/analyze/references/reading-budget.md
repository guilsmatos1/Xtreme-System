# Reading Budget

Shared cost discipline for every `coding--analyze--*` skill. These reviews sweep many files, so
everything loaded into context is paid for again on **every later turn** of the run. Two things
drive the cost, and they multiply:

- **how much you load** — a file read at turn 30 of a 125-turn run is re-sent ~95 times
- **how many turns you take** — each turn re-sends the entire accumulated context

A real measurement from one `coding--analyze--duplicates` run: 125 turns, 39 `Read` calls covering
29 unique files (251 KB), context growing 26k → 249k tokens, **16.1M cache-read tokens**. Most of
that was full-file reads of route modules where only handler shapes mattered.

## Load less

- Default to a **signature sweep first, scoped read second**. Establish shape with
  `rg -n "^(def |class |@router|{% macro )" <files>`, then `Read` with `offset`/`limit` only the
  ranges that sweep points at.
- "Read enough surrounding context" means enough to judge the finding and quote it correctly — not
  the whole file. A snippet in a report is 10-15 lines.
- **Never re-read a file already in context.** If you need a second region of it, you already have
  the first — scroll your own context before issuing another `Read`.
- Before opening anything over ~300 lines, state what the full file gives you that a scoped read
  does not. If there is no answer, scope it.
- Prefer `graphify query` / `explain` / `path` over raw browsing; it returns a scoped subgraph
  instead of whole files. Never re-derive the file tree or definition list by hand.

## Take fewer turns

- **Batch independent shell work into one command.** Never spend a turn on a lone `date`, `ls`, or
  `wc -l` that could have ridden along with the next call.
- Never issue the same `graphify` query twice with a different `tail`/`head`. Pick the budget once.
- Report progress to a coordinator at real milestones only — orientation done, findings frozen,
  report written. Each ping is a full turn at current context.
- When validating output, run the validator once, read the **whole** violation list, and fix it in a
  single `Edit`. A validate/edit/re-validate loop costs a full turn at full context per fix.

## Write once

The report body is the most expensive artifact these skills produce. Hand findings to
`coding--generate--issues-md`, which writes the document exactly once, straight to the output path.
Never draft the report into a scratchpad or the chat and copy it over afterwards — that doubles the
output cost and leaves the draft sitting in context for the rest of the run.

## What this must not cost you

Budget discipline never justifies a worse review. Do not drop a finding, skip verifying a cited
location, or fabricate a snippet to save tokens. If a finding genuinely needs a wide read, take it
and say why. The goal is removing waste, not lowering the evidence bar.
