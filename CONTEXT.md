# Book Lamp — Context

The domain language for this project. These are the canonical names: use them in
code, in commits, and in conversation.

## Book

A work in the collection, identified by its ISBN. A Book is the thing a Reading
Record is about and the thing a Reading List holds.

## Reading Record

One attempt at reading a Book, with a Reading Status and the dates it started and
ended. A Book gathers several Reading Records over its life: it can be planned,
started, abandoned, and started again.

## Reading List

The queue of Books the reader intends to read next, in the reader's chosen order.

## Reading Log

The reader's history of Reading Records: what has been started, completed or
abandoned. A Book with no Reading Status does not appear in the Reading Log.

## Reading Status

The status of a Book's Current Reading Record — what the reader is currently
doing with the Book. A Book has at most one Reading Status at a time.

## Reading Statuses

The three statuses that give a Book a Reading Status: **In Progress**,
**Completed** and **Abandoned**. A Book in any other state — on the Reading List,
or not yet looked at — has no Reading Status.

## Current Reading Record

The Reading Record that currently represents a Book, and whose status is that
Book's Reading Status. It is the record that started latest; when two started on
the same date, the one added last.
