/**
 * A 401 must not steer the browser to the page it is already on.
 *
 * App polls /api/sync/diagnostics on every mount, and that endpoint requires a
 * session. fetchJSON redirects to /unauthorised on any 401, so an unauthenticated
 * visitor reloads /unauthorised forever and never reaches the sign-in button.
 */
import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, waitFor } from '@testing-library/react';
import App from '../App';

const SYNC_DIAGNOSTICS = '/api/sync/diagnostics';

let navigations: string[] = [];
let requested: string[] = [];

function response(body: unknown, status = 200) {
    return {
        ok: status >= 200 && status < 300,
        status,
        statusText: '',
        headers: { get: () => null },
        json: async () => body,
    } as unknown as Response;
}

/** Point the app at `pathname`, recording any attempt to assign location.href. */
function installLocation(pathname: string) {
    // Set the URL while jsdom's own Location is still in place: history consults it.
    window.history.replaceState({}, '', pathname);

    // Then swap it for a plain object so `window.location.href = ...` can be
    // recorded instead of being swallowed by jsdom's unimplemented navigation.
    const location = {
        origin: 'http://localhost',
        protocol: 'http:',
        host: 'localhost',
        hostname: 'localhost',
        port: '',
        pathname,
        search: '',
        hash: '',
        assign: (target: string) => navigations.push(target),
        replace: (target: string) => navigations.push(target),
        reload: () => {},
        toString: () => pathname,
    };
    Object.defineProperty(location, 'href', {
        configurable: true,
        get: () => navigations[navigations.length - 1] ?? pathname,
        set: (target: string) => {
            navigations.push(target);
        },
    });
    Object.defineProperty(window, 'location', { configurable: true, value: location });
}

/**
 * Answer every request. Anything whose URL contains one of `unauthorised`
 * comes back 401, which is what a missing session produces.
 */
function installFetch(unauthorised: string[]) {
    vi.stubGlobal(
        'fetch',
        vi.fn(async (input: RequestInfo | URL) => {
            const url = String(input);
            requested.push(url);

            if (url.includes('/api/auth/status')) {
                return response({
                    is_authenticated: false,
                    user: null,
                    google_client_id: 'test-client-id',
                });
            }
            if (unauthorised.some((fragment) => url.includes(fragment))) {
                return response({ error: 'Unauthorized' }, 401);
            }
            return response({});
        })
    );
}

beforeEach(() => {
    navigations = [];
    requested = [];

    // jsdom implements no matchMedia, and App's theme effect reads it.
    window.matchMedia = ((query: string) => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: () => {},
        removeListener: () => {},
        addEventListener: () => {},
        removeEventListener: () => {},
        dispatchEvent: () => false,
    })) as unknown as typeof window.matchMedia;
});

afterEach(() => {
    vi.unstubAllGlobals();
});

/** Give queued promises and effects a chance to settle. */
const settle = () => new Promise((resolve) => setTimeout(resolve, 50));

describe('an unauthenticated visitor on /unauthorised', () => {
    it('is not sent back to /unauthorised, and never probes a session endpoint', async () => {
        installLocation('/unauthorised');
        installFetch([SYNC_DIAGNOSTICS]);

        render(React.createElement(App));

        await waitFor(() => expect(fetch).toHaveBeenCalled());
        await settle();

        expect(navigations).not.toContain('/unauthorised');
        expect(requested.some((url) => url.includes(SYNC_DIAGNOSTICS))).toBe(false);
    });
});

describe('an expired session on a page that needs one', () => {
    it('is still sent to /unauthorised', async () => {
        installLocation('/books');
        installFetch(['/api/books']);

        render(React.createElement(App));

        await waitFor(() => expect(navigations).toContain('/unauthorised'));
    });
});
