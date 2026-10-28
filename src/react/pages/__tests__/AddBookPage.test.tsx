/**
 * AddBookPage drives Material Web controls.
 *
 * Two things changed with that migration and shape this file:
 *
 * - Labels and placeholders live inside the component's shadow root, so
 *   `getByLabelText` / `getByPlaceholderText` can no longer see them. Fields
 *   are addressed by the id the page assigns the host element.
 * - The host carries no implicit ARIA role, so buttons are found by their
 *   slotted label text (slotted content stays in the light DOM) and then
 *   resolved to the nearest Material Web button.
 */
import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import AddBookPage from '../../pages/AddBookPage';
import { createBook, lookupISBN } from '../../services/api';

// The scanner library reaches for the camera; stub it out. It must be a real
// constructor: AddBookPage does `new Html5Qrcode(...)`, and an arrow-function
// mock throws there, which the page swallows into its error state.
vi.mock('html5-qrcode', () => ({
    Html5Qrcode: class {
        start = vi.fn().mockResolvedValue(undefined);
        stop = vi.fn().mockResolvedValue(undefined);
    },
}));

vi.mock('../../services/api', () => ({
    lookupISBN: vi.fn(),
    createBook: vi.fn(),
    addToReadingList: vi.fn(),
}));

const lookup = vi.mocked(lookupISBN);
const create = vi.mocked(createBook);

const BUTTON_SELECTOR =
    'md-filled-button, md-filled-tonal-button, md-outlined-button, md-text-button';

const renderPage = () =>
    render(
        <MemoryRouter>
            <AddBookPage />
        </MemoryRouter>
    );

const renderAt = (path: string) =>
    render(
        <MemoryRouter initialEntries={[path]}>
            <AddBookPage />
        </MemoryRouter>
    );

/** A Material Web text field host, addressed by the id the page gives it. */
const field = (id: string) =>
    document.getElementById(id) as (HTMLElement & { value: string }) | null;

/** The Material Web button whose visible label matches. */
const button = (name: RegExp) => screen.getByText(name).closest(BUTTON_SELECTOR) as HTMLElement;

/** The reading-list option, which only exists once the form is open. */
const checkbox = (container: HTMLElement) =>
    container.querySelector('md-checkbox') as (HTMLElement & { checked: boolean }) | null;

/** Type into a Material Web field: set the host value, then report the input. */
function typeInto(id: string, value: string) {
    const input = field(id);
    if (!input) throw new Error(`No field #${id}`);
    input.value = value;
    fireEvent.input(input);
}

async function doLookup(isbn: string) {
    typeInto('isbn', isbn);
    fireEvent.click(button(/lookup isbn/i));
}

beforeEach(() => {
    vi.clearAllMocks();
});

describe('AddBookPage barcode scanner', () => {
    it('opens the scanner when the Scan button is clicked', async () => {
        const { container } = renderPage();

        // The scanner container is hidden until scanning starts, so it is not in
        // the accessibility tree and cannot be queried by role.
        const scannerContainer = container.querySelector('.scanner-container') as HTMLElement;
        expect(scannerContainer).toHaveStyle('display: none');

        fireEvent.click(button(/scan barcode/i));

        await waitFor(() => {
            expect(screen.getByText(/stop scanner/i)).toBeInTheDocument();
            expect(scannerContainer).toHaveStyle('display: block');
        });

        // The scanner must stay open. A failed `new Html5Qrcode()` or start()
        // flips scanning back off and shows an error, and the waitFor above can
        // catch that transient state before it reverts.
        await new Promise((resolve) => setTimeout(resolve, 0));
        expect(screen.getByText(/stop scanner/i)).toBeInTheDocument();
        expect(screen.queryByText(/failed to start camera/i)).not.toBeInTheDocument();
    });
});

describe('AddBookPage reading-list option', () => {
    it('starts ticked when the Reading List sent the reader here', () => {
        const { container } = renderAt('/books/new?add_to_reading_list=1');

        fireEvent.click(button(/enter manually/i));

        expect(checkbox(container)?.checked).toBe(true);
    });

    it('starts unticked for every other entry point into the form', () => {
        const { container } = renderAt('/books/new');

        fireEvent.click(button(/enter manually/i));

        expect(checkbox(container)?.checked).toBe(false);
    });
});

describe('AddBookPage submit', () => {
    it('sends the ISBN to the create endpoint, which stores and de-duplicates on it', async () => {
        create.mockResolvedValue({ id: 7, title: 'Emma', author: 'Jane Austen' });

        const { container } = renderPage();
        fireEvent.click(button(/enter manually/i));
        typeInto('title', 'Emma');
        typeInto('author', 'Jane Austen');
        typeInto('isbn', '978-0-14-143960-0');

        // A custom element is not a native submit button, so submit the form
        // itself; the payload is what the endpoint contract depends on. The
        // handler creates the Book and then navigates, so let it finish inside
        // act rather than updating the router after the test has moved on.
        await act(async () => {
            fireEvent.submit(container.querySelector('form') as HTMLFormElement);
        });

        expect(create).toHaveBeenCalledWith({
            title: 'Emma',
            author: 'Jane Austen',
            publisher: undefined,
            publication_year: undefined,
            isbn: '9780141439600',
        });
    });

    it('refuses to submit without an ISBN, which is what identifies a Book', async () => {
        const { container } = renderPage();
        fireEvent.click(button(/enter manually/i));
        typeInto('title', 'Emma');
        typeInto('author', 'Jane Austen');

        await act(async () => {
            fireEvent.submit(container.querySelector('form') as HTMLFormElement);
        });

        expect(create).not.toHaveBeenCalled();
        expect(screen.getByText(/an isbn is required/i)).toBeInTheDocument();
    });
});

describe('AddBookPage ISBN lookup', () => {
    it('prefills the form when the lookup returns book details', async () => {
        lookup.mockResolvedValue({
            id: 0,
            title: 'The Body Keeps the Score',
            author: 'Bessel van der Kolk',
            publisher: 'Penguin Books',
            publication_year: 2015,
        });

        renderPage();
        await doLookup('9780143127741');

        await waitFor(() => {
            expect(field('title')?.value).toBe('The Body Keeps the Score');
        });
        expect(field('author')?.value).toBe('Bessel van der Kolk');
    });

    it('falls back to manual entry when only partial data is returned', async () => {
        // A cover-only / ISBN-only result carries no title or author. The page
        // must still change so the user is not left staring at a blank form.
        lookup.mockResolvedValue({ id: 0, title: '', isbn13: '0143127741' });

        renderPage();
        await doLookup('0143127741');

        await waitFor(() => {
            expect(field('title')).toBeInTheDocument();
        });
        expect(screen.getByText(/no details found/i)).toBeInTheDocument();
    });

    it('falls back to manual entry when the lookup fails', async () => {
        lookup.mockRejectedValue(new Error('HTTP 502: Lookup failed'));

        renderPage();
        await doLookup('9780306406157');

        await waitFor(() => {
            expect(field('title')).toBeInTheDocument();
        });
        expect(screen.getByText(/could not look up/i)).toBeInTheDocument();
    });
});
