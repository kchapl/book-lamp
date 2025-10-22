import { test, expect } from '@playwright/test';

test('auth guard redirects to unauthorized when not logged in', async ({ page }) => {
    await page.goto('/about');
    await expect(page).toHaveURL(/.*unauthorized/);
    await expect(page.getByRole('heading', { name: 'Unauthorized' })).toBeVisible();
});

test('auth guard allows access after test login', async ({ page }) => {
    // Go to login and wait for successful redirect
    await page.goto('/test/login');
    await page.waitForURL('/', { timeout: 30000 });
    await page.waitForSelector('text=Hello Test User!', { timeout: 30000 });

    // Then navigate to about page and verify content
    await page.goto('/about');
    await page.waitForLoadState('networkidle');
    await expect(page.getByRole('heading', { name: 'About' })).toBeVisible();
});


