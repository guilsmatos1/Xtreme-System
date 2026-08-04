---
name: loops--loop-runner--token-efficiency
description: Dispatch token-efficiency analysis for unanalyzed Codex sessions.
disable-model-invocation: true
metadata:
    skill-organizer:
        original-name: loops--loop-runner--token-efficiency
        source-relative-path: loops/loop-runner/token-efficiency
        disabled: false
        risk-score: 0
        risk-evaluated-at: ""
        risk-evaluator: ""
        risk-reason: ""
        risk-source-hash: ""
---

# Analyze Token Efficiency

Process every eligible, unanalyzed Codex worker session with a fresh agent and
context. This skill coordinates the batch; it does not analyze sessions itself.

## Flow

1. Discover pending sessions and generate a temporary jobs file once:

   ```bash
   python3 skills-organized/loops/loop-runner/token-efficiency/build_jobs.py prepare
   ```

2. Read the compact JSON summary printed by `prepare` and retain the exact
   absolute `jobs_file` value for the remaining commands.
   - If `pending` is zero, report that there are no eligible pending sessions and stop.
   - Do not inspect rollout contents or alter the generated jobs.

3. Invoke skill `loops--task-orchestration--skill-dispatcher` with the generated jobs file.
   Follow that skill and [../../references/orchestration-harness.md](../../references/orchestration-harness.md):
   run the helper detached, poll JSONL, wait for the final summary (strict sequencing +
   fresh Orca terminal per analysis).

4. After the dispatcher finishes, audit the expected artifacts:

   ```bash
   python3 skills-organized/loops/loop-runner/token-efficiency/build_jobs.py \
     verify --jobs-file "<jobs_file from prepare>"
   ```

5. Report the discovery counts, dispatcher summary, completed reports, and any
   missing or invalid reports. A missing report remains pending for the next run.

## Fixed Policy

- Select only `codex-tui` sessions under an
  `orca/workspaces/xtreme-system/GUI-NNN` worktree.
- Require at least one `token_count` event.
- Exclude `CODEX_THREAD_ID` and rollouts modified in the last 10 minutes.
- Treat only current `docs/analyze-token-efficiency/*.md` reports containing the
  session ID as analyzed.
- Process all pending sessions oldest first.
- Use worktree mode `current`.
- Use Codex `gpt-5.6-luna` with reasoning effort `medium`.
- Continue the dispatcher after job-level failures, escalations, or timeouts.
- Never invoke this batch from the Codex Stop hook.
