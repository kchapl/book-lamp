import { afterEach, describe, expect, it, vi } from 'vitest';
import { formatDate, todayIso } from '../format';

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

describe('todayIso', () => {
    afterEach(() => {
        vi.useRealTimers();
    });

    it('names today as the local calendar date', () => {
        // Built from local parts, so this holds in any timezone the suite runs in.
        vi.useFakeTimers();
        vi.setSystemTime(new Date(2026, 9, 12, 9, 30));

        expect(todayIso()).toBe('2026-10-12');
    });

    it('zero-pads a single-digit month and day', () => {
        // A date input and the API both want `YYYY-MM-DD`, not `2026-1-5`.
        vi.useFakeTimers();
        vi.setSystemTime(new Date(2026, 0, 5, 9, 30));

        expect(todayIso()).toBe('2026-01-05');
    });
});
