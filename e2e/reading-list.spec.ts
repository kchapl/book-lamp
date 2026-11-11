import { expect, test } from '@playwright/test';
import { resetAndSeed } from './seed';

test.beforeEach(async ({ request }) => {
    await resetAndSeed(request);
});

test('queues a Book, starts reading it, and reorders the queue', async ({ page }) => {
    // Queue a Book from its page, which is how the list grows.
    await page.goto('/books/2');
    await page.getByText('Add to reading list', { exact: true }).click();

    await page.goto('/reading-list');
    await expect(page.locator('.reading-list-item h2')).toHaveText([
        'Piranesi',
        'A Wizard of Earthsea',
        'The Dispossessed',
    ]);

    // Starting a Book removes it from the queue and begins a Reading.
    await page
        .locator('.reading-list-item', { hasText: 'Piranesi' })
        .getByText('Start Reading', { exact: true })
        .click();
    await expect(page.locator('.reading-list-item h2')).toHaveText([
        'A Wizard of Earthsea',
        'The Dispossessed',
    ]);

    // Dragging starts from the handle, not the row: the title and cover are
    // links, so a press on them must not pick the row up.
    const source = page.locator('.reading-list-item', { hasText: 'The Dispossessed' });
    const target = page.locator('.reading-list-item', { hasText: 'A Wizard of Earthsea' });

    const handle = await source.locator('.drag-handle').boundingBox();
    const targetBox = await target.boundingBox();
    if (!handle || !targetBox) throw new Error('Reading List rows have no layout');

    await page.mouse.move(handle.x + handle.width / 2, handle.y + handle.height / 2);
    await page.mouse.down();
    await page.mouse.move(handle.x + handle.width / 2, targetBox.y - 8, { steps: 12 });
    await page.mouse.up();

    await expect(page.locator('.reading-list-item h2')).toHaveText([
        'The Dispossessed',
        'A Wizard of Earthsea',
    ]);

    // The order is persisted, not just painted.
    await page.reload();
    await expect(page.locator('.reading-list-item h2')).toHaveText([
        'The Dispossessed',
        'A Wizard of Earthsea',
    ]);
});
