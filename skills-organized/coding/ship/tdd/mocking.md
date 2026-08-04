# Mocking Guidelines

Prefer real collaborators at the seam under test.

**Mock only** across a true boundary you do not own in this test (external HTTP, email, WhatsApp, clock) when the real one is slow, flaky, or unsafe.

**Do not mock** sibling functions inside the same brick, SQLAlchemy session internals when an integration DB fixture exists, or policy helpers just to force a branch — use fixtures and real calls instead.

If the design forces heavy mocking to test behavior, that is a seam smell — note it; do not paper over it with more mocks.
