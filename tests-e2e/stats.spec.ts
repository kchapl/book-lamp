import { test, expect } from '@playwright/test';

test.beforeEach(async ({ page, request }) => {
    await request.post('/test/reset');
    await page.goto('/test/connect');
});

test('stats page shows collection statistics', async ({ page }) => {
    // 1. Add some data
    await page.goto('/books/new');
    await page.fill('#isbn', '9780000000000');
    await page.getByRole('button', { name: 'Find & Add Book' }).click();

    // 2. Go to stats
    await page.goto('/stats');
    await expect(page.getByRole('heading', { name: 'Collection Statistics' })).toBeVisible();

    // 3. Check some stats
    await expect(page.locator('text=Total Books')).toBeVisible();
    await expect(page.locator('.stat-value').first()).toHaveText('1');
});
