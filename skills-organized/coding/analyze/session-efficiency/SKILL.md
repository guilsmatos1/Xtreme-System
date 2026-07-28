---
name: coding--analyze--session-efficiency
description: Analyzes exactly one Codex worker rollout and writes its canonical token-efficiency report. Use only for isolated jobs dispatched by loops--loop-runner--token-efficiency through Orca.
metadata:
    skill-organizer:
        original-name: coding--analyze--session-efficiency
        source-relative-path: coding/analyze/session-efficiency
        disabled: false
        risk-score: 0
        risk-evaluated-at: ""
        risk-evaluator: ""
        risk-reason: ""
        risk-source-hash: ""
---

# Analyze One Codex Session

Analyze exactly the session described by the JSON object in the skill arguments.
Required keys are `session_id`, `issue`, `rollout`, and `report_path`.

## Flow

1. Validate that all four arguments are non-empty, `rollout` exists, and
 `report_path` is under `docs/analyze-token-efficiency/`.
2. Extract the compact profile once:
  ```bash
   PROFILE="$(mktemp /tmp/codex-token-profile.XXXXXX)"
   python3 skills-organized/loops/loop-runner/token-efficiency/profile_session.py \
     --session-id "<session_id>" --rollout "<rollout>" > "$PROFILE"
  ```
3. Read the profile once. Choose up to five improvements, sorted by estimated
 savings descending. Include only improvements supported by profile evidence
 that change a Codex-consumed channel and preserve the exact deliverable,
 investigation, and validation quality.
4. Create the parent directory of `report_path`, then write only that report in
 this canonical format:
  ```markdown
   # Token Efficiency — <issue>
   _Codex: <session_id> · input: <N> · cached: <N> · output: <N> · total: <N>_

   Improvement #1: <title>
   - Problem: <observed waste>
   - Evidence: <tool/call, repetition, or size>
   - Solution: <Codex channel and concrete change>
   - Estimated savings: ~<N> tokens
   - Same-result test: <why the deliverable would be identical>
  ```
5. Confirm that the report exists and contains the requested session ID, then
 report completion through the injected Orca orchestration contract.

## Guardrails

- Analyze only the supplied rollout; never discover or enqueue other sessions.
- Do not read the full rollout directly unless profile extraction fails.
- Do not invent improvements when the profile has fewer than five valid candidates.
- Do not edit product code, hook state, orchestration state, or other reports.
- Real token totals come from the profile; only isolated savings are estimates.

