# 4. An MCP server reads as one reader, and Google says who

- **Status:** Accepted
- **Date:** 2026-10-12

## Context

The point of this work is to tell Gemini about a Reading in a sentence — "finished
Project Hail Mary yesterday, four stars" — rather than clicking through the form.
That means an MCP server Gemini can reach.

Three facts about that surface shaped everything else. Custom apps are added in
the Gemini web app by pasting an **MCP server URL**, so the endpoint has to be
public HTTPS and reachable from Google's infrastructure; nothing local will do.
The transport must be **Streamable HTTP** — the legacy SSE transport is refused.
And authentication is either **none** or **OAuth 2.0**: there is no
paste-an-API-key option, so a bearer token in a header is not available.

Two facts about this repository shaped the rest. The MCP Python SDK's HTTP
transports are ASGI — they depend on `starlette`, `uvicorn` and `sse-starlette` —
and this application is Flask, which is WSGI. The endpoint therefore cannot be a
route in the app, however much it would have been convenient for it to be one.
And Google does not implement **Dynamic Client Registration**, which is what MCP
clients expect to find: they register themselves and get credentials without a
human configuring anything.

## Decision

A second service, from this repository, serving the MCP protocol over Streamable
HTTP and sharing the application's PostgreSQL database.

- **Layout**: `book_lamp/mcp_server.py`, with `fastmcp` as an optional extra
  (`mcp`) so the Flask deploy does not install it. Deployment is a second Render
  service with its own start command, not a route in the existing one.
- **Authentication**: delegated to Google through FastMCP's `GoogleProvider`,
  which is an OAuth *proxy*. It owns `/register`, `/authorize`, `/token` and the
  `/.well-known/` documents, so a client can discover and register as MCP expects,
  and it forwards the actual sign-in to Google. The server never sees a password
  and implements no user interface of its own beyond the consent step.
- **Identity**: the server reads as **one configured reader**,
  `BOOK_LAMP_USER_EMAIL`. Two things must hold and neither is assumed: Google
  signed the token, and the address it carries is that reader. The address must
  already be a Book Lamp user; the lookup is read-only, so the server cannot
  create an account by being asked to.
- **Scope**: the tools are read-only — search Books, read one Book with its
  Readings, read the Reading Log. The endpoint has no write path at all.

## Consequences

- There is no unauthenticated mode and no default reader. A missing setting or an
  unreachable identity stops the server rather than serving somebody; the
  reader's email is both the allowlist and the identity, so it cannot drift from
  the account it reads.
- Because the endpoint writes nothing, publishing its URL costs disclosure of a
  reading history, not damage to it. That is what made it acceptable to build the
  read path first and prove the transport with it.
- Client registrations and tokens are held in memory, so a deploy makes Gemini
  register and consent again. This is a deliberate deferral: the alternative is a
  Redis-backed store, which is a second managed service for a single-reader
  application.
- The requested scopes (`openid`, `userinfo.email`) are non-sensitive, so the
  Google consent screen can be published to Production without going through
  Google's verification review. That matters more than it looks: an app left in
  *Testing* has its refresh tokens expire every 7 days.
- The rename from `reading_records` to `readings` had to land first, because these
  tools are built on the same storage seam and would otherwise have been written
  against the retired vocabulary.
- Two services share one database. Neither deploy blocks the other, at the cost
  of the MCP service needing its own start command kept in step with this repo.

## Alternatives considered

- **A stdio server under Gemini CLI, on the reader's machine.** Rejected for now,
  not on merit: it needs no hosting and no authentication at all, and the tools
  would be identical. But the sentence that started this work is one a reader says
  to the app they already have on their phone, and a stdio server is reached from
  a terminal. It remains the fallback if the hosted path proves unreliable.
- **No authentication, on a long random path.** Rejected: the URL is then the only
  secret, it is stored by Google, and the read path alone would expose a whole
  reading history to anyone who learned it.
- **Implementing an authorization server ourselves.** Rejected: it is a consent
  page, a token endpoint, PKCE, refresh and revocation — a week of security-critical
  surface for one reader, to end up somewhere Google could take us for nothing.
- **A separate project with its own lock file.** Rejected: the service imports the
  storage seam, the reading rules and the search, so splitting projects would mean
  a path dependency and two lock files to keep in step for a boundary an optional
  extra already gives us.
- **Mounting the ASGI app inside the Flask service.** Rejected: one deploy, but two
  runtimes in one process, where a WSGI problem takes the MCP endpoint down with it.
- **Write tools from the start.** Rejected: the write path did not exist yet on any
  surface (see ADR-0003), and shipping writes behind an untested transport would
  have meant debugging two new things at once.
