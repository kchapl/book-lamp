import { test, expect } from '@playwright/test';

test.beforeEach(async ({ page, request }) => {
    // Reset database
    await request.post('/test/reset');

    // Authorize
    await page.goto('/test/connect');
});

test('can add and view reading records', async ({ page }) => {
    // 1. Add a book first
    await page.goto('/books/new');
    await page.fill('#isbn', '9780000000000');
    await page.getByRole('button', { name: 'Find & Add Book' }).click();
    await expect(page.locator('.book-card .title')).toHaveText('Test Driven Development');

    // 2. Go to book detail
    await page.getByRole('link', { name: 'Test Driven Development' }).first().click();
    await expect(page.getByRole('heading', { name: 'Test Driven Development' })).toBeVisible();

    // 3. Add a reading record
    const addRecordBtn = page.locator('.add-record-toggle');
    await addRecordBtn.click();

    const form = page.locator('.add-record-form');
    await expect(form).toBeVisible();

    await form.locator('select[name="status"]').selectOption('Completed');
    await form.locator('input[name="start_date"]').fill('2024-01-01');
    await form.locator('input[name="end_date"]').fill('2024-01-10');
    await form.locator('select[name="rating"]').selectOption('5');
    await form.getByRole('button', { name: 'Save' }).click();

    // 4. Verify record on detail page
    await expect(page.locator('.status-badge')).toHaveText('Completed');
    await expect(page.locator('.stars')).toHaveText('★★★★★');
    // Let's check book_detail.html: {% for _ in range(record.rating) %}★{% endfor %} {% for _ in range(5 - record.rating) %}☆{% endfor %}
    // So for 5 stars, it's 5 full stars. The test above had 10 stars total?
    // Ah, line 378 in book_detail.html: range(record.rating) + range(5 - record.rating) = 5 stars.
    // So 5 stars = ★★★★★.

    // 5. Verify record in history
    await page.goto('/history');
    await expect(page.getByRole('heading', { name: 'Reading History' })).toBeVisible();
    await expect(page.locator('.history-list')).toBeVisible();
    await expect(page.locator('.history-book-title')).toHaveText('Test Driven Development');
});
