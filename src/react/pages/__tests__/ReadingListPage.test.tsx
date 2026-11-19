/**
 * The Reading List's add action.
 *
 * The page had no way to add a Book: its empty state pointed at your books
 * in prose only, which is what made the capability read as missing. The action
 * now lands on the Add a Book form, which puts the new Book at the end of the
 * queue.
 *
 * Material Web buttons navigate from a click listener on the host element, and
 * the host carries no implicit ARIA role, so they are found by their slotted
 * label and clicked directly.
 */
import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import ReadingListPage from '../ReadingListPage';
import { getReadingList, removeFromReadingList, startReading } from '../../services/api';
import {
    CollectionRevisionProvider,
    useRefreshCollection,
} from '../../hooks/useCollectionRevision';
import type { ReadingListItem } from '../../types';

vi.mock('../../services/api', () => ({
    getReadingList: vi.fn(),
    reorderReadingList: vi.fn(),
    removeFromReadingList: vi.fn(),
    startReading: vi.fn(),
}));

const list = vi.mocked(getReadingList);
const remove = vi.mocked(removeFromReadingList);
const start = vi.mocked(startReading);

const BUTTON_SELECTOR =
    'md-filled-button, md-filled-tonal-button, md-outlined-button, md-text-button';

/** Reports where navigation landed, query string included. */
const Destination: React.FC = () => {
    const location = useLocation();
    return <p>{`destination:${location.pathname}${location.search}`}</p>;
};

const renderPage = () =>
    render(
        <MemoryRouter initialEntries={['/reading-list']}>
            <Routes>
                <Route path="/reading-list" element={<ReadingListPage />} />
                <Route path="/books/new" element={<Destination />} />
            </Routes>
        </MemoryRouter>
    );

/** The Material Web button whose visible label matches. */
const button = (name: RegExp) => screen.getByText(name).closest(BUTTON_SELECTOR) as HTMLElement;

const queuedBook: ReadingListItem = {
    id: 1,
    title: 'Piranesi',
    subtitle: 'A Novel',
    author: 'Susanna Clarke',
};

beforeEach(() => {
    vi.clearAllMocks();
});

describe('ReadingListPage row links', () => {
    it('links the title and the cover to the Book page', async () => {
        list.mockResolvedValue({
            books: [{ ...queuedBook, thumbnail_url: 'https://example.com/piranesi.jpg' }],
        });

        const { container } = renderPage();
        await waitFor(() => expect(screen.getByText('Piranesi')).toBeInTheDocument());

        const title = container.querySelector('.item-info h2 a') as HTMLAnchorElement;
        expect(title).toHaveAttribute('href', '/books/1');

        const cover = container.querySelector('.item-cover-link') as HTMLAnchorElement;
        expect(cover).toHaveAttribute('href', '/books/1');
        expect(cover).toHaveAccessibleName('Piranesi');
        // The image is decorative: the link already carries the Book's name.
        expect(container.querySelector('.item-cover-link img')).toHaveAttribute('alt', '');
    });

    it('shows the stored subtitle beneath the title', async () => {
        list.mockResolvedValue({ books: [queuedBook] });

        const { container } = renderPage();
        await waitFor(() => expect(screen.getByText('Piranesi')).toBeInTheDocument());

        expect(screen.getByText('A Novel')).toHaveClass('item-subtitle');
        expect(container.querySelector('.item-info h2')?.textContent).toBe('Piranesi');
    });

    it('does not make the placeholder cover a link', async () => {
        list.mockResolvedValue({ books: [queuedBook] });

        const { container } = renderPage();
        await waitFor(() => expect(screen.getByText('Piranesi')).toBeInTheDocument());

        expect(container.querySelector('.item-placeholder')?.closest('a')).toBeNull();
    });

    it('starts the Book from the row', async () => {
        list.mockResolvedValue({ books: [queuedBook] });

        renderPage();
        await waitFor(() => expect(screen.getByText('Piranesi')).toBeInTheDocument());

        fireEvent.click(button(/start reading/i));

        await waitFor(() => expect(start).toHaveBeenCalledWith(1));
    });

    it('removes the Book from the row', async () => {
        list.mockResolvedValue({ books: [queuedBook] });

        renderPage();
        await waitFor(() => expect(screen.getByText('Piranesi')).toBeInTheDocument());

        fireEvent.click(button(/remove/i));

        await waitFor(() => expect(remove).toHaveBeenCalledWith(1));
    });
});

describe('ReadingListPage background refresh', () => {
    const RefreshButton: React.FC = () => {
        const refreshCollection = useRefreshCollection();
        return <button onClick={refreshCollection}>Refresh collection</button>;
    };

    it('refetches the queue when a background run changes the collection', async () => {
        list.mockResolvedValue({ books: [queuedBook] });

        render(
            <MemoryRouter initialEntries={['/reading-list']}>
                <CollectionRevisionProvider>
                    <Routes>
                        <Route path="/reading-list" element={<ReadingListPage />} />
                    </Routes>
                    <RefreshButton />
                </CollectionRevisionProvider>
            </MemoryRouter>
        );

        await waitFor(() => expect(list).toHaveBeenCalledTimes(1));

        fireEvent.click(screen.getByText('Refresh collection'));

        await waitFor(() => expect(list).toHaveBeenCalledTimes(2));
    });
});

describe('ReadingListPage add action', () => {
    it('offers an add action when the list is empty, and queues the Book', async () => {
        list.mockResolvedValue({ books: [] });

        renderPage();
        await waitFor(() =>
            expect(screen.getByText(/your reading list is empty/i)).toBeInTheDocument()
        );

        fireEvent.click(button(/add a book/i));

        await waitFor(() =>
            expect(
                screen.getByText('destination:/books/new')
            ).toBeInTheDocument()
        );
    });

    it('offers the same action above a populated list', async () => {
        list.mockResolvedValue({ books: [queuedBook] });

        renderPage();
        await waitFor(() => expect(screen.getByText('Piranesi')).toBeInTheDocument());

        fireEvent.click(button(/add a book/i));

        await waitFor(() =>
            expect(
                screen.getByText('destination:/books/new')
            ).toBeInTheDocument()
        );
    });
});
