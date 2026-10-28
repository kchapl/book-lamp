/**
 * The query strings the pages hand the server.
 *
 * Both bugs pinned here were the same shape: a page named a parameter one way and
 * the route read it another, so the control moved and nothing else did. The page
 * tests render a mocked API, which cannot see this — these call the real module
 * against a stubbed `fetch`, so the outgoing URL is the thing under test.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { getBooks, getHistory } from '../api';

let requested: string[] = [];

function installFetch(): void {
    vi.stubGlobal(
        'fetch',
        vi.fn(async (input: RequestInfo | URL) => {
            requested.push(String(input));
            return {
                ok: true,
                status: 200,
                statusText: '',
                headers: { get: () => null },
                json: async () => ({}),
            } as unknown as Response;
        })
    );
}

/** The URL of the one request that was made. */
function requestUrl(): string {
    expect(requested).toHaveLength(1);
    return requested[0];
}

afterEach(() => {
    requested = [];
    vi.unstubAllGlobals();
});

describe('getBooks', () => {
    it('sends the sort the books page picked', async () => {
        installFetch();

        await getBooks({ sort: 'title' });

        expect(requestUrl()).toBe('/api/books?sort=title');
    });

    it('carries filters and the sort in one query', async () => {
        installFetch();

        await getBooks({ status: 'Completed', sort: 'author' });

        const url = requestUrl();
        expect(url).toContain('sort=author');
        expect(url).toContain('status=Completed');
    });

    it('omits anything unset rather than sending it empty', async () => {
        installFetch();

        await getBooks({ status: '', sort: '' });

        expect(requestUrl()).toBe('/api/books');
    });
});

describe('getHistory', () => {
    it('sends the minimum rating under the name the route reads', async () => {
        installFetch();

        await getHistory({ min_rating: 4 });

        expect(requestUrl()).toBe('/api/history?min_rating=4');
    });

    it('keeps the minimum rating and the sort distinct', async () => {
        installFetch();

        await getHistory({ min_rating: 3, sort: 'rating_desc' });

        const url = requestUrl();
        expect(url).toContain('min_rating=3');
        expect(url).toContain('sort=rating_desc');
    });
});
