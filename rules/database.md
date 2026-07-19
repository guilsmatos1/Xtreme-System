---
paths:
  - "alembic/versions/**"
  - "components/xtreme_system/database/**"
  - "components/*/database/**"
---

# Database Migrations

- **Never modify an existing migration.** Always create a new migration for changes. Existing migrations may have already run in production. Generate with `make migrate` / `uv run alembic revision --autogenerate -m "..."`, don't hand-write revision IDs.
- Every migration must be reversible. Implement both `upgrade()` and `downgrade()`.
- Test migrations in both directions locally before committing (`uv run alembic upgrade head` then `uv run alembic downgrade -1`).
- Migration order follows the `down_revision` chain, not filenames — verify the chain when adding one.
- Never use raw SQL when SQLAlchemy/Alembic op helpers cover the operation.
- Never seed production data in migration files.
- Never drop columns or tables without first confirming the data is no longer needed.
- New enums, constraints, and indexes belong in `DATABASE.md` — update it alongside the migration.
- Read `DATABASE.md` before writing schema, model, or enum changes; it documents current models, constraints, and relationships.
