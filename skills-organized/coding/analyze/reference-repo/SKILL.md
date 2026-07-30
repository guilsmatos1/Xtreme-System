---
name: coding--analyze--reference-repo
description: Compare a reference repository against this local project and surface high-value opportunities the local project is missing or implementing worse. Use when the user provides a reference repo path or link and asks to compare with reference repo, what the reference is doing better, patterns we are ignoring, features missing compared to X, opportunities from this codebase, or the Portuguese equivalents (oportunidades do repositório referência, o que o projeto está ignorando, padrões que faltam).
metadata:
    skill-organizer:
        original-name: reference-repo-opportunities
        source-relative-path: coding/analyze/reference-repo
        disabled: false
        risk-score: 0
        risk-evaluated-at: ""
        risk-evaluator: ""
        risk-reason: ""
        risk-source-hash: ""
---

# Analyze Reference Repo Opportunities

Compare a **reference repository** (`REF`) against **this local project** (`LOCAL`) and surface
the highest-value patterns, capabilities, or conventions LOCAL is missing or implementing worse.
Quality over quantity: target 5-12 opportunities, but only include `High` or `Medium` impact
findings. It is better to return 4 excellent opportunities than to pad the list with cosmetic
differences.

## Inputs

1. **Reference path** (required) — absolute or relative path to the reference repo. If the user
   only gives a GitHub URL, ask where to clone it (or use the scratchpad directory), clone it
   shallowly, and proceed with the local path.
2. **Scope** (optional) — a specific area to focus on (auth, API layer, state management, testing,
   CLI, UI, performance, …). Default: whole project.
3. **Depth** (optional) — `quick` (surface patterns only, skim manifests/READMEs/dir structure) or
   `deep` (also read key implementations). Default: `deep`.

## Process

### 1. Setup

- `LOCAL` = current project root. `REF` = the path supplied by the user.
- Detect the stack of both sides (languages, frameworks, package managers, test runners, build
  tools). If the stacks differ radically, separate transferable *ideas* from patterns that only
  make sense to directly port.

### 2. Reconnaissance

For `LOCAL`, orient with `graphify` before any raw browsing — it exists at `graphify-out/` in this
project:

- broad shape: `graphify query "top-level structure and core modules"`, or read
  `graphify-out/wiki/index.md` if present
- a specific concern: `graphify query "<concern, e.g. auth, error handling, caching>"`
- a concept in isolation: `graphify explain "<concept>"`
- only fall back to `find`/`rg`/reading files for what graphify's subgraph doesn't answer, or to
  confirm exact line ranges before citing them.

`REF` has no graph — map it directly but cheaply: directory listing, README, package manifest,
targeted `rg` for the same concerns you checked in LOCAL. Do not read every file on either side;
dive into code only where a pattern looks promising.

For both sides, map how these concerns are solved: auth, data access, error handling, config,
logging, validation, concurrency, caching, CLI/API surface, tests, and any abstraction that
visibly collapses repeated logic.

### 3. Opportunity hunting

Look specifically for what REF does better or has that LOCAL lacks:

| Category | What to hunt |
|----------|--------------|
| **Less code, same result** | helpers, DSLs, codegen, shared primitives that collapse repeated logic |
| **Missing capabilities** | features, safety nets, observability, resilience, DX tooling present in REF, absent or weak in LOCAL |
| **Stronger patterns** | error handling, validation, config, dependency injection, testing strategy, module boundaries, API design |
| **Consistency & conventions** | naming, layout, lint/format rules REF enforces well |
| **Performance / reliability** | caching, batching, retries, timeouts, backpressure, resource management |
| **Security & correctness** | authz checks, input sanitization, secret handling, invariant enforcement |
| **Developer experience** | scripts, generators, good defaults, docs, type-level guarantees |

Ignore pure style differences and framework-specific APIs that cannot transfer. Prefer ideas
adaptable with reasonable effort over exact ports that assume a different stack.

### 4. Evidence and ranking

For every candidate opportunity, before it is allowed onto the list:

1. Point to concrete evidence in REF — file path and a short snippet or precise description.
2. Point to the corresponding gap or weaker version in LOCAL — file path, or state "absent" if
   there's genuinely nothing to point to.
3. Estimate **impact** (`High`/`Medium`; drop `Low` rather than including it) and **effort**
   (`Small`/`Medium`/`Large`).
4. State a concrete next step — what to extract, adapt, or reimplement, not just "consider doing
   this."

Rank by impact ÷ effort, highest first.

## Reading Budget

This skill sweeps two repos, so the discipline in
[../references/reading-budget.md](../references/reading-budget.md) applies with full force on the
LOCAL side (graphify-scoped reads, signature sweep before full-file reads, never re-read a file
already in context). On the REF side, apply the same spirit manually since no graph exists: skim
manifests and signatures before opening full implementation files, and only open what a promising
pattern actually requires.

## Output Format

Do not hand-format the report. Hand the ranked opportunities (and any notable discarded
candidates) to the `coding--generate--issues-md` skill using Mode A (collected findings). For each
opportunity supply:

- **Short title** — actionable, specific to the pattern
- **Impact** / **Effort** as scored above
- **Category** — from the table in step 3
- **Description** — what REF does, in one or two sentences
- **Why it matters** — the concrete consequence of LOCAL not having it
- **Concrete fix** — the suggested action from step 4
- **Domain details** (preserved verbatim under `Domain details`):
  - `ref_evidence` — file path + snippet/description from REF
  - `local_gap` — file path in LOCAL, or `absent`
  - `transferability` — direct port / adaptable idea / not transferable, with a one-line reason

Also hand over a short **Stack snapshot** (LOCAL stack, REF stack, transferability notes) and a
**Not recommended** list — patterns you considered and rejected, with a one-line reason each, so
the user knows they were weighed and not missed.

## Persistence

The output path is `.loop/running/issues-reference-repo.md`. Pass it to
`coding--generate--issues-md`, which creates the directory if missing, sets `Generated`/`Total`
from the actual document, and validates it against the shared contract.

**Do not print the report or a summary of it in the terminal.** The full report is the
deliverable, and it goes to `.loop/running/issues-reference-repo.md` only.
