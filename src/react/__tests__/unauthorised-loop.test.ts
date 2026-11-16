/**
 * A 401 must not steer the browser to the page it is already on.
 *
 * App polls /api/sync/diagnostics on every mount, and that endpoint requires a
 * session. fetchJSON redirects to /unauthorised on any 401, so an unauthenticated
 * visitor reloads /unauthorised forever and never reaches the sign-in button.
 */
import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import App from '../App';

const SYNC_DIAGNOSTICS = '/api/sync/diagnostics';
const AUTH_STATUS = '/api/auth/status';

/** Bounds the failure: without it a missing redirect is a bare test timeout. */
const REDIRECT_BUDGET_MS = 4000;

let navigations: string[] = [];
let requested: string[] = [];

interface NavigationWaiter {
    resolve: (target: string) => void;
    timer: ReturnType<typeof setTimeout>;
}

let waiters: NavigationWaiter[] = [];

/** Record a navigation and release anything waiting for one. */
function recordNavigation(target: string) {
    navigations.push(target);

    const released = waiters;
    waiters = [];
    for (const waiter of released) {
        clearTimeout(waiter.timer);
        waiter.resolve(target);
    }
}

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
        assign: recordNavigation,
        replace: recordNavigation,
        reload: () => {},
        toString: () => pathname,
    };
    Object.defineProperty(location, 'href', {
        configurable: true,
        get: () => navigations[navigations.length - 1] ?? pathname,
        set: recordNavigation,
    });
    Object.defineProperty(window, 'location', { configurable: true, value: location });
}

/**
 * Resolve as soon as the app sends the browser somewhere.
 *
 * `expectation` completes the failure sentence, so the message names what was
 * awaited rather than reporting a bare timeout.
 */
function nextNavigation(expectation: string): Promise<string> {
    const seen = navigations[navigations.length - 1];
    if (seen !== undefined) {
        return Promise.resolve(seen);
    }

    return new Promise((resolve, reject) => {
        const timer = setTimeout(() => {
            waiters = waiters.filter((waiter) => waiter.timer !== timer);
            reject(
                new Error(
                    `${expectation}, but no navigation happened within ${REDIRECT_BUDGET_MS} ms ` +
                        `(requests: ${JSON.stringify(requested)})`
                )
            );
        }, REDIRECT_BUDGET_MS);

        waiters.push({ resolve, timer });
    });
}

/**
 * Answer every request. Anything whose URL contains one of `unauthorised`
 * comes back 401, which is what a missing session produces.
 *
 * `authenticated` decides what /api/auth/status says; the sync probe only runs
 * for a visitor the app believes is signed in.
 */
function installFetch(unauthorised: string[], { authenticated = false } = {}) {
    vi.stubGlobal(
        'fetch',
        vi.fn(async (input: RequestInfo | URL) => {
            const url = String(input);
            requested.push(url);

            // A listed URL answers 401 for every endpoint, the auth check
            // included: a session that has gone answers 401 wherever it is
            // asked, and that is what makes the reload loop possible.
            if (unauthorised.some((fragment) => url.includes(fragment))) {
                return response({ error: 'Unauthorized' }, 401);
            }
            if (url.includes('/api/auth/status')) {
                return response({
                    is_authenticated: authenticated,
                    user: authenticated ? { email: 'reader@example.com' } : null,
                    google_client_id: 'test-client-id',
                });
            }
            return response({});
        })
    );
}

beforeEach(() => {
    navigations = [];
    requested = [];
    waiters = [];

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
    for (const waiter of waiters) clearTimeout(waiter.timer);
    waiters = [];
    vi.unstubAllGlobals();
});

describe('an unauthenticated visitor on /unauthorised', () => {
    it('is not sent back to /unauthorised, and never probes a session endpoint', async () => {
        installLocation('/unauthorised');
        // A 401 from the auth check is what the guard in fetchJSON exists for:
        // without it this visitor would be sent back to the page they are on.
        installFetch([SYNC_DIAGNOSTICS, AUTH_STATUS]);

        render(React.createElement(App));

        // The heading is behind the router's lazy chunk, so seeing it means the
        // mount effects — the auth check among them — have run.
        await screen.findByRole('heading', { name: 'Authentication Required' });

        expect(navigations).not.toContain('/unauthorised');
        expect(requested.some((url) => url.includes(SYNC_DIAGNOSTICS))).toBe(false);
    });
});

describe('a 401 that arrives on /unauthorised', () => {
    it('does not navigate to the page it is already on', async () => {
        installLocation('/unauthorised');
        installFetch([SYNC_DIAGNOSTICS], { authenticated: true });

        render(React.createElement(App));

        // The badge appears after fetchJSON has handled the 401, so this is
        // asserted after the decision rather than in a race with it.
        await screen.findByRole('img', { name: 'Sync problem' });

        expect(navigations).toEqual([]);
    });
});

describe('an expired session on a page that needs one', () => {
    it('is still sent to /unauthorised', async () => {
        installLocation('/books');
        installFetch(['/api/books']);

        render(React.createElement(App));

        const target = await nextNavigation(
            'A 401 on /api/books should send the reader to /unauthorised'
        );
        expect(target).toBe('/unauthorised');
    });
});
