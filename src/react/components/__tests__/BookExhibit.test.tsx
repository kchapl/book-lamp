/**
 * A Book card's title, when the stored title carries a subtitle.
 *
 * The split is presentation only: the heading announces the main title, and
 * the subtitle is supporting text inside the same card link.
 */
import React from 'react';
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import BookExhibit from '../BookExhibit';
import type { Book } from '../../types';

const book = (title: string): Book => ({ id: 1, title, author: 'An Author' });

const renderExhibit = (title: string, titleAs?: 'h2' | 'h3') =>
    render(
        <MemoryRouter>
            <BookExhibit book={book(title)} titleAs={titleAs} />
        </MemoryRouter>
    );

const mainTitle = 'A History of England in 100 Places';
const subtitle = 'From Stonehenge to the Gherkin';

describe('BookExhibit', () => {
    it('shows the subtitle beneath the main title, outside the heading', () => {
        renderExhibit(`${mainTitle}: ${subtitle}`);

        const heading = screen.getByRole('heading', { name: mainTitle });
        expect(heading.textContent).toBe(mainTitle);

        const supporting = screen.getByText(subtitle);
        expect(supporting.className).toBe('exhibit-subtitle');
        expect(supporting.closest('h3')).toBeNull();
    });

    it('keeps the requested heading level for the main title only', () => {
        renderExhibit(`Title: Subtitle`, 'h2');

        expect(screen.getByRole('heading', { level: 2, name: 'Title' })).toBeTruthy();
        expect(screen.queryByRole('heading', { name: 'Subtitle' })).toBeNull();
    });

    it('renders a Book with no separable subtitle as one heading, as before', () => {
        renderExhibit('Piranesi');

        expect(screen.getByRole('heading', { name: 'Piranesi' })).toBeTruthy();
        expect(document.querySelector('.exhibit-subtitle')).toBeNull();
    });

    it('leaves a title the rule refuses to split whole', () => {
        renderExhibit('Re: Zero');

        expect(screen.getByRole('heading', { name: 'Re: Zero' })).toBeTruthy();
        expect(document.querySelector('.exhibit-subtitle')).toBeNull();
    });
});
