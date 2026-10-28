/**
 * BookDetailPage's Reading history: the "Add reading" form, and the per-row
 * edit and delete controls.
 *
 * The API requires a start date, and a Reading that has ended must also carry an
 * end date (see book_lamp/utils/readings.py). The form used to send neither, so
 * every submission came back 400 and the failure was swallowed into
 * console.error. These tests therefore assert on both halves: the payload the
 * form sends, and that a rejection actually reaches the reader.
 *
 * A Book whose Reading was In Progress had no way to record that it had
 * finished: the history rows were read-only, so the status could not be
 * corrected from the Book page. The rows now carry edit and delete controls,
 * wired to the routes the API client already wrapped.
 *
 * Like AddBookPage, this page drives Material Web controls, so fields are
 * addressed by the id the page gives the host element and buttons by their
 * slotted label. Two dialogs share a "Delete" label, so the reading dialog's
 * actions are addressed within that dialog.
 */
import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import BookDetailPage from '../BookDetailPage';
import { createReading, deleteReading, getBookDetail, updateBook, updateReading } from '../../services/api';

vi.mock('../../services/api', () => ({
    getBookDetail: vi.fn(),
    updateBook: vi.fn(),
    deleteBook: vi.fn(),
    createReading: vi.fn(),
    updateReading: vi.fn(),
    deleteReading: vi.fn(),
    addToReadingList: vi.fn(),
    removeFromReadingList: vi.fn(),
}));

const detail = vi.mocked(getBookDetail);
const save = vi.mocked(updateBook);
const create = vi.mocked(createReading);
const update = vi.mocked(updateReading);
const remove = vi.mocked(deleteReading);

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

/** A button inside the dialog carrying this headline. */
const dialogButton = (headline: string, name: RegExp) => {
    const dialog = screen.getByText(headline).closest('md-dialog') as HTMLElement;
    return within(dialog).getByText(name).closest(BUTTON_SELECTOR) as HTMLElement;
};

/** A button inside the row's edit form, which the page labels "Edit reading". */
const editFormButton = (name: RegExp) => {
    const form = screen.getByText(/edit reading/i).closest('.reading-form') as HTMLElement;
    return within(form).getByText(name).closest(BUTTON_SELECTOR) as HTMLElement;
};

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

/** The Book whose Reading is still open, which the issue is about. */
const openReading = {
    id: 11,
    book_id: 1,
    status: 'In Progress',
    start_date: '2026-10-01',
    rating: 0,
};

/** A Reading that has ended, so its form carries an end-date control. */
const completedReading = {
    id: 12,
    book_id: 1,
    status: 'Completed',
    start_date: '2026-10-01',
    end_date: '2026-10-11',
    rating: 5,
};

/** Open the row's edit form and wait for it to be filled in from the Reading. */
async function openEditReading() {
    await waitFor(() => expect(screen.getByLabelText(/edit reading of 2026-10-01/i)).toBeInTheDocument());
    fireEvent.click(screen.getByLabelText(/edit reading of 2026-10-01/i));
    await waitFor(() => expect(field('edit-record-start-date')).toBeInTheDocument());
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

describe('BookDetailPage edit book', () => {
    /** A Book two people wrote: its display string cannot be read back. */
    const coauthored = {
        id: 1,
        title: 'Good Omens',
        author: 'Neil Gaiman, Terry Pratchett',
        authors: ['Neil Gaiman', 'Terry Pratchett'],
        readings: [],
    };

    async function openEditBook() {
        await waitFor(() => expect(screen.getByText('Good Omens')).toBeInTheDocument());
        fireEvent.click(button(/^edit$/i));
        await waitFor(() => expect(field('edit-title')).toBeInTheDocument());
    }

    it('sends the names it was built from when the author text is untouched', async () => {
        detail.mockResolvedValue(coauthored);
        save.mockResolvedValue(undefined);

        renderPage();
        await openEditBook();

        typeInto('edit-title', 'Good Omens (1990)');
        fireEvent.click(button(/^save$/i));

        await waitFor(() => expect(save).toHaveBeenCalledTimes(1));
        expect(save).toHaveBeenCalledWith(
            1,
            expect.objectContaining({
                title: 'Good Omens (1990)',
                authors: ['Neil Gaiman', 'Terry Pratchett'],
            })
        );
    });

    it('lets the server read the text once the author is edited', async () => {
        detail.mockResolvedValue(coauthored);
        save.mockResolvedValue(undefined);

        renderPage();
        await openEditBook();

        typeInto('edit-author', 'Neil Gaiman');
        fireEvent.click(button(/^save$/i));

        await waitFor(() => expect(save).toHaveBeenCalledTimes(1));
        const payload = save.mock.calls[0][1] as Record<string, unknown>;
        expect(payload.author).toBe('Neil Gaiman');
        // New text that lists names is the server's to read, so the stale list
        // must not travel with it.
        expect(payload).not.toHaveProperty('authors');
    });
});

describe('BookDetailPage edit reading', () => {
    it('offers an edit control on a Reading in the history', async () => {
        detail.mockResolvedValue({ id: 1, title: 'Project Hail Mary', readings: [openReading] });

        renderPage();

        await waitFor(() =>
            expect(screen.getByLabelText(/edit reading of 2026-10-01/i)).toBeInTheDocument()
        );
    });

    it('pre-fills the form from the Reading it edits', async () => {
        detail.mockResolvedValue({ id: 1, title: 'Project Hail Mary', readings: [openReading] });

        renderPage();
        await openEditReading();

        expect(field('edit-record-start-date')?.value).toBe('2026-10-01');
        expect(field('edit-record-rating')?.value).toBe('0');
        // An open Reading has no end, so the form offers no end-date control.
        expect(field('edit-record-end-date')).not.toBeInTheDocument();
    });

    it('sends the edit to the reading route with the dates the form holds', async () => {
        detail.mockResolvedValue({ id: 1, title: 'Project Hail Mary', readings: [completedReading] });
        update.mockResolvedValue(undefined);

        renderPage();
        await openEditReading();

        typeInto('edit-record-end-date', '2026-10-20');
        fireEvent.click(editFormButton(/^save$/i));

        await waitFor(() => expect(update).toHaveBeenCalledTimes(1));
        // The status select cannot be driven in jsdom, so the Reading keeps the
        // status it was seeded with and takes the end date the form was given.
        expect(update).toHaveBeenCalledWith(12, {
            status: 'Completed',
            start_date: '2026-10-01',
            end_date: '2026-10-20',
            rating: 5,
        });
    });

    it('shows why the API refused the edit instead of swallowing it', async () => {
        detail.mockResolvedValue({ id: 1, title: 'Project Hail Mary', readings: [completedReading] });
        update.mockRejectedValue(new Error('HTTP 400: an end date is required when a Reading is Completed'));

        renderPage();
        await openEditReading();

        typeInto('edit-record-end-date', '');
        fireEvent.click(editFormButton(/^save$/i));

        await waitFor(() => expect(screen.getByText(/end date is required/i)).toBeInTheDocument());
    });

    it('closes the form when the edit is cancelled', async () => {
        detail.mockResolvedValue({ id: 1, title: 'Project Hail Mary', readings: [openReading] });

        renderPage();
        await openEditReading();

        fireEvent.click(editFormButton(/^cancel$/i));

        await waitFor(() =>
            expect(field('edit-record-start-date')).not.toBeInTheDocument()
        );
        expect(update).not.toHaveBeenCalled();
    });
});

describe('BookDetailPage delete reading', () => {
    it('deletes the Reading only after the reader confirms', async () => {
        detail.mockResolvedValue({ id: 1, title: 'Project Hail Mary', readings: [openReading] });
        remove.mockResolvedValue(undefined);

        renderPage();
        await waitFor(() =>
            expect(screen.getByLabelText(/delete reading of 2026-10-01/i)).toBeInTheDocument()
        );

        fireEvent.click(screen.getByLabelText(/delete reading of 2026-10-01/i));
        expect(remove).not.toHaveBeenCalled();

        fireEvent.click(dialogButton('Delete this reading?', /^delete$/i));

        await waitFor(() => expect(remove).toHaveBeenCalledWith(11));
    });

    it('leaves the Reading alone when the reader cancels', async () => {
        detail.mockResolvedValue({ id: 1, title: 'Project Hail Mary', readings: [openReading] });

        renderPage();
        await waitFor(() =>
            expect(screen.getByLabelText(/delete reading of 2026-10-01/i)).toBeInTheDocument()
        );

        fireEvent.click(screen.getByLabelText(/delete reading of 2026-10-01/i));
        fireEvent.click(dialogButton('Delete this reading?', /^cancel$/i));

        expect(remove).not.toHaveBeenCalled();
    });
});
