# PostgreSQL Migration Plan

**Status:** Ready for implementation  
**Confirmed:** 2026-05-04

Replace the Google Sheets data store with a shared PostgreSQL database (Neon
in production, Podman locally). Remove all caching, async-sync, and OAuth
redirect infrastructure that existed solely to work around Sheets latency.

---

## Design Decisions (all confirmed)

| # | Topic | Decision |
|---|---|---|
| 1 | Auth | **Google One Tap** — JWT verified server-side; no OAuth redirect; no Drive scope |
| 2 | Users | **Multi-user** — shared Neon DB, all per-user data scoped by `user_id` |
| 3 | Job queue | **Keep** `job_queue.py` — background threads for long-running enrichment |
| 4 | CI database | **`pytest-docker`** — Postgres 16 container in CI; unit tests stay on `MockStorage` |
| 5 | Recommendations TTL | **Keep 7-day check** — `recommendations.py` logic is unchanged |
| 6 | `GOOGLE_CLIENT_SECRET` | **Remove** from all configs — One Tap only needs `GOOGLE_CLIENT_ID` |

---

## Architecture Before / After

| Area | Before | After |
|---|---|---|
| Data store | Google Sheets (per-user spreadsheet) | Shared Postgres DB |
| Auth | Google OAuth + Drive scope | Google One Tap (JWT only) |
| Caching | `SQLiteCache` (15-min TTL) | Removed |
| Async sync layer | `AsyncSQLiteStorage` + outbox | Removed |
| SQLite state | `SQLiteStateStore` | Removed |
| Local dev DB | none | Podman Compose (Postgres 16) |
| Prod DB | none | Neon serverless Postgres |
| Schema migrations | none | Alembic |
| Test storage | `MockStorage` (in-memory) | `MockStorage` (unchanged) |

---

## Implementation Steps

Each step below is one commit. Work on a feature branch
(`feat/postgres-migration`). Do not merge to `main` until all steps are done
and tests pass.

---

### Step 1 — Add infrastructure files

**Commit message:** `chore: add Podman Compose and Alembic scaffold`

**Files to create:**

**`compose.yaml`** (project root):
```yaml
services:
  db:
    image: docker.io/library/postgres:16-alpine
    environment:
      POSTGRES_DB: book_lamp_dev
      POSTGRES_USER: book_lamp
      POSTGRES_PASSWORD: book_lamp
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U book_lamp"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
```

**`.env.example`** — add:
```env
DATABASE_URL=postgresql://book_lamp:book_lamp@localhost:5432/book_lamp_dev
```

**`.env.example`** — remove:
```env
GOOGLE_CLIENT_SECRET=...
```

**`.gitignore`** — add:
```
.cache/
```

**Review checklist:**
- [ ] `podman-compose up -d` starts the container without errors
- [ ] `podman-compose ps` shows the `db` container as healthy
- [ ] `.env.example` has no `GOOGLE_CLIENT_SECRET`

---

### Step 2 — Add Python dependencies

**Commit message:** `chore: swap Google API deps for psycopg3 and alembic`

**`pyproject.toml` — add to `[tool.poetry.dependencies]`:**
```toml
psycopg = {extras = ["binary"], version = "3.3.4"}
psycopg-pool = "3.3.1"
alembic = "1.13.0"
```

**`pyproject.toml` — remove from `[tool.poetry.dependencies]`:**
```toml
authlib = "1.6.11"
google-auth-oauthlib = "^1.1.0"
google-auth-httplib2 = "^0.2.0"
google-api-python-client = "^2.108.0"
protobuf = ">=6.33.4"
```

**`pyproject.toml` — keep:**
```toml
google-auth = "2.43.0"   # still needed for One Tap JWT verification
```

**`pyproject.toml` — add to `[tool.poetry.group.dev.dependencies]`:**
```toml
pytest = "8.3.4"
pytest-docker = "3.1.1"
```

Run:
```bash
poetry lock
poetry install
```

**Review checklist:**
- [ ] `poetry install` completes without errors
- [ ] `import psycopg` works in a `poetry run python -c` check
- [ ] `poetry run alembic --version` prints a version
- [ ] `poetry run pytest --collect-only` still collects all existing tests

---

### Step 3 — Initialise Alembic and write the initial migration

**Commit message:** `feat: add initial postgres schema via alembic`

Run in the repo root:
```bash
poetry run alembic init alembic
```

**Edit `alembic/env.py`** — replace the `sqlalchemy.url` config line with:
```python
import os
config.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])
```

Also configure `run_migrations_online` to use a plain `psycopg` connection
rather than SQLAlchemy (since we are not using an ORM):

```python
from psycopg import connect as pg_connect

def run_migrations_online() -> None:
    url = config.get_main_option("sqlalchemy.url")
    with pg_connect(url) as conn:
        context.configure(connection=conn, target_metadata=None)
        with context.begin_transaction():
            context.run_migrations()
```

**Create `alembic/versions/0001_initial_schema.py`:**

```python
"""Initial schema.

Revision ID: 0001
Revises:
Create Date: 2026-05-04
"""
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id         SERIAL PRIMARY KEY,
            email      TEXT NOT NULL UNIQUE,
            name       TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS books (
            id                  SERIAL PRIMARY KEY,
            isbn13              TEXT NOT NULL UNIQUE,
            title               TEXT NOT NULL,
            author              TEXT NOT NULL,
            publication_year    INTEGER,
            thumbnail_url       TEXT,
            publisher           TEXT,
            description         TEXT,
            series              TEXT,
            bisac_category      TEXT,
            bisac_main_category TEXT,
            bisac_sub_category  TEXT,
            language            TEXT,
            page_count          INTEGER,
            physical_format     TEXT,
            edition             TEXT,
            cover_url           TEXT,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS authors (
            id   SERIAL PRIMARY KEY,
            name TEXT NOT NULL UNIQUE
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS book_authors (
            book_id   INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
            author_id INTEGER NOT NULL REFERENCES authors(id) ON DELETE CASCADE,
            PRIMARY KEY (book_id, author_id)
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS reading_records (
            id         SERIAL PRIMARY KEY,
            user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            book_id    INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
            status     TEXT NOT NULL,
            start_date DATE,
            end_date   DATE,
            rating     INTEGER DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS reading_list (
            user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            book_id    INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
            position   INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (user_id, book_id)
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS recommendations (
            id            SERIAL PRIMARY KEY,
            user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            title         TEXT NOT NULL,
            author        TEXT NOT NULL,
            isbn13        TEXT,
            justification TEXT,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            key     TEXT NOT NULL,
            value   TEXT NOT NULL,
            PRIMARY KEY (user_id, key)
        )
    """)


def downgrade() -> None:
    for table in [
        "settings", "recommendations", "reading_list",
        "reading_records", "book_authors", "authors", "books", "users",
    ]:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
```

**Review checklist:**
- [ ] `podman-compose up -d` running
- [ ] `DATABASE_URL=... poetry run alembic upgrade head` applies without errors
- [ ] All 8 tables exist: `\dt` in `psql` confirms them
- [ ] `DATABASE_URL=... poetry run alembic downgrade base` removes all tables cleanly

---

### Step 4 — Write `PostgresStorage` adapter (read operations)

**Commit message:** `feat: add PostgresStorage adapter — read operations`

Create `book_lamp/services/pg_storage.py`.

Implement all **read** methods against Postgres. Write operations are stubbed
(`raise NotImplementedError`) so the file is valid Python and mypy-clean from
the start.

Key design points:
- Module-level `ConnectionPool` initialised from `DATABASE_URL`.
- All queries use `%s` placeholders (psycopg3 style).
- `get_all_books()` does a single JOIN across `books`, `authors`, and
  `book_authors` to return the same dict shape as `MockStorage`.
- `get_reading_history()` JOINs `reading_records` with `books`.
- `search()` delegates to the existing `book_lamp.services.search.search_books`
  pure function (no changes needed there).
- `prefetch()` is a no-op.
- `is_authorised()` returns `True` (if `user_id` is set, the user exists by
  construction).

**Review checklist:**
- [ ] `poetry run mypy book_lamp/services/pg_storage.py` passes
- [ ] `poetry run pytest` (existing suite) still passes — nothing is wired up yet
- [ ] Manual smoke test: start Podman DB, run migration, call `get_all_books()`
      from a `poetry run python` shell → returns `[]` (empty DB)

---

### Step 5 — Write `PostgresStorage` adapter (write operations)

**Commit message:** `feat: add PostgresStorage adapter — write operations`

Implement all **write** methods in `pg_storage.py`:

- `add_book` / `update_book` / `delete_book` / `upsert_book`
- `add_reading_record` / `update_reading_record` / `delete_reading_record`
- `add_to_reading_list` / `remove_from_reading_list` /
  `update_reading_list_order` / `start_reading`
- `save_recommendations`
- `update_setting`
- `bulk_import` (wrap in a single transaction)
- `upsert_user(email, name) -> int` (used by the auth endpoint)

All writes use explicit transactions (`with pool.connection() as conn: conn.autocommit = False`).

**Review checklist:**
- [ ] `poetry run mypy book_lamp/services/pg_storage.py` passes
- [ ] `poetry run pytest` (existing suite) still passes
- [ ] Manual smoke test against Podman DB: add a book, read it back, update it,
      delete it — results match expectations

---

### Step 6 — Integration tests for `PostgresStorage`

**Commit message:** `test: add pg_storage integration tests with pytest-docker`

Create `tests/test_pg_storage.py`.

The test module uses `pytest-docker` to spin up the Postgres container defined
in `compose.yaml`, runs `alembic upgrade head`, then exercises
`PostgresStorage`.

Coverage required:
- `add_book` + `get_book_by_isbn` round-trip
- `upsert_book` idempotency (second call updates, does not duplicate)
- `add_reading_record` + `get_reading_records` scoped to `user_id`
- Multi-user isolation: user A's records are not visible to user B
- `bulk_import` inserts correct counts
- `start_reading` removes from reading list and adds an "In Progress" record
- `save_recommendations` + `get_recommendations` round-trip
- `update_setting` + `get_settings` round-trip

Also create `tests/test_one_tap_auth.py`:
- Mock `google.oauth2.id_token.verify_oauth2_token` to return a fake payload
- `POST /api/auth/google` with valid credential → 200, session has `user_id`
- `POST /api/auth/google` with missing credential → 400
- `POST /api/auth/google` where verify raises `ValueError` → 401

**Review checklist:**
- [ ] `podman-compose up -d` running
- [ ] `DATABASE_URL=... poetry run pytest tests/test_pg_storage.py -v` passes
- [ ] `poetry run pytest tests/test_one_tap_auth.py -v` passes (uses `MockStorage`)
- [ ] All existing tests still pass

---

### Step 7 — Add `POST /api/auth/google` endpoint

**Commit message:** `feat: add Google One Tap login endpoint`

Add to `book_lamp/app.py`:

```python
@app.route("/api/auth/google", methods=["POST"])
def google_one_tap_login():
    """Verify a Google One Tap credential JWT and create a session."""
    from google.oauth2 import id_token
    from google.auth.transport import requests as google_requests

    if is_test_mode():
        return jsonify({"error": "Not available in test mode"}), 400

    data = request.get_json(silent=True) or {}
    credential = data.get("credential")
    if not credential:
        return jsonify({"error": "Missing credential"}), 400

    try:
        id_info = id_token.verify_oauth2_token(
            credential,
            google_requests.Request(),
            app.config["GOOGLE_CLIENT_ID"],
        )
        email = id_info["email"]
        name = id_info.get("name", "")

        from book_lamp.services.pg_storage import PostgresStorage
        user_id = PostgresStorage.upsert_user(email=email, name=name)
        session["user_id"] = user_id
        session["user_email"] = email

        return jsonify({"ok": True})
    except ValueError:
        app.logger.exception("One Tap credential verification failed")
        return jsonify({"error": "Invalid credential"}), 401
```

Remove from `app.py`:
- `from authlib.integrations.flask_client import OAuth`
- `oauth = OAuth(app)` and `oauth.register(...)` block
- `app.config["GOOGLE_CLIENT_SECRET"]`
- `app.config["GOOGLE_DISCOVERY_URL"]`
- The validation block that raises `ValueError` for missing client secret

**Review checklist:**
- [ ] `poetry run mypy book_lamp/app.py` passes
- [ ] `poetry run pytest tests/test_one_tap_auth.py -v` passes
- [ ] No `authlib` import anywhere in the codebase (`grep -r authlib book_lamp/`)

---

### Step 8 — Update frontend: replace OAuth button with One Tap

**Commit message:** `feat: replace Google Sheets OAuth button with One Tap UI`

**`book_lamp/templates/home.html`** (or base template):
- Remove the "Connect Google Sheets" button and any Sheets-related messaging.
- Add the GSI script tag:
  ```html
  <script src="https://accounts.google.com/gsi/client" async defer></script>
  ```
- Add the One Tap initialisation element:
  ```html
  <div id="g_id_onload"
       data-client_id="{{ config['GOOGLE_CLIENT_ID'] }}"
       data-callback="handleOneTapCredential"
       data-auto_prompt="false">
  </div>
  <div class="g_id_signin"
       data-type="standard"
       data-size="large"
       data-theme="outline"
       data-text="sign_in_with"
       data-shape="rectangular">
  </div>
  ```

**`src/ts/one_tap.ts`** (new file):
```typescript
/** Handles the Google One Tap credential callback. */
async function handleOneTapCredential(response: { credential: string }): Promise<void> {
  const res = await fetch("/api/auth/google", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ credential: response.credential }),
  });

  if (res.ok) {
    window.location.href = "/books";
  } else {
    console.error("One Tap login failed", await res.json());
  }
}

// Expose to global scope for the GSI callback
(window as unknown as Record<string, unknown>)["handleOneTapCredential"] =
  handleOneTapCredential;
```

Add `one_tap.ts` to the TypeScript build (update `tsconfig.json` includes if
needed, or import from `main.ts`).

Remove:
- `/connect` route handler from `app.py`
- `/authorize` route handler from `app.py`
- The `test_connect` / `test_disconnect` routes (if they exist solely for OAuth
  test mode plumbing)

Update `/logout` to simply `session.clear()`.

**Review checklist:**
- [ ] `npm run build` succeeds with no TS errors
- [ ] Home page renders without any reference to Google Sheets
- [ ] "Sign in with Google" button appears on the home page
- [ ] `/connect` and `/authorize` URLs return 404
- [ ] `poetry run pytest` passes

---

### Step 9 — Rewire `get_storage()` to use `PostgresStorage`

**Commit message:** `feat: wire get_storage() to PostgresStorage for authenticated users`

**`book_lamp/app.py`** — replace `get_storage()`:

```python
def get_storage():
    """Return the appropriate storage backend for the current request."""
    if is_test_mode():
        return _mock_storage_singleton

    user_id = session.get("user_id")
    if not user_id:
        # Callers protected by @authorisation_required will never reach this,
        # but return an unauthorised-looking object for safety.
        from book_lamp.services.mock_storage import MockStorage
        unauthed = MockStorage()
        unauthed.set_authorised(False)
        return unauthed

    if "storage" not in g:
        from book_lamp.services.pg_storage import PostgresStorage
        g.storage = PostgresStorage(user_id=int(user_id))
    return g.storage
```

**`authorisation_required` decorator** — change to check session directly:

```python
def authorisation_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("unauthorised"))
        return f(*args, **kwargs)
    return decorated_function
```

Remove from `app.py`:
- `_async_storage_singleton` global and its initialisation
- `AsyncSQLiteStorage` import
- The `ASYNC_SQLITE_STORAGE` env-var branch in `get_storage()`
- The `GoogleSheetsStorage` import and its branch in `get_storage()`
- `from book_lamp.services import sheets_storage as from_sheets_storage`
- `storage.prefetch()` calls (or keep as no-ops — they are safe since
  `PostgresStorage.prefetch()` is a no-op)
- `if storage.spreadsheet_id: session["spreadsheet_id"] = ...` lines
- The `inject_global_vars` context processor — simplify: read `user_id` from
  session rather than checking `credentials`

**Review checklist:**
- [ ] `poetry run pytest` (full suite) passes — existing unit tests still use `MockStorage`
- [ ] `poetry run mypy book_lamp/app.py` passes
- [ ] Manual test: start Podman DB + run app; sign in via One Tap; `/books` loads data from Postgres
- [ ] `grep -r spreadsheet_id book_lamp/` returns nothing
- [ ] `grep -r credentials book_lamp/` returns nothing

---

### Step 10 — Update `conftest.py` and test fixtures

**Commit message:** `test: update test fixtures for postgres-era auth`

**`tests/conftest.py`**:
- Remove `GOOGLE_CLIENT_SECRET` from the dummy env vars.
- Keep `GOOGLE_CLIENT_ID` (still needed at import time for the app config).
- Update `authenticated_client` fixture:

```python
@pytest.fixture()
def authenticated_client(client):
    """Client with active session — no JWT flow in tests."""
    with client.session_transaction() as sess:
        sess["user_id"] = 1
        sess["user_email"] = "user@example.com"
        sess["user_name"] = "Test User"
    return client
```

- Update `_storage_reset` fixture if it references `user_email` session key.

**Review checklist:**
- [ ] `poetry run pytest` (full suite) passes
- [ ] No test references `spreadsheet_id` or `credentials` session keys

---

### Step 11 — Delete Sheets, cache, and async-sync files

**Commit message:** `refactor: delete sheets storage, cache, and async-sync infrastructure`

**Delete these files:**
- `book_lamp/services/sheets_storage.py`
- `book_lamp/services/async_sqlite_storage.py`
- `book_lamp/services/sqlite_state_store.py`
- `book_lamp/services/cache.py`
- `tests/test_async_sqlite_storage.py`
- `tests/test_sync_diagnostics.py`

**Remove from `app.py`:**
- `sync_diagnostics` route (`/api/sync/diagnostics`)
- `init-sheets` CLI command
- `backfill-bisac` CLI command referencing Sheets (keep the business logic,
  rewire to use `get_storage()` if still useful)
- `from book_lamp.utils.protobuf_patch import apply_patch` and `apply_patch()`
  call (CVE patch was for `google-api-python-client` which is now removed)

**Remove from `.gitignore`** any Sheets-specific entries (e.g. `token.json`,
`credentials.json`).

**Review checklist:**
- [ ] `poetry run pytest` (full suite) passes
- [ ] `poetry run mypy book_lamp/` passes with no new errors
- [ ] `grep -r "sheets_storage\|async_sqlite\|sqlite_state\|cache\.py\|protobuf_patch" book_lamp/` returns nothing
- [ ] `grep -r "from authlib" book_lamp/` returns nothing
- [ ] `grep -r "google-api-python-client\|google-auth-oauthlib" pyproject.toml` returns nothing

---

### Step 12 — Remove `types-protobuf` and clean up dev deps

**Commit message:** `chore: remove obsolete dev dependencies`

**`pyproject.toml` — remove from dev dependencies:**
```toml
types-protobuf = "^6.32.1.20251210"
pbr = "7.0.1"           # transitive requirement of google-api-python-client
```

Run:
```bash
poetry lock
poetry install
```

**Review checklist:**
- [ ] `poetry install` completes cleanly
- [ ] `poetry run pytest` passes
- [ ] `poetry run mypy book_lamp/` passes

---

### Step 13 — Update `DEPLOYMENT.md` and `.env.example`

**Commit message:** `docs: update deployment guide for postgres/neon`

**`DEPLOYMENT.md`** — rewrite:
- Remove all Google Sheets / Drive setup instructions.
- Remove `GOOGLE_CLIENT_SECRET` from required env vars.
- Add Neon setup: create project → copy connection string → set `DATABASE_URL`.
- Update build command:
  ```bash
  npm ci && npm run build && pip install poetry && poetry install --without dev && poetry run alembic upgrade head
  ```
- Update required env vars table:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Postgres connection string (Neon in prod) |
| `SECRET_KEY` | Flask session key |
| `FLASK_ENV` | Set to `production` |
| `GOOGLE_CLIENT_ID` | Google One Tap JWT audience |
| `LLM_API_KEY` | Optional — AI recommendations |

**`.env.example`** — final state should have no Sheets / OAuth references.

**Review checklist:**
- [ ] `DEPLOYMENT.md` has no mention of "Google Sheets", "Drive", or "spreadsheet"
- [ ] `.env.example` has no `GOOGLE_CLIENT_SECRET`
- [ ] All required env vars are documented

---

### Step 14 — Update `GEMINI.md` and `AGENT_CONTEXT.md`

**Commit message:** `docs: update agent context for postgres architecture`

Update `GEMINI.md`:
- Change "Core Technologies" to reflect `psycopg3`, `alembic`, `Podman`.
- Remove Google API client libraries from the list.
- Update "Google Sheets Integration" section — replace with "PostgreSQL Integration".
- Update "Initial Setup" to reference `podman-compose up -d` and
  `alembic upgrade head`.
- Update "Required Environment Variables" to remove `GOOGLE_CLIENT_SECRET`.

Update `AGENT_CONTEXT.md` with the same corrections (if it duplicates
`GEMINI.md` content).

Update the `book-lamp-development` skill file at
`.agent/skills/book-lamp-development/SKILL.md`:
- Replace the "Working with Google Sheets Storage" section with a
  "Working with PostgresStorage" section describing the adapter pattern,
  connection pool, and migration workflow.

**Review checklist:**
- [ ] `GEMINI.md` accurately reflects the new stack
- [ ] No mention of "Google Sheets" remains in agent-facing docs (unless in the
      data migration section)

---

### Step 15 — Data migration script (run once before prod cutover)

**Commit message:** `chore: add one-off sheets-to-postgres data migration script`

> This step only applies if there is existing data in Google Sheets to preserve.
> It can be skipped for a fresh start.

Create `scripts/migrate_sheets_to_pg.py`:

1. Accept `--spreadsheet-id` and `--user-email` as CLI args.
2. Use `google-auth` (installed as a temporary dev dep, or run in a venv) to
   authenticate with the Sheets API using a service account.
3. Read each tab (Books, ReadingRecords, ReadingList, Settings, Recommendations).
4. Upsert the user row in Postgres.
5. Use `PostgresStorage` to upsert all records.
6. Print a summary of counts inserted / skipped.

Run once:
```bash
DATABASE_URL=<neon-url> poetry run python scripts/migrate_sheets_to_pg.py \
  --spreadsheet-id <id> \
  --user-email <email>
```

**Review checklist:**
- [ ] Script runs without errors against a test spreadsheet
- [ ] Row counts in Postgres match the spreadsheet
- [ ] Running the script twice is idempotent (no duplicates)

---

## Branch and PR Strategy

```
main
└── feat/postgres-migration
    ├── Step 1  (infrastructure files)
    ├── Step 2  (dependencies)
    ├── Step 3  (Alembic + initial migration)
    ├── Step 4  (pg_storage reads)
    ├── Step 5  (pg_storage writes)
    ├── Step 6  (integration tests)
    ├── Step 7  (One Tap backend endpoint)
    ├── Step 8  (One Tap frontend)
    ├── Step 9  (rewire get_storage)       ← main cutover point
    ├── Step 10 (fix test fixtures)
    ├── Step 11 (delete dead code)         ← point of no return
    ├── Step 12 (clean up dev deps)
    ├── Step 13 (update DEPLOYMENT.md)
    ├── Step 14 (update agent docs)
    └── Step 15 (data migration script)
```

Steps 1–8 can be developed and reviewed without affecting the running app
(old `GoogleSheetsStorage` is still in place). Step 9 is the cutover.
Step 11 is the point of no return — after that, Sheets code is gone.

---

## Quick Reference: Files Deleted by This Migration

| File | Step |
|---|---|
| `book_lamp/services/sheets_storage.py` | 11 |
| `book_lamp/services/async_sqlite_storage.py` | 11 |
| `book_lamp/services/sqlite_state_store.py` | 11 |
| `book_lamp/services/cache.py` | 11 |
| `book_lamp/utils/protobuf_patch.py` | 11 |
| `tests/test_async_sqlite_storage.py` | 11 |
| `tests/test_sync_diagnostics.py` | 11 |
| `.cache/` (directory) | 1 (gitignore) |

## Quick Reference: Files Created by This Migration

| File | Step |
|---|---|
| `compose.yaml` | 1 |
| `alembic/` (directory) | 3 |
| `alembic/versions/0001_initial_schema.py` | 3 |
| `book_lamp/services/pg_storage.py` | 4–5 |
| `src/ts/one_tap.ts` | 8 |
| `tests/test_pg_storage.py` | 6 |
| `tests/test_one_tap_auth.py` | 6 |
| `scripts/migrate_sheets_to_pg.py` | 15 |
