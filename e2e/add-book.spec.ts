import { expect, test } from '@playwright/test';
import { fillField } from './helpers';
import { resetAndSeed } from './seed';

test.beforeEach(async ({ request }) => {
    await resetAndSeed(request);
});

test('adds a Book through the ISBN lookup', async ({ page }) => {
    await page.goto('/books/new');

    await fillField(page, 'isbn', '9780000000000');
    await page.getByText('Lookup ISBN', { exact: true }).click();

    await expect(page.locator('#title input')).toHaveValue('Test Book');
    await expect(page.locator('#author input')).toHaveValue('Test Author');

    // "Add Book" is also a nav link, so the submit action is scoped to the form.
    await page.locator('.add-book-form').getByText('Add Book', { exact: true }).click();

    // The seeded store holds five Books, so the new one is the sixth.
    await expect(page).toHaveURL(/\/books\/6$/);
    await expect(page.getByRole('heading', { name: 'Test Book' })).toBeVisible();
});
