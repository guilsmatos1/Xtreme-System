---
name: coding--review--standards-spec
description: Two-axis review of the diff since a fixed point — Standards (repo conventions) and Spec (originating Issue/PRD). Use when reviewing a branch, PR, WIP changes, or when asked to review since a commit/branch.
metadata:
    skill-organizer:
        original-name: coding--review--standards-spec
        source-relative-path: coding/review/standards-spec
        disabled: false
        risk-score: 0
        risk-evaluated-at: ""
        risk-evaluator: ""
        risk-reason: ""
        risk-source-hash: ""
---

# Standards + Spec Review

Review the diff between `HEAD` and a fixed point along two axes, in **parallel sub-agents**, then aggregate without reranking:

- **Standards** — does the code follow this repo's documented conventions?
- **Spec** — does the code faithfully implement the originating Issue / PRD / acceptance criteria?

Read `CONTEXT.md` for domain vocabulary. Prefer `graphify` only if Standards/Spec need structural orientation.

## Process

### 1. Pin the fixed point

Use the commit/branch/tag/`main`/`HEAD~N` the user named. If missing, ask.

Capture once:

- `git rev-parse <fixed-point>` (must succeed)
- `git diff <fixed-point>...HEAD` (three-dot; must be non-empty)
- `git log <fixed-point>..HEAD --oneline`

Fail here on a bad ref or empty diff — do not spawn sub-agents.

### 2. Identify the Spec source (in order)

1. Issue keys in commit messages (`GUI-123`, `Closes GUI-45`) — fetch with `orca linear issue <KEY> --full` (or `--json` if body alone is enough).
2. Path the user passed.
3. A spec under `docs/`, `specs/`, or `.loop/` matching the branch/feature.
4. If none: ask. If they confirm there is no spec, skip the Spec sub-agent and report "no spec available".

### 3. Identify Standards sources

- `AGENTS.md`, `ARCHITECTURE.md`, `API.md`, `DATABASE.md`, `CONTEXT.md`
- Project coding conventions visible in the touched area

Plus this **smell baseline** (judgement calls only; repo docs override; skip what tooling already enforces):

- Mysterious Name → rename or redesign
- Duplicated Code → extract shared shape
- Feature Envy → move behavior to the data it uses
- Data Clumps → bundle into a type
- Primitive Obsession → small domain type
- Repeated Switches → polymorphism or one shared map
- Shotgun Surgery → gather what changes together
- Divergent Change → split by reason-to-change
- Speculative Generality → delete until a real need
- Message Chains → hide behind one method
- Middle Man → call the real target
- Refused Bequest → prefer composition

### 4. Spawn both sub-agents in parallel

One message, two `generalPurpose` (or `general`) sub-agents.

**Standards brief** — include diff command, commit list, standards file paths, and the smell baseline pasted in full. Ask for: (a) documented-standard breaches with cite; (b) baseline smells with hunk quote. Distinguish hard violations vs judgement calls. Under 400 words.

**Spec brief** — include diff command, commit list, and Issue/spec body. Ask for: (a) missing/partial requirements; (b) scope creep; (c) wrong implementations — quote the spec/Issue line each time. Under 400 words.

### 5. Aggregate

Present under `## Standards` and `## Spec` verbatim or lightly cleaned. Do **not** merge or pick a single winner across axes.

End with one line: findings count per axis, and the worst issue within each axis.

## Why two axes

Standards-pass + Spec-fail means polished wrong feature. Spec-pass + Standards-fail means correct feature that fights the repo. Reporting them separately stops one from masking the other.
