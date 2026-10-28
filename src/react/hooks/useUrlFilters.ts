/**
 * Filters kept in the query string.
 *
 * The books page and the reading log both read several filters out of the URL and
 * write one back at a time, and both carried their own copy of that round trip.
 * The URL stays the source of truth; this is only the read/write seam.
 */
import { useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';

export interface UrlFilters<K extends string> {
    /** The managed keys, read fresh from the URL. Absent keys read as ''. */
    values: Record<K, string>;
    /**
     * Write values, deleting any key set to ''. Keys outside `keys` are allowed
     * on purpose: a page sometimes has to drop a parameter it does not own — the
     * books page clears its search box when a filter changes.
     */
    set: (updates: Record<string, string>) => void;
    /** Drop every parameter. */
    clear: () => void;
}

export function useUrlFilters<K extends string>(keys: readonly K[]): UrlFilters<K> {
    const [searchParams, setSearchParams] = useSearchParams();

    const values = {} as Record<K, string>;
    for (const key of keys) {
        values[key] = searchParams.get(key) ?? '';
    }

    const set = useCallback(
        (updates: Record<string, string>) => {
            const next = new URLSearchParams(searchParams);
            for (const [key, value] of Object.entries(updates)) {
                if (value) {
                    next.set(key, value);
                } else {
                    next.delete(key);
                }
            }
            setSearchParams(next);
        },
        [searchParams, setSearchParams]
    );

    const clear = useCallback(() => setSearchParams({}), [setSearchParams]);

    return { values, set, clear };
}
