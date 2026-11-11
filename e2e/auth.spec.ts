import { expect, test } from '@playwright/test';

test.beforeEach(async ({ request }) => {
    await request.get('/test/connect');
});

test('an unauthenticated visitor is sent to the unauthorised page', async ({ page, request }) => {
    await request.get('/test/disconnect');

    // A page that needs a session asks the API for data, gets 401, and is
    // steered to the sign-in page — the gate the reader meets.
    await page.goto('/books');

    await expect(page).toHaveURL(/\/unauthorised$/);
    await expect(page.getByRole('heading', { name: 'Authentication Required' })).toBeVisible();
});

test('an authorised reader sees the home page', async ({ page, request }) => {
    // The harness's own answer, before the SPA asks the same question.
    const status = await (await request.get('/api/auth/status')).json();
    expect(status.is_authenticated).toBe(true);

    await page.goto('/');

    await expect(page.getByRole('heading', { name: 'Your books.' })).toBeVisible();
    await expect(page.getByText('Browse your books')).toBeVisible();
});
