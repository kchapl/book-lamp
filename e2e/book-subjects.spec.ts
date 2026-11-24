import { expect, test } from '@playwright/test';
import { resetAndSeed } from './seed';

test.beforeEach(async ({ request }) => {
    await resetAndSeed(request);
});

test('shows every subject a Book carries and filters by any of them', async ({ page, request }) => {
    const response = await request.post('/api/books', {
        data: {
            isbn: '9780000002211',
            title: 'A Mystery',
            authors: ['An Author'],
            subjects: ['Fiction / Mystery', 'Murder'],
        },
    });
    expect(response.ok()).toBeTruthy();
    const book = await response.json();

    await page.goto(`/books/${book.id}`);
    await expect(page.getByRole('link', { name: 'Fiction' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Murder' })).toBeVisible();

    // My Books carries Books with a Reading Status, so the filter is applied
    // to one that has been read.
    const recorded = await request.post(`/api/books/${book.id}/readings`, {
        data: { status: 'Completed', start_date: '2026-01-01', end_date: '2026-01-02', rating: 4 },
    });
    expect(recorded.ok()).toBeTruthy();

    // The collection filter matches the second subject as readily as the first.
    await page.goto('/books?category=Murder');
    await expect(page.getByRole('heading', { name: 'A Mystery' })).toBeVisible();
});
