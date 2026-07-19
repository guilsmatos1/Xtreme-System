# Rules

Rules are modular instruction files that Claude Code loads automatically from `.claude/rules/` (this `rules/` directory is checked in and referenced from `CLAUDE.md`). They extend `CLAUDE.md` without bloating it.

- **No `paths:` frontmatter**. Loaded every session, like `CLAUDE.md`. Costs tokens every turn, so keep it tight.
- **`paths: [...]` frontmatter**. Loaded only when working with files matching the glob patterns. Free until you're near matched files.

Budget convention for always-loaded rules: under 30 lines each. Push everything that doesn't actively change Claude's behavior into a path-scoped rule, or out entirely.

## Available rules

### code-quality.md
**Scope**: Always. ~25 lines.

Anti-defaults that counter common Claude tendencies (no premature abstraction, no scope expansion, no surrounding refactors, WHY-not-WHAT comments). Plus naming conventions and file organization for this codebase's Polylith/Python layout.

### testing.md
**Scope**: Always. ~10 lines.

Terse principles for pytest in this repo: verify behavior, run the specific test file (`test/components/...` / `test/bases/...`), fix or delete flaky tests, prefer real implementations, one assertion per test.

### security.md
**Scope**: Path-scoped (`bases/xtreme_system/api/routes/**`, `components/xtreme_system/auth/**`, `bases/xtreme_system/api/**middleware**`)

Loads when touching route handlers or auth code. Input validation, parameterized SQLAlchemy queries, JWT/argon2 handling, secret logging, CSRF/cookie flags, rate limiting.

### error-handling.md
**Scope**: Path-scoped (`bases/xtreme_system/api/routes/**`, `components/*/core.py`, `components/*/workflows.py`)

Loads near route handlers and component logic. Where validation belongs (core vs. workflows vs. routes), `IntegrityError`/`HTTPException` handling, transaction/rollback discipline (see `bases/xtreme_system/api/crud_writes.py` and `get_session`), consistent HTTP error shapes.

### database.md
**Scope**: Path-scoped (`alembic/versions/**`, `components/*/database/**`)

Loads near Alembic migrations and SQLAlchemy models. Never modify an existing migration, reversibility, test both directions, enums/constraints/indexes conventions.

### frontend.md
**Scope**: Path-scoped (`bases/xtreme_system/api/templates/**`, `bases/xtreme_system/api/static/**`, `**/*.html`)

Loads when touching Jinja2/HTMX templates or static assets. HTMX attribute conventions, partial vs. full-page templates, `app.css` token usage, accessibility, no client-side framework creep.

## Adding your own

Create a new `.md` file in this directory. With no frontmatter it loads every session:

```markdown
# Your Rule Name

- Your instructions here
```

Or path-scoped, so it only loads when Claude touches matching files:

```yaml
---
paths:
  - "components/xtreme_system/your_area/**"
---

# Your Rule Name

- Instructions that only apply when touching these files
```

See [Claude Code docs](https://code.claude.com/docs/en/memory#path-specific-rules) for glob pattern syntax.
