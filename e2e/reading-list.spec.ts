import { expect, test, type Locator, type Page } from '@playwright/test';
import { resetAndSeed } from './seed';

test.beforeEach(async ({ request }) => {
    await resetAndSeed(request);
});

/**
 * The box Playwright measures, or a failure that names the element with none.
 *
 * `boundingBox()` answers null for an element that exists but has no layout box
 * yet — a Material Web host the library has not upgraded, on a loaded runner.
 * The visibility assertion is what absorbs that: it retries until the element
 * is laid out, so a null box afterwards is a real bug. The message names the
 * element, because "the rows have no layout" leaves the next run with nowhere
 * to start.
 */
async function measured(locator: Locator, description: string) {
    await expect(locator, `${description} should be visible before it is measured`).toBeVisible();
    const box = await locator.boundingBox();
    if (!box) throw new Error(`${description} has no layout after being reported visible`);
    return box;
}

/**
 * Leave the queue holding exactly A Wizard of Earthsea, then The Dispossessed.
 *
 * Queueing a Book from its page is how the list grows; starting one takes it out
 * of the queue and begins a Reading.
 */
async function queueTwoBooks(page: Page): Promise<void> {
    await page.goto('/books/2');

    // The click resolves when it is dispatched, not when the Book is queued.
    // Navigating on the click alone races the write, and the list then loads
    // before the Book is on it; waiting for the answer starts the journey from
    // a state that is known rather than hoped for.
    const queued = page.waitForResponse(
        (response) => response.url().includes('/add-to-reading-list') && response.ok()
    );
    await page.getByText('Add to reading list', { exact: true }).click();
    await queued;

    await page.goto('/reading-list');
    await expect(page.locator('.reading-list-item h2')).toHaveText([
        'Piranesi',
        'A Wizard of Earthsea',
        'The Dispossessed',
    ]);

    await page
        .locator('.reading-list-item', { hasText: 'Piranesi' })
        .getByText('Start Reading', { exact: true })
        .click();
    await expect(page.locator('.reading-list-item h2')).toHaveText([
        'A Wizard of Earthsea',
        'The Dispossessed',
    ]);
}

test('queues a Book, starts reading it, and reorders the queue', async ({ page }) => {
    await queueTwoBooks(page);

    // Dragging starts from the handle, not the row: the title and cover are
    // links, so a press on them must not pick the row up. Both boxes are
    // measured only once Playwright has seen the elements laid out, so a
    // missing box names the element rather than the list.
    const source = page.locator('.reading-list-item', { hasText: 'The Dispossessed' });
    const target = page.locator('.reading-list-item', { hasText: 'A Wizard of Earthsea' });

    const handle = await measured(
        source.locator('.drag-handle'),
        'The drag handle for "The Dispossessed"'
    );
    const targetBox = await measured(
        target,
        'The Reading List row for "A Wizard of Earthsea"'
    );

    await page.mouse.move(handle.x + handle.width / 2, handle.y + handle.height / 2);
    await page.mouse.down();
    await page.mouse.move(handle.x + handle.width / 2, targetBox.y - 8, { steps: 12 });
    await page.mouse.up();

    await expect(page.locator('.reading-list-item h2')).toHaveText([
        'The Dispossessed',
        'A Wizard of Earthsea',
    ]);

    // The order is persisted, not just painted: the reload is what proves the
    // new order reached the server rather than only the optimistic override.
    await page.reload();
    await expect(page.locator('.reading-list-item h2')).toHaveText([
        'The Dispossessed',
        'A Wizard of Earthsea',
    ]);
});
