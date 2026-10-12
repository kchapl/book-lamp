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
