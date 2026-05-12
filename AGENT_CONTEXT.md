# Book Lamp – Agent and Contributor Guidelines

This file provides shared context and guardrails for Cursor and other AI agents (and humans) when making changes.

### Product philosophy
- **Clarity over cleverness**: Prefer readable, explicit code and simple designs.
- **Small, safe steps**: Make incremental edits with tests; avoid large, risky rewrites.
- **User-centric**: Optimize for reliability and maintainability before micro-optimizations.

### Architecture
- **PostgreSQL storage**: All data stored in PostgreSQL tables managed by Alembic.
- **Google One Tap**: Optional authentication via Google One Tap (no OAuth flow).
- **Effectful boundaries**: PostgreSQL access isolated in adapter layer.
- **Environment variables**: Use environment variables for sensitive data (e.g., API keys, OAuth secrets).
- Be consistent with the 12-factor app methodology.

### Engineering principles
- **Single responsibility**: Each module/class/function should do one thing well.
- **Pure vs. effectful code separation**:
  - Put domain logic in pure, deterministic functions (no I/O, no globals, no time randomness).
  - Isolate effects (PostgreSQL, network, filesystem, environment, time) at the edges behind small adapters.
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
- **Frontend standards**:
  - **Type Safety**: All frontend logic MUST be written in TypeScript in `src/ts/`. Never edit the compiled `.js` files in `book_lamp/static/`.
  - **Separation of Concerns**: Keep CSS in dedicated files in `book_lamp/static/`. Compiled JavaScript artifacts also reside there.
  - **CSS**: Avoid inline styles and `<style>` blocks in HTML templates. Use `base.css` for global styles and specific files (e.g., `books.css`) for page-specific styles.
  - **HTML**: Templates should focus on structure and Jinja2 logic. Logic should be extracted to modules.
- **Structure**:
  - Keep Flask routes thin; delegate to services/use-cases (pure where possible).
  - Use adapters/gateways for PostgreSQL and external APIs; keep their interfaces narrow.
  - No database models; data is plain dictionaries from Postgres adapter.

### Testing policy
- **All new features must be unit tested.**
  - Test pure functions with table-driven tests; aim for high coverage of branches.
  - Mock only process boundaries (PostgreSQL, network, time). Avoid mocking internal pure helpers.
  - Add regression tests for every bug fix.
  - TEST_MODE uses mock in-memory storage instead of PostgreSQL.
- Prefer fast, deterministic tests; avoid sleeps and real network calls.

### Effects and boundaries
- Centralize configuration (e.g., `python-dotenv`) and avoid reading env vars deep in code.
- Time, UUIDs, randomness: pass in suppliers/factories rather than calling globally.
- PostgreSQL: use PostgresStorage adapter; keep all database calls in that module.

### Security and reliability
- Validate and sanitize all external inputs (requests, env vars, web forms).
- **No Regex Search**: Do not allow unsanitized user input in regular expressions. To prevent ReDoS (Regular Expression Denial of Service), user search inputs must be escaped or regex capabilities disabled entirely for end-users.
- **Database Security**: Use parameterized queries and proper connection pooling. Validate all inputs before database operations.
- Never log secrets. Use structured, levelled logging.
- Keep dependencies minimal; respect pinned versions managed by Poetry.
- Never commit tokens or credentials to version control.

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

### Tooling
- **Tool Manager**: `mise` (manages Python, Node, and Poetry versions)
- **Python**: 3.13.x
- **Dependency Managers**: Poetry (`poetry run`) and NPM (`npm install`)
- **Build**: TypeScript (`npm run build`) via `tsc`.
- **Formatters**: `black`, `isort`
- **Linters**: `ruff`, `mypy` (strict mode), `tsc` (strict mode)
- **Testing**: `pytest` (backend) and `vitest` (frontend)
