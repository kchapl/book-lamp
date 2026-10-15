# Book Lamp through Gemini

Book Lamp's MCP service lets the Gemini apps read a reading history directly: ask
"what did I finish this year?" in a chat and get an answer from Book Lamp's own
storage, without a form and without an export. It is the same data the app
shows, read by a model.

The service is read-only. It can answer questions about the Reading Log, one
Book, or the collection; it cannot change anything. That is deliberate — see
`docs/adr/0004-an-mcp-server-reads-as-one-reader.md` for why the read path came
first and the write path is still deferred.

This document is the reader's guide: what to set up, how to attach it to Gemini,
and what it is good for. `DEPLOYMENT.md` is the operator's reference — service
settings, build commands and the Google OAuth client.

## What you need first

1. **The MCP service deployed somewhere with a public HTTPS URL.** Gemini reaches
   MCP servers over Streamable HTTP from Google's infrastructure, so
   `http://localhost:8000` can never work. `DEPLOYMENT.md` → "MCP Service (Gemini
   custom app)" has the build command, start command, environment variables and
   the Google OAuth client to create. A tunnel in front of a local server is fine
   for a trial, but `BOOK_LAMP_MCP_BASE_URL` and the OAuth client's redirect URI
   must both be the tunnel's URL, exactly.
2. **An account already in Book Lamp.** The server reads as one reader,
   `BOOK_LAMP_USER_EMAIL`, and the verified Google address has to equal it. That
   address must also have signed in to Book Lamp once, because the lookup that
   finds the reader is read-only: the server cannot create an account by being
   asked to. Sign in to the app with the account you intend to use before you
   point Gemini at the server.
3. **A Gemini account that can add custom apps.** Per Google's help for custom
   apps (<https://support.google.com/gemini/answer/17209137>): a **personal**
   Google account (not work or school), 18 or over, in the **US**, in **English**,
   with **Keep Activity on**. When that setting is off, custom apps are
   unavailable and there is nothing to fix on your side.

## Attaching it to Gemini

Custom apps can only be *added* from the web app. Once connected, the app works
in both the Gemini web app and the Gemini mobile app.

1. On a computer, go to <https://gemini.google.com>.
2. At the bottom, **Settings & help** → **Connected Apps**.
3. Under **Custom apps** — labelled **Custom apps for Spark** on some screens —
   click **Add a custom app** (the field reads "Add a custom app link to get
   started" before your first one).
4. Paste your MCP server URL — `<BOOK_LAMP_MCP_BASE_URL>/mcp`, for example
   `https://book-lamp-mcp.onrender.com/mcp`.
5. Click **Next** and follow the sign-in prompt, signing in as the account named
   by `BOOK_LAMP_USER_EMAIL`.

Leave **Advanced features** alone. It is the fallback for servers that do not
support Dynamic Client Registration; Book Lamp's does, because FastMCP's Google
provider serves `/register` and the `/.well-known/` documents itself. So Gemini
registers its own credentials and there is no client ID or secret to paste here.

### Checking it worked

In a chat, type `@` and pick Book Lamp to point a prompt at it explicitly, then
ask the server what it can do. A good first question:

> Which Book Lamp tools can you see, and what does each one take?

If it names `search_books`, `get_book` and `get_reading_log`, the transport, the
OAuth handshake and the reader check all worked. Then try a real one:

> What did I finish reading this year?

That path has been walked end to end: Book Lamp's own service is connected as a
custom app in the **consumer** Gemini app and answers questions in a chat
(October 2026). Custom apps are not limited to Spark.

## What the server can answer

Three tools, all read-only.

| Tool | Takes | Gives back |
| --- | --- | --- |
| `search_books` | `query` — free text | Up to 10 closest Books: ISBN, title, author, publication year, series |
| `get_book` | `identifier` — an ISBN, or a title naming exactly one Book | That Book — plus category and page count — and every Reading of it, newest first |
| `get_reading_log` | `status`, `min_rating`, `year` — all optional | The reader's Readings, newest first: title, author, status, start and end dates, rating |

A few behaviours worth knowing, because they shape what you can ask:

- **Readings, not Books, make the log.** A Book only appears in the Reading Log
  once it has a Reading with a status of `In Progress`, `Completed` or
  `Abandoned`. A Book sitting on the Reading List has no Reading Status and is
  therefore not in the log.
- **Ratings are 1–5, and unrated means 0.** So "everything I rated 4 or more"
  quietly leaves out Readings you finished without rating. Ask for it that way
  and you get exactly that.
- **A year means the year a Reading ended** — or, for one still open, the year it
  started.
- **Search is broad.** It matches title, author, ISBN, series, publisher,
  category, publication year, and the Reading's own fields (status, rating,
  dates). It returns identity fields only, though, so use the Reading Log when
  you want statuses and ratings back.
- **A title has to name exactly one Book.** `get_book` with "Dune" refuses when
  several Books match, and hands back the ISBNs to choose from. Naming the author
  or passing the ISBN avoids the round trip.

## Questions worth asking

**Recalling what you read**

- What did I finish in 2026?
- What did I rate five stars?
- What did I abandon last year, and what did I rate it?
- What am I reading right now, and when did each one start?
- How long has *Dune* been in progress?
- Did I read *The Little Prince* more than once? — `get_book` returns every
  Reading of a Book, so re-readings are visible.

**Working it out**

- Read my year back to me as a few paragraphs I can edit into a wrap-up post.
- What have I abandoned, and do those Books have anything in common?
- Which of my five-star Reads should I revisit?
- I'm partway through a series — what should I pick up next? — worth knowing that
  the series name is attached to each Book, not to a series record, so this takes
  a search plus a `get_book` per candidate.
- How many pages did I read this year? — answerable from page counts, but it is
  one `get_book` per finished Book, so a big year takes a while.

**On a schedule, in Gemini Spark**

Spark runs tasks rather than answering in a chat, which suits Book Lamp's
data — it changes at most daily, when you log something.

- Every Sunday, tell me what I finished this week.
- On the first of the month, summarise the month's reading and what is still
  open.
- Keep a running note of everything I rate five stars.

## What it cannot do

- **Record anything.** "I finished *Project Hail Mary* yesterday, four stars"
  will not be logged. There is no write path at all, so a mistaken call cannot
  damage the Reading Log — but adding Readings still means using the app
  (ADR-0004).
- **Serve anyone but the configured reader.** Any other address gets a refusal.
- **Show the Reading List.** The queue and the order you put it in are not
  exposed. Search can confirm a Book is in the collection, but there is no way to
  list what is on the shelf.
- **Show the app's recommendations.** They are computed for the Dashboard and are
  not a tool.
- **Give you covers, notes or descriptions.** Only the fields in the table above
  come back.
- **Hand back more than 10 search matches** at once.

## When it misbehaves

**`403 NotTheReader` in the service logs.** The signed-in address is not
`BOOK_LAMP_USER_EMAIL`, or it is but that account has never signed in to Book
Lamp, so there is no reader to read as. Sign in to the app once with it.

**Nothing appears under Custom apps.** Check the eligibility list above — a work
or school account, location, language, or Keep Activity will do it. That list is
the whole of Google's rules and the feature is live in the consumer app, so a
missing section means one of them is unmet rather than something to wait for. The
heading also varies: **Custom apps** in Google's help, **Custom apps for Spark**
on some screens.

**Gemini asks for consent again after every deploy.** Client registrations and
tokens are held in memory, so a deploy makes Gemini register and consent again.
Deliberate, and deferred in ADR-0004.

**The service refuses to start.** A missing environment variable — intended.
There is no unauthenticated mode and no default reader, so it stops rather than
serving somebody.

## What Gemini sees, honestly

Gemini may share information from the conversation and from other sources it can
reach — connected apps, Personal Intelligence, skills and tasks — with the MCP
server, and the server answers only the one configured reader. The endpoint is
read-only, so publishing its URL costs disclosure of a reading history rather
than any risk of damage to it, which is the trade ADR-0004 accepted. Treat the
URL as a secret anyway, and disconnect the app in Gemini's Connected Apps
settings when you are done with it.

## Where the rest is written down

- `docs/adr/0004-an-mcp-server-reads-as-one-reader.md` — why a second service,
  why Google authenticates it, and why the tools are read-only.
- `DEPLOYMENT.md` → "MCP Service (Gemini custom app)" — service configuration,
  environment variables, the Google OAuth client, and the operator's
  troubleshooting.
- `book_lamp/mcp_server.py` — the server, and the docstrings that are the tools'
  descriptions to a model.
- `CONTEXT.md` — the domain language these tools speak in.
