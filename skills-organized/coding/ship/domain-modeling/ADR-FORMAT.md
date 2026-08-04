# ADR Format

ADRs live in `docs/adr/` as `0001-slug.md`, `0002-slug.md`, … Create the directory lazily. Scan for the highest number and increment.

## Template

```md
# {Short title of the decision}

{1-3 sentences: context, decision, why.}
```

Optional only when valuable: Status, Considered Options, Consequences.

## When to offer

All three must be true: hard to reverse, surprising without context, real trade-off. Otherwise skip.
