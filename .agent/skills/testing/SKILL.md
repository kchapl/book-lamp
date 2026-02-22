---
name: testing
description: Standards and best practices for testing the Book Lamp application, focused on simplicity, coverage, and maintenance.
---

# Testing Skill

This skill provides the authoritative standards for testing within the Book Lamp project. Following these guidelines ensures a fast, reliable, and maintainable test suite.

## 1. Core Principles

- **Simplicity Above All**: Tests should be as simple as possible. They should be easy to read and understand without complex setup or logic.
- **Total Coverage, Zero Overlap**:
    - **No Gaps**: Every branch of logic and every route MUST have at least one corresponding test case. New features MUST include updated or new tests.
    - **No Overlaps**: Avoid testing the same logic in multiple layers. If a unit test covers a service function, the route test for that service should mock the service rather than re-verifying the internal logic.
- **Fast and Deterministic**: Tests must run quickly (typically < 1s for the whole suite) and must never be flaky. No network calls or real I/O.
- **High Maintenance Standards**: Remove tests as soon as they become redundant (e.g., if a feature is removed or logic is refactored and covered elsewhere).

## 2. Testing Strategy

We explicitly use **Unit Tests** and **Mock Integration Tests**. We do NOT perform End-to-End (E2E) testing (e.g., Playwright) as it is slow and prone to flakiness.

### Location and Execution
- **Location**: All tests reside in the `tests/` directory.
- **Execution**: Run with `poetry run pytest`.
- **Environment**: Always use `TEST_MODE=1` to trigger mock storage and avoid real Google Sheets API interactions.

### Component-Specific Testing

1.  **Pure Logic (Services/Utils)**:
    - Use **Table-Driven Tests** for functions with multiple input combinations.
    - Test edge cases and error handling explicitly.
2.  **Routes and Entry Points**:
    - Use the Flask `test_client`.
    - Mock underlying services (e.g., `GoogleSheetsStorage`) to isolate route logic from data persistence.
    - Verify status codes, redirects, and key content in responses.
3.  **Persistence (Adapters)**:
    - Test adapters by following the **MockStorage** pattern or mocking specific API client methods (e.g., Google API `execute()` calls).
4.  **Performance Efficiency**:
    - Use unit tests to verify backend efficiency (e.g., asserting that batch operations are used instead of N+1 patterns when importing data).

## 3. Best Practices

- **Mocking**: Use `unittest.mock` (or `pytest-mock`) to isolate units of work. Prefer mocking classes/methods over patching at high levels when possible.
- **Fixtures**: Centralise common setup (app context, authenticated client, common mock data) in `tests/conftest.py`.
- **Naming**: Use descriptive test names that state the intention (e.g., `test_add_book_fails_with_invalid_isbn`).
- **Assertions**: Use specific assertions. Prefer `resp.status_code == 200` and `b"Expected Text" in resp.data`.

## 4. Maintenance Workflow

1.  **New Feature**: Add corresponding unit tests. Ensure no existing tests are duplicated.
2.  **Bug Fix**: Add a regression test that specifically targets the discovered bug.
3.  **Refactor**: Update tests to reflect changes in structure, but maintain the same level of logical coverage.
4.  **Cleanup**: Identify and delete tests that are no longer adding value or are subsumed by better tests.
