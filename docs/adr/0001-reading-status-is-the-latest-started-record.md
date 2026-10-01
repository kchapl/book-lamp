# 1. A Book's Reading Status comes from its latest-started Reading Record

- **Status:** Accepted
- **Date:** 2026-09-28

## Context

A Book gathers Reading Records as it is planned, started, abandoned and restarted.
The catalogue, the dashboard and the reading-date sort each need to know which
record currently represents a Book, and therefore that Book's Reading Status.

That rule had grown four separate implementations, and they did not agree. They
took two different tie-breaks, so for two Reading Records that started on the same
date two of them kept the later-added record and two kept the earlier one.

This is not only untidy. The two storage adapters return records in different
orders — the Postgres adapter orders by `created_at` descending, the in-memory
adapter in insertion order. Any rule that leans on the order records are iterated
gives one answer under test and another in production.

## Decision

The Current Reading Record is the one with the greatest `(start_date, id)`:

- the record that started latest wins;
- when two started on the same date, the one added last wins;
- the answer must not depend on the order the records are iterated in.

A record outside the Reading Statuses gives a Book no Reading Status, so a Book
whose current record is a planned-only entry has none.

## Consequences

- The rule has one home and every caller crosses the same seam, so the catalogue,
  the dashboard and the sort cannot disagree about a Book.
- `id` breaks ties rather than `created_at`, because the in-memory adapter gives
  every Reading Record the same fixed `created_at` and so could never break one.
- A Reading Record whose `book_id` or `id` cannot be read as a positive integer is
  ignored: it can neither be attributed to a Book nor ordered against its
  siblings. The alternative — keeping it and letting the comparison do something
  arbitrary — hides a data problem instead of surfacing it.
- The Reading Log's SQL status filter stays a separate copy of the Reading
  Statuses. It is a query rather than a rule and this decision does not reach it.

## Alternatives considered

- **Let each caller keep its own rule.** Rejected: two of the four copies had
  already drifted apart, and nothing tested the tie-break, so the disagreement was
  invisible until it was looked for.
- **Trust the adapter's ordering and take the first or last record seen.**
  Rejected: the adapters order records differently, so this is the cause of the
  divergence rather than a fix for it.
- **Break ties on `created_at`.** Rejected: the in-memory adapter sets a constant
  `created_at`, so same-day records could not be separated with it.
