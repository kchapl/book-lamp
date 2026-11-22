import { expect, test } from '@playwright/test';
import { resetAndSeed } from './seed';

test.beforeEach(async ({ request }) => {
    await resetAndSeed(request);
});

test('a Book card shows the stored subtitle under its title', async ({ page, request }) => {
    const created = await request.post('/api/books', {
        data: {
            isbn: '9780306406157',
            title: 'A History of England in 100 Places: From Stonehenge to the Gherkin',
            author: 'David Long',
        },
    });
    expect(created.ok()).toBeTruthy();
    const book = await created.json();

    // A Book reaches My Books by having a Reading Status; the subtitle does not
    // change that, so the card is asserted where the collection shows it.
    const reading = await request.post(`/api/books/${book.id}/readings`, {
        data: { status: 'In Progress', start_date: '2024-06-01' },
    });
    expect(reading.ok()).toBeTruthy();

    await page.goto('/books');

    const card = page.locator('.exhibit').filter({ hasText: 'From Stonehenge to the Gherkin' });
    await expect(card.getByRole('heading', { name: 'A History of England in 100 Places' })).toBeVisible();
    await expect(card).toContainText('From Stonehenge to the Gherkin');
});

test('a Book card puts the publication year above the Reading Status', async ({ page, request }) => {
    const created = await request.post('/api/books', {
        data: {
            isbn: '9780306406157',
            title: 'A History of England in 100 Places',
            author: 'David Long',
            publication_year: 2022,
        },
    });
    expect(created.ok()).toBeTruthy();
    const book = await created.json();

    const reading = await request.post(`/api/books/${book.id}/readings`, {
        data: { status: 'In Progress', start_date: '2024-06-01' },
    });
    expect(reading.ok()).toBeTruthy();

    await page.goto('/books');

    const card = page.locator('.exhibit').filter({ hasText: 'A History of England in 100 Places' });
    const year = card.locator('.exhibit-accession');
    const statusRow = card.locator('.exhibit-meta');
    await expect(year).toHaveText('2022');
    await expect(statusRow).toContainText('In Progress');
    await expect(statusRow.locator('.exhibit-accession')).toHaveCount(0);

    const yearBox = await year.boundingBox();
    const statusBox = await statusRow.boundingBox();
    expect(yearBox!.y).toBeLessThan(statusBox!.y);
});

test('a provider-separated subtitle is stored as its own part', async ({ request }) => {
    const created = await request.post('/api/books', {
        data: {
            isbn: '9780241181346',
            title: 'The Spy and the Traitor',
            subtitle: 'The Greatest Espionage Story of the Cold War',
            author: 'Ben Macintyre',
        },
    });
    expect(created.ok()).toBeTruthy();

    const book = await created.json();
    expect(book.title).toBe('The Spy and the Traitor');
    expect(book.subtitle).toBe('The Greatest Espionage Story of the Cold War');
});
