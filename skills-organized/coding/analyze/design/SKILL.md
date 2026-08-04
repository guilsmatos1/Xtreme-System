---
name: coding--analyze--design
description: Analyze visual-design consistency and design-system/token adherence, ranking the highest-impact drift. Use when asked for a design audit, visual consistency review, or where the UI diverges from its design system.
metadata:
    skill-organizer:
        original-name: coding--analyze--design
        source-relative-path: coding/analyze/design
        disabled: false
        risk-score: 0
        risk-evaluated-at: ""
        risk-evaluator: ""
        risk-reason: ""
        risk-source-hash: ""
---

# Analyze Design

Analyze this system's visual design and identify where it drifts from a coherent, consistent
design language — prioritized by how visible and how frequently encountered the drift is.
This skill is about **what the interface looks like and whether it looks like one system**, not
whether it is easy to operate (that is `coding--analyze--ui-ux`) and not about redesigning it
(that is `coding--refactor--design-overhaul`, which implements change; this skill only reports).

## Review Dimensions

For each opportunity, evaluate the relevant dimensions below:

1. Design tokens and variables
  - hardcoded colors/spacing/radii/shadows that duplicate an existing CSS variable or token
  - one-off values that should map to an existing scale (spacing, font-size, z-index)
  - tokens defined but unused, or multiple tokens meaning the same thing
2. Color consistency
  - divergent shades for the same semantic role (e.g. three near-identical "danger" reds)
  - inconsistent use of brand vs. neutral palette across screens
  - contrast/legibility drift between light and dark contexts if both exist
3. Typography
  - inconsistent font sizes/weights for the same semantic level (e.g. section headers)
  - divergent line-height or letter-spacing between similar components
  - mixed heading hierarchies across templates for equivalent content
4. Component consistency
  - the same UI concept (button, badge, card, modal, table) styled differently in different
    templates instead of reusing a shared macro/component/class
  - divergent border-radius, padding, or shadow treatment for equivalent components
  - icon sets or icon sizes mixed inconsistently
5. Spacing and layout rhythm
  - inconsistent gutter/margin values between structurally similar sections
  - misaligned grids or ad hoc pixel values instead of the spacing scale
  - inconsistent container widths/breakpoints across pages
6. Design-system adherence
  - custom one-off styles that bypass an existing `_macros.html`, component library, or
    documented design-system primitive
  - CSS overrides (`!important`, deeply nested overrides) that indicate fighting the system
    instead of extending it
  - new patterns introduced without a corresponding token/component, risking further drift

## Process

1. Explore the interface and styling structure before judging individual templates.
2. Identify likely hotspots:
  - CSS variable/token definitions (`app.css`, theme files, `:root` blocks)
  - `_macros.html` or shared component partials
  - `base.html` global layout
  - templates that render the same UI concept in more than one place (buttons, badges,
    tables, cards, modals)
3. Build a quick mental map of the declared design system (tokens, scales, shared components)
   before flagging drift — a value only "drifts" relative to something that is supposed to be
   consistent.
4. Grep for repeated hardcoded values (hex colors, `px` spacing, `border-radius`) across
   templates/CSS to find where a token exists but isn't used, or where no token exists at all.
5. If the app can be run, render the same UI concept (e.g. all button variants, all badges)
   side by side to spot divergence visually; if it cannot, rely on template/CSS evidence and say so.
6. Prefer fixes that consolidate into a shared token, class, or macro over per-template patches.
7. Tie every recommendation to a specific selector, token name, macro, or template.
8. Do not report a single non-repeating one-off unless it is highly visible (e.g. primary CTA,
   global nav) — prioritize drift that recurs across multiple screens.
9. After preparing the findings, hand them to the `coding--generate--issues-md` skill,
   which formats and writes `.loop/running/issues-design.md`.

## What Strong Findings Look Like

Strong finding:

```text
Danger buttons use three different reds (#e53e3e, #dc2626, #ef4444) across venda.html,
fechamento.html, and caixa.html instead of the --color-danger token already defined in
app.css, so destructive actions read with inconsistent severity depending on which screen
the user is on.
```

Weak finding:

```text
I'd prefer a slightly different shade of blue for the header.
```

Do not report pure aesthetic taste (font choice you'd personally prefer, color you find
prettier) — only report drift from an established or implied system, or inconsistency between
equivalent elements. Do not lower the bar just to reach a round number of findings.

## Shared harness

Follow [../references/analyze-harness.md](../references/analyze-harness.md) for ranking, graphify
orientation, reading budget, output fields, issues-md handoff, and review standard.

## Persistence

- The output path is `.loop/running/issues-design.md`. Pass it to `coding--generate--issues-md` per
  the harness.
- Hand over every retained finding and discarded candidate from this review — do not summarize, drop,
  or re-rank them on the way in.
