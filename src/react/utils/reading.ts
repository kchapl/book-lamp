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
import { endsReading, RATED_STATUS } from './status';

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
        // A rating is a verdict on a finished Reading, so only a Completed
        // one submits the score the form holds.
        rating: draft.status === RATED_STATUS ? draft.rating : 0,
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
        rating: status === RATED_STATUS ? draft.rating : 0,
    };
}

/**
 * The draft an edit form starts from, taken from an existing Reading.
 *
 * The inverse of :func:`readingPayload` for a Reading that follows the rating
 * rule, so it round-trips through the form unchanged when the reader only means
 * to change its status. An open Reading that carries a rating keeps it in the
 * draft; :func:`readingPayload` drops it when the draft is saved.
 */
export function readingDraft(reading: Reading): ReadingDraft {
    return {
        status: reading.status,
        start_date: reading.start_date ?? '',
        end_date: reading.end_date ?? '',
        rating: reading.rating ?? 0,
    };
}
