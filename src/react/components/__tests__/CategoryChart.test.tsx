/**
 * The Subjects treemap's tiles.
 *
 * A tile is a placard pinned to the bottom of a coloured block. Sizing that
 * block by the subject's share alone made a small tile shorter than its own
 * text, so the placard lost its first line — the subject name — and the tile
 * showed only a count and a share. The block is now floored at the height its
 * lines need, so the name is always drawn.
 */
import React from 'react';
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import CategoryChart from '../CategoryChart';

interface Category {
    label: string;
    count: number;
    subcategories: { name: string; count: number }[];
}

const renderChart = (categories: Category[], maxCount = 52) =>
    render(
        <MemoryRouter>
            <CategoryChart categories={categories} maxCount={maxCount} />
        </MemoryRouter>
    );

/** The first tile's placard, read by class because the hover tooltip repeats its text. */
const firstPlacard = (container: HTMLElement) => container.querySelector('.category-item-interactive')!;

describe('CategoryChart subject tiles', () => {
    it('names a subject that has subcategories, beside its count, share and hint', () => {
        const { container } = renderChart([
            { label: 'Fiction', count: 26, subcategories: [{ name: 'Fantasy', count: 8 }] },
            { label: 'History', count: 13, subcategories: [] },
        ]);

        const tile = firstPlacard(container);
        expect(tile.querySelector('.category-name')?.textContent).toBe('Fiction');
        expect(tile.querySelector('.category-count')?.textContent).toBe('26');
        expect(tile.querySelector('.category-percent')?.textContent).toBe('66.7%');
        expect(tile.querySelector('.category-expand-hint')?.textContent).toBe('Click to expand');
        expect(tile.querySelector('.category-link')).toHaveAttribute('href', '/books?category=Fiction');
    });

    it('draws a small subject at the height its own lines need', () => {
        const { container } = renderChart([{ label: 'Rare', count: 1, subcategories: [] }]);

        const block = container.querySelector('.category-block') as HTMLElement;
        // The share is tiny, but the placard still holds its name, count and share.
        expect(parseInt(block.style.minHeight, 10)).toBeGreaterThanOrEqual(96);
        expect(block.style.height).toBe('');
        expect(block.querySelector('.category-name')?.textContent).toBe('Rare');
    });

    it('keeps a long subject name in the tile rather than dropping it', () => {
        const name = 'A Very Long Subject Name That Would Overflow A Narrow Tile';
        const { container } = renderChart([{ label: name, count: 4, subcategories: [] }]);

        expect(container.querySelector('.category-name')?.textContent).toBe(name);
    });

    it('leaves the expand hint off a subject without subcategories', () => {
        const { container } = renderChart([{ label: 'History', count: 13, subcategories: [] }]);

        const tile = firstPlacard(container);
        expect(tile.querySelector('.category-name')?.textContent).toBe('History');
        expect(tile.querySelector('.category-expand-hint')).toBeNull();
        expect(screen.queryByText('Click to expand')).toBeNull();
    });
});
