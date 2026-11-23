/**
 * The Subjects treemap's tiles.
 *
 * A tile is a placard pinned to the bottom of a coloured block. The block used
 * to be given a share-sized inline `height`, which could be shorter than its
 * own text, so the placard lost its first line — the subject name — and the
 * tile showed only a count and a share. It now sizes to its content above the
 * CSS minimum. jsdom does no layout, so the rendered result is covered by the
 * dashboard screenshot; these tests pin the sizing contract and the lines.
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

const renderChart = (categories: Category[]) =>
    render(
        <MemoryRouter>
            <CategoryChart categories={categories} />
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

    it('does not pin a small subject to a share-sized height', () => {
        const { container } = renderChart([{ label: 'Rare', count: 1, subcategories: [] }]);

        const block = container.querySelector('.category-block') as HTMLElement;
        // A tiny share used to become an inline height shorter than the placard.
        expect(block.style.height).toBe('');
        expect(block.querySelector('.category-name')?.textContent).toBe('Rare');
        expect(block.querySelector('.category-count')?.textContent).toBe('1');
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
