/**
 * What the sync badge reports.
 *
 * `GET /api/sync/diagnostics` distinguishes a healthy store (`ok`), a failed
 * one (`error`) and a request that carried no session (`unauthenticated`). Only
 * the middle one is a storage problem worth a badge: a page whose session has
 * gone must not leave a red dot claiming the store is broken — it must drop
 * its signed-in state and stop probing.
 */
import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, render, screen, waitFor } from '@testing-library/react';
import App from '../App';

type DiagnosticsStatus = 'ok' | 'error' | 'unauthenticated';

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

/** Answer the page's requests, with diagnostics reporting `status`. */
function installFetch(status: DiagnosticsStatus) {
    requested = [];
    vi.stubGlobal(
        'fetch',
        vi.fn(async (input: RequestInfo | URL) => {
            const url = String(input);
            requested.push(url);

            if (url.includes('/api/auth/status')) {
                return response({
                    is_authenticated: true,
                    user: null,
                    google_client_id: 'test-client-id',
                });
            }
            if (url.includes('/api/sync/diagnostics')) {
                return response(
                    status === 'unauthenticated'
                        ? { status, storage: 'unauthenticated' }
                        : { status, storage: 'postgres' }
                );
            }
            if (url.includes('/api/recommendations')) {
                return response({ recommendations: [] });
            }
            return response({}, 404);
        })
    );
}

const probes = () =>
    requested.filter((url) => url.includes('/api/sync/diagnostics')).length;

const badge = () => screen.queryByRole('img', { name: 'Sync problem' });

beforeEach(() => {
    window.history.replaceState({}, '', '/');
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
    vi.useRealTimers();
});

describe('the sync badge', () => {
    it('stays away when diagnostics answer ok', async () => {
        installFetch('ok');

        render(<App />);

        await waitFor(() => expect(probes()).toBeGreaterThan(0));
        expect(await screen.findByText('Account')).toBeInTheDocument();
        expect(badge()).not.toBeInTheDocument();
    });

    it('reports a genuine storage failure', async () => {
        installFetch('error');

        render(<App />);

        const dot = await screen.findByRole('img', { name: 'Sync problem' });
        expect(dot).toHaveAttribute('title', 'Sync problem — check storage');
        expect(screen.getByText('Account')).toBeInTheDocument();
    });

    it('treats a lost session as signed out, not as a storage failure', async () => {
        installFetch('unauthenticated');

        render(<App />);

        // The page loaded while signed in, then the probe found no session.
        expect(await screen.findByText('Account')).toBeInTheDocument();
        await waitFor(() =>
            expect(screen.queryByText('Account')).not.toBeInTheDocument()
        );

        expect(badge()).not.toBeInTheDocument();
        expect(screen.getByText('Sign in')).toBeInTheDocument();
    });

    it('stops probing once the session is gone', async () => {
        vi.useFakeTimers();
        installFetch('unauthenticated');

        render(<App />);

        // Let the auth check and the first probe settle.
        await act(async () => {
            await vi.advanceTimersByTimeAsync(0);
            await vi.advanceTimersByTimeAsync(0);
        });
        expect(probes()).toBe(1);

        // Three intervals' worth of time: a probe left running would fire again.
        await act(async () => {
            await vi.advanceTimersByTimeAsync(180_000);
        });

        expect(probes()).toBe(1);
    });
});
