---
name: coding--debug--diagnosing-bugs
description: Diagnosis loop for hard bugs and performance regressions. Use when the user says diagnose/debug this, or reports something broken, throwing, failing, or slow.
metadata:
    skill-organizer:
        original-name: coding--debug--diagnosing-bugs
        source-relative-path: coding/debug/diagnosing-bugs
        disabled: false
        risk-score: 0
        risk-evaluated-at: ""
        risk-evaluator: ""
        risk-reason: ""
        risk-source-hash: ""
---

# Diagnosing Bugs

A discipline for hard bugs. Skip phases only when explicitly justified.

When exploring the codebase, read `CONTEXT.md` (if it exists) for domain vocabulary, and check ADRs in the area you're touching. Prefer `graphify query` before broad file reads.

## Phase 1 — Build a feedback loop

**This is the skill.** Everything else is mechanical. If you have a **tight** pass/fail signal for the bug — one that goes red on _this_ bug — you will find the cause. Without one, staring at code will not save you.

Spend disproportionate effort here. Be aggressive. Be creative. Refuse to give up.

### Ways to construct one — try in roughly this order

1. **Failing test** at whatever seam reaches the bug — unit, integration, e2e (pytest).
2. **Curl / HTTP script** against a running FastAPI/dev server (JSON API or HTMX route).
3. **CLI invocation** with a fixture input, diffing stdout against a known-good snapshot.
4. **Headless browser** — run the `coding--debug--playwright-cli` skill for HTMX UI paths.
5. **Replay a captured trace** (HAR, request payload, event log) through the code path in isolation.
6. **Throwaway harness** — minimal subset of the system exercising the bug path with one call.
7. **Property / fuzz loop** — if "sometimes wrong output", run many random inputs.
8. **Bisection harness** — automate boot-at-state-X for `git bisect run` between two known states.
9. **Differential loop** — same input through old vs new version/config; diff outputs.
10. **HITL script** — last resort; structure human clicks so captured output still feeds the loop.

### Tighten the loop

- Faster? (cache setup, skip unrelated init, narrow scope)
- Sharper signal? (assert the exact symptom, not "didn't crash")
- More deterministic? (pin time, seed RNG, isolate filesystem/network)

A 30-second flaky loop is barely better than none; a 2-second deterministic one is tight.

### Non-deterministic bugs

Raise reproduction rate until the bug is debuggable (parallelise, stress, narrow timing). 50% flake is workable; 1% is not.

### When you cannot build a loop

Stop. List what you tried. Ask for environment access, a captured artifact, or permission for temporary instrumentation. Do **not** hypothesise without a loop.

### Completion criterion — tight and red-capable

Phase 1 is done when you can name **one command** you have **already run** (paste invocation + output) that is:

- [ ] **Red-capable** — asserts the user's exact symptom on this bug path
- [ ] **Deterministic** (or pinned high repro rate for flakes)
- [ ] **Fast** — seconds, not minutes
- [ ] **Agent-runnable** (or HITL-structured)

No red-capable command → no Phase 2. Do not read code to theorise first.

## Phase 2 — Reproduce + minimise

Confirm the loop shows the user's failure mode, is reproducible, and the symptom is captured. Then shrink the repro one cut at a time until every remaining element is load-bearing.

## Phase 3 — Hypothesise

Generate **3–5 ranked, falsifiable** hypotheses before testing any:

> If \<X\> is the cause, then \<changing Y\> makes the bug disappear / \<changing Z\> makes it worse.

Show the ranked list to the user (don't block if AFK).

## Phase 4 — Instrument

Map each probe to a Phase 3 prediction. Change one variable at a time.

1. Debugger / REPL if available
2. Targeted logs at distinguishing boundaries — tag with `[DEBUG-<id>]` for cleanup
3. Never "log everything and grep"

**Perf:** measure first (timing harness, query plan, profiler), then bisect. Logs alone are usually wrong.

## Phase 5 — Fix + regression test

Write the regression test **before the fix** only at a **correct seam** (real bug pattern at the call site). If no correct seam exists, document that as an architecture finding.

1. Minimised repro → failing test
2. Watch it fail → fix → watch it pass
3. Re-run Phase 1 loop on the original scenario

Respect analysis-only Claude mode: if this session cannot edit code, stop after a written diagnosis + proposed fix and hand off to an implement worker.

## Phase 6 — Cleanup + post-mortem

- [ ] Phase 1 loop green on original repro
- [ ] Regression test passes (or missing seam documented)
- [ ] All `[DEBUG-...]` logs removed
- [ ] Throwaway harnesses deleted or marked
- [ ] Winning hypothesis stated in commit/PR message

Ask what would have prevented the bug. If the answer is architectural (no seam, tangled callers), note it for `coding--analyze--llm-adherence` or a future architecture skill — after the fix lands.
