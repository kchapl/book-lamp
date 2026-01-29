import { test, expect } from '@playwright/test';

test('auth guard redirects to unauthorised when not logged in', async ({ page }) => {
    await page.goto('/about');
    await expect(page).toHaveURL(/.*unauthorised/);
    await expect(page.getByRole('heading', { name: 'Unauthorised' })).toBeVisible();
});

test('auth guard allows access after test authorisation', async ({ page }) => {
    // Go to connect and wait for successful redirect
    await page.goto('/test/connect');
    await page.waitForURL('/', { timeout: 30000 });
    await page.waitForSelector('text=Google Sheets Connected', { timeout: 30000 });

    // Then navigate to about page and verify content
    await page.goto('/about');
    await page.waitForLoadState('networkidle');
    await expect(page.getByRole('heading', { name: 'About Book Lamp' })).toBeVisible();
});


