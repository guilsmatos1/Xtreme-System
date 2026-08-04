---
name: devops--handoff
description: Compact the current conversation into a handoff document for another agent.
disable-model-invocation: true
metadata:
    skill-organizer:
        original-name: devops--handoff
        source-relative-path: devops/handoff
        disabled: false
        risk-score: 0
        risk-evaluated-at: ""
        risk-evaluator: ""
        risk-reason: ""
        risk-source-hash: ""
---

# Handoff

Write a handoff document so a fresh agent can continue the work.

## Where to save

Prefer `.loop/running/handoff-<YYYYMMDD-HHMM>.md` in the workspace (visible to Orca workers). If the user asks for OS temp instead, use `$TMPDIR` / `/tmp`.

## Contents

1. **Goal** — what the next session must achieve (use args if the user passed a focus).
2. **Done so far** — bullets; link Issues, PRs, commits, specs, ADRs, diffs by path/URL — do not paste their bodies.
3. **Open decisions** — unresolved branches only.
4. **Next steps** — ordered, small enough for one context window each.
5. **Suggested skills** — which skills the next agent should invoke (e.g. `coding--debug--diagnosing-bugs`, `coding--review--standards-spec`).
6. **Repo state** — branch name, notable dirty paths (`git status --short` summary).

## Rules

- Use `CONTEXT.md` vocabulary.
- Redact secrets, tokens, passwords, and PII.
- Do not duplicate content already in artifacts — reference them.
- Do not start implementing; only write the handoff.
