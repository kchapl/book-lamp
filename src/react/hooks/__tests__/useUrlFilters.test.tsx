/** The URL round trip behind a page's filters. */
import React from 'react';
import { act, renderHook, waitFor } from '@testing-library/react';
import { MemoryRouter, useSearchParams } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import { useUrlFilters } from '../useUrlFilters';

/** Wrap the hook with a router parked on `entry`. */
const at = (entry: string) => {
    const Wrapper = ({ children }: { children: React.ReactNode }) => (
        <MemoryRouter initialEntries={[entry]}>{children}</MemoryRouter>
    );
    return Wrapper;
};

/** Read the filters and what the URL actually holds, side by side. */
function useSubject(entry: string) {
    return renderHook(
        () => {
            const filters = useUrlFilters(['status', 'year']);
            const [params] = useSearchParams();
            return { filters, query: params.toString() };
        },
        { wrapper: at(entry) }
    );
}

describe('useUrlFilters', () => {
    it('reads the keys it was given and leaves the others alone', () => {
        const { result } = useSubject('/books?status=Completed&year=2024&q=foo');

        expect(result.current.filters.values.status).toBe('Completed');
        expect(result.current.filters.values.year).toBe('2024');
        expect(Object.keys(result.current.filters.values)).toEqual(['status', 'year']);
    });

    it('reads a key that is absent as empty', () => {
        const { result } = useSubject('/books?status=Completed');

        expect(result.current.filters.values.year).toBe('');
    });

    it('writes a value, then deletes it when set empty', async () => {
        const { result } = useSubject('/books');

        act(() => result.current.filters.set({ status: 'Completed' }));
        await waitFor(() => expect(result.current.query).toBe('status=Completed'));

        act(() => result.current.filters.set({ status: '' }));
        await waitFor(() => expect(result.current.query).toBe(''));
    });

    it('keeps parameters it does not manage', async () => {
        const { result } = useSubject('/books?q=foo');

        act(() => result.current.filters.set({ status: 'Completed' }));

        await waitFor(() => expect(result.current.query).toContain('status=Completed'));
        expect(result.current.query).toContain('q=foo');
    });

    it('can drop a parameter outside its keys, for the page that owns it', async () => {
        // The books page leaves search mode when a filter changes.
        const { result } = useSubject('/books?q=foo');

        act(() => result.current.filters.set({ status: 'Completed', q: '' }));

        await waitFor(() => expect(result.current.query).toBe('status=Completed'));
    });

    it('clears every parameter', async () => {
        const { result } = useSubject('/books?status=Completed&q=foo');

        act(() => result.current.filters.clear());

        await waitFor(() => expect(result.current.query).toBe(''));
    });
});
