import { expect, test } from '@playwright/test';
import { choose } from './helpers';
import { resetAndSeed } from './seed';

test.beforeEach(async ({ request }) => {
    await resetAndSeed(request);
});

test('filters and sorts the Reading Log', async ({ page }) => {
    await page.goto('/history');

    const groupTitles = page.locator('.history-group .exhibit-title');
    await expect(groupTitles).toHaveText([
        'The Final Empire',
        'Project Hail Mary',
        'The Dispossessed',
    ]);
    await expect(page.locator('.history-group .exhibit-accession')).toHaveText(['2006', '2021', '1974']);
    // A Reading states its status on its own row; the exhibit does not repeat it.
    await expect(page.locator('.history-group .exhibit-meta')).toHaveCount(0);
    await expect(page.locator('.history-record .status-badge')).toHaveText([
        'In Progress',
        'Completed',
        'Completed',
    ]);
    await expect(page.locator('.history-record .dates').first()).toContainText('May');

    await choose(page, 'history-status', 'Completed');
    await expect(page).toHaveURL(/status=Completed/);
    await expect(groupTitles).toHaveText([
        'Project Hail Mary',
        'The Dispossessed',
    ]);

    await choose(page, 'history-rating', '5 Stars');
    await expect(page).toHaveURL(/min_rating=5/);
    await expect(groupTitles).toHaveText(['The Dispossessed']);

    await page.getByText('Clear Filters', { exact: true }).click();
    await expect(page).toHaveURL(/\/history$/);

    await choose(page, 'history-sort', 'Oldest First');
    await expect(page).toHaveURL(/sort=date_asc/);
    await expect(groupTitles).toHaveText([
        'The Dispossessed',
        'Project Hail Mary',
        'The Final Empire',
    ]);
});
