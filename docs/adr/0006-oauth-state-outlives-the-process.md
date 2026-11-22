# 6. OAuth state outlives the process

- **Status:** Accepted
- **Date:** 2026-11-22

## Context

The MCP service on Render's free plan has an ephemeral filesystem and spins down
after 15 minutes without traffic. FastMCP's Google provider keeps dynamic client
registrations and upstream Google tokens in a file store under its data
directory when no `client_storage` is supplied. ADR-0004 described that state as
held in memory; it was not, but the effect on Render was the same — a deploy,
restart or spin-down lost it.

Gemini registers itself once and then reuses that client ID. When the next
instance did not recognise it, `/authorize` served **Client Not Registered** and
the tool call failed. Removing and re-adding the custom app in Gemini restored
service until the next deployment or idle shutdown.

## Decision

Persist FastMCP's OAuth state in the application's existing Neon Postgres.

- **Store**: `PostgreSQLStore` from `py-key-value-aio`, in a table named
  `mcp_oauth_state` that the MCP service owns. It creates the table on first use,
  so there is no Alembic migration and no shared-schema release.
- **Connections**: a dedicated asyncpg pool of one to two connections. Its
  statement cache is disabled because `DATABASE_URL` is Neon's pooled PgBouncer
  endpoint, and named prepared statements do not survive transaction pooling.
- **Encryption**: `FernetEncryptionWrapper` encrypts values at rest. The Fernet
  key is derived deterministically from the existing
  `BOOK_LAMP_MCP_CLIENT_SECRET`, so there is no new required environment
  variable: the same secret reopens the store after a restart, and a rotated
  secret cannot read the old rows.
- **Startup**: `main()` builds the store and passes it to `auth_provider()`, and
  the FastMCP lifespan awaits `store.setup()` before the port opens. A database
  that cannot be reached fails startup instead of serving a healthy-looking
  service that refuses every OAuth request.
- **Dependencies**: `asyncpg` belongs to the `mcp` extra only. The Flask deploy
  does not install it and its psycopg pool is unchanged.

## Consequences

- A registration and its upstream token survive a deploy, a restart and a free
  plan's idle spin-down. Gemini does not need to be removed and re-added after
  every release.
- The store is one more table and one more small pool in the same database the
  app already uses. It needs no Redis, persistent disk or second managed
  service.
- Losing the database, or changing the Google client secret without a migration,
  still loses the state. That is accepted: the old rows cannot be decrypted with
  a different secret, and the recovery is the same remove-and-re-add.
- The service now refuses to start when `DATABASE_URL` is missing or unreachable.
  That matches the existing rule that a missing reader setting stops the server
  rather than defaulting.

## Alternatives considered

- **Redis or another managed key-value service.** Rejected: a second paid
  dependency for a single-reader application that already has Postgres.
- **A persistent disk on Render.** Rejected: not available on the free plan, and
  it would make the OAuth state a second source of truth outside the database.
- **Keeping the file store and accepting re-registration.** Rejected: it is the
  bug. Every deploy made Gemini's connected app fail until a human intervened.
- **A new encryption secret.** Rejected: the Google client secret is already
  high-entropy and required, so deriving from it adds no configuration and no
  new way to start with a mismatched key.
