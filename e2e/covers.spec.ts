import { expect, test } from '@playwright/test';
import { resetAndSeed } from './seed';

/**
 * Filling in covers for the Books that have none (#370).
 *
 * The provider chain is a live network call, and the run's backend behaviour is
 * covered by the integration tests. What this journey pins is the screen: the
 * reader finds the utility in the account menu and the layout reports the run
 * it finishes with. The job endpoints are answered here so the suite never
 * depends on a provider.
 */
test.beforeEach(async ({ request }) => {
    await resetAndSeed(request);
});

test('runs the missing-covers utility from the account menu', async ({ page }) => {
    await page.route('**/api/books/fetch-covers', (route) =>
        route.fulfill({ json: { job_id: 'e2e-covers' } })
    );
    await page.route('**/api/jobs/e2e-covers', (route) =>
        route.fulfill({
            json: {
                id: 'e2e-covers',
                status: 'completed',
                progress: 100,
                result:
                    'Checked 5 book(s) without a cover: filled 3, replaced 1 placeholders, 1 still missing.',
            },
        })
    );

    await page.goto('/books');
    await page.getByRole('button', { name: 'Account' }).click();
    const menu = page.locator('.account-menu');
    await expect(menu).toBeVisible();
    await menu.getByText('Fill missing covers', { exact: true }).click();

    await expect(page.locator('.job-indicator')).toHaveText(
        'Checked 5 book(s) without a cover: filled 3, replaced 1 placeholders, 1 still missing.'
    );
});
