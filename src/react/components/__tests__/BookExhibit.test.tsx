/**
 * A Book card's title and subtitle, as the Book stores them.
 *
 * The split is not made here: the heading is the stored title and the subtitle
 * is stored beside it, so the card, Series, Author and the Reading List all
 * show the same two parts.
 */
import React from 'react';
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import BookExhibit from '../BookExhibit';
import type { Book } from '../../types';

const renderExhibit = (book: Book, titleAs?: 'h2' | 'h3') =>
    render(
        <MemoryRouter>
            <BookExhibit book={book} titleAs={titleAs} />
        </MemoryRouter>
    );

const mainTitle = 'A History of England in 100 Places';
const subtitle = 'From Stonehenge to the Gherkin';

describe('BookExhibit', () => {
    it('shows the stored subtitle beneath the main title, outside the heading', () => {
        renderExhibit({ id: 1, title: mainTitle, subtitle, author: 'An Author' });

        const heading = screen.getByRole('heading', { name: mainTitle });
        expect(heading.textContent).toBe(mainTitle);

        const supporting = screen.getByText(subtitle);
        expect(supporting.className).toBe('exhibit-subtitle');
        expect(supporting.closest('h3')).toBeNull();
    });

    it('keeps the requested heading level for the main title only', () => {
        renderExhibit({ id: 1, title: 'Title', subtitle: 'Subtitle' }, 'h2');

        expect(screen.getByRole('heading', { level: 2, name: 'Title' })).toBeTruthy();
        expect(screen.queryByRole('heading', { name: 'Subtitle' })).toBeNull();
    });

    it('renders a Book with no subtitle as one heading, as before', () => {
        renderExhibit({ id: 1, title: 'Piranesi' });

        expect(screen.getByRole('heading', { name: 'Piranesi' })).toBeTruthy();
        expect(document.querySelector('.exhibit-subtitle')).toBeNull();
    });

    it('does not split a title that carries a separator but no stored subtitle', () => {
        // The rule ran when the Book was stored; the card never re-derives it.
        renderExhibit({ id: 1, title: 'Re: Zero' });

        expect(screen.getByRole('heading', { name: 'Re: Zero' })).toBeTruthy();
        expect(document.querySelector('.exhibit-subtitle')).toBeNull();
    });

    it('shows the publication year on its own accession line above the status row', () => {
        const { container } = renderExhibit({
            id: 1,
            title: 'London Parks',
            author: 'Hunter Davies',
            publication_year: 2022,
            latest_status: 'Completed',
        });

        const year = container.querySelector('.exhibit-accession');
        const meta = container.querySelector('.exhibit-meta');

        expect(year?.textContent).toBe('2022');
        expect(year?.closest('.exhibit-meta')).toBeNull();
        expect(meta?.textContent).toBe('Completed');
        expect(meta?.querySelector('.exhibit-accession')).toBeNull();
        expect(
            year!.compareDocumentPosition(meta!) & Node.DOCUMENT_POSITION_FOLLOWING
        ).toBeTruthy();
    });

    it('renders no accession line or status row when the Book has neither', () => {
        const { container } = renderExhibit({ id: 1, title: 'Piranesi' });

        expect(container.querySelector('.exhibit-accession')).toBeNull();
        expect(container.querySelector('.exhibit-meta')).toBeNull();
    });

    it('still shows the year when the Book has no Reading Status', () => {
        const { container } = renderExhibit({ id: 1, title: 'Piranesi', publication_year: 2020 });

        expect(container.querySelector('.exhibit-accession')?.textContent).toBe('2020');
        expect(container.querySelector('.exhibit-meta')).toBeNull();
    });
});
