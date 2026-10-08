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
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import AddBookPage from '../../pages/AddBookPage';
import { lookupISBN } from '../../services/api';

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

const BUTTON_SELECTOR =
    'md-filled-button, md-filled-tonal-button, md-outlined-button, md-text-button';

const renderPage = () =>
    render(
        <MemoryRouter>
            <AddBookPage />
        </MemoryRouter>
    );

/** A Material Web text field host, addressed by the id the page gives it. */
const field = (id: string) =>
    document.getElementById(id) as (HTMLElement & { value: string }) | null;

/** The Material Web button whose visible label matches. */
const button = (name: RegExp) => screen.getByText(name).closest(BUTTON_SELECTOR) as HTMLElement;

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
