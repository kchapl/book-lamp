import { describe, expect, it } from 'vitest';
import {
    IN_PROGRESS_STATUS,
    READING_LIST_CLASS,
    READING_STATUSES,
    statusAccentClass,
    statusClass,
} from '../status';

describe('statusClass', () => {
    it('gives each Reading Status its condition chip', () => {
        expect(statusClass('Completed')).toBe('status-completed');
        expect(statusClass('In Progress')).toBe('status-in-progress');
        expect(statusClass('Abandoned')).toBe('status-abandoned');
    });

    it('gives a Book with no Reading the planned role', () => {
        // The reading list is the absence of a Reading, so its chip cannot come
        // from a status; it takes the planned role the tokens define.
        expect(statusClass(undefined)).toBe(READING_LIST_CLASS);
        expect(statusClass('')).toBe(READING_LIST_CLASS);
    });

    it('falls back to the planned role for a status it does not know', () => {
        expect(statusClass('Someday')).toBe(READING_LIST_CLASS);
    });

    it('covers every status a Reading can carry', () => {
        expect(READING_STATUSES.map((status) => statusClass(status))).toEqual([
            'status-in-progress',
            'status-completed',
            'status-abandoned',
        ]);
        expect(READING_STATUSES).toContain(IN_PROGRESS_STATUS);
    });
});

describe('statusAccentClass', () => {
    it('is the chip class in the dashboard tile spelling', () => {
        // Derived rather than repeated: whatever statusClass says, this says in
        // the `is-*` spelling the status tiles and meter fills are keyed off.
        for (const status of READING_STATUSES) {
            expect(statusAccentClass(status)).toBe(statusClass(status).replace('status-', 'is-'));
        }
        expect(statusAccentClass('Completed')).toBe('is-completed');
    });

    it('follows the same fallback, so the two cannot drift', () => {
        expect(statusAccentClass(undefined)).toBe('is-planned');
        expect(statusAccentClass('Someday')).toBe('is-planned');
    });
});
