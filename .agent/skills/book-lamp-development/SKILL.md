---
name: book-lamp-development
description: Guidelines and workflows for developing the Book Lamp application, focusing on the PostgreSQL adapter pattern and project philosophy.
---

# Book Lamp Development Skill

This skill provides comprehensive guidelines for developing, maintaining, and extending the Book Lamp application.

## Core Philosophy

Following the **Python Architecture Tutor** principles, we prioritise clarity, readability, and explicit structure:

### 1. Layered Architecture (Separation of Concerns)
The project is structured into distinct layers to separate business logic from external side effects:
- **Models/Entities**: Pure data structures (e.g., book dictionaries with defined keys).
- **Adapters (Persistence)**: Isolated in `book_lamp/services/`. `PostgresStorage` is our primary adapter for PostgreSQL.
- **Service Layer**: Pure logic that sits between entry points and adapters (e.g., `book_lookup.py`).
- **Entry Points**: Flask routes in `app.py` and CLI commands.

### 2. Pure vs. Effectful Separation
- **Pure Code**: Logic should be deterministic. It should not perform I/O or rely on system time directly.
- **Effectful Code**: All I/O (PostgreSQL, network, filesystem, time) must be isolated at the edges in adapter classes or functions.
- **Dependency Injection**: Inject adapters into logic or entry points to keep them decoupled.

### 3. Mentorship & Readability
- **Explicit over Implicit**: Avoid "magic". Prefer clear connections between components.
- **British English**: All comments, documentation, and naming (where possible) MUST use British English (e.g., `serialise`, `colour`, `optimise`).
- **Standard Library**: Prefer modern Python standards (e.g., `datetime.now(timezone.utc)`, `pathlib`).

### 4. Frontend Architecture
- **Type Safety**: All frontend logic MUST be written in TypeScript in `src/ts/`. Never edit the compiled `.js` files in `book_lamp/static/`.
- **Separation of Concerns**: CSS and compiled JavaScript artifacts must be kept in dedicated files in `book_lamp/static/`.
- **CSS**: Avoid inline styles or `<style>` blocks in HTML templates. Use descriptive filenames (e.g., `base.css`, `books.css`).
- **HTML**: Keep templates focused on structure and Jinja2 logic. Extract all logic to TypeScript modules.

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

## Working with PostgresStorage

The `PostgresStorage` class in `book_lamp/services/postgres_storage.py` is the primary adapter for data.

### Database Schema
- **books**: `id`, `isbn13`, `title`, `author`, `publication_year`, `thumbnail_url`, `created_at`
- **reading_records**: `id`, `book_id`, `status`, `start_date`, `end_date`, `rating`, `created_at`
- **users**: `id`, `email`, `created_at`
- **reading_list**: `id`, `user_id`, `book_id`, `created_at`
- **settings**: `id`, `user_id`, `key`, `value`, `created_at`
- **recommendations**: `id`, `user_id`, `book_id`, `reason`, `created_at`

### Database Management
- Schema is managed by Alembic migrations in the `alembic/` directory.
- Use `alembic upgrade head` to apply migrations.
- Use `alembic revision --autogenerate -m "description"` to create new migrations.

### Extending the Schema
1.  Create a new Alembic migration: `alembic revision --autogenerate -m "Add new table"`
2.  Update the `PostgresStorage` class methods to handle new columns/tables.
3.  Use parameterized queries for all database operations.
4.  Test the migration with `alembic upgrade head` and `alembic downgrade -1`.

### Handling IDs
- IDs are auto-incrementing serial columns managed by PostgreSQL.
- Foreign key constraints ensure referential integrity.

## Testing Strategy

Refer to the **Testing** skill for standards and patterns. All code must be verified with simple, high-coverage unit tests in the `tests/` directory.

## Security and Configuration

### Authentication
- The application optionally uses **Google One Tap** for authentication.
- No OAuth flow is required; users can use the app without Google login.
- If Google One Tap is used, only `GOOGLE_CLIENT_ID` is needed.

### Secrets and Sanitization
- Never commit `.env` files or credentials.
- **Required Environment Variables**:
  - `SECRET_KEY`: For Flask session management.
  - `DATABASE_URL`: PostgreSQL connection string.
  - `GOOGLE_CLIENT_ID`: Optional Google One Tap Client ID.
- **Input Sanitization**: Always strip and normalize user input (ISBNs, titles) before processing or storing.

## Debugging and Diagnostics

### Common PostgreSQL Errors
- **Connection Error**: Check if `DATABASE_URL` is correct and database is accessible.
- **Migration Error**: Run `alembic upgrade head` to ensure schema is current.
- **Constraint Violation**: Check foreign key relationships and data integrity.
- **Pool Timeout**: Increase connection pool size or check database load.

### Logs
- Application logs are configured with standard formatting. Check terminal output for database queries and connection pool status.

## Environment Setup
1.  **Dependencies**: Run `mise install`, then `poetry install` for backend and `npm install` for frontend.
2.  **Configuration**: Copy `.env.example` to `.env` and fill in `DATABASE_URL` and optional `GOOGLE_CLIENT_ID`.
3.  **Database Setup**: Run `podman-compose up -d` to start PostgreSQL, then `poetry run alembic upgrade head`.
4.  **Frontend Build**: Run `npm run build` to compile TypeScript to JavaScript.
5.  **Initialization**: The database schema is automatically created by Alembic migrations.
6.  **Local Run**: `poetry run flask --app book_lamp.app run --debug`.

## Commits and Change Discipline
- Use **Semantic Commits** (e.g., `feat:`, `fix:`, `refactor:`, `docs:`).
- Subject line: Max 50 characters.
- Body lines: Max 72 characters.
- Make small, cohesive edits. Verify each step with tests.

## Tooling
- **Tool Manager**: `mise` (manages Python, Node, and Poetry versions)
- **Python**: 3.13.x
- **Dependency Managers**: Poetry (`poetry run`) and NPM (`npm install`)
- **Build**: TypeScript (`npm run build`) via `tsc`.
- **Formatters**: `black`, `isort`
- **Linters**: `ruff`, `mypy` (strict mode), `tsc` (strict mode)
- **Testing**: `pytest` (backend) and `vitest` (frontend)
