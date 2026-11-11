import { expect, type Page } from '@playwright/test';

/**
 * Wait until the page has stopped showing a loading state and the local font
 * has loaded. Screenshots are never taken over a skeleton.
 */
export async function settle(page: Page): Promise<void> {
    await expect(page.locator('.loading, .page-loading, [aria-busy="true"]')).toHaveCount(0);
    await page.evaluate(async () => {
        await document.fonts.ready;
    });
}

/**
 * Capture a screen against its committed baseline.
 *
 * The footer carries the current year, which is the one piece of the shell that
 * changes without the data changing; it is hidden so the baseline encodes the
 * layout rather than the calendar.
 */
export async function expectScreenshot(page: Page, name: string): Promise<void> {
    await settle(page);
    await page.addStyleTag({ content: '.site-footer { visibility: hidden !important; }' });
    await expect(page).toHaveScreenshot(name, { fullPage: true });
}

/** Type into a Material Web field by the id the page gives its host. */
export async function fillField(page: Page, id: string, value: string): Promise<void> {
    await page.locator(`#${id} input`).fill(value);
}

/** Choose an option from a Material Web select. */
export async function choose(page: Page, selectId: string, label: string): Promise<void> {
    await page.locator(`#${selectId}`).click();

    const byRole = page.getByRole('option', { name: label });
    if ((await byRole.count()) > 0) {
        await byRole.first().click();
        return;
    }

    // Some Material Web releases expose options only as slotted elements.
    await page.locator('md-select-option').filter({ hasText: label }).first().click();
}
