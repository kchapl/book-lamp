/**
 * The Author page's action on an external result.
 *
 * The "From Open Library" section is only populated outside test mode, so this
 * test supplies the external results itself. An external result is not a
 * collection row and carries no id: the action has to create the Book from the
 * metadata already on screen rather than post a null id.
 *
 * Material Web buttons navigate and click from a listener on the host element,
 * so each is found by its slotted label and clicked directly.
 */
import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import AuthorPage from '../AuthorPage';
import { createBook, getAuthorPage } from '../../services/api';
import type { AuthorPage as AuthorPageData, Book, ExternalBook } from '../../types';

vi.mock('../../services/api', () => ({
    getAuthorPage: vi.fn(),
    createBook: vi.fn(),
}));

const authorPage = vi.mocked(getAuthorPage);
const create = vi.mocked(createBook);

const BUTTON_SELECTOR =
    'md-filled-button, md-filled-tonal-button, md-outlined-button, md-text-button';

const externalBook: ExternalBook = {
    id: null,
    title: 'Emma',
    author: 'Jane Austen',
    isbn13: '9780141439600',
    publication_year: 1815,
    publisher: 'John Murray',
};

const queuedBook: Book = {
    id: 7,
    title: 'Emma',
    author: 'Jane Austen',
    isbn13: '9780141439600',
    publication_year: 1815,
};

const page = (
    unread_books: ExternalBook[],
    reading_list_books: Book[] = []
): AuthorPageData => ({
    author_name: 'Jane Austen',
    read_books: [],
    reading_list_books,
    unread_books,
});

const renderPage = () =>
    render(
        <MemoryRouter initialEntries={['/author/jane-austen']}>
            <Routes>
                <Route path="/author/:authorSlug" element={<AuthorPage />} />
            </Routes>
        </MemoryRouter>
    );

/** The Material Web button whose visible label matches. */
const addButton = () =>
    screen.getByText('Add to Reading List').closest(BUTTON_SELECTOR) as HTMLElement;

beforeEach(() => {
    vi.clearAllMocks();
});

describe('AuthorPage external results', () => {
    it('creates the Book from the result and moves it onto the Reading List', async () => {
        authorPage
            .mockResolvedValueOnce(page([externalBook]))
            .mockResolvedValueOnce(page([], [queuedBook]));
        create.mockResolvedValue(queuedBook);

        renderPage();
        await screen.findByText('From Open Library (1)');

        fireEvent.click(addButton());

        await waitFor(() =>
            expect(create).toHaveBeenCalledWith({
                title: 'Emma',
                author: 'Jane Austen',
                isbn: '9780141439600',
                publication_year: 1815,
                thumbnail_url: undefined,
                publisher: 'John Murray',
                description: undefined,
            })
        );

        await waitFor(() =>
            expect(screen.queryByText('From Open Library (1)')).not.toBeInTheDocument()
        );
        expect(screen.getByText('Reading List (1)')).toBeInTheDocument();
        expect(screen.getByText('On Reading List')).toBeInTheDocument();
    });

    it('offers no add action for a result that carries no ISBN', async () => {
        authorPage.mockResolvedValue(page([{ ...externalBook, isbn13: undefined }]));

        renderPage();
        await screen.findByText('From Open Library (1)');

        expect(screen.queryByText('Add to Reading List')).not.toBeInTheDocument();
        expect(
            screen.getByText(/no isbn, so it cannot be added automatically/i)
        ).toBeInTheDocument();
        expect(create).not.toHaveBeenCalled();
    });

    it('tells the reader when the Book could not be added', async () => {
        authorPage.mockResolvedValue(page([externalBook]));
        create.mockRejectedValue(new Error('HTTP 500'));

        renderPage();
        await screen.findByText('From Open Library (1)');

        fireEvent.click(addButton());

        expect(await screen.findByRole('alert')).toHaveTextContent(
            /could not add “Emma” to your Reading List/i
        );
        expect(screen.getByText('From Open Library (1)')).toBeInTheDocument();
    });
});
