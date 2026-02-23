import { test, expect } from '@playwright/test';

test.describe('Reading List feature', () => {
    test.beforeEach(async ({ page }) => {
        await page.goto('/connect'); // Authorise in test environment
    });

    test('can add a book to reading list and reorder', async ({ page }) => {
        // Add book
        await page.goto('/books/new');
        await page.fill('input[name="isbn"]', '9780000000000');
        await page.locator('button', { hasText: 'Add to Reading List' }).click();

        await expect(page).toHaveURL(/.*\/reading-list/);
        await expect(page.locator('.alert.success')).toBeVisible();

        await expect(page.locator('.draggable-item')).toHaveCount(1);
        await expect(page.locator('.draggable-item')).toContainText('Test Driven Development');

        // Check main books list that pseudo-record is used
        await page.goto('/history');
        await expect(page.locator('.status-plan-to-read')).toBeVisible();

        // Remove book
        await page.goto('/reading-list');
        await page.click('button[title="Remove from list"]');

        await expect(page.locator('.alert.success')).toContainText('Removed');
        await expect(page.locator('text=Your reading list is empty')).toBeVisible();
    });
});
