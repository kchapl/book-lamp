import { test, expect } from '@playwright/test';

// Increase timeout for setup since CI can be slower
test.setTimeout(120000);

test.beforeEach(async ({ page, request }) => {
    await request.post('/test/reset');
    await page.goto('/test/connect');
});

test('books list initially empty and link to add', async ({ page }) => {
    await page.goto('/books');
    await expect(page.getByRole('heading', { name: 'Books', exact: true })).toBeVisible();
    await expect(page.locator('text=Your bookshelf is empty')).toBeVisible();
    await page.getByRole('link', { name: 'Add Your First Book' }).click();
    await expect(page).toHaveURL(/.*\/books\/new/);
});

test('adding invalid ISBN shows error', async ({ page }) => {
    await page.goto('/books/new');
    await page.fill('#isbn', '123');
    await page.getByRole('button', { name: 'Find & Add Book' }).click();
    await expect(page.locator('.messages .error', { hasText: 'valid 13-digit ISBN' })).toBeVisible();
});

test('adding duplicate shows info message', async ({ page }) => {
    // First addition
    await page.goto('/books/new');
    await page.fill('#isbn', '9780000000000');
    await Promise.all([
        page.waitForURL('/books'),
        page.getByRole('button', { name: 'Find & Add Book' }).click()
    ]);
    await expect(page.locator('.messages .success')).toHaveText('Book added successfully.');

    // Try adding the same book again
    await page.goto('/books/new');
    await page.fill('#isbn', '9780000000000');
    await Promise.all([
        page.waitForURL('/books'),
        page.getByRole('button', { name: 'Find & Add Book' }).click()
    ]);
    await expect(page.locator('.messages .info')).toHaveText('This book has already been added.');
});

test('successful add shows on list with metadata', async ({ page }) => {
    await page.goto('/books/new');
    await page.fill('#isbn', '9780000000000');

    // Click add and wait for redirect
    await Promise.all([
        page.waitForURL('/books'),
        page.getByRole('button', { name: 'Find & Add Book' }).click()
    ]);

    // Check for success message and book details
    await expect(page.locator('.messages .success')).toHaveText('Book added successfully.');
    await expect(page.locator('.book-card .title')).toHaveText('Test Driven Development');
    await expect(page.locator('.book-card .author')).toHaveText('Test Author');
    await expect(page.locator('.book-card .year')).toHaveText('2019');
    await expect(page.locator('.book-card .isbn')).toHaveText('ISBN-13: 9780000000000');
});
