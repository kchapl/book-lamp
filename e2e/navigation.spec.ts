import { expect, test } from '@playwright/test';
import { resetAndSeed } from './seed';

test.beforeEach(async ({ request }) => {
    await resetAndSeed(request);
});

test('reaches the About page from the primary navigation', async ({ page }) => {
    await page.goto('/');

    await page.getByRole('navigation', { name: 'Primary' }).getByRole('link', { name: 'About' }).click();

    await expect(page).toHaveURL(/\/about$/);
    await expect(page.getByRole('heading', { name: 'About Book Lamp' })).toBeVisible();
    // The version is the reason the page exists: which deploy is answering.
    await expect(page.getByText(/^Version: /)).toBeVisible();
});
