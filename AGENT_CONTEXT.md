# Book Lamp – Agent and Contributor Guidelines

This file provides shared context and guardrails for Cursor and other AI agents (and humans) when making changes.

### Product philosophy
- **Clarity over cleverness**: Prefer readable, explicit code and simple designs.
- **Small, safe steps**: Make incremental edits with tests; avoid large, risky rewrites.
- **User-centric**: Optimize for reliability and maintainability before micro-optimizations.

### Architecture
- **Google Sheets storage**: All data stored in Google Sheets tabs (no database).
- **Google OAuth**: Authentication via Google with allowlist-based access control.
- **Effectful boundaries**: Google Sheets API access isolated in adapter layer.
- **Environment variables**: Use environment variables for sensitive data (e.g., API keys, OAuth secrets).
- Be consistent with the 12-factor app methodology.

### Engineering principles
- **Single responsibility**: Each module/class/function should do one thing well.
- **Pure vs. effectful code separation**:
  - Put domain logic in pure, deterministic functions (no I/O, no globals, no time randomness).
  - Isolate effects (Sheets API, network, filesystem, environment, time) at the edges behind small adapters.
  - Dependency-inject effectful collaborators into pure logic; do not import effects deep into the domain.
- **Explicit contracts**: Use clear function signatures, docstrings, and precise naming.
- **Composition first**: Prefer composing small functions over inheritance-heavy designs.
- **Fail fast with context**: Validate inputs early and raise actionable errors.
- **Security**: Validate and sanitize all external inputs (requests, env vars, web forms).
- Never log secrets. Use structured, levelled logging.
- Keep dependencies minimal; respect pinned versions managed by Poetry.

### Coding standards (Python)
- **Language and tooling**:
  - Python 3.13.x
  - Use `poetry` for dependency management.
  - Call `poetry run` for all commands.
  - Format with `black` and sort imports with `isort` (keep default project configs if present).
  - Lint with `ruff` and type-check with `mypy` (be strict on public APIs; avoid `Any`).
- **Style**:
  - Descriptive names: functions as verbs, variables as nouns. Avoid abbreviations.
  - Early returns; handle errors and edge cases first.
  - Keep functions small; prefer pure helpers for logic.
  - Do not add comments for the obvious; document "why" more than "how".
  - css should be in a separate file to html
- **Structure**:
  - Keep Flask routes thin; delegate to services/use-cases (pure where possible).
  - Use adapters/gateways for Google Sheets and external APIs; keep their interfaces narrow.
  - No database models; data is plain dictionaries from Sheets adapter.

### Testing policy
- **All new features must be unit tested.**
  - Test pure functions with table-driven tests; aim for high coverage of branches.
  - Mock only process boundaries (Sheets API, network, time). Avoid mocking internal pure helpers.
  - Add regression tests for every bug fix.
  - TEST_MODE uses mock in-memory storage instead of Google Sheets.
- Prefer fast, deterministic tests; avoid sleeps and real network calls.

### Effects and boundaries
- Centralize configuration (e.g., `python-dotenv`) and avoid reading env vars deep in code.
- Time, UUIDs, randomness: pass in suppliers/factories rather than calling globally.
- Google Sheets: use GoogleSheetsStorage adapter; keep all API calls in that module.

### Security and reliability
- Validate and sanitize all external inputs (requests, env vars, web forms).
- Never log secrets. Use structured, levelled logging.
- Keep dependencies minimal; respect pinned versions managed by Poetry.
- Never commit credentials.json or token.json to version control.

### Change discipline
- Small, cohesive edits with clear commit messages.
- If an edit increases complexity, extract helpers or add tests to compensate.
- Prefer additive changes over broad refactors unless tests already cover the surface area.

### When in doubt
- Default to adding a pure function plus a thin effectful adapter.
- Write the test first for the behavior you intend to change.
- Optimize for readability for the next engineer. 
- Comments and naming generally must always be in British English.

### Commits
 - Subject line should be maximum of 50 chars in semantic commit format.
 - Body lines should be maximum of 72 chars.

