import { describe, expect, it } from 'vitest';
import { formatDate } from '../format';

describe('formatDate', () => {
    it('formats an ISO date for display', () => {
        expect(formatDate('2024-03-10')).toBe(
            new Date('2024-03-10T00:00:00').toLocaleDateString(undefined, {
                day: 'numeric',
                month: 'short',
                year: 'numeric',
            })
        );
    });

    it("uses the caller's wording for an empty date", () => {
        // The reading log and the dashboard disagreed on this, which is why it is
        // a parameter rather than a baked-in string.
        expect(formatDate(null)).toBe('—');
        expect(formatDate(undefined)).toBe('—');
        expect(formatDate(null, 'no entries yet')).toBe('no entries yet');
        expect(formatDate('', 'no entries yet')).toBe('no entries yet');
    });

    it('passes an unparseable value through rather than inventing a date', () => {
        expect(formatDate('not-a-date')).toBe('not-a-date');
    });
});
