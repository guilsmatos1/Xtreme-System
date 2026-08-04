---
name: coding--ship--domain-modeling
description: Build and sharpen the project domain model. Use when pinning terminology, recording an ADR, or when another skill maintains the domain model.
metadata:
    skill-organizer:
        original-name: coding--ship--domain-modeling
        source-relative-path: coding/ship/domain-modeling
        disabled: false
        risk-score: 0
        risk-evaluated-at: ""
        risk-evaluator: ""
        risk-reason: ""
        risk-source-hash: ""
---

# Domain Modeling

Actively build and sharpen the project's domain model. Merely *reading* `CONTEXT.md` is not this skill — that is a one-line habit. This skill is for *changing* the model.

## Layout

Single context (this repo):

```
/
├── CONTEXT.md
└── docs/adr/
```

Create files lazily. If `CONTEXT.md` is missing, create it when the first term is resolved. If `docs/adr/` is missing, create it when the first ADR is needed.

## During the session

1. **Challenge** terms that conflict with `CONTEXT.md`.
2. **Sharpen** vague/overloaded words into a canonical term (+ `_Avoid_` list).
3. **Stress-test** relationships with concrete edge-case scenarios.
4. **Cross-check** claims against code (graphify / scoped reads); surface contradictions.
5. **Update `CONTEXT.md` inline** the moment a term is resolved — no batching. Format: [CONTEXT-FORMAT.md](CONTEXT-FORMAT.md). No implementation details in the glossary.
6. **Offer an ADR** only when all three hold: hard to reverse, surprising without context, real trade-off. Format: [ADR-FORMAT.md](ADR-FORMAT.md).
