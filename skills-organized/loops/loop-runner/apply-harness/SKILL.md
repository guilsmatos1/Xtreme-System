---
name: loops--loop-runner--apply-harness
description: Applies the accumulated harness-improvement ranking maintained by skill loops--state-management--consolidate-harness. Selects improvements with more than 3 mentions, refines proposals, applies them one at a time through a Codex subagent, reviews the result, records it in implementations.md, and removes it from the ranking. Use when asked to apply harness improvements, implement the ranking, put consolidated suggestions into practice, or close the loop started by 0004.
metadata:
    skill-organizer:
        original-name: loops--loop-runner--apply-harness
        source-relative-path: loops/loop-runner/apply-harness
        disabled: false
        risk-score: 0
        risk-evaluated-at: ""
        risk-evaluator: ""
        risk-reason: ""
        risk-source-hash: ""
---

# Apply Harness Improvements

Close the loop from skill **0004**: take the ranking in `improvements-harness.md`, turn generic proposals into concrete actions, and apply improvements to the harness that guides **Codex** workers. Stay conservative: lowest risk first, one improvement at a time, review before continuing.

## Scope

Here, the harness is the infrastructure that guides Codex workers, not the `xtreme-system` app.

Valid targets, from lowest to highest risk:

1. `AGENTS.md` — guidance read by Codex. Preferred target.
2. Skills in `skills-organized/` — text or behavior of skills used by Codex.
3. RTK in `/Users/guilsmatos/.codex/RTK.md` or equivalent local references — command-saving/rewrite rules.
4. Scripts/orchestration that start Codex workers, such as `process_issue.py` or an injected prompt — high risk.
5. Codex hooks/configuration, when present in the repo or `$CODEX_HOME` and clearly used by the flow — high risk.

Ineligible:

- Production app code (`bases/`, `components/`, migrations, app tests, etc.).
- Any improvement that only helps another executor and does not change what Codex reads/uses.
- Speculative changes with no verification path.

## Files

- Ranking: `skills-organized/loops/state-management/consolidate-harness/improvements-harness.md` (locate with `find skills-organized -name improvements-harness.md` if needed).
- Log: `skills-organized/loops/loop-runner/apply-harness/implementations.md`.
- Skills: always write to `skills-organized/...`. If `.claude/skills` exists as a symlink, do not duplicate anything.

## Done

1. Improvements with **mentions > 3** had their `Solution` refined in the ranking.
2. Eligible improvements were sorted by increasing risk and applied one at a time.
3. Each approved application was recorded in `implementations.md`.
4. Applied improvements were removed from the ranking, with table/numbering/total updated.

## Flow

### 1. Select

- Read the `Ranking by mentions` table.
- Select only items with **mentions > 3** (exactly 3 stays out).
- Sort by mentions desc; ties by title.
- Tell the user the selected list before editing.

### 2. Refine Solutions

For each selected item, rewrite only the `Solution` field or add `**Refined proposal:**`, keeping title and count unchanged.

The refined proposal must state:

- exact file(s) consumed by Codex;
- text/rule/behavior to change;
- trigger and boundary for applying it;
- how to verify it.

### 3. Classify Risk

- Low: additive text in `AGENTS.md` or a skill; no automation changes.
- Medium: changes behavior of an existing skill or RTK rule.
- High: orchestration scripts, global prompts, hooks, automatic config.

Apply low before medium. For high-risk items, leave the proposal ready and ask for confirmation before editing.

### 4. Apply One At A Time

For each eligible improvement:

1. Start a synchronous subagent to implement only that improvement.
2. Review the result yourself:
   - `git status --short` and `git diff --stat`;
   - only expected harness files changed;
   - no app code was touched;
   - the change matches the refined proposal;
   - Markdown/config/scripts remain coherent.
3. If review fails, fix narrowly or send the subagent specific feedback.
4. If review passes, record it in `implementations.md` and remove it from the ranking before moving to the next item.

Never apply two improvements in parallel.

#### Lean Subagent Prompt

```text
Implement ONE harness improvement in the xtreme-system repo.

IMPROVEMENT: <title>
REFINED PROPOSAL:
<paste refined solution>

TARGET(S): <exact file(s)>
RISK: <low|medium|high>

Rules:
- Change only the listed targets.
- Do not touch app code: bases/, components/, migrations, app tests.
- The improvement must affect what Codex workers read/use.
- Preserve existing style and language.
- Do not commit.

Deliver: changed files, short summary, and how to verify.
```

### 5. Record and Clean Ranking

After each approved improvement, append this to `implementations.md`:

```markdown
### <Title> — <date>
- **Risk level:** low | medium | high
- **Changed files:** <paths>
- **What changed:** <summary>
- **How to verify:** <check/command>
- **How to revert:** <file + section, or git revert of commit>
- **Source:** improvements-harness.md #<position> (<mentions> mentions)
```

Then remove that improvement from `improvements-harness.md`:

- delete the item section;
- delete the table row;
- renumber remaining entries;
- update total/footer and `_Last updated:_`.

Do this incrementally so the state stays consistent if execution is interrupted.

## Final Report

Report:

- selected items and how many were refined;
- risk plan: applied, delayed as high risk, or ineligible;
- for each applied item: title, files, and review verdict;
- how many improvements remain in the ranking and where the log is.

## Guardrails

- Codex is the target executor.
- Harness only; never app code.
- High risk requires confirmation.
- One improvement at a time, with review.
- Do not commit/merge without an explicit request.
- Idempotency: if it is already in `implementations.md`, do not reapply it.
