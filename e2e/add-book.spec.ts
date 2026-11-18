import { expect, test } from '@playwright/test';
import { fillField } from './helpers';
import { resetAndSeed } from './seed';

test.beforeEach(async ({ request }) => {
    await resetAndSeed(request);
});

test('adds a Book through the ISBN lookup, with the provider title normalised', async ({ page }) => {
    await page.goto('/books/new');

    await fillField(page, 'isbn', '9780000000000');
    await page.getByText('Lookup ISBN', { exact: true }).click();

    // The canned answer stands in for a provider response and arrives as
    // `  the  last english king. `; the form shows the tidied title.
    await expect(page.locator('#title input')).toHaveValue('The Last English King');
    await expect(page.locator('#author input')).toHaveValue('Test Author');

    await page.locator('.add-book-form').getByText('Add Book', { exact: true }).click();

    // The seeded store holds five Books, so the new one is the sixth.
    await expect(page).toHaveURL(/\/books\/6$/);
    await expect(page.getByRole('heading', { name: 'The Last English King' })).toBeVisible();

    // The card reads the same normalised title once the Book has a Reading.
    await page.getByText('Add reading', { exact: true }).click();
    await fillField(page, 'record-start-date', '2024-06-01');
    await page.getByText('Add', { exact: true }).click();

    await page.goto('/books');
    await expect(page.locator('.exhibit').filter({ hasText: 'The Last English King' })).toBeVisible();
});
