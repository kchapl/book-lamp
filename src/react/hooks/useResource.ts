/**
 * The fetch lifecycle for a page's data.
 *
 * Eight pages each declared the same four things by hand: a loading flag, an
 * error string, an async loader wrapped in try/catch/finally, and an effect that
 * called it. The copies had already drifted — one page tolerated a partial
 * failure, another early-returned, and the loading text differed — so the
 * lifecycle lives here instead.
 *
 * The interface is deliberately small: hand it a fetcher and the values that
 * should trigger a refetch, and it owns everything else.
 */
import { useCallback, useEffect, useRef, useState } from 'react';

export interface Resource<T> {
    /** The last successful result, or null before the first one arrives. */
    data: T | null;
    loading: boolean;
    error: string | null;
    /** Refetch, e.g. after a write. A no-op while the resource is disabled. */
    reload: () => void;
}

export interface ResourceOptions {
    /**
     * Fetch only while this is true. A disabled resource never fetches and is
     * never loading; flipping it true starts the fetch.
     */
    enabled?: boolean;
    /**
     * Shown when the fetch throws, so a page keeps its own wording rather than
     * surfacing a raw HTTP message.
     */
    errorMessage?: string;
}

const DEFAULT_ERROR_MESSAGE = 'Failed to load this page';

/**
 * Run `fetch` and report its state.
 *
 * `deps` is the refetch contract, compared element-wise exactly as `useEffect`
 * compares its dependencies. The fetcher itself is a new closure on every render
 * and is deliberately not a dependency: pass a primitive in `deps` (`[bookId]`,
 * `[searchParams]`) rather than relying on the fetcher's identity.
 */
export function useResource<T>(
    fetch: () => Promise<T>,
    deps: readonly unknown[],
    { enabled = true, errorMessage = DEFAULT_ERROR_MESSAGE }: ResourceOptions = {}
): Resource<T> {
    const [data, setData] = useState<T | null>(null);
    const [loading, setLoading] = useState(enabled);
    const [error, setError] = useState<string | null>(null);
    const [reloadToken, setReloadToken] = useState(0);

    // Read straight from refs so the effect never depends on an identity that
    // changes every render.
    const fetchRef = useRef(fetch);
    fetchRef.current = fetch;
    const enabledRef = useRef(enabled);
    enabledRef.current = enabled;

    // Responses can arrive out of order. Every run takes a number, and only the
    // newest number may touch state — so a slow earlier request cannot land on
    // top of a fast later one. Disabling also bumps the number, which discards
    // anything still in flight.
    const runRef = useRef(0);

    useEffect(() => {
        const run = ++runRef.current;

        if (!enabled) {
            setLoading(false);
            return;
        }

        setLoading(true);
        setError(null);

        fetchRef.current()
            .then((result) => {
                if (run !== runRef.current) return;
                setData(result);
            })
            .catch((caught: unknown) => {
                if (run !== runRef.current) return;
                // The page shows its own wording; the cause goes to the console.
                console.error('Failed to load resource:', caught);
                setError(errorMessage);
            })
            .finally(() => {
                if (run !== runRef.current) return;
                setLoading(false);
            });
    }, [...deps, enabled, reloadToken]);

    const reload = useCallback(() => {
        if (!enabledRef.current) return;
        setReloadToken((token) => token + 1);
    }, []);

    return { data, loading, error, reload };
}
