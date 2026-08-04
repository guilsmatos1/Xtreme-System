# Graphify (detail)

Project knowledge graph lives at `graphify-out/`.

## Commands

- Scoped question: `graphify query "<question>"`
- Concept: `graphify explain "<concept>"`
- Relationship: `graphify path "<A>" "<B>"`
- Broad nav: `graphify-out/wiki/index.md` when present
- Full architecture dump: `graphify-out/GRAPH_REPORT.md` only when query/path/explain are insufficient

## Habits

- Prefer graphify over raw tree walks when the graph exists.
- Dirty `graphify-out/` after hooks is expected — not a reason to skip graphify.
- `/graphify` → use the installed graphify skill first.
