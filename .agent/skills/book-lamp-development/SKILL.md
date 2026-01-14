---
name: book-lamp-development
description: Guidelines and workflows for developing the Book Lamp application, focusing on the Google Sheets adapter pattern and project philosophy.
---

# Book Lamp Development Skill

This skill provides comprehensive guidelines for developing, maintaining, and extending the Book Lamp application.

## Core Philosophy

### 1. Pure vs. Effectful Separation
- **Pure Code**: Domain logic must reside in pure, deterministic functions. They should not perform I/O, access globals, or rely on system time directly.
- **Effectful Code**: All I/O (Google Sheets API, network, filesystem, time) must be isolated at the edges in adapter classes (e.g., `GoogleSheetsStorage`).
- **Dependency Injection**: Inject effectful collaborators into pure logic as suppliers or factories.

### 2. Modern Python Standards (Code Refactoring)
- **Time**: Avoid `datetime.utcnow()` (deprecated). Use `datetime.now(datetime.timezone.utc)`.
- **Paths**: Use `pathlib.Path` for filesystem operations.
- **Type Hints**: Use modern type hinting (e.g., `list[str]` instead of `List[str]` from `typing`).
- **f-strings**: Prefer f-strings for all string formatting.

### 3. British English Requirement
- All code comments, documentation, and naming (where possible and not restricted by external APIs) MUST use **British English**.
- Example: Use `serialise` instead of `serialize`, `colour` instead of `color`, `optimise` instead of `optimize`.

## Documentation Standard
- **Docstrings**: Use **Google Style** docstrings for all public functions and classes.
- **Template**:
  ```python
  def function_name(param1: str) -> bool:
      """Short summary of the function.

      Detailed description if necessary.

      Args:
          param1: Description of param1.

      Returns:
          Description of the return value.
      """
  ```

## Working with Google Sheets Storage

The `GoogleSheetsStorage` class in `book_lamp/services/sheets_storage.py` is the primary adapter for data.

### Extending the Schema
1.  Update the `initialize_sheets` method to include new headers.
2.  Update the range in `get_all_books` (e.g., `Books!A:G` to `Books!A:H`).
3.  Update the mapping logic in `get_all_books` and `add_book`.
4.  Always use 1-based indexing for row deletions and updates as required by the Google Sheets API.

### Handling IDs
- IDs are managed manually by finding the maximum value in the first column of a tab and incrementing it.
- Always check for empty sheets or sheets with only headers.

## Testing Strategy

### Unit Tests
- Test pure logic with table-driven tests.
- Mock the `GoogleSheetsStorage` or use the `MOCK_STORAGE` pattern if available.
- Place unit tests in the `tests/` directory.

### E2E Tests (Playwright)
- E2E tests are located in `tests-e2e/`.
- Use `npm test` to run the suite.
- The app should automatically handle `TEST_MODE` to avoid hitting real Google APIs during testing.

## Security and Configuration

### Allowed User Email
- The application is restricted to a single user.
- The user is identified by the SHA-256 hash of their email address, stored in `book_lamp/config.py`.
- **To generate a new hash**: `poetry run flask --app book_lamp.app hash-email user@example.com`
- Ensure the email is normalised (lowercase, stripped) before hashing.

### Secrets and Sanitization
- Never commit `credentials.json`, `token.json`, or `.env` files.
- Use `ALLOWED_USER_EMAIL_HASH` environment variable to override the default hash in production.
- **Input Sanitization**: Always strip and normalize user input (ISBNs, titles) before processing or storing.

## Debugging and Diagnostics

### Common Google Sheets Errors
- **403 Forbidden**: Check if the Service Account or OAuth user has "Editor" access to the spreadsheet.
- **404 Not Found**: Verify `GOOGLE_SPREADSHEET_ID` in `.env` matches the ID in the URL of your sheet.
- **Invalid Credentials**: Delete `token.json` and re-run the login flow.

### Logs
- Application logs are configured with standard formatting. Check terminal output for `Computed hash` vs `Expected hash` during login failures.

## Environment Setup
1.  **Dependencies**: Run `mise install` followed by `poetry install`.
2.  **Configuration**: Copy `.env.example` to `.env` and fill in Google Cloud credentials.
3.  **Initialization**: Run `poetry run flask --app book_lamp.app init-sheets` to prepare the spreadsheet.
4.  **Local Run**: `poetry run flask --app book_lamp.app run --debug`.

## Commits and Change Discipline
- Use **Semantic Commits** (e.g., `feat:`, `fix:`, `refactor:`, `docs:`).
- Subject line: Max 50 characters.
- Body lines: Max 72 characters.
- Make small, cohesive edits. Verify each step with tests.

## Tooling
- **Tool Manager**: `mise` (manages Python, Node, and Poetry versions)
- **Python**: 3.13.x
- **Dependency Manager**: Poetry (`poetry install`, `poetry run`)
- **Formatters**: `black`, `isort`
- **Linters**: `ruff`, `mypy` (strict mode)
