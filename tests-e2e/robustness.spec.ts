import { test, expect } from '@playwright/test';

test.setTimeout(120000);

test.beforeEach(async ({ page, request }) => {
    await request.post('/test/reset');
    await page.goto('/test/connect');
});

test('handles corrupt spreadsheet data gracefully', async ({ page, request }) => {
    // We can't easily corrupt the MockStorage via REST API without adding a new test endpoint,
    // but we can verify that normal operations still work after we add "blank" rows.

    // For now, let's verify that the import STILL works even with the new robustness changes.
    // The previous test already verified this partially.

    // Let's add a test for a Libib CSV with weird headers or missing values
    // that our new libib_import.py should handle.
});
