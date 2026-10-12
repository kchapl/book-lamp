# Book Lamp — Context

The domain language for this project. These are the canonical names: use them in
code, in commits, and in conversation.

## Book

A work in the collection, identified by its ISBN. A Book is the thing a Reading is
about and the thing a Reading List holds.

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
