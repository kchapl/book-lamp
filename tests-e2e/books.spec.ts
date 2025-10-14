import { test, expect } from '@playwright/test';

test.beforeEach(async ({ page, request }) => {
    await request.post('/test/reset');
    await page.goto('/test/login');
});

test('books list initially empty and link to add', async ({ page }) => {
    await page.goto('/books');
    await expect(page.getByRole('heading', { name: 'Books' })).toBeVisible();
    await expect(page.locator('text=No books yet.')).toBeVisible();
    await page.getByRole('link', { name: 'Add one' }).click();
    await expect(page).toHaveURL(/.*\/books\/new/);
});

test('adding invalid ISBN shows error', async ({ page }) => {
    await page.goto('/books/new');
    await page.fill('#isbn', '123');
    await page.getByRole('button', { name: 'Add' }).click();
    await expect(page.locator('.messages .error', { hasText: 'valid 13-digit ISBN' })).toBeVisible();
});

test('adding duplicate shows info message', async ({ page }) => {
    await page.goto('/books/new');
    await page.fill('#isbn', '9780000000000');
    await page.getByRole('button', { name: 'Add' }).click();
    await expect(page).toHaveURL(/.*\/books$/);
    await expect(page.locator('.messages .success', { hasText: 'Book added successfully' })).toBeVisible();

    await page.goto('/books/new');
    await page.fill('#isbn', '9780000000000');
    await page.getByRole('button', { name: 'Add' }).click();
    await expect(page).toHaveURL(/.*\/books$/);
    await expect(page.locator('.messages .info', { hasText: 'already been added' })).toBeVisible();
});

test('successful add shows on list with metadata', async ({ page }) => {
    await page.goto('/books/new');
    await page.fill('#isbn', '9780000000000');
    await page.getByRole('button', { name: 'Add' }).click();
    await expect(page.locator('.messages .success', { hasText: 'Book added successfully' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Books' })).toBeVisible();
    await expect(page.locator('.card .title', { hasText: 'Test Driven Development' })).toBeVisible();
    await expect(page.locator('.card .author', { hasText: 'Test Author' })).toBeVisible();
    await expect(page.locator('.card .year', { hasText: '2019' })).toBeVisible();
    await expect(page.locator('.card .isbn', { hasText: '9780000000000' })).toBeVisible();
});


