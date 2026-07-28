---
name: coding--analyze--ui-ux
description: Analyze the system's UI/UX and visual design and identify the 10 highest-impact interface improvements, prioritized by how much friction they remove for the daily user. Use when asked for a UX review, design audit, interface critique, accessibility check, visual consistency review, form/table usability analysis, or a prioritized list of concrete UI improvements tied to specific templates, CSS rules, and screens.
metadata:
    skill-organizer:
        original-name: coding--analyze--ui-ux
        source-relative-path: coding/analyze/ui-ux
        disabled: false
        risk-score: 0
        risk-evaluated-at: ""
        risk-evaluator: ""
        risk-reason: ""
        risk-source-hash: ""
---

# Analyze UI/UX

Analyze this system thoroughly as an interface and identify the best UI/UX improvement opportunities,
prioritized by how much friction each one removes for people who use the system every day. Prioritize
hesitation, misreads, mis-clicks, retyping, inaccessible controls, and unclear system state over
pure visual preference.

Quality over quantity. Target 8-12 opportunities, but only include findings with impact `High` or
`Medium`. It is better to return 6 excellent findings than to pad the list to hit a number. If you
cannot find 8 strong opportunities, return fewer and say so — do not invent or inflate weak findings
to fill the count.

## Review Dimensions

For each opportunity, evaluate the relevant dimensions below:

1. Information hierarchy
  - important values hidden
  - overloaded tables
  - weak visual priority
2. Form ergonomics
  - poor field order
  - missing input modes or masks
  - unclear required fields
3. Feedback and system state
  - missing loading/success/error states
  - HTMX swaps without indicators
  - destructive actions without confirmation
4. Error presentation
  - errors far from fields
  - lost user input
  - generic or inconsistent messages
5. Consistency
  - macro bypasses
  - divergent button/table/modal patterns
  - terminology drift
6. Density and scanability
  - hard-to-scan rows
  - poor alignment for numbers/statuses
  - overflow or truncation hiding meaning
7. Accessibility and responsiveness
  - weak focus states
  - missing labels or semantics
  - broken tablet/smaller desktop layouts

## Process

1. Explore the interface structure before diving into specific templates.
2. Identify likely hotspots:
  - `base.html` global layout and navigation
  - `_macros.html` design-system primitives
  - long forms for veículo, compra, venda, fechamento, and caixa
  - table rows/fragments and modal flows
  - `app.css`, `columns.js`, `filters.js`, and HTMX attributes
3. Read enough template/CSS/route context to understand each issue before judging it.
4. If the app can be run, render key screens at desktop and smaller widths; if it cannot, say so
   and rely only on template/CSS evidence.
5. Prefer fixes in shared macros and CSS over per-template patches when the issue repeats.
6. Tie every recommendation to a specific template, selector, macro, route, or JS behavior.
7. Avoid feature requests or code-quality refactors unless the interface issue cannot be fixed without them.
8. After preparing the final report, save the content to `.loop/running/improvements-ui-ux.json` as JSON.

## Suggested Workflow

Use `graphify` first to orient cheaply, then only read/grep what it can't answer:

- design system usage: `graphify query "templates using macros and raw repeated controls"`
- HTMX feedback: `graphify query "hx attributes indicators targets error states"`
- screen concept: `graphify explain "<screen or template>"`
- route-to-template relationship: `graphify path "<route>" "<template>"`
- navigation without raw browsing: `graphify-out/wiki/index.md`, if present

Only fall back to `rg`/`find`/`wc -l`/reading full files for what graphify's scoped subgraph doesn't
surface, or to confirm exact line ranges before citing them in a finding. Use Playwright screenshots
only when the app can run and visual observations are needed; never invent visual observations.

## What Strong Findings Look Like

Strong finding:

```text
Money-changing HTMX forms submit without disabled/loading state or nearby error recovery, so staff can double-submit or lose confidence during slow saves.
```

Weak finding:

```text
The page would look nicer with more spacing.
```

Do not report subjective visual polish unless it materially affects comprehension, task speed,
accessibility, or error rate. Do not lower the bar just to reach a round number of findings.

## Output Requirements

Deliver 8-12 opportunities (fewer if that's all the evidence supports), ordered from highest to
lowest impact. Only include `High` or `Medium` impact findings — discard `Low` impact candidates
rather than padding the list with them.

For each opportunity, include:

- **ID**: unique identifier (format: `imp-YYYYMMDD-NNN`)
- **Short title**: actionable, specific to the UI/UX issue
- **Location**: representative file, line range, function/macro/selector, and a real code snippet (8-12 lines)
- **Impact**: `High` or `Medium`
- **Category**: primary dimension from review dimensions
- **Description**: specific explanation tied to the interface
- **Why it matters**: user friction, error risk, accessibility, trust, or frequency
- **Concrete fix**: smallest useful template, CSS, JS, macro, or route change
- **Estimated effort**: `Low`, `Medium`, or `High`
- **Potential savings**: concrete, estimated benefit when it can be reasoned about — omit rather than guess
- **Priority**: `high`, `medium`, or `low` (may differ from impact)
- **Risk level**: `high`, `medium`, or `low` (implementation risk)
- **Tags**: searchable labels
- **Files affected**: list of all files involved in the fix
- **Related opportunities**: IDs of related findings from the same analysis
- **Self-critique**: per-opportunity honest assessment — confidence score, strengths, weaknesses, and uncertainty
- **UI/UX details**: screens, frequency of exposure, propagation, proposed change, and acceptance criteria

## Output Format

Deliver results as a JSON file with this comprehensive structure:

```json
{
  "analysis_timestamp": "ISO-8601 timestamp",
  "total_opportunities": 9,
  "opportunities": [
    {
      "id": "imp-YYYYMMDD-NNN",
      "short_title": "<short, actionable title>",
      "location": {
        "file": "path/to/template.html",
        "line_start": 120,
        "line_end": 135,
        "function": "macro_or_selector_name",
        "snippet": "<8-12 lines of the actual relevant code>"
      },
      "impact": "High",
      "category": "Feedback and system state",
      "estimated_effort": "Medium",
      "potential_savings": "<concrete estimated benefit, omit if not justifiable>",
      "description": "<specific explanation tied to the interface>",
      "why_it_matters": "<user friction, error risk, accessibility, trust, or frequency>",
      "concrete_fix": "<smallest useful template, CSS, JS, macro, or route change>",
      "example": "<before/after interaction or markup when useful>",
      "additional_fields": {
        "priority": "high|medium|low",
        "risk_level": "high|medium|low",
        "tags": ["tag1", "tag2"],
        "files_affected": ["path1", "path2"],
        "related_opportunities": ["imp-YYYYMMDD-NNN"],
        "screens": ["lista de veiculos", "form de venda"],
        "frequency_of_exposure": "Every session|Daily|Occasional",
        "propagates_to": "<how many screens this fix improves>",
        "proposed_change": "<specific macro/CSS/attribute/route change>",
        "acceptance_criteria": ["<verifiable statement 1>", "<verifiable statement 2>"]
      },
      "self_critique": {
        "confidence_score": 8.5,
        "strengths": ["<why this finding is solid, cite what was verified>"],
        "weaknesses": ["<what wasn't verified, assumptions made>"],
        "uncertain": false,
        "suggested_improvements": ["<how to raise confidence further>"]
      }
    }
  ],
  "design_system_current_state": {
    "summary": "<what _macros.html and app.css establish today>",
    "gaps": ["<concrete design-system gap>"]
  },
  "discarded_candidates": [
    {
      "title": "<candidate considered and rejected>",
      "reason": "<why it is not a strong UI/UX opportunity>"
    }
  ]
}
```

## Persistence

- Write the final report to `.loop/running/improvements-ui-ux.json`.
- If the directory does not exist, create it.
- If the file already exists, overwrite it with the latest report.
- `total_opportunities` must match the actual number of items in `opportunities` — do not hardcode it to 10.
- Include all analysis data in the JSON structure above, preserving all findings from the review.

## Review Standard

- Be specific, surgical, and evidence-based.
- Describe the user's friction first, then the template/CSS/HTMX evidence.
- Prefer shared macro and CSS fixes over one-off template tweaks.
- Respect the existing stack: Jinja, HTMX, handwritten CSS, and server-rendered routes.
- Do not propose new features or business rules as UI/UX findings.
- If visual behavior was not rendered, say so in the self-critique instead of inventing observations.
- If a suspected issue is uncertain, set `self_critique.uncertain: true`, list it in `weaknesses`,
  and lower its priority/confidence_score accordingly.
- Include all enriched metadata: tags, affected files, related opportunities, screens, acceptance
  criteria, propagation, and self-assessment of confidence.
- Honesty over completeness: an accurate list of 7 is better than an inflated list of 10.



**IMPORTANT — DO NOT print the report or a summary of it in the terminal.**

The full report is the deliverable, and it goes to
`.loop/running/improvements-ui-ux.json` ONLY.
