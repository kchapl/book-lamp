import { test, expect } from '@playwright/test';

test.beforeEach(async ({ request }) => {
    await request.post('/test/reset');
});

test('auth guard redirects to unauthorised when not logged in', async ({ page }) => {
    await page.goto('/about');
    await expect(page).toHaveURL(/.*unauthorised/);
    await expect(page.getByRole('heading', { name: 'Unauthorised' })).toBeVisible();
});

test('auth guard allows access after test authorisation', async ({ page }) => {
    // Go to connect and wait for successful redirect
    await page.goto('/test/connect');
    await page.waitForURL('/', { timeout: 30000 });
    await page.waitForSelector('#connection-status.connected', { timeout: 30000 });
    await expect(page.locator('#connection-status')).toHaveAttribute('title', /Google Sheets Connected/);

    // Then navigate to about page and verify content
    await page.goto('/about');
    await page.waitForLoadState('networkidle');
    await expect(page.getByRole('heading', { name: 'About Book Lamp' })).toBeVisible();
});


