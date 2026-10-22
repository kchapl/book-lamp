/**
 * BookDetailPage's "Add reading" form.
 *
 * The API requires a start date, and a Reading that has ended must also carry an
 * end date (see book_lamp/utils/readings.py). The form used to send neither, so
 * every submission came back 400 and the failure was swallowed into
 * console.error. These tests therefore assert on both halves: the payload the
 * form sends, and that a rejection actually reaches the reader.
 *
 * Like AddBookPage, this page drives Material Web controls, so fields are
 * addressed by the id the page gives the host element and buttons by their
 * slotted label.
 */
import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import BookDetailPage from '../BookDetailPage';
import { createReading, getBookDetail } from '../../services/api';

vi.mock('../../services/api', () => ({
    getBookDetail: vi.fn(),
    updateBook: vi.fn(),
    deleteBook: vi.fn(),
    createReading: vi.fn(),
    addToReadingList: vi.fn(),
    removeFromReadingList: vi.fn(),
}));

const detail = vi.mocked(getBookDetail);
const create = vi.mocked(createReading);

const BUTTON_SELECTOR =
    'md-filled-button, md-filled-tonal-button, md-outlined-button, md-text-button';

const renderPage = () =>
    render(
        <MemoryRouter initialEntries={['/books/1']}>
            <Routes>
                <Route path="/books/:bookId" element={<BookDetailPage />} />
            </Routes>
        </MemoryRouter>
    );

/** A Material Web control host, addressed by the id the page gives it. */
const field = (id: string) => document.getElementById(id) as (HTMLElement & { value: string }) | null;

/** The Material Web button whose visible label matches. */
const button = (name: RegExp) => screen.getByText(name).closest(BUTTON_SELECTOR) as HTMLElement;

/** Type into a Material Web field: set the host value, then report the input. */
function typeInto(id: string, value: string) {
    const input = field(id);
    if (!input) throw new Error(`No field #${id}`);
    input.value = value;
    fireEvent.input(input);
}

/*
 * There is deliberately no test here for an open Reading (In Progress) sending
 * no end date. Material Web's select keeps its value in a shadow-root menu that
 * jsdom cannot drive: setting `.value` on the host does not stick and no
 * `change` payload arrives, so the form can only be exercised in the status it
 * starts in. That branch is covered by `src/react/utils/__tests__/reading.test.ts`
 * against the same `readingPayload` this page calls.
 */

async function openAddReading() {
    await waitFor(() => expect(screen.getByText(/add reading/i)).toBeInTheDocument());
    fireEvent.click(button(/add reading/i));
    await waitFor(() => expect(field('record-start-date')).toBeInTheDocument());
}

beforeEach(() => {
    vi.clearAllMocks();
    detail.mockResolvedValue({ id: 1, title: 'Project Hail Mary', author: 'Andy Weir', readings: [] });
    create.mockResolvedValue({ id: 1, book_id: 1, status: 'Completed' });
});

describe('BookDetailPage add reading', () => {
    it('sends a start date and an end date for a Reading that has ended', async () => {
        renderPage();
        await openAddReading();

        typeInto('record-start-date', '2026-10-01');
        typeInto('record-end-date', '2026-10-11');
        fireEvent.click(button(/^add$/i));

        await waitFor(() => expect(create).toHaveBeenCalledTimes(1));
        expect(create).toHaveBeenCalledWith(1, {
            status: 'Completed',
            start_date: '2026-10-01',
            end_date: '2026-10-11',
            rating: 5,
        });
    });

    it("links the Book's series to that series' page", async () => {
        detail.mockResolvedValue({
            id: 1,
            title: 'The Final Empire',
            author: 'Brandon Sanderson',
            series: 'Mistborn: Era 1',
            readings: [],
        });

        renderPage();

        const link = await screen.findByRole('link', { name: 'Mistborn: Era 1' });
        expect(link).toHaveAttribute('href', '/series/Mistborn%3A%20Era%201');
    });

    it('shows why the API refused a Reading instead of swallowing it', async () => {
        create.mockRejectedValue(new Error('HTTP 400: an end date is required when a Reading is Completed'));

        renderPage();
        await openAddReading();

        typeInto('record-start-date', '2026-10-01');
        fireEvent.click(button(/^add$/i));

        await waitFor(() => expect(screen.getByText(/end date is required/i)).toBeInTheDocument());
    });
});
