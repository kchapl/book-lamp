import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { getAuthStatus } from '../../react/services/api';

// The SPA serves /unauthorised from the same bundle, so a 401 caught while
// already on that path must not navigate again or the page reloads forever.
let navigations: string[];

function mockLocation(pathname: string) {
    navigations = [];
    const location = {
        pathname,
        set href(value: string) {
            navigations.push(value);
        },
        get href() {
            return pathname;
        },
    };
    Object.defineProperty(window, 'location', {
        configurable: true,
        writable: true,
        value: location,
    });
}

function mock401() {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ error: 'Unauthorized' }), {
            status: 401,
            headers: { 'Content-Type': 'application/json' },
        })
    ));
}

describe('api 401 redirect guard', () => {
    beforeEach(() => {
        vi.restoreAllMocks();
    });

    afterEach(() => {
        vi.restoreAllMocks();
    });

    it('redirects to /unauthorised when a 401 arrives on another route', async () => {
        mockLocation('/books');
        mock401();

        await expect(getAuthStatus()).rejects.toThrow('Unauthorized');
        expect(navigations).toEqual(['/unauthorised']);
    });

    it('does not navigate again when already on /unauthorised', async () => {
        mockLocation('/unauthorised');
        mock401();

        await expect(getAuthStatus()).rejects.toThrow('Unauthorized');
        expect(navigations).toEqual([]);
    });
});
