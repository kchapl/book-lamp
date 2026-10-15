# 5. A Book's authors come from the links

- **Status:** Accepted
- **Date:** 2026-10-14

## Context

A Book's authors were stored twice: as one string in `books.author`, and as rows
in `authors` joined through `book_authors`. The string was the input — every write
path derived the rows from it, `_update_book_authors` calling `split_authors` on
the same value it wrote to the column — so the rows were the copy, not the
original. Nothing kept the two in step, and they did not agree:

- The reading list read the whole string; book detail and lookup read the first
  linked author only. A Book with three authors therefore named one of them on its
  detail page and all three in the reading list, from the same row.
- `book_authors` had no order. Its primary key is `(book_id, author_id)`, and the
  three `array_agg(a.name)` reads carried no `ORDER BY`, so the order a Book's
  authors appeared in was unspecified, and in practice followed `author_id`.

The copy is also lossy in a way that cannot be undone. In the 270 Books in
production, two strings do not mean what the splitter read them as: one is a
single name containing " & ", and one is a "Last, First" name beside a plain one.
Re-splitting cannot recover either, because the four other Books whose three
authors really are comma-separated have the same shape as the second.

## Decision

A Book's authors are its links, and the string is derived from them.

- `book_authors.position` holds the order, written by every path that writes links
  (migration 0006). Reads join the names in that order and nowhere else.
- The two Books whose strings the splitter mangled are corrected from the string,
  per Book, in a migration — not by re-running a rule that would reproduce the
  defect (0007).
- `books.author` is dropped (0008), one release after the application stopped
  writing it, because the instance replaced during a rollout still writes it.

`author` stays in the API contract as the display string, derived as
`", ".join(authors)`, so callers that name an author in one field — the reading
list, the MCP server's book payload, the recommendation prompt — are unchanged.

## Consequences

- Both adapters present a Book's authors the same way, and every page agrees about
  them. The endpoints that disagree today (`get_book_by_id` and `get_book_by_isbn`
  returning only the first author) no longer can.
- The order survives the round trip through storage. It did not before, and
  `position` is what says so: a Book's authors are listed in the order they were
  entered, not in the order authors happen to have been created.
- Dropping the column is proven lossless before it runs: migration 0008 refuses
  while any Book's links, in order, do not join back to that Book's string, and
  names the Books that fail. Of the 270 Books in production, one failed it (the
  " & " one, which 0007 repairs in the same run); every other Book's links
  reproduce its string, so the column held no text they cannot.
- A downgrade rebuilds the string from the links, so it returns the names but not
  the original separators: a Book entered as "A and B" comes back as "A, B". The
  two Books 0007 repaired are the exception — that repair reads the string, so
  what it writes joins back to it exactly.
- The write path still takes authors as one string and splits it, so a display
  string that goes out to a form and comes back in can be split differently than
  it was joined: "Sutherland, John, John Crace" is two authors' worth of links and
  three names' worth of commas. Submitting a list instead of a string is the fix,
  and it is not part of this decision.
- Author rows that no Book references stay (`authors` has always kept them; 41 did
  before this change). The four halves the mangled split invented are removed, as
  they named no Book and no person.
- The splitter reads a single comma as "Last, First", so a string of two plain
  names became one author row — "David Edmonds, John Eidinow" is one author in
  `authors`, and its author page is titled with both. Those rows are not text
  lossy (their one link joins back to the string), and this decision leaves them
  as they are: telling that shape from a real "Last, First" name is a splitter
  problem, and a migration that guessed at it would rename people.

## Alternatives considered

- **Keep both, and fix the read paths to agree.** Rejected: agreement is a rule
  that has to be re-established on every write, which is what failed here. The two
  values had already drifted in production.
- **Keep the string and drop the links.** Rejected: the links are what
  `/api/author/<slug>` and `/api/publisher/<slug>` are built on, and they are what
  makes an author a thing with a page.
- **Re-derive every Book's links from its string before dropping the column.**
  Rejected as the repair: for the 268 Books that agree it is a no-op, and for the
  two that do not it reproduces the defect exactly. The repair has to read the
  string and record what it means, not what the rule says.
- **Teach the splitter to read "Last, First" beside a plain name.** Rejected: it
  cannot be told apart from "Author A, Author B, Author C" — four Books in
  production have that shape and mean three authors.
- **Add the order column without a default in 0006.** Rejected: the previous
  release must be able to write a link while a release rolls out, and it writes
  none. 0008 renumbers such rows from `author_id` and then makes `position`
  required.
