import { expect, test } from '@playwright/test';
import { resetAndSeed } from './seed';

/**
 * Filling in covers for the Books that have none (#370).
 *
 * The provider chain is a live network call, and the run's backend behaviour is
 * covered by the integration tests. What this journey pins is the screen: the
 * reader starts the run from My Books and sees the report it finishes with. The
 * job endpoints are answered here so the suite never depends on a provider.
 */
test.beforeEach(async ({ request }) => {
    await resetAndSeed(request);
});

test('starts the missing-covers run and shows its report', async ({ page }) => {
    await page.route('**/api/books/fetch-covers', (route) =>
        route.fulfill({ json: { job_id: 'e2e-covers' } })
    );
    await page.route('**/api/jobs/e2e-covers', (route) =>
        route.fulfill({
            json: {
                id: 'e2e-covers',
                status: 'completed',
                progress: 100,
                result: 'Checked 5 book(s) without a cover: filled 3, 2 still missing.',
            },
        })
    );

    await page.goto('/books');
    await page.getByRole('button', { name: 'Fill missing covers' }).click();

    await expect(page.getByRole('status')).toHaveText(
        'Checked 5 book(s) without a cover: filled 3, 2 still missing.'
    );
});
