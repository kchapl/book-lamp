# Book Lamp — Context

The domain language for this project. These are the canonical names: use them in
code, in commits, and in conversation.

Book Lamp is one reader's reading log. It records Readings of Books — what was
started, finished, abandoned and thought of — not copies the reader owns. The
museum language (the reading room, exhibits, accession lines) is how that log is
presented; see `DESIGN.md`. It is not a claim to ownership.

## Book

A work the reader has recorded a Reading of, is reading, or means to read,
identified by its ISBN. A Book is the thing a Reading is about and the thing a
Reading List holds. Logging a Book says nothing about owning a copy of it.

## Author

A person who wrote a Book. A Book has at least one Author, and the order they are
credited in is the order the source gave them. An Author is identified by name:
two spellings of a name are two Authors, each with its own page.

## Reading

One attempt at reading a Book. A Reading begins and ends, and has a Reading
Status: the dates it started and ended are its two ends. A Book gathers several
Readings over its life: it can be planned, started, abandoned, and started again.

## Reading List

The queue of Books the reader intends to read next, in the reader's chosen order.

## Reading Log

The reader's history of Readings: what has been started, completed or abandoned. A
Book with no Reading Status does not appear in the Reading Log.

## Reading Status

The status of a Book's Current Reading — what the reader is currently doing with
the Book. A Book has at most one Reading Status at a time.

## Reading Statuses

The three statuses that give a Book a Reading Status: **In Progress**, **Completed**
and **Abandoned**. A Book in any other state — on the Reading List, or not yet
looked at — has no Reading Status.

## Current Reading

The Reading that currently represents a Book, and whose status is that Book's
Reading Status. It is the Reading that started latest; when two started on the same
date, the one added last.
