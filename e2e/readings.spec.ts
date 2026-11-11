import { expect, test } from '@playwright/test';
import { fillField } from './helpers';
import { resetAndSeed } from './seed';

test.beforeEach(async ({ request }) => {
    await resetAndSeed(request);
});

test('adds, edits and deletes a Reading on a Book page', async ({ page }) => {
    await page.goto('/books/3');
    await expect(page.getByRole('heading', { name: 'Project Hail Mary' })).toBeVisible();

    await page.getByText('Add reading', { exact: true }).click();
    await fillField(page, 'record-start-date', '2024-06-01');
    await fillField(page, 'record-end-date', '2024-06-10');
    await fillField(page, 'record-rating', '5');
    await page.getByText('Add', { exact: true }).click();

    await expect(page.getByText('2024-06-01 → 2024-06-10')).toBeVisible();

    await page.getByLabel('Edit reading of 2024-06-01').click();
    await fillField(page, 'edit-record-end-date', '2024-06-20');
    await page.locator('.reading-form').getByText('Save', { exact: true }).click();

    await expect(page.getByText('2024-06-01 → 2024-06-20')).toBeVisible();

    await page.getByLabel('Delete reading of 2024-06-01').click();
    await page.locator('md-dialog[open]').getByText('Delete', { exact: true }).click();

    await expect(page.getByText('2024-06-01 → 2024-06-20')).toHaveCount(0);
    // The seeded Reading is untouched by the delete.
    await expect(page.getByText('2024-04-01 → 2024-04-12')).toBeVisible();
});
