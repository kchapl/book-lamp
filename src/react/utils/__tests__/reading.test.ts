import { describe, expect, it } from 'vitest';
import { readingPayload } from '../reading';

describe('readingPayload', () => {
    it('keeps the end date for a Reading that has ended', () => {
        expect(
            readingPayload({
                status: 'Completed',
                start_date: '2026-10-01',
                end_date: '2026-10-11',
                rating: 4,
            })
        ).toEqual({
            status: 'Completed',
            start_date: '2026-10-01',
            end_date: '2026-10-11',
            rating: 4,
        });
    });

    it('sends no end date for a Reading that is still open', () => {
        // The form clears the end date when the status stops ending a Reading, so
        // an open Reading never claims one.
        expect(
            readingPayload({
                status: 'In Progress',
                start_date: '2026-10-01',
                end_date: '',
                rating: 5,
            })
        ).toEqual({
            status: 'In Progress',
            start_date: '2026-10-01',
            end_date: undefined,
            rating: 5,
        });
    });

    it('keeps the end date for an Abandoned Reading, which has ended too', () => {
        // The route refuses both ending statuses without an end date, not just
        // Completed.
        expect(
            readingPayload({
                status: 'Abandoned',
                start_date: '2026-10-01',
                end_date: '2026-10-05',
                rating: 0,
            }).end_date
        ).toBe('2026-10-05');
    });
});
