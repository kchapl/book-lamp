import { expect, test } from '@playwright/test';
import { choose, fillField } from './helpers';
import { resetAndSeed } from './seed';

test.beforeEach(async ({ request }) => {
    await resetAndSeed(request);
});

test('edits a co-authored Book one Author row at a time', async ({ page, request }) => {
    // The seed has no Book two people wrote, so one is created through the same
    // API the app uses. Its Authors travel as a list.
    const response = await request.post('/api/books', {
        data: {
            isbn: '9780306406157',
            title: 'Good Omens',
            authors: ['Neil Gaiman', 'Terry Pratchett'],
        },
    });
    expect(response.ok()).toBeTruthy();
    const book = await response.json();

    await page.goto(`/books/${book.id}`);
    await expect(page.getByRole('link', { name: 'Neil Gaiman' })).toBeVisible();

    await page.getByText('Edit', { exact: true }).click();
    // One row per Author, in the order the Book credits them.
    await expect(page.locator('#edit-author-0 input')).toHaveValue('Neil Gaiman');
    await expect(page.locator('#edit-author-1 input')).toHaveValue('Terry Pratchett');

    await fillField(page, 'edit-author-1', 'Sir Terry Pratchett');
    await page.locator('.edit-form').getByText('Save', { exact: true }).click();

    // Only the row that was edited changed, and both names are still Authors.
    await expect(page.getByRole('link', { name: 'Neil Gaiman' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Sir Terry Pratchett' })).toBeVisible();
});

test('records a Book format by hand and clears it again', async ({ page, request }) => {
    const response = await request.post('/api/books', {
        data: { isbn: '9780306406157', title: 'Good Omens', authors: ['Neil Gaiman'] },
    });
    expect(response.ok()).toBeTruthy();
    const book = await response.json();

    await page.goto(`/books/${book.id}`);
    const formatRow = page.locator('.placard-row').filter({ hasText: 'Format' });
    await expect(formatRow).toHaveCount(0);

    await page.getByText('Edit', { exact: true }).click();
    await choose(page, 'edit-format', 'Paperback');
    await page.locator('.edit-form').getByText('Save', { exact: true }).click();

    // The chosen binding appears among the Book's details.
    await expect(page.locator('.placard-row').filter({ hasText: 'Format' })).toContainText('Paperback');

    // "Not recorded" removes a wrong format rather than making it permanent.
    await page.getByText('Edit', { exact: true }).click();
    await choose(page, 'edit-format', 'Not recorded');
    await page.locator('.edit-form').getByText('Save', { exact: true }).click();

    await expect(page.locator('.placard-row').filter({ hasText: 'Format' })).toHaveCount(0);
});
