import { describe, expect, it } from 'vitest';
import { draftWithStatus, readingDraft, readingPayload, type ReadingDraft } from '../reading';

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
            // A rating only travels with a Completed Reading, so an open one
            // submits none.
            rating: 0,
        });
    });

    it('sends no rating for a Reading that has not completed', () => {
        // Abandoned ends a Reading but is not a verdict on it, so the score the
        // draft still holds is not submitted.
        expect(
            readingPayload({
                status: 'Abandoned',
                start_date: '2026-10-01',
                end_date: '2026-10-05',
                rating: 4,
            }).rating
        ).toBe(0);
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

describe('draftWithStatus', () => {
    const open: ReadingDraft = {
        status: 'In Progress',
        start_date: '2026-10-01',
        end_date: '',
        rating: 0,
    };

    it('dates an ending status today when it has no end date yet', () => {
        expect(draftWithStatus(open, 'Completed', '2026-10-26').end_date).toBe('2026-10-26');
    });

    it('keeps the end date a Reading already has when it ends again', () => {
        const ended = { ...open, status: 'Completed', end_date: '2026-10-11' };

        expect(draftWithStatus(ended, 'Abandoned', '2026-10-26').end_date).toBe('2026-10-11');
    });

    it('clears the rating when the status leaves Completed', () => {
        const rated = { ...open, status: 'Completed', rating: 5 };

        expect(draftWithStatus(rated, 'In Progress', '2026-10-26').rating).toBe(0);
        expect(draftWithStatus(rated, 'Abandoned', '2026-10-26').rating).toBe(0);
    });

    it('clears the end date when a Reading is open again', () => {
        const ended = { ...open, status: 'Completed', end_date: '2026-10-11' };

        expect(draftWithStatus(ended, 'In Progress', '2026-10-26').end_date).toBe('');
    });
});

describe('readingDraft', () => {
    it('is the inverse of readingPayload for an open Reading', () => {
        const reading = {
            id: 7,
            book_id: 1,
            status: 'In Progress',
            start_date: '2026-10-01',
            rating: 3,
        };

        expect(readingPayload(readingDraft(reading))).toEqual({
            status: 'In Progress',
            start_date: '2026-10-01',
            end_date: undefined,
            rating: 0,
        });
    });

    it('is the inverse of readingPayload for an ended Reading', () => {
        const reading = {
            id: 7,
            book_id: 1,
            status: 'Completed',
            start_date: '2026-10-01',
            end_date: '2026-10-11',
            rating: 5,
        };

        expect(readingPayload(readingDraft(reading))).toEqual({
            status: 'Completed',
            start_date: '2026-10-01',
            end_date: '2026-10-11',
            rating: 5,
        });
    });
});
