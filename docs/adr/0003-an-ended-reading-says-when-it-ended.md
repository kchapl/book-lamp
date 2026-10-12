# 3. An ended Reading says when it ended

- **Status:** Accepted
- **Date:** 2026-10-12

## Context

A Reading has two ends: the date it started and the date it ended. The statuses
that say a Reading has stopped — Completed and Abandoned — therefore describe a
Reading with a known finish, and the Reading Log renders the second end as
`end_date || 'Present'` on the assumption that one exists when the status says so.

Nothing enforced it, and nothing could have. The create route required a status
and a start date and then wrote whatever `end_date` it was handed, so a Completed
Reading with no end date was accepted. The Book Detail form was worse: it posted
`{status, rating}` — no dates at all — so every "Add reading" came back 400 and
`handleAddRecord` swallowed the failure into `console.error`. The form had never
worked, and the tests pinned the 400 rather than the form. Reading ends were
never recorded from the app at all.

The rule was not absent everywhere; it was present once, in the Libib importer,
which filled a Completed row's end date from its start date. It did not do the
same for an Abandoned row, so the one place with an opinion about starts and ends
disagreed with itself about which statuses end a Reading.

## Decision

A Reading whose Reading Status ends it must carry an end date. One rule, in
`book_lamp/utils/readings.py`:

- `ENDING_STATUSES` is Completed and Abandoned;
- a write giving a Reading one of those statuses without an end date is refused.

The rule is enforced where every writer meets, not in the routes: `add_reading`,
`update_reading` and `bulk_import` on both storage adapters raise
`ReadingEndsWithoutADate`, and the Reading routes map that to 400. The Book Detail
form gains a start and an end control, the end defaulting to today when the status
ends and cleared when it does not, so a reader is never blocked by it. The
importer fills an ending row's end date from its start date for every ending
status, not only Completed.

## Consequences

- Existing rows are left alone. A Reading completed before this decision has no
  end date, shows "Present" in the log, and stays that way: the date was never
  captured, so there is nothing to backfill and guessing would invent history.
- The form is repaired as a side effect, because a payload without a start date
  was already refused and the form sent one without either.
- Both adapters now refuse the same writes. Previously only Postgres was reached
  by the tested routes, so a rule enforced in one adapter and not the other would
  have been invisible.
- The storage seam is the enforcement point, so a writer that does not go through
  the Flask routes — the MCP server is one — inherits the rule rather than
  bypassing it.
- The importer can no longer import a row it cannot date. A Completed or
  Abandoned row with no dates at all is dated today by the importer's existing
  fallback, so the import cannot fail on a row it would previously have written
  open-ended.

## Alternatives considered

- **Default silently to today in the API.** Rejected: the write path is shared
  with the importer and the MCP tools, and a silent default there would record
  today as the day a Reading from 2019 ended. A client that means "today" can say
  so; the SPA does.
- **Validate in the UI only.** Rejected: it is what the app effectively had, and it
  is why the rule was true in the importer and false in the API.
- **Require an end date for Completed only.** Rejected: an Abandoned Reading has
  also stopped, and the importer's own Completed-only fallback was the split this
  decision exists to close.
- **Backfill existing Completed Readings from their start date.** Rejected: it
  would record a one-day Reading for every historical book and make the log look
  more complete than the data is.
