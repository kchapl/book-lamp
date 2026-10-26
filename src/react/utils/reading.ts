/**
 * The payload the readings API accepts for a new Reading.
 *
 * The route requires a start date, and a Reading that has ended must carry an
 * end date as well (see `book_lamp/utils/readings.py`). The decision lives here
 * rather than inline in the page so it can be tested directly: jsdom cannot
 * drive a Material Web select, so a page-level test only ever reaches the status
 * the form starts in.
 */
import type { Reading } from '../types';
import { endsReading } from './status';

export interface ReadingDraft {
    status: string;
    start_date: string;
    end_date: string;
    rating: number;
}

export function readingPayload(draft: ReadingDraft): Partial<Reading> {
    return {
        status: draft.status,
        start_date: draft.start_date,
        end_date: endsReading(draft.status) ? draft.end_date : undefined,
        rating: draft.rating,
    };
}

/**
 * Move a draft to another status, keeping its end date honest.
 *
 * Ending a Reading defaults its end date to today; starting one clears it, so an
 * open Reading never claims to have finished (see `book_lamp/utils/readings.py`).
 * `today` is a parameter rather than a call to `todayIso` so the rule can be
 * tested without the clock.
 */
export function draftWithStatus(draft: ReadingDraft, status: string, today: string): ReadingDraft {
    return {
        ...draft,
        status,
        end_date: endsReading(status) ? draft.end_date || today : '',
    };
}

/**
 * The draft an edit form starts from, taken from an existing Reading.
 *
 * The inverse of :func:`readingPayload`, so a Reading round-trips through the
 * form unchanged when the reader only means to change its status.
 */
export function readingDraft(reading: Reading): ReadingDraft {
    return {
        status: reading.status,
        start_date: reading.start_date ?? '',
        end_date: reading.end_date ?? '',
        rating: reading.rating ?? 0,
    };
}
