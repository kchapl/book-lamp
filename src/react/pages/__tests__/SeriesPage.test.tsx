/**
 * The Series page.
 *
 * A series is a name on each Book rather than a record, so the page is the Books
 * the API returns: the order is the API's, and what this page owes the reader is
 * links into each Book plus enough state to see where they are in the series —
 * including the volumes they have not started, which have no Reading Status.
 */
import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import SeriesPage from '../SeriesPage';
import { getSeriesPage } from '../../services/api';
import type { Book } from '../../types';

vi.mock('../../services/api', () => ({
    getSeriesPage: vi.fn(),
}));

const page = vi.mocked(getSeriesPage);

const books: Book[] = [
    {
        id: 1,
        title: 'Leviathan Wakes',
        author: 'James S. A. Corey',
        publication_year: 2011,
        latest_status: 'Completed',
    },
    {
        id: 2,
        title: "Caliban's War",
        author: 'James S. A. Corey',
        publication_year: 2012,
        in_reading_list: true,
    },
    {
        id: 3,
        title: "Abaddon's Gate",
        author: 'James S. A. Corey',
        publication_year: 2013,
    },
];

const renderPage = (path = '/series/The%20Expanse') =>
    render(
        <MemoryRouter initialEntries={[path]}>
            <Routes>
                <Route path="/series/:seriesSlug" element={<SeriesPage />} />
            </Routes>
        </MemoryRouter>
    );

beforeEach(() => {
    vi.clearAllMocks();
});

describe('SeriesPage', () => {
    it('names the series and lists its Books in the order the API gave them', async () => {
        page.mockResolvedValue({ series_name: 'The Expanse', books });

        renderPage();

        await waitFor(() => expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('The Expanse'));

        const titles = screen.getAllByRole('link', { name: /Leviathan Wakes|Caliban's War|Abaddon's Gate/ });
        expect(titles.map((link) => link.textContent)).toEqual([
            'Leviathan Wakes',
            "Caliban's War",
            "Abaddon's Gate",
        ]);
        expect(screen.getByText('3 books')).toBeInTheDocument();
    });

    it('links each Book to its detail page', async () => {
        page.mockResolvedValue({ series_name: 'The Expanse', books });

        renderPage();

        const link = await screen.findByRole('link', { name: 'Leviathan Wakes' });
        expect(link).toHaveAttribute('href', '/books/1');
    });

    it('shows each Book its reading state, and marks the ones with no Reading at all', async () => {
        page.mockResolvedValue({ series_name: 'The Expanse', books });

        renderPage();

        await screen.findByText('Leviathan Wakes');

        expect(screen.getByText('Completed')).toBeInTheDocument();
        expect(screen.getByText('On Reading List')).toBeInTheDocument();
        // The third Book is unread and unqueued: listed, with no state claimed.
        expect(screen.getAllByText(/Completed|On Reading List/)).toHaveLength(2);
    });

    it('asks the API for the name the route decoded', async () => {
        page.mockResolvedValue({ series_name: 'Mistborn: Era 1', books: [] });

        renderPage('/series/Mistborn%3A%20Era%201');

        await waitFor(() => expect(page).toHaveBeenCalledWith('Mistborn: Era 1'));
    });

    it('reports a series no Book carries as not found', async () => {
        page.mockRejectedValue(new Error('HTTP 404: Series not found'));

        renderPage('/series/The%20Silmarillion');

        expect(await screen.findByText('Series not found')).toBeInTheDocument();
    });
});
