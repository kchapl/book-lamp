# 2. A Dewey code never overwrites a real category

- **Status:** Accepted
- **Date:** 2026-10-12

## Context

Every Book carries a category, stored as three columns: `bisac_category`,
`bisac_main_category` and `bisac_sub_category`. Real values are BISAC headings;
older rows, and rows imported from a spreadsheet, carry Dewey decimals instead.
The enrichment backfill exists to replace those with real categories fetched from
the book APIs.

The precedence rule — an incoming value that is not Dewey wins, otherwise the
stored value stands — had been written twice, word for word, in the two storage
adapters' `update_book`, and the "is this value a Dewey code?" test had three
further spellings besides the named `is_dewey_category` in `utils/books.py`. The
three agreed with each other and disagreed with the named one on a value made
only of dots and spaces, which they called a Dewey code and it does not.

The copies did not only disagree about what a Dewey code looks like. The two
adapters disagreed about **whether the rule ran at all**. The in-memory adapter's
`upsert_book` delegates to `update_book`, so an import preserved a stored
category; the Postgres adapter's `add_book`, `upsert_book` and `bulk_import` wrote
the incoming triple unconditionally. The enrichment backfill writes through
`bulk_import`, so on the adapter production uses, a Dewey value from an API
response could overwrite a real category. Nothing tested it: every category
expectation in the suite ran against the in-memory adapter.

## Decision

A Book's category is resolved by one rule, in one place, on every write path:

- an incoming value that is not a Dewey code replaces whatever is stored;
- an incoming value that is absent leaves the stored value standing;
- an incoming Dewey code never replaces a stored category, Dewey or not;
- main and sub come from the incoming value when it supplies them, and are
  otherwise derived from the winning category, so the three columns cannot
  disagree about what the Book is.

The rule owns the whole triple. `add_book`, `update_book`, `upsert_book` and
`bulk_import` all cross the same seam, so no path carries its own spelling, and a
Dewey code means `is_dewey_category`: at least one digit and only digits, dots,
slashes and spaces.

## Consequences

- Precedence is decided in Python, by the same function, on every path. The
  Postgres bulk import reads the stored triple inside its existing transaction and
  resolves before writing, rather than letting SQL decide.
- The rule is defined against Dewey alone. An incoming value that is not Dewey
  wins even when it is not a real category either, so a language code (`en`), a
  page count or a format string can still displace a category. A value made only
  of dots and spaces is the concrete case where the old copies were stricter:
  they called it Dewey and refused it, the named predicate does not, so it now
  displaces a category. Requiring an incoming value to *be* a valid category is a
  deliberate follow-up, not part of this decision.
- A Book can now be re-categorised from the edit form without leaving its old
  major category behind: a caller that supplies no main or sub gets them derived
  from the category that won.
- The Postgres bulk import no longer erases a stored category when the imported
  row carries none. It wrote NULL over all three columns; the in-memory adapter
  had always preserved them, so this brings the two adapters back together.
- This is forward-only. Rows written before this decision may hold a category the
  rule would now refuse, and the value is not recoverable from the database — the
  enrichment backfill re-fetches it. Rows where a Dewey `bisac_category` sits
  beside a real `bisac_main_category` are the shape a partial clobber leaves and
  are detectable read-only; rows clobbered in all three columns cannot be told
  apart from rows that never had a real category.

## Alternatives considered

- **Share only the Dewey predicate and leave precedence in each adapter.**
  Rejected: precedence is what the adapters actually disagreed about, so sharing
  the predicate alone would have left the divergence in place.
- **Let each write path keep its own handling of the triple.** Rejected: it is how
  the Postgres import path came to discard a category that the in-memory path
  preserved.
- **Express the rule in SQL for the bulk import.** Rejected: a second spelling, in
  a language no test on the rule reaches, is the failure this decision removes.
- **Treat any unrecognised value, not just Dewey, as bad.** Rejected for now: it
  would change which categories a bulk import is permitted to store, which is a
  larger behavioural change than this decision sets out to make.
