import { test, expect } from '@playwright/test';

test.beforeEach(async ({ request }) => {
    // Ensure DB is reset before each test file, idempotent
    await request.post('/test/reset');
});

test('home page shows disconnected state, then authorisation works in TEST_MODE', async ({ page }) => {
    await page.goto('/');

    // Check for the disconnected status dot
    const statusDot = page.locator('#connection-status');
    await expect(statusDot).toHaveClass(/disconnected/);
    await expect(statusDot).toHaveAttribute('title', /Google Sheets Not Connected/);

    // Click dot to authorise
    await statusDot.click();

    // Verify modal appears and click confirm
    await expect(page.locator('#confirm-modal')).toBeVisible();
    await page.locator('#modal-confirm-btn').click();

    // Check for the connected status dot
    await expect(statusDot).toHaveClass(/connected/);
    await expect(statusDot).toHaveAttribute('title', /Google Sheets Connected/);

    // Click dot to disconnect
    await statusDot.click();

    // Verify modal appears and click confirm
    await expect(page.locator('#confirm-modal')).toBeVisible();
    await page.locator('#modal-confirm-btn').click();

    // Verify it returned to disconnected
    await expect(statusDot).toHaveClass(/disconnected/);
});


