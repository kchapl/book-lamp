import { test, expect } from '@playwright/test';

// Increase timeout for setup since CI can be slower
test.setTimeout(120000);

test.beforeEach(async ({ page, request }, testInfo) => {
    console.log(`Setting up test: ${testInfo.title}`);

    // Try to reset the database up to 5 times
    let attempts = 0;
    while (attempts < 5) {
        try {
            console.log(`Attempt ${attempts + 1} to reset database...`);
            const res = await request.post('/test/reset', { timeout: 30000 });
            if (!res.ok()) {
                throw new Error(`Failed to reset DB: ${res.status()}`);
            }

            // After reset, verify database is clean by checking books endpoint
            console.log('Verifying database is clean...');
            const verifyRes = await request.get('/books', { timeout: 30000 });
            const text = await verifyRes.text();
            if (!text.includes('No books yet')) {
                throw new Error('Database reset did not clear books');
            }

            console.log('Database reset successful');
            break;
        } catch (error) {
            attempts++;
            console.log(`Reset attempt ${attempts} failed:`, error);
            if (attempts === 5) {
                throw error;
            }
            // Increase wait time between retries
            const waitTime = 5000 * attempts;
            console.log(`Waiting ${waitTime}ms before retry...`);
            await new Promise(resolve => setTimeout(resolve, waitTime));
        }
    }

    // Login and verify session is active with increased timeouts
    console.log('Attempting to log in...');
    await page.goto('/test/login', { timeout: 30000 });
    await Promise.race([
        page.waitForURL('/', { timeout: 60000 }),
        page.waitForResponse(
            response => response.url().includes('/') && response.status() === 200,
            { timeout: 60000 }
        )
    ]);
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
    // First addition
    await page.goto('/books/new');
    await page.fill('#isbn', '9780000000000');

    // Click and wait for both the URL change and network requests to complete
    await Promise.all([
        page.waitForURL(/.*\/books$/),
        page.waitForResponse(response => response.url().includes('/books') && response.status() === 302),
        page.getByRole('button', { name: 'Add' }).click()
    ]);

    // Wait for page load and flash message container
    await page.waitForLoadState('networkidle');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.messages').waitFor({ state: 'attached' });

    // Verify first addition was successful
    await expect(
        page.locator('.messages .success')
    ).toHaveText('Book added successfully.', { timeout: 10000 });

    // Try adding the same book again
    await page.goto('/books/new');
    await page.fill('#isbn', '9780000000000');

    // Click and wait for both the URL change and network requests
    await Promise.all([
        page.waitForURL(/.*\/books$/),
        page.waitForResponse(response => response.url().includes('/books') && response.status() === 302),
        page.getByRole('button', { name: 'Add' }).click()
    ]);

    // Wait for page load and flash message
    await page.waitForLoadState('networkidle');
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.messages').waitFor({ state: 'attached' });

    // Verify duplicate message
    await expect(
        page.locator('.messages .info')
    ).toHaveText('This book has already been added.', { timeout: 10000 });
});

test('successful add shows on list with metadata', async ({ page }) => {
    await page.goto('/books/new');
    await page.fill('#isbn', '9780000000000');

    // Click add and wait for redirect
    await Promise.all([
        page.waitForURL(/.*\/books$/),
        page.getByRole('button', { name: 'Add' }).click()
    ]);

    // Wait for navigation and page load to complete first
    await page.waitForLoadState('networkidle');
    await page.waitForLoadState('domcontentloaded');

    // Wait for flash message container to be present
    await page.locator('.messages').waitFor({ state: 'attached' });

    // Then check for success message
    const successMessage = page.locator('.messages .success', { hasText: 'Book added successfully' });
    await expect(successMessage).toBeVisible({ timeout: 10000 });
    await expect(page.getByRole('heading', { name: 'Books' })).toBeVisible();
    await expect(page.locator('.card .title', { hasText: 'Test Driven Development' })).toBeVisible();
    await expect(page.locator('.card .author', { hasText: 'Test Author' })).toBeVisible();
    await expect(page.locator('.card .year', { hasText: '2019' })).toBeVisible();
    await expect(page.locator('.card .isbn', { hasText: '9780000000000' })).toBeVisible();
});


