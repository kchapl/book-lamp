import { expect, test } from '@playwright/test';
import { expectScreenshot } from './helpers';
import { resetAndSeed } from './seed';

test.beforeEach(async ({ request }) => {
    await resetAndSeed(request);
});

test('home', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('heading', { name: 'Your books.' })).toBeVisible();
    await expectScreenshot(page, 'home.png');
});

test('collection', async ({ page }) => {
    await page.goto('/books');
    // My Books carries the Books with a Reading Status; the two unread Books
    // in the seed belong to the Reading List instead.
    await expect(page.locator('.exhibit')).toHaveCount(3);
    await expectScreenshot(page, 'books.png');
});

test('book detail', async ({ page }) => {
    await page.goto('/books/2');
    await expect(page.getByRole('heading', { name: 'The Dispossessed' })).toBeVisible();
    await expectScreenshot(page, 'book-detail.png');
});

test('reading list', async ({ page }) => {
    await page.goto('/reading-list');
    await expect(page.locator('.reading-list-item')).toHaveCount(2);
    await expectScreenshot(page, 'reading-list.png');
});

test('dashboard', async ({ page }) => {
    await page.goto('/dashboard');
    await expect(page.getByRole('heading', { name: 'Your reading at a glance' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Most-read authors' })).toBeVisible();
    await expectScreenshot(page, 'dashboard.png');
});
