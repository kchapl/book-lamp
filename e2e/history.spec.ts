import { expect, test } from '@playwright/test';
import { choose } from './helpers';
import { resetAndSeed } from './seed';

test.beforeEach(async ({ request }) => {
    await resetAndSeed(request);
});

test('filters and sorts the Reading Log', async ({ page }) => {
    await page.goto('/history');

    await expect(page.locator('.group-title')).toHaveText([
        'The Final Empire',
        'Project Hail Mary',
        'The Dispossessed',
    ]);

    await choose(page, 'history-status', 'Completed');
    await expect(page).toHaveURL(/status=Completed/);
    await expect(page.locator('.group-title')).toHaveText([
        'Project Hail Mary',
        'The Dispossessed',
    ]);

    await choose(page, 'history-rating', '5 Stars');
    await expect(page).toHaveURL(/min_rating=5/);
    await expect(page.locator('.group-title')).toHaveText(['The Dispossessed']);

    await page.getByText('Clear Filters', { exact: true }).click();
    await expect(page).toHaveURL(/\/history$/);

    await choose(page, 'history-sort', 'Oldest First');
    await expect(page).toHaveURL(/sort=date_asc/);
    await expect(page.locator('.group-title')).toHaveText([
        'The Dispossessed',
        'Project Hail Mary',
        'The Final Empire',
    ]);
});
