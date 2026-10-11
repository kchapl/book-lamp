/**
 * The fetch lifecycle, tested through its own interface.
 *
 * The page tests render a page with the API mocked, so they can only show that
 * one page happens to work. These call the hook directly: a page and a test
 * cross the same seam.
 */
import React, { StrictMode } from 'react';
import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useResource } from '../useResource';

/** A promise whose settlement the test controls. */
function deferred<T>() {
    let resolve!: (value: T) => void;
    let reject!: (reason?: unknown) => void;
    const promise = new Promise<T>((res, rej) => {
        resolve = res;
        reject = rej;
    });
    return { promise, resolve, reject };
}

/** Keep the expected console noise out of the test output. */
function silenceConsoleError() {
    return vi.spyOn(console, 'error').mockImplementation(() => {});
}

afterEach(() => {
    vi.restoreAllMocks();
});

describe('useResource', () => {
    it('goes from loading to data', async () => {
        const fetch = vi.fn().mockResolvedValue(['a']);

        const { result } = renderHook(() => useResource(fetch, []));

        expect(result.current.loading).toBe(true);
        expect(result.current.data).toBeNull();

        await waitFor(() => expect(result.current.data).toEqual(['a']));
        expect(result.current.loading).toBe(false);
        expect(result.current.error).toBeNull();
    });

    it('reports the wording it was given when the fetch fails', async () => {
        silenceConsoleError();
        const fetch = vi.fn().mockRejectedValue(new Error('HTTP 500: boom'));

        const { result } = renderHook(() =>
            useResource(fetch, [], { errorMessage: 'Failed to load books' })
        );

        await waitFor(() => expect(result.current.error).toBe('Failed to load books'));
        expect(result.current.loading).toBe(false);
        expect(result.current.data).toBeNull();
    });

    it('refetches on reload', async () => {
        const fetch = vi.fn().mockResolvedValueOnce('first').mockResolvedValueOnce('second');

        const { result } = renderHook(() => useResource(fetch, []));
        await waitFor(() => expect(result.current.data).toBe('first'));

        act(() => result.current.reload());

        await waitFor(() => expect(result.current.data).toBe('second'));
        expect(fetch).toHaveBeenCalledTimes(2);
    });

    it('refetches when a dependency changes', async () => {
        const fetch = vi.fn().mockResolvedValue('x');

        const { rerender } = renderHook(({ id }) => useResource(fetch, [id]), {
            initialProps: { id: 1 },
        });
        await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));

        rerender({ id: 2 });

        await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
    });

    it('ignores a response that arrives after a newer one', async () => {
        const older = deferred<string>();
        const newer = deferred<string>();
        const fetch = vi.fn().mockReturnValueOnce(older.promise).mockReturnValueOnce(newer.promise);

        const { result, rerender } = renderHook(({ id }) => useResource(fetch, [id]), {
            initialProps: { id: 1 },
        });
        rerender({ id: 2 });
        await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));

        // The newer request lands first...
        await act(async () => newer.resolve('newer'));
        expect(result.current.data).toBe('newer');

        // ...so the older one, still in flight, must not overwrite it.
        await act(async () => older.resolve('older'));
        expect(result.current.data).toBe('newer');
    });

    it('does not fetch while disabled, and starts when enabled', async () => {
        const fetch = vi.fn().mockResolvedValue('loaded');

        const { result, rerender } = renderHook(
            ({ enabled }) => useResource(fetch, [], { enabled }),
            { initialProps: { enabled: false } }
        );

        expect(result.current.loading).toBe(false);
        expect(result.current.data).toBeNull();
        expect(fetch).not.toHaveBeenCalled();

        rerender({ enabled: true });

        await waitFor(() => expect(result.current.data).toBe('loaded'));
        expect(fetch).toHaveBeenCalledTimes(1);
    });

    it('ignores reload while disabled', () => {
        const fetch = vi.fn().mockResolvedValue('x');

        const { result } = renderHook(() => useResource(fetch, [], { enabled: false }));

        act(() => result.current.reload());

        expect(fetch).not.toHaveBeenCalled();
    });

    it('settles under StrictMode instead of refetching forever', async () => {
        const fetch = vi.fn().mockResolvedValue('once');

        const { result } = renderHook(() => useResource(fetch, []), {
            wrapper: ({ children }: { children: React.ReactNode }) => (
                <StrictMode>{children}</StrictMode>
            ),
        });

        await waitFor(() => expect(result.current.data).toBe('once'));

        // StrictMode deliberately invokes effects twice on mount; what matters is
        // that it stops there rather than refetching on every render.
        const afterMount = fetch.mock.calls.length;
        expect(afterMount).toBeLessThanOrEqual(2);

        await act(async () => {
            await new Promise((resolve) => setTimeout(resolve, 20));
        });

        expect(fetch.mock.calls.length).toBe(afterMount);
        expect(result.current.data).toBe('once');
    });
});
