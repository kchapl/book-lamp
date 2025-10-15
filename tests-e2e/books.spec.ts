import { test, expect } from '@playwright/test';

test.beforeEach(async ({ page, request }) => {
    // Try to reset the database up to 3 times
    let attempts = 0;
    while (attempts < 3) {
        try {
            const res = await request.post('/test/reset');
            if (!res.ok()) {
                throw new Error(`Failed to reset DB: ${res.status()}`);
            }
            break;
        } catch (error) {
            attempts++;
            if (attempts === 3) {
                throw error;
            }
            // Wait a bit before retrying
            await new Promise(resolve => setTimeout(resolve, 1000));
        }
    }

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
    const successMessage = page.locator('.messages .success', { hasText: 'Book added successfully' });
    await Promise.all([
        page.waitForURL(/.*\/books$/),
        page.getByRole('button', { name: 'Add' }).click()
    ]);
    // Wait for both network idle and DOM content to be ready
    await page.waitForLoadState('networkidle');
    await page.waitForLoadState('domcontentloaded');
    // Wait specifically for the success message with a custom timeout
    await expect(successMessage).toBeVisible({ timeout: 10000 });

    await page.goto('/books/new');
    await page.fill('#isbn', '9780000000000');
    await page.getByRole('button', { name: 'Add' }).click();
    await expect(page).toHaveURL(/.*\/books$/);
    await expect(page.locator('.messages .info', { hasText: 'already been added' })).toBeVisible();
});

test('successful add shows on list with metadata', async ({ page }) => {
    await page.goto('/books/new');
    await page.fill('#isbn', '9780000000000');
    const successMessage = page.locator('.messages .success', { hasText: 'Book added successfully' });
    await Promise.all([
        page.waitForURL(/.*\/books$/),
        page.getByRole('button', { name: 'Add' }).click()
    ]);
    // Wait for both network idle and DOM content to be ready
    await page.waitForLoadState('networkidle');
    await page.waitForLoadState('domcontentloaded');
    // Wait specifically for the success message with a custom timeout
    await expect(successMessage).toBeVisible({ timeout: 10000 });
    await expect(page.getByRole('heading', { name: 'Books' })).toBeVisible();
    await expect(page.locator('.card .title', { hasText: 'Test Driven Development' })).toBeVisible();
    await expect(page.locator('.card .author', { hasText: 'Test Author' })).toBeVisible();
    await expect(page.locator('.card .year', { hasText: '2019' })).toBeVisible();
    await expect(page.locator('.card .isbn', { hasText: '9780000000000' })).toBeVisible();
});


