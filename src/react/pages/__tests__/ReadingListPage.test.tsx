/**
 * The Reading List's add action.
 *
 * The page had no way to add a Book: its empty state pointed at the collection
 * in prose only, which is what made the capability read as missing. The action
 * now lands on the Add a Book form with the reading-list option already ticked,
 * so a reader who came from the list queues the Book on submit instead of
 * having to notice the checkbox.
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
import { getReadingList } from '../../services/api';
import type { ReadingListItem } from '../../types';

vi.mock('../../services/api', () => ({
    getReadingList: vi.fn(),
    reorderReadingList: vi.fn(),
    removeFromReadingList: vi.fn(),
    startReading: vi.fn(),
}));

const list = vi.mocked(getReadingList);

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
    author: 'Susanna Clarke',
};

beforeEach(() => {
    vi.clearAllMocks();
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
                screen.getByText('destination:/books/new?add_to_reading_list=1')
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
                screen.getByText('destination:/books/new?add_to_reading_list=1')
            ).toBeInTheDocument()
        );
    });
});
