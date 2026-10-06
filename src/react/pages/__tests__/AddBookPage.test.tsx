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

const renderPage = () =>
    render(
        <MemoryRouter>
            <AddBookPage />
        </MemoryRouter>
    );

async function doLookup(isbn: string) {
    fireEvent.change(screen.getByPlaceholderText(/enter isbn/i), { target: { value: isbn } });
    fireEvent.click(screen.getByRole('button', { name: /lookup isbn/i }));
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

        fireEvent.click(screen.getByRole('button', { name: /scan barcode/i }));

        await waitFor(() => {
            expect(screen.getByRole('button', { name: /stop scanner/i })).toBeInTheDocument();
            expect(scannerContainer).toHaveStyle('display: block');
        });

        // The scanner must stay open. A failed `new Html5Qrcode()` or start()
        // flips scanning back off and shows an error, and the waitFor above can
        // catch that transient state before it reverts.
        await new Promise((resolve) => setTimeout(resolve, 0));
        expect(screen.getByRole('button', { name: /stop scanner/i })).toBeInTheDocument();
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
            expect(screen.getByLabelText(/title/i)).toHaveValue('The Body Keeps the Score');
        });
        expect(screen.getByLabelText(/author/i)).toHaveValue('Bessel van der Kolk');
    });

    it('falls back to manual entry when only partial data is returned', async () => {
        // A cover-only / ISBN-only result carries no title or author. The page
        // must still change so the user is not left staring at a blank form.
        lookup.mockResolvedValue({ id: 0, title: '', isbn13: '0143127741' });

        renderPage();
        await doLookup('0143127741');

        await waitFor(() => {
            expect(screen.getByLabelText(/title/i)).toBeInTheDocument();
        });
        expect(screen.getByText(/no details found/i)).toBeInTheDocument();
    });

    it('falls back to manual entry when the lookup fails', async () => {
        lookup.mockRejectedValue(new Error('HTTP 502: Lookup failed'));

        renderPage();
        await doLookup('9780306406157');

        await waitFor(() => {
            expect(screen.getByLabelText(/title/i)).toBeInTheDocument();
        });
        expect(screen.getByText(/could not look up/i)).toBeInTheDocument();
    });
});
