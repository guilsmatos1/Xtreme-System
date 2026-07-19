# Testing

- Verify behavior, not implementation. Don't assert mock call counts when a return value or DB state check would do.
- Run the specific test file after changes (`uv run pytest test/components/xtreme_system/<component>/test_core.py`), not the full suite. Faster feedback, fewer tokens.
- Tests run in parallel via `pytest-xdist` — don't rely on shared mutable state or execution order between test files.
- Flaky test? Fix it or delete it. Never retry to make it pass.
- Prefer real implementations against the test database. Mock only at true system boundaries (external HTTP calls, clock, randomness) — not SQLAlchemy sessions.
- One assertion per test where practical. Test names describe behavior. Arrange-Act-Assert.
- Never `assert True` or check a mock was called without verifying arguments.
