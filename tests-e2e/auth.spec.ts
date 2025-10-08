import { test, expect } from '@playwright/test';

test('auth guard redirects to unauthorized when not logged in', async ({ page }) => {
    await page.goto('/about');
    await expect(page).toHaveURL(/.*unauthorized/);
    await expect(page.getByRole('heading', { name: 'Unauthorized' })).toBeVisible();
});

test('auth guard allows access after test login', async ({ page }) => {
    await page.goto('/test/login');
    await page.goto('/about');
    await expect(page.locator('text=This is a simple Flask web application.')).toBeVisible();
});


