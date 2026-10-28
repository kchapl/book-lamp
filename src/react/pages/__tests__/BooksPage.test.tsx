/**
 * The books page's search field and the Enter key.
 *
 * The field is a Material Web control whose real input lives in a shadow root,
 * so the browser's implicit form submission never fires from it: pressing Enter
 * did nothing at all until the page handled the key itself. These tests drive
 * the host element the way the browser retargets the event, and assert the same
 * search runs once — not twice, and not differently from the button.
 */
import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import BooksPage from '../BooksPage';
import { getBooks, searchBooks } from '../../services/api';

vi.mock('../../services/api', () => ({
    getBooks: vi.fn(),
    searchBooks: vi.fn(),
}));

const list = vi.mocked(getBooks);
const search = vi.mocked(searchBooks);

const BUTTON_SELECTOR =
    'md-filled-button, md-filled-tonal-button, md-outlined-button, md-text-button';

/** Reports where the page has navigated, query string included. */
const Where: React.FC = () => {
    const location = useLocation();
    return <p>{`location:${location.pathname}${location.search}`}</p>;
};

const renderPage = () =>
    render(
        <MemoryRouter initialEntries={['/books']}>
            <Where />
            <Routes>
                <Route path="/books" element={<BooksPage />} />
            </Routes>
        </MemoryRouter>
    );

/** The search field's host, addressed by the id the page gives it. */
const searchField = () =>
    document.getElementById('book-search') as (HTMLElement & { value: string }) | null;

/** Type into the field: set the host value, then report the input. */
function typeInto(value: string) {
    const field = searchField();
    if (!field) throw new Error('No search field');
    field.value = value;
    fireEvent.input(field);
}

beforeEach(() => {
    vi.clearAllMocks();
    list.mockResolvedValue({
        books: [],
        sort: 'reading_date',
        sort_options: {},
        filters: {
            status: '',
            year: '',
            month: '',
            rating: '',
            category: '',
            sort: 'reading_date',
        },
        categories: [],
    });
    search.mockResolvedValue({ books: [], search_query: '' });
});

describe('BooksPage search', () => {
    it('runs the search when Enter is pressed in the field', async () => {
        renderPage();

        typeInto('dune');
        fireEvent.keyDown(searchField() as HTMLElement, { key: 'Enter' });

        await waitFor(() => expect(screen.getByText('location:/books?q=dune')).toBeInTheDocument());
        expect(search).toHaveBeenCalledTimes(1);
        expect(search).toHaveBeenCalledWith('dune');
    });

    it('trims what was typed, as the button does', async () => {
        renderPage();

        typeInto('  dune  ');
        fireEvent.keyDown(searchField() as HTMLElement, { key: 'Enter' });

        await waitFor(() => expect(screen.getByText('location:/books?q=dune')).toBeInTheDocument());
    });

    it('clears the search when Enter is pressed on an empty field', async () => {
        renderPage();

        fireEvent.keyDown(searchField() as HTMLElement, { key: 'Enter' });

        await waitFor(() => expect(screen.getByText('location:/books')).toBeInTheDocument());
        expect(search).not.toHaveBeenCalled();
    });

    it('leaves other keys alone', async () => {
        renderPage();
        // Let the initial fetch settle, so nothing updates state after the test.
        await waitFor(() => expect(list).toHaveBeenCalled());

        typeInto('dune');
        fireEvent.keyDown(searchField() as HTMLElement, { key: 'a' });

        expect(screen.getByText('location:/books')).toBeInTheDocument();
        expect(search).not.toHaveBeenCalled();
    });

    it('still searches when the form is submitted', async () => {
        // jsdom does not give a custom element the activation behaviour that
        // makes a type="submit" button press its form, so the submit event is
        // dispatched directly — that is what the Search button produces in a
        // browser.
        const { container } = renderPage();

        typeInto('dune');
        fireEvent.submit(container.querySelector('form') as HTMLFormElement);

        await waitFor(() => expect(screen.getByText('location:/books?q=dune')).toBeInTheDocument());
        expect(search).toHaveBeenCalledTimes(1);
    });
});
