import { test, expect } from '@playwright/test';

test.beforeEach(async ({ request }) => {
    // Ensure DB is reset before each test file, idempotent
    await request.post('/test/reset');
});

test('home page shows logged-out state, then login works in TEST_MODE', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('text=You are not logged in.')).toBeVisible();
    await page.getByRole('link', { name: 'Login with Google' }).click();
    await expect(page.locator('text=Hello Test User!')).toBeVisible();
    await page.getByRole('link', { name: 'Logout' }).click();
    await expect(page.locator('text=You are not logged in.')).toBeVisible();
});


