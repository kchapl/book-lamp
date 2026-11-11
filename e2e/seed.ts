import type { APIRequestContext } from '@playwright/test';

/**
 * The dataset every journey is built on.
 *
 * Reading dates sit in 2024 rather than "this year" so the Dashboard's
 * current-year figures do not change with the calendar. Everything is created
 * through the public API, which is also how the app itself creates Books.
 */
interface SeedBook {
    payload: Record<string, unknown>;
    reading?: Record<string, unknown>;
    /** Books with a Reading or in progress do not stay on the Reading List. */
    keepOnReadingList?: boolean;
}

const SEED: SeedBook[] = [
    {
        payload: {
            isbn: '9781635575637',
            title: 'Piranesi',
            author: 'Susanna Clarke',
            publisher: 'Bloomsbury Publishing',
            publication_year: 2020,
            bisac_category: 'Fiction / Fantasy',
        },
    },
    {
        payload: {
            isbn: '9780060512750',
            title: 'The Dispossessed',
            author: 'Ursula K. Le Guin',
            publisher: 'Harper & Row',
            publication_year: 1974,
            bisac_category: 'Fiction / Science Fiction',
        },
        reading: {
            status: 'Completed',
            start_date: '2024-03-01',
            end_date: '2024-03-20',
            rating: 5,
        },
        keepOnReadingList: false,
    },
    {
        payload: {
            isbn: '9780593135204',
            title: 'Project Hail Mary',
            author: 'Andy Weir',
            publisher: 'Ballantine Books',
            publication_year: 2021,
            bisac_category: 'Fiction / Science Fiction',
        },
        reading: {
            status: 'Completed',
            start_date: '2024-04-01',
            end_date: '2024-04-12',
            rating: 4,
        },
        keepOnReadingList: false,
    },
    {
        payload: {
            isbn: '9780765311788',
            title: 'The Final Empire',
            author: 'Brandon Sanderson',
            publisher: 'Tor Books',
            publication_year: 2006,
            series: 'Mistborn',
            bisac_category: 'Fiction / Fantasy',
        },
        reading: {
            status: 'In Progress',
            start_date: '2024-05-01',
            rating: 0,
        },
        keepOnReadingList: false,
    },
    {
        payload: {
            isbn: '9780547773742',
            title: 'A Wizard of Earthsea',
            author: 'Ursula K. Le Guin',
            publisher: 'Parnassus Press',
            publication_year: 1968,
            bisac_category: 'Fiction / Fantasy',
        },
    },
];

async function created(api: APIRequestContext, payload: Record<string, unknown>) {
    const response = await api.post('/api/books', { data: payload });
    if (!response.ok()) {
        throw new Error(
            `seeding ${String(payload.title)} failed: ${response.status()} ${await response.text()}`
        );
    }
    return response.json();
}

/** Reset the store, sign the test reader in, and create the fixed dataset. */
export async function resetAndSeed(api: APIRequestContext): Promise<void> {
    const reset = await api.post('/test/reset');
    if (!reset.ok()) throw new Error(`test reset failed: ${reset.status()}`);

    const connected = await api.get('/test/connect');
    if (!connected.ok()) throw new Error(`test connect failed: ${connected.status()}`);

    for (const { payload, reading, keepOnReadingList = true } of SEED) {
        const book = await created(api, payload);

        if (reading) {
            const recorded = await api.post(`/api/books/${book.id}/readings`, { data: reading });
            if (!recorded.ok()) {
                throw new Error(
                    `seeding a Reading for ${String(payload.title)} failed: ${recorded.status()} ${await recorded.text()}`
                );
            }
        }

        if (!keepOnReadingList) {
            await api.post(`/api/reading-list/remove/${book.id}`);
        }
    }
}
