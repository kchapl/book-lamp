# Deployment Guide

## Render Deployment

### Required Environment Variables

Set the following environment variables in your Render web service:

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string from Neon |
| `SECRET_KEY` | Flask session secret (generate with `python -c "import secrets; print(secrets.token_hex(32))"` ) |
| `FLASK_DEBUG` | Set to `False` for production deployment (set to `True` for development debugging - doesn't affect authentication) |
| `GOOGLE_CLIENT_ID` | Google One Tap Client ID (optional, for login) |
| `LLM_API_KEY` | OpenAI API key (optional, for AI features) |

### Neon Database Setup

1. Create a Neon account at https://neon.tech
2. Create a new project
3. Copy the connection string (starts with `postgresql://`)
4. Set `DATABASE_URL` in Render environment variables
5. Run `alembic upgrade head` to initialize the database schema

### Google One Tap Setup (Optional)

If you want Google login functionality:
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create OAuth 2.0 Client ID
3. Add your Render URL to authorized origins
4. Set `GOOGLE_CLIENT_ID` in environment variables

### Security Notes

- Database credentials are read from environment variables at runtime
- This follows the [12-factor app](https://12factor.net/config) methodology
- Never commit `.env` file to version control

### Build Configuration

**Build Command:**
```bash
npm ci && npm run build && uv sync --no-dev && uv run --no-dev alembic upgrade head
```

**Start Command:**
```bash
uv run --no-dev gunicorn book_lamp.app:app
```

Every `uv run` passes `--no-dev`, the start command included. A bare `uv run`
re-syncs the environment first, and the default `dev` group is part of what it
syncs: without the flag the service downloads pytest, black, mypy and ruff
before it serves anything. A sleeping service pays that on every wake.

### Schema changes that span two releases

The build command runs `alembic upgrade head`, so a migration lands before the
instance written for it starts — while the instance it replaces is still serving.
A release that removes a column the running application still writes therefore
cannot go out in one step.

`books.author` is one: the application wrote it until migration `0006`, and `0008`
drops it. Deploy in two steps.

1. This release, with the application that stopped writing the column: `0006`
   gives `book_authors` the order a Book's authors are listed in, and `0007`
   repairs the two Books whose stored author strings the splitter had mangled.
2. The next release: `0008` drops the column.

`0008` refuses to run while any Book's links cannot reproduce its author string,
and names the Books that fail, so a Book needing attention stops the deploy
instead of losing its author. See
`docs/adr/0005-a-books-authors-come-from-the-links.md`.

### First-Time Setup

After deployment:
1. Visit your app URL
2. The app should work immediately with PostgreSQL storage
3. If using Google One Tap, you can click the Google login button
4. Start adding books via the UI

### Troubleshooting

**Database Connection Errors:**
1. Verify `DATABASE_URL` is set correctly in Render environment variables
2. Ensure your Neon project is active
3. Check that `alembic upgrade head` ran successfully during build

**Google One Tap Issues:**
1. Verify `GOOGLE_CLIENT_ID` is set in environment variables
2. Ensure your Render URL is added to authorized origins in Google Cloud Console
3. Check browser console for JavaScript errors

**General Issues:**
1. Check Render build logs for any errors during `alembic upgrade head`
2. Verify all required environment variables are set
3. Check application logs for connection errors

**Build fails with `version solving failed`:** the service is installing with
Poetry. Poetry cannot resolve this project: `requires-python` has no upper
bound, and `jsonschema-path` — which arrives with `fastmcp` in the `mcp` extra —
caps Python at `<4.0.0`, so Poetry rejects the combination while uv resolves it
from `uv.lock`. The build and start commands above must be the ones the service
uses; a command that leaves out `alembic upgrade head` also deploys code ahead
of the schema, which migration `0004` needs (it renames `reading_records` to
`readings`).

Set `UV_VERSION` to pin the same uv that wrote `uv.lock`; Render's default may
be older.

## MCP Service (Gemini custom app)

A second Render service serves the MCP protocol, so Gemini's custom apps can read
the reading history. See `docs/adr/0004-an-mcp-server-reads-as-one-reader.md` for
why it is a separate service, why Google authenticates it, and why its tools are
read-only.

### Service configuration

Create a second Render web service from this same repository. It shares the
application's `DATABASE_URL` but nothing else.

| Setting | Value |
|---------|-------|
| Build Command | `uv sync --no-dev --extra mcp` |
| Start Command | `uv run --no-dev --extra mcp python -m book_lamp.mcp_server` |
| Health check path | `/.well-known/oauth-protected-resource/mcp` |

`--extra mcp` is what installs `fastmcp`. The Flask service does not pass it, so
the extra never reaches that deploy.

### Environment variables

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | The same PostgreSQL connection string the app uses |
| `BOOK_LAMP_USER_EMAIL` | The one reader this server serves. The verified Google address must equal it, and the address must already be a Book Lamp user |
| `BOOK_LAMP_MCP_CLIENT_ID` | Client ID of the MCP OAuth client (below) |
| `BOOK_LAMP_MCP_CLIENT_SECRET` | Client secret of the same client |
| `BOOK_LAMP_MCP_BASE_URL` | This service's own public URL, e.g. `https://book-lamp-mcp.onrender.com`. It must match the redirect URI registered below exactly |

`PORT` is provided by Render. There is no unauthenticated mode: a missing variable
stops the service rather than serving somebody.

### Google OAuth client

The MCP service authenticates readers through Google, so it needs its own OAuth
client — the app's existing `GOOGLE_CLIENT_ID` cannot be reused, because One Tap
needs neither a secret nor a redirect URI and this needs both.

1. In [Google Cloud Console](https://console.cloud.google.com/), under **APIs &
   Services → OAuth consent screen**, configure the consent screen. Add only
   `openid` and `.../auth/userinfo.email`; both are non-sensitive, so publishing
   needs no verification review.
2. Under **Credentials**, create an OAuth client of type **Web application**.
3. Add an **Authorized redirect URI** of `<BOOK_LAMP_MCP_BASE_URL>/auth/callback`.
   It must match exactly.
4. Set the **Publishing status** to **Production**. Left in *Testing*, Google
   expires the refresh token after 7 days and the reader has to consent again
   every week.
5. Copy the client ID (`...apps.googleusercontent.com`) and secret (`GOCSPX-...`)
   into the two environment variables above.

### Connecting Gemini

In the Gemini web app: **Settings → Connected Apps → Custom apps**, then paste
`<BOOK_LAMP_MCP_BASE_URL>/mcp`. Sign in with the account named by
`BOOK_LAMP_USER_EMAIL`. Custom apps can only be added from the web app, and only
by an eligible account (personal Google account, 18+, US, English, Keep Activity
on).

Step by step, with example questions and the eligibility list:
`docs/mcp-service.md`.

### Troubleshooting

**`RuntimeError: ... must be set`** — the service refused to start because a
setting is missing. That is intended; there is no fallback reader.

**`403 NotTheReader` in the logs** — the token's address is not
`BOOK_LAMP_USER_EMAIL`, or that address has never signed in to the app, so no
`users` row exists for it. Sign in to Book Lamp once with that account.

**Gemini asks for consent again after every deploy** — client registrations and
tokens are held in memory. Persisting them needs a `client_storage` backend (Redis)
and a `jwt_signing_key`; it is deliberately deferred in ADR-0004.
