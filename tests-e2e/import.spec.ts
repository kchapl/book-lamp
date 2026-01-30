import { test, expect } from '@playwright/test';
import path from 'path';

// Increase timeout for setup since CI can be slower
test.setTimeout(120000);

test.beforeEach(async ({ page, request }) => {
    // Reset the mock storage before each test
    await request.post('/test/reset');
    // Connect to the mock storage
    await page.goto('/test/connect');
});

test('importing Libib CSV creates books and reading records', async ({ page }) => {
    // Navigate to the import page
    await page.goto('/books/import');
    await expect(page.getByRole('heading', { name: 'Import from Libib', exact: true })).toBeVisible();

    // Set the file input to our sample CSV
    const filePath = path.resolve(__dirname, 'assets/libib_import.csv');
    await page.setInputFiles('#csv_file', filePath);

    // Submit the import form
    await Promise.all([
        page.waitForURL('/books'),
        page.getByRole('button', { name: 'Start Import' }).click()
    ]);

    // Verify success message
    await expect(page.locator('.messages .success')).toContainText('Successfully imported 2 entries');

    // Verify both books appear in the list
    await expect(page.locator('.book-card .title', { hasText: 'The Great Gatsby' })).toBeVisible();
    await expect(page.locator('.book-card .title', { hasText: 'Thinking, Fast and Slow' })).toBeVisible();

    // Go to the reading history page to verify records
    await page.goto('/history');
    await expect(page.getByRole('heading', { name: 'Reading History' })).toBeVisible();

    // Verify Gatsby record
    const gatsbyHistory = page.locator('.history-book-card', { hasText: 'The Great Gatsby' });
    await expect(gatsbyHistory).toBeVisible();
    await expect(gatsbyHistory.locator('.status-badge')).toHaveText('Completed');
    await expect(gatsbyHistory.locator('.event-dates')).toContainText('Completed: 2023-01-15');

    // Verify Thinking record
    const thinkingHistory = page.locator('.history-book-card', { hasText: 'Thinking, Fast and Slow' });
    await expect(thinkingHistory).toBeVisible();
    await expect(thinkingHistory.locator('.status-badge')).toHaveText('In Progress');
    await expect(thinkingHistory.locator('.event-dates')).toContainText('Began: 2023-02-01');

    // Verify stats are updated
    await page.goto('/stats');
    await expect(page.locator('.stat-card', { has: page.locator('.stat-label', { hasText: 'Total Books' }) }).locator('.stat-value')).toHaveText('2');
    await expect(page.locator('.stat-card', { has: page.locator('.stat-label', { hasText: 'Unique Authors' }) }).locator('.stat-value')).toHaveText('2');
    await expect(page.locator('.stat-card', { has: page.locator('.stat-label', { hasText: 'Reading Events' }) }).locator('.stat-value')).toHaveText('2');
});
