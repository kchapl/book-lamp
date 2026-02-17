import { test, expect } from '@playwright/test';

test.describe('Performance Standards', () => {
    test.beforeEach(async ({ page, request }) => {
        // Reset DB
        await request.post('/test/reset');

        // Go to home and connect to mock storage
        await page.goto('/');

        // Wait for connection status to be available
        const statusDot = page.locator('#connection-status');
        await expect(statusDot).toBeVisible();

        // If not connected, connect
        const className = await statusDot.getAttribute('class');
        if (className && className.includes('disconnected')) {
            await statusDot.click();
            await page.locator('#modal-confirm-btn').click();
            await expect(statusDot).toHaveClass(/connected/);
        }
    });

    test('images meet performance standards (lazy loading & dimensions)', async ({ page }) => {
        // Go to books list - it has book cover images
        await page.goto('/books');

        // Identify all images that are likely book covers or large content
        const images = page.locator('img.thumb');
        const count = await images.count();

        // If there are no books, add one first to test
        if (count === 0) {
            await page.goto('/books/new');
            await page.locator('input[name="isbn"]').fill('9780000000000');
            await page.locator('button[type="submit"]').click();
            await expect(page.locator('.book-card')).toBeVisible();
            await page.goto('/books');
        }

        const bookImages = page.locator('img.thumb');
        const bookCount = await bookImages.count();
        expect(bookCount).toBeGreaterThan(0);

        for (let i = 0; i < bookCount; i++) {
            const img = bookImages.nth(i);
            const src = await img.getAttribute('src');

            const loading = await img.getAttribute('loading');
            const width = await img.getAttribute('width');
            const height = await img.getAttribute('height');

            // According to Performance Engineer Skill:
            // "Use modern image formats. Ensure images have width and height attributes to prevent CLS."
            // "Implement lazy loading for images below the fold." (We enforce it for all covers in the list)

            expect(loading, `Image ${src} is missing loading="lazy"`).toBe('lazy');
            expect(width, `Image ${src} is missing width attribute`).not.toBeNull();
            expect(height, `Image ${src} is missing height attribute`).not.toBeNull();
        }
    });

    test('critical scripts are deferred', async ({ page }) => {
        await page.goto('/');
        const scripts = page.locator('script[src]');
        const count = await scripts.count();

        for (let i = 0; i < count; i++) {
            const script = scripts.nth(i);
            const src = await script.getAttribute('src');
            const isAsync = await script.getAttribute('async') !== null;
            const isDefer = await script.getAttribute('defer') !== null;
            const isModule = await script.getAttribute('type') === 'module';

            // Performance standard: "Defer non-critical JavaScript"
            // External scripts should be async, defer, or module
            expect(isAsync || isDefer || isModule, `Script ${src} is blocking (not async, defer, or module)`).toBe(true);
        }
    });
});
