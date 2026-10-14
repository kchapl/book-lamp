# book-lamp

A personal reading history tracker.

## Setup

This project uses [mise](https://mise.jdx.dev/) to manage tool versions (Python, Node, uv).

Two scripts cover the whole of the local setup:

```bash
scripts/setup   # once, after cloning
scripts/start   # every time you want to run the app
```

**`scripts/setup`** installs the pinned toolchain with `mise install`, installs the
Python and Node dependencies, and creates a `.env` from `.env.example` if one is
missing. It is unprivileged: when it cannot find podman-compose it prints the
command to install podman and podman-compose instead of running it, so you decide
when to use `sudo`. Run it once after cloning; re-running is safe.

**`scripts/start`** brings up the PostgreSQL container, waits for it to accept
connections, applies the Alembic migrations, builds the React SPA and serves
everything through the Flask development server on <http://127.0.0.1:5000>.
`HOST` and `PORT` override the bind address and port. Containers and volumes are
reused between runs, so the database keeps its data.

On podman hosts whose kernel cannot program the compose bridge (nested containers
and other minimal sandboxes), the database runs on the host network instead; see
`compose.hostnet.yaml`.

### Manual steps

1. Install tools: `mise install`
2. Install backend dependencies: `uv sync`
3. Install frontend dependencies: `npm install`
4. Build the React SPA: `npm run build`
5. Create a `.env` file with the required variables:
   ```
   FLASK_DEBUG=True
   GOOGLE_CLIENT_ID=your_oauth_client_id
   SECRET_KEY=your_secret_key
   ```
6. Run the app: `uv run flask --app book_lamp.app run`

### Signing in locally

Book Lamp signs readers in with Google One Tap, so a real OAuth client ID is
required — the app has no local username/password or dev-login path.

1. In the [Google Cloud console](https://console.cloud.google.com/apis/credentials),
   create an OAuth 2.0 client of type **Web application**.
2. Add `http://localhost:5000` (and `http://127.0.0.1:5000`) under
   **Authorized JavaScript origins**. No redirect URI is needed.
3. Copy the client ID (it ends in `.apps.googleusercontent.com`) into
   `GOOGLE_CLIENT_ID` in `.env` and restart the app.

If `GOOGLE_CLIENT_ID` is left at the placeholder, the sign-in button is not
rendered and `POST /api/auth/google` answers `503` explaining that sign-in is
unconfigured, rather than a confusing `401`.

## Asking Gemini about your reading

Book Lamp ships a read-only MCP service, so the Gemini apps can answer questions
about the Reading Log — "what did I finish this year?" — straight from the same
storage the app reads.

See **[docs/mcp-service.md](docs/mcp-service.md)** for attaching it to Gemini as
a custom app and the questions it is good for, and `DEPLOYMENT.md` → "MCP
Service (Gemini custom app)" for deploying it.

## Testing

Run backend unit tests:
```bash
uv run pytest
```

Run frontend unit tests:
```bash
npm test
```

