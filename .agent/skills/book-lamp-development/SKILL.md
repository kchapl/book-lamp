---
name: book-lamp-development
description: Authoritative guide for developing, running and extending Book Lamp — the Flask-blueprint API, React SPA and PostgreSQL architecture, coding standards, build/run workflow, data model and security.
---

# Book Lamp Development

Book Lamp is a self-hosted personal reading-history tracker: a Flask JSON API
backed by PostgreSQL, serving a React single-page application.

## Product philosophy

- **Clarity over cleverness**: prefer readable, explicit code and simple designs.
- **Small, safe steps**: incremental edits backed by tests; avoid large, risky rewrites.
- **User-centric**: optimise for reliability and maintainability before micro-optimisations.
- **British English** in all comments, documentation and naming (`authorisation`, `colour`, `normalise`).

## Architecture

### Backend (Python / Flask)

- The app is built by the `create_app()` factory in `book_lamp/__init__.py`.
  `book_lamp/app.py` is only a thin WSGI shim that re-exports the app and common
  helpers for compatibility with tests and scripts.
- Routes are Blueprints in `book_lamp/routes/`, registered by
  `book_lamp/routes/__init__.py`: `auth`, `books`, `reading_list`,
  `reading_records`, `authors`, `stats`, `recommendations`, `jobs`, `spa`,
  `testing`. Keep routes thin; delegate to services.
- Middleware lives in `book_lamp/middleware/`: `auth`
  (`@authorisation_required`) and `csrf` (`@csrf_protect`, `X-CSRF-Token`).
- Services live in `book_lamp/services/`: storage adapters (`pg_storage`,
  `mock_storage`, `storage_factory`), the PostgreSQL-backed `job_queue`,
  `stats_calculator`, `book_lookup`, `search`, `recommendations` and
  `llm_client`.
- Pure helpers live in `book_lamp/utils/` (`books`, `authors`, `publishers`,
  `reading_status`, `redirects`, `sorting`, `libib_import`).
- There are **no Jinja templates**. The `spa` blueprint serves the built React
  shell from `book_lamp/static/react/` for every page route. If the shell is
  missing it returns HTTP 503 telling the operator to run `npm run build`.

### Frontend (React / TypeScript)

- React 19 + TypeScript in `src/react/`, bundled by Vite into
  `book_lamp/static/react/`. Never edit the built output directly.
- Non-home routes are code-split with `React.lazy`; the home route stays eager
  because it is the LCP element.
- All API access goes through `src/react/services/api.ts`.
- Styles: shared CSS in `book_lamp/static/css/`, component styles in
  `src/react/styles/`.
- `src/ts/` holds legacy vanilla modules that the SPA no longer loads. Do not
  extend them; they are slated for removal.

## Setup and running

- **`scripts/setup`** (once after cloning): installs the pinned toolchain with
  `mise install`, the Python and Node dependencies, and creates `.env` if missing.
- **`scripts/start`** (every run): starts the PostgreSQL container, applies the
  Alembic migrations, builds the React SPA and serves everything through the
  Flask development server on <http://127.0.0.1:5000>. `HOST` and `PORT`
  override the bind address and port.
- Manual equivalent: `mise install`; `uv sync --all-extras`; `npm ci`;
  `npm run build`; `uv run flask --app book_lamp.app run --debug`.
- Environment variables (see `.env.example`): `SECRET_KEY` (**required**),
  `DATABASE_URL`, `GOOGLE_CLIENT_ID` (optional One Tap),
  `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL` (optional recommendations).

## Coding standards

### Python

- Python 3.13.x, managed by `mise`. Run every command with `uv run`.
- Format with `black` (120 columns) and `isort` (black profile, 120 columns).
  Lint with `ruff`. Type-check with `mypy`, strict on public APIs; avoid `Any`.
- Single responsibility per module, class and function; early returns; handle
  errors and edge cases first.
- Descriptive names: verbs for functions, nouns for variables. No abbreviations.
- Document *why*, not *how*; do not comment the obvious.
- Google-style docstrings on all public functions and classes.
- **Pure vs effectful separation**: keep domain logic in deterministic functions
  (no I/O, globals or direct time/randomness) and isolate effects (PostgreSQL,
  network, filesystem, environment, time) at the edges. Inject effectful
  collaborators rather than importing effects into the domain.

### Frontend

- All UI is React + TypeScript under `src/react/`. Never edit compiled JS in
  `book_lamp/static/react/`.
- Keep components small and colocated; route all data access through
  `src/react/services/api.ts`.

### Structure rules

- Keep Flask routes thin; delegate logic to services/use-cases.
- Data is plain dictionaries produced by the PostgreSQL adapter — there are no
  ORM models.

## Data model and PostgreSQL

- Primary adapter: `PostgresStorage` in `book_lamp/services/pg_storage.py`.
  `MockStorage` backs tests under `TEST_MODE`.
- Tables: `books`, `authors`, `book_authors`, `reading_records`,
  `reading_list`, `recommendations`, `settings`, `users`, `jobs`.
- Schema is managed by Alembic migrations in `alembic/versions/`. Apply with
  `uv run alembic upgrade head`; create with
  `uv run alembic revision --autogenerate -m "description"`.
- Use parameterised queries and connection pooling, and keep every database call
  inside the adapter.

## Authentication and security

- Authentication is optional **Google One Tap**; only `GOOGLE_CLIENT_ID` is
  needed. There is no OAuth flow.
- Protect routes with `@authorisation_required` and mutations with
  `@csrf_protect` (the SPA sends `X-CSRF-Token`).
- Validate and sanitise all external input (requests, environment, forms). Never
  pass unsanitised user input to a regular expression (ReDoS); use
  `get_safe_redirect_target` for user-controlled redirects.
- Never log or commit secrets or credentials.

## Testing

See the **testing** skill. In short: `TEST_MODE=1 uv run pytest` for the backend,
`npm run test` (vitest) and `npx tsc --noEmit` for the frontend.

## Commits and change discipline

- Semantic commits (`feat:`, `fix:`, `refactor:`, `docs:`, `chore:`).
- Subject line at most 50 characters; body lines at most 72.
- Make small, cohesive edits and verify each with tests. Add a regression test
  for every bug fix.
- Before finishing, run the same checks as CI:
  - `TEST_MODE=1 uv run pytest --ignore=tests/test_pg_storage.py`
  - `npm run test` and `npx tsc --noEmit`
  - `uv run ruff check .`, `uv run black --check .`,
    `uv run isort --check-only .`, `uv run mypy .`

## Tooling summary

- **Tool manager**: `mise` (Python, Node, uv versions).
- **Python**: 3.13.x. **Dependencies**: `uv` (`uv sync`) and `npm` (`npm ci`).
- **Build**: `npm run build` (`tsc` + Vite).
- **Format/lint**: `black`, `isort`, `ruff`, `mypy`; `tsc` for TypeScript.
- **Tests**: `pytest` (backend), `vitest` (frontend).
