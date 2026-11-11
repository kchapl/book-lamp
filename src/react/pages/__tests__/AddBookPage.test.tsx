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
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import AddBookPage from '../../pages/AddBookPage';
import { createBook, discoverBooks, findBooksByTitleAuthor, lookupISBN } from '../../services/api';

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
    findBooksByTitleAuthor: vi.fn(),
    discoverBooks: vi.fn(),
    createBook: vi.fn(),
    addToReadingList: vi.fn(),
}));

const lookup = vi.mocked(lookupISBN);
const findMatches = vi.mocked(findBooksByTitleAuthor);
const discover = vi.mocked(discoverBooks);
const create = vi.mocked(createBook);

/** Reports where the page navigated. */
const Destination: React.FC = () => {
    const location = useLocation();
    return <p>{`destination:${location.pathname}`}</p>;
};

const renderToBook = () =>
    render(
        <MemoryRouter initialEntries={['/books/new']}>
            <Routes>
                <Route path="/books/new" element={<AddBookPage />} />
                <Route path="/books/:bookId" element={<Destination />} />
            </Routes>
        </MemoryRouter>
    );

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

        fireEvent.click(button(/enter title & author/i));

        expect(checkbox(container)?.checked).toBe(true);
    });

    it('starts unticked for every other entry point into the form', () => {
        const { container } = renderAt('/books/new');

        fireEvent.click(button(/enter title & author/i));

        expect(checkbox(container)?.checked).toBe(false);
    });
});

describe('AddBookPage submit', () => {
    it('sends the ISBN to the create endpoint, which stores and de-duplicates on it', async () => {
        create.mockResolvedValue({ id: 7, title: 'Emma', author: 'Jane Austen' });

        const { container } = renderPage();
        fireEvent.click(button(/enter title & author/i));
        typeInto('title', 'Emma');
        typeInto('author', 'Jane Austen');
        typeInto('isbn', '978-0-14-143960-0');

        // A custom element is not a native submit button, so submit the form
        // itself; the payload is what the endpoint contract depends on. The
        // handler creates the Book and then navigates, so let it finish inside
        // act rather than updating the router after the test has moved on.
        await act(async () => {
            fireEvent.submit(container.querySelector('.add-book-form') as HTMLFormElement);
        });

        expect(create).toHaveBeenCalledWith({
            title: 'Emma',
            author: 'Jane Austen',
            publisher: undefined,
            publication_year: undefined,
            isbn: '9780141439600',
        });
    });

    it('finds the ISBN from the title and author when the form has none', async () => {
        // A reader who knows only the cover must still be able to add the Book:
        // the title and author are what the ISBN lookup needs.
        findMatches.mockResolvedValue([
            { title: 'Emma', author: 'Jane Austen', isbn13: '9780141439600' },
        ]);
        create.mockResolvedValue({ id: 7, title: 'Emma', author: 'Jane Austen' });

        const { container } = renderPage();
        fireEvent.click(button(/enter title & author/i));
        typeInto('title', 'Emma');
        typeInto('author', 'Jane Austen');

        await act(async () => {
            fireEvent.submit(container.querySelector('.add-book-form') as HTMLFormElement);
        });

        expect(findMatches).toHaveBeenCalledWith('Emma', 'Jane Austen');
        expect(create).toHaveBeenCalledWith({
            title: 'Emma',
            author: 'Jane Austen',
            publisher: undefined,
            publication_year: undefined,
            isbn: '9780141439600',
        });
    });

    it('offers the matching editions instead of picking one when several share the title', async () => {
        findMatches.mockResolvedValue([
            { title: 'Emma', author: 'Jane Austen', publisher: 'Penguin', isbn13: '9780141439600' },
            { title: 'Emma', author: 'Jane Austen', publisher: 'Oxford', isbn13: '9780141439587' },
        ]);

        const { container } = renderPage();
        fireEvent.click(button(/enter title & author/i));
        typeInto('title', 'Emma');
        typeInto('author', 'Jane Austen');

        await act(async () => {
            fireEvent.submit(container.querySelector('.add-book-form') as HTMLFormElement);
        });

        expect(create).not.toHaveBeenCalled();
        expect(screen.getByText(/several books match/i)).toBeInTheDocument();
        expect(screen.getByText(/9780141439587/)).toBeInTheDocument();
    });

    it('says so when nothing matches, rather than failing silently', async () => {
        findMatches.mockResolvedValue([]);

        const { container } = renderPage();
        fireEvent.click(button(/enter title & author/i));
        typeInto('title', 'A Book That Does Not Exist');
        typeInto('author', 'Nobody');

        await act(async () => {
            fireEvent.submit(container.querySelector('.add-book-form') as HTMLFormElement);
        });

        expect(create).not.toHaveBeenCalled();
        expect(screen.getByText(/no matching book found/i)).toBeInTheDocument();
    });

    it('fills the ISBN in from the title and author without submitting', async () => {
        findMatches.mockResolvedValue([
            { title: 'Emma', author: 'Jane Austen', publication_year: 1815, isbn13: '9780141439600' },
        ]);

        renderPage();
        fireEvent.click(button(/enter title & author/i));
        typeInto('title', 'Emma');
        typeInto('author', 'Jane Austen');
        fireEvent.click(button(/find isbn from title & author/i));

        await waitFor(() => {
            expect(field('isbn')?.value).toBe('9780141439600');
        });
        expect(field('year')?.value).toBe('1815');
    });

    it('names the lookup on the submit button when the ISBN is blank', () => {
        renderPage();
        fireEvent.click(button(/enter title & author/i));

        expect(button(/find isbn & add book/i)).toBeInTheDocument();
        expect(
            screen.getByText(/look for a matching edition and use its isbn/i)
        ).toBeInTheDocument();
    });
});

describe('AddBookPage discover search', () => {
    it('lists candidates by title or author and adds the chosen one', async () => {
        discover.mockResolvedValue([
            {
                title: 'Dune',
                author: 'Frank Herbert',
                publication_year: 1965,
                isbn13: '9780441172719',
            },
            {
                title: 'Dune Messiah',
                author: 'Frank Herbert',
                publication_year: 1969,
                isbn13: '9780593098233',
            },
        ]);
        create.mockResolvedValue({ id: 7, title: 'Dune' });

        renderToBook();
        typeInto('discover-query', 'Frank Herbert');
        fireEvent.click(button(/^search$/i));

        await waitFor(() => expect(screen.getByText('Dune Messiah')).toBeInTheDocument());
        expect(discover).toHaveBeenCalledWith('Frank Herbert');
        // A row carries the title, author, year and cover the reader needs to
        // tell one edition from another.
        expect(screen.getByText(/Frank Herbert · 1965/)).toBeInTheDocument();

        const row = screen.getByText('Dune').closest('.book-item') as HTMLElement;
        fireEvent.click(within(row).getByText(/add to reading list/i));

        await waitFor(() => expect(create).toHaveBeenCalledTimes(1));
        expect(create).toHaveBeenCalledWith(
            expect.objectContaining({
                title: 'Dune',
                author: 'Frank Herbert',
                isbn: '9780441172719',
                publication_year: 1965,
            })
        );
        await waitFor(() =>
            expect(screen.getByText('destination:/books/7')).toBeInTheDocument()
        );
    });

    it('queues the existing Book when the candidate is already owned', async () => {
        // The create endpoint de-duplicates on ISBN; the page makes the one
        // request and lands on the Book that already exists.
        discover.mockResolvedValue([
            {
                title: 'Dune',
                author: 'Frank Herbert',
                isbn13: '9780441172719',
            },
        ]);
        create.mockResolvedValue({ id: 2, title: 'Dune', author: 'Frank Herbert' });

        renderToBook();
        typeInto('discover-query', 'Dune');
        fireEvent.click(button(/^search$/i));

        await waitFor(() => expect(screen.getByText('Dune')).toBeInTheDocument());
        const row = screen.getByText('Dune').closest('.book-item') as HTMLElement;
        fireEvent.click(within(row).getByText(/add to reading list/i));

        await waitFor(() => expect(create).toHaveBeenCalledTimes(1));
        await waitFor(() =>
            expect(screen.getByText('destination:/books/2')).toBeInTheDocument()
        );
    });

    it('says so when nothing matches', async () => {
        discover.mockResolvedValue([]);

        renderPage();
        typeInto('discover-query', 'A Book That Does Not Exist');
        fireEvent.click(button(/^search$/i));

        expect(await screen.findByText(/no books found/i)).toBeInTheDocument();
        expect(create).not.toHaveBeenCalled();
    });

    it('says the search failed when the providers are unavailable', async () => {
        discover.mockRejectedValue(new Error('HTTP 502: Book search is unavailable right now'));

        renderPage();
        typeInto('discover-query', 'Dune');
        fireEvent.click(button(/^search$/i));

        expect(await screen.findByText(/could not search for books/i)).toBeInTheDocument();
        // The ISBN and manual paths are still there to fall back to.
        expect(button(/lookup isbn/i)).toBeInTheDocument();
        expect(button(/enter title & author/i)).toBeInTheDocument();
    });

    it('leaves the ISBN and manual entry paths in place', () => {
        renderPage();

        expect(button(/lookup isbn/i)).toBeInTheDocument();
        expect(button(/scan barcode/i)).toBeInTheDocument();
        expect(button(/enter title & author/i)).toBeInTheDocument();
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
