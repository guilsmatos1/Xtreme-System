# Analyze Harness

Shared process for every `coding--analyze--*` skill that writes an issues report.
Each skill keeps domain intro, Review Dimensions, Process hotspots, strong/weak examples,
and its output path. Everything below is the single source of truth for ranking, orientation,
handoff, field list, and review standard.

When exploring the codebase, read `CONTEXT.md` (if it exists) for domain vocabulary.

## Ranking

Quality over quantity. Target 10-15 opportunities, but only include findings with impact `High` or
`Medium`. It is better to return 6 excellent findings than to pad the list to hit a number. If you
cannot find 8 strong opportunities, return fewer and say so — do not invent or inflate weak findings
to fill the count.

Deliver 10-15 opportunities (fewer if that's all the evidence supports), ordered from highest to
lowest impact. Discard `Low` impact candidates rather than padding the list.

## Graphify orientation

Use `graphify` first to orient cheaply, then only read/grep what it can't answer:

- hotspots: `graphify query "<concern>"`
- a concept: `graphify explain "<concept>"`
- relationship: `graphify path "<A>" "<B>"`
- navigation without raw browsing: `graphify-out/wiki/index.md`, if present

Only fall back to `rg`/`find`/`wc -l`/reading full files for what graphify's scoped subgraph doesn't
surface, or to confirm exact line ranges before citing them. Never re-derive the whole file tree or
definition list by hand when graphify can answer with fewer tokens.

## Reading budget

Follow [reading-budget.md](reading-budget.md) — the shared cost discipline for every
`coding--analyze--*` skill (repo path: `skills-organized/coding/analyze/references/reading-budget.md`).

## Output fields

For each opportunity, include:

- **ID**: `imp-YYYYMMDD-NNN`
- **Short title**: actionable and specific
- **Location**: file, line range, function, and a real code snippet (10-15 lines)
- **Impact**: `High` or `Medium`
- **Category**: primary dimension from the skill's Review Dimensions
- **Description**: specific explanation tied to the code
- **Why it matters**: correctness, risk, maintainability, user, or operational consequence
- **Concrete fix**: smallest useful fix (before/after when applicable)
- **Estimated effort**: `Low`, `Medium`, or `High`
- **Potential savings**: concrete benefit when justifiable — omit rather than guess
- **Priority**: `high`, `medium`, or `low`
- **Risk level**: `high`, `medium`, or `low`
- **Tags**: searchable labels
- **Files affected**: all files involved
- **Related opportunities**: IDs from the same analysis
- **Self-critique**: confidence, strengths, weaknesses, uncertainty
- Plus any domain-specific fields the calling skill names (e.g. consolidation details)

## Handoff to issues-md

Do not format the report yourself. Invoke the `coding--generate--issues-md` skill and hand it the
retained opportunities in final ranked order, the discarded candidates with their reasons, every
analysis-specific field, and the output path named by the calling skill. That skill owns the shared
Issues Markdown contract; it preserves analysis-specific fields under `Domain details` and validates
the finished document.

Persistence rules:

- Pass the skill's `.loop/running/issues-<name>.md` path to `coding--generate--issues-md`, which
  creates the directory when missing, overwrites any existing report, and sets `Generated`/`Total`.
- Hand over every retained finding and discarded candidate — do not summarize, drop, or re-rank.

**IMPORTANT — DO NOT print the report or a summary of it in the terminal.** The full report is the
deliverable and goes only to the skill's output path.

## Review standard

- Be specific, surgical, and evidence-based.
- Prefer concrete defects and real risks over style opinions.
- Name the tradeoff when a fix is larger than the immediate issue.
- If multiple files share the same problem, cite the best representative examples and list every
  affected file.
- If a suspected issue is uncertain, mark it uncertain, list it in weaknesses, and lower
  priority/confidence — never silently upgrade a hunch.
- Include enriched metadata: tags, affected files, related opportunities, self-assessment.
- Honesty over completeness: an accurate list of 7 is better than an inflated list of 10.
