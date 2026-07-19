---
paths:
  - "bases/xtreme_system/api/routes/**"
  - "components/xtreme_system/auth/**"
  - "bases/xtreme_system/api/**middleware**"
---

# Security

- Validate all user input at the route boundary (Pydantic schemas). Never trust raw request params or form data.
- Use SQLAlchemy's parameterized query construction. Never format/concatenate user input into raw SQL.
- Escape output rendered into Jinja2 templates; rely on autoescaping — don't use `| safe` on user-supplied content.
- Passwords hashed with argon2; never log or store plaintext passwords or hashes in plaintext logs.
- JWT tokens: keep expiry short, validate signature/claims on every request, don't put sensitive data in the payload.
- UI auth uses httpOnly cookies — set `Secure`, `HttpOnly`, and `SameSite` appropriately; API auth uses Bearer tokens.
- Never log secrets, tokens, passwords, or PII (client documents, CPF, etc.).
- Rate-limit authentication endpoints (login, token refresh).
- File uploads (comprovantes, documentos, imagens) must validate content type/size before writing to `static/uploads` or `media`.
