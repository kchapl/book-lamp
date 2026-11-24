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
import type { Book, BookMatch } from '../../types';

// The scanner library reaches for the camera; stub it out. It must be a real
// constructor: AddBookPage does `new Html5Qrcode(...)`, and an arrow-function
// mock throws there, which the page swallows into its error state. The decode
// callback is kept so a test can deliver a scan.
const scanner = vi.hoisted(() => ({
    decode: null as ((text: string) => void) | null,
}));

vi.mock('html5-qrcode', () => ({
    Html5Qrcode: class {
        start = vi.fn(
            async (_camera: unknown, _config: unknown, onDecoded: (text: string) => void) => {
                scanner.decode = onDecoded;
            }
        );
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

/** Start the scanner and deliver one barcode, as the camera would. */
async function scan(isbn: string) {
    fireEvent.click(button(/scan barcode/i));
    await waitFor(() => expect(scanner.decode).not.toBeNull());
    await act(async () => {
        scanner.decode?.(isbn);
    });
    scanner.decode = null;
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

describe('AddBookPage layout', () => {
    it('captures the ISBN above the title-or-author search', () => {
        const { container } = renderPage();
        const isbn = container.querySelector('.isbn-section') as HTMLElement;
        const discover = container.querySelector('.discover-section') as HTMLElement;

        expect(isbn).not.toBeNull();
        expect(discover).not.toBeNull();
        // DOCUMENT_POSITION_FOLLOWING means the discovery search renders after
        // the ISBN block, which is the order a reader reads.
        expect(
            isbn.compareDocumentPosition(discover) & Node.DOCUMENT_POSITION_FOLLOWING
        ).toBeTruthy();
    });

    it('points the ISBN helper text at the form, not at the search', () => {
        renderPage();

        const host = field('isbn') as (HTMLElement & { supportingText?: string }) | null;
        const copy = host?.getAttribute('supporting-text') ?? host?.supportingText ?? '';

        expect(copy).toMatch(/title and author form below/i);
        expect(copy).not.toMatch(/enter the title and author below/i);
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
                subtitle: 'Book One of the Dune Chronicles',
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
                subtitle: 'Book One of the Dune Chronicles',
                author: 'Frank Herbert',
                isbn: '9780441172719',
                publication_year: 1965,
            })
        );
        await waitFor(() =>
            expect(screen.getByText('destination:/books/7')).toBeInTheDocument()
        );
    });

    it('tells two editions of one work apart instead of listing a duplicate', async () => {
        discover.mockResolvedValue([
            {
                title: 'A History of England in 100 Places',
                author: 'John Julius Norwich',
                publication_year: 2011,
                publisher: 'John Murray',
                isbn13: '9781848549234',
            },
            {
                title: 'A History of England in 100 Places',
                subtitle: 'From Stonehenge to the Gherkin',
                author: 'John Julius Norwich',
                publication_year: 2011,
                publisher: 'John Murray',
                isbn13: '9781848549241',
            },
        ]);

        renderPage();
        typeInto('discover-query', 'A history of England in 100 places');
        fireEvent.click(button(/^search$/i));

        // The subtitle gets its own line, so the second row reads as the same
        // book with a subtitle rather than as the title repeated.
        expect(await screen.findByText('From Stonehenge to the Gherkin')).toBeInTheDocument();
        // Each row says which ISBN it would add. That is the only difference a
        // reader could act on, since author, year and publisher agree.
        expect(screen.getByText('ISBN 9781848549234')).toBeInTheDocument();
        expect(screen.getByText('ISBN 9781848549241')).toBeInTheDocument();
    });

    it('does not number rows the ISBN already tells apart', async () => {
        // Two editions can agree on title, author, year and publisher. The ISBN
        // is on the identity line for the reader to check a copy against, so it
        // separates the rows without help.
        discover.mockResolvedValue([
            {
                title: 'Dune',
                author: 'Frank Herbert',
                publication_year: 1965,
                publisher: 'Chilton',
                isbn13: '9780441172719',
            },
            {
                title: 'Dune',
                author: 'Frank Herbert',
                publication_year: 1965,
                publisher: 'Chilton',
                isbn13: '9780593099322',
            },
        ]);

        renderPage();
        typeInto('discover-query', 'Dune');
        fireEvent.click(button(/^search$/i));

        expect(await screen.findByText('ISBN 9780441172719')).toBeInTheDocument();
        expect(screen.getByText('ISBN 9780593099322')).toBeInTheDocument();
        expect(screen.queryByText(/of 2/)).not.toBeInTheDocument();
    });

    it('numbers records that agree on the ISBN and every detail', async () => {
        // Nothing in the row separates these records, so list position is all
        // there is to name — and the label says position, not edition.
        discover.mockResolvedValue([
            {
                title: 'Dune',
                author: 'Frank Herbert',
                publication_year: 1965,
                publisher: 'Chilton',
                isbn13: '9780441172719',
            },
            {
                title: 'Dune',
                author: 'Frank Herbert',
                publication_year: 1965,
                publisher: 'Chilton',
                isbn13: '9780441172719',
            },
        ]);

        renderPage();
        typeInto('discover-query', 'Dune');
        fireEvent.click(button(/^search$/i));

        expect(await screen.findByText(/Option 1 of 2/)).toBeInTheDocument();
        expect(screen.getByText(/Option 2 of 2/)).toBeInTheDocument();
    });

    it('shows the subtitle the provider stored, not a split of the title', async () => {
        discover.mockResolvedValue([
            {
                title: 'Piranesi',
                subtitle: 'A Novel',
                author: 'Susanna Clarke',
                isbn13: '9781635575637',
            },
        ]);

        renderPage();
        typeInto('discover-query', 'Piranesi');
        fireEvent.click(button(/^search$/i));

        expect(await screen.findByText('Piranesi')).toBeInTheDocument();
        expect(screen.getByText('A Novel')).toBeInTheDocument();
    });

    it('leaves a combined title whole when the provider supplied no subtitle', async () => {
        // No surface splits a title at render: where a provider gave one string,
        // that is the title until the Book is stored by the shared rule.
        discover.mockResolvedValue([
            { title: 'Re: Zero', author: 'Tappei Nagatsuki', isbn13: '9780316395344' },
        ]);

        renderPage();
        typeInto('discover-query', 'Re Zero');
        fireEvent.click(button(/^search$/i));

        expect(await screen.findByText('Re: Zero')).toBeInTheDocument();
        expect(screen.queryByText('Zero')).not.toBeInTheDocument();
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

    it('lets the newer query win and ignores the answer to the replaced one', async () => {
        const pending: Record<string, (books: BookMatch[]) => void> = {};
        discover.mockImplementation(
            (query: string) =>
                new Promise<BookMatch[]>((resolve) => {
                    pending[query] = resolve;
                })
        );

        renderPage();
        typeInto('discover-query', 'Dune');
        fireEvent.click(button(/^search$/i));
        await waitFor(() => expect(discover).toHaveBeenCalledWith('Dune'));

        // The reader edits the field and presses Enter before the first answer
        // lands. The newer search must run rather than be silently dropped.
        typeInto('discover-query', 'Foundation');
        fireEvent.keyDown(field('discover-query') as HTMLElement, { key: 'Enter' });
        await waitFor(() => expect(discover).toHaveBeenCalledWith('Foundation'));

        // The Dune answer is stale; painting it would show Dune results under
        // the Foundation query that replaced it.
        await act(async () => {
            pending['Dune']([
                { title: 'Dune Messiah', author: 'Frank Herbert', isbn13: '9780593098233' },
            ]);
        });
        expect(screen.queryByText('Dune Messiah')).not.toBeInTheDocument();

        await act(async () => {
            pending['Foundation']([
                { title: 'Foundation and Empire', author: 'Isaac Asimov', isbn13: '9780553293371' },
            ]);
        });
        expect(await screen.findByText('Foundation and Empire')).toBeInTheDocument();
        // The stale answer must not have left the search stuck in progress.
        expect(screen.queryByText(/searching\.\.\./i)).not.toBeInTheDocument();
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

    it('ignores a failure that answers for the ISBN the reader replaced', async () => {
        let failLookup: ((error: Error) => void) | undefined;
        lookup.mockImplementation(
            () =>
                new Promise<Book | null>((_resolve, reject) => {
                    failLookup = reject;
                })
        );

        const { container } = renderPage();
        await doLookup('9781529339604');
        await waitFor(() => expect(lookup).toHaveBeenCalledWith('9781529339604'));

        // The reader corrects the ISBN before the first lookup fails; that
        // failure is not about the ISBN now in the field.
        typeInto('isbn', '9780306406157');
        await act(async () => {
            failLookup?.(new Error('HTTP 502: Lookup failed'));
        });

        expect(screen.queryByText(/could not look up/i)).not.toBeInTheDocument();
        // Nor does it open manual entry for a Book the reader has not asked to
        // fill in by hand.
        expect(container.querySelector('.add-book-form')).toBeNull();
    });
});


describe('AddBookPage covers', () => {
    it('keeps the cover an ISBN lookup found without a title or author', async () => {
        lookup.mockResolvedValue({
            isbn13: '9781529339604',
            thumbnail_url: 'https://covers.example/9781529339604-M.jpg',
            cover_url: 'https://covers.example/9781529339604-L.jpg',
        } as never);
        create.mockResolvedValue({ id: 9 } as never);

        const { container } = renderToBook();
        await doLookup('9781529339604');

        // The lookup knows the cover but not the title, so the reader types it.
        await waitFor(() => expect(field('title')).toBeInTheDocument());
        typeInto('title', 'A History of England in 100 Places');
        typeInto('author', 'Philip Wilkinson');

        // A custom element is not a native submit button, so submit the form
        // itself, as the other add-form tests do.
        await act(async () => {
            fireEvent.submit(container.querySelector('.add-book-form') as HTMLFormElement);
        });

        expect(create).toHaveBeenCalledTimes(1);
        expect(create).toHaveBeenCalledWith(
            expect.objectContaining({
                isbn: '9781529339604',
                thumbnail_url: 'https://covers.example/9781529339604-M.jpg',
                cover_url: 'https://covers.example/9781529339604-L.jpg',
            })
        );
    });

    it('does not send a cover whose lookup answered for the replaced ISBN', async () => {
        let answerLookup: ((book: Book | null) => void) | undefined;
        lookup.mockImplementation(
            () =>
                new Promise<Book | null>((resolve) => {
                    answerLookup = resolve;
                })
        );
        create.mockResolvedValue({ id: 9 } as never);

        const { container } = renderToBook();
        await doLookup('9781529339604');
        await waitFor(() => expect(lookup).toHaveBeenCalledWith('9781529339604'));

        // The reader corrects the ISBN while the first lookup is still out; its
        // answer, image included, belongs to the ISBN it was asked about.
        typeInto('isbn', '9780306406157');
        await act(async () => {
            answerLookup?.({
                isbn13: '9781529339604',
                thumbnail_url: 'https://covers.example/old-M.jpg',
                cover_url: 'https://covers.example/old-L.jpg',
            } as never);
        });

        // The lookups answer for their own ISBN, so this one leaves the form
        // closed; the reader opens it to type the details for the new ISBN.
        fireEvent.click(button(/enter title & author/i));
        typeInto('title', 'A Book');
        typeInto('author', 'Somebody');
        await act(async () => {
            fireEvent.submit(container.querySelector('.add-book-form') as HTMLFormElement);
        });

        expect(create).toHaveBeenCalledTimes(1);
        const sent = create.mock.calls[0][0] as {
            isbn?: string;
            thumbnail_url?: string;
            cover_url?: string;
        };
        expect(sent.isbn).toBe('9780306406157');
        expect(sent.thumbnail_url).toBeUndefined();
        expect(sent.cover_url).toBeUndefined();
    });

    it('does not send the previous cover after scanning a different ISBN', async () => {
        lookup.mockImplementation(async (value) =>
            value === '9781529339604'
                ? ({
                      isbn13: '9781529339604',
                      thumbnail_url: 'https://covers.example/old-M.jpg',
                      cover_url: 'https://covers.example/old-L.jpg',
                  } as never)
                : null
        );
        create.mockResolvedValue({ id: 9 } as never);

        const { container } = renderToBook();
        await doLookup('9781529339604');
        await waitFor(() => expect(screen.getByText(/found a cover/i)).toBeInTheDocument());

        // A scan replaces the ISBN while the old cover stays tied to the one it
        // was looked up for, and the scan's own lookup finds nothing: the old
        // image must not be sent under the scanned ISBN.
        await scan('9780306406157');

        typeInto('title', 'A Book');
        typeInto('author', 'Somebody');
        await act(async () => {
            fireEvent.submit(container.querySelector('.add-book-form') as HTMLFormElement);
        });

        expect(create).toHaveBeenCalledTimes(1);
        const sent = create.mock.calls[0][0] as {
            isbn?: string;
            thumbnail_url?: string;
            cover_url?: string;
        };
        expect(sent.isbn).toBe('9780306406157');
        expect(sent.thumbnail_url).toBeUndefined();
        expect(sent.cover_url).toBeUndefined();
    });

    it('carries the cover of the edition the title and author matched', async () => {
        findMatches.mockResolvedValue([
            {
                isbn13: '9781635575637',
                title: 'Piranesi',
                author: 'Susanna Clarke',
                thumbnail_url: 'https://covers.example/piranesi.jpg',
                cover_url: 'https://covers.example/piranesi-L.jpg',
            },
        ]);
        create.mockResolvedValue({ id: 9 } as never);

        const { container } = renderToBook();
        fireEvent.click(button(/enter title & author/i));
        typeInto('title', 'Piranesi');
        typeInto('author', 'Susanna Clarke');
        fireEvent.click(button(/find isbn from title & author/i));
        await waitFor(() => expect(field('isbn')?.value).toBe('9781635575637'));

        await act(async () => {
            fireEvent.submit(container.querySelector('.add-book-form') as HTMLFormElement);
        });

        expect(create).toHaveBeenCalledTimes(1);
        expect(create).toHaveBeenCalledWith(
            expect.objectContaining({
                isbn: '9781635575637',
                thumbnail_url: 'https://covers.example/piranesi.jpg',
                cover_url: 'https://covers.example/piranesi-L.jpg',
            })
        );
    });
});

describe('AddBookPage subjects', () => {
    const subjects = [
        { category: 'HISTORY / Europe', main: 'HISTORY', sub: 'Europe' },
        { category: 'MURDER', main: 'MURDER', sub: null },
    ];

    const submit = async (container: HTMLElement) => {
        await act(async () => {
            fireEvent.submit(container.querySelector('.add-book-form') as HTMLFormElement);
        });
    };

    it('sends the subjects an ISBN lookup found', async () => {
        lookup.mockResolvedValue({
            isbn13: '9781529339604',
            title: 'A History of England in 100 Places',
            author: 'Philip Wilkinson',
            subjects,
        } as never);
        create.mockResolvedValue({ id: 9 } as never);

        const { container } = renderToBook();
        await doLookup('9781529339604');
        await waitFor(() => expect(field('title')?.value).toBe('A History of England in 100 Places'));

        await submit(container);

        expect(create).toHaveBeenCalledWith(expect.objectContaining({ isbn: '9781529339604', subjects }));
    });

    it('does not send subjects whose lookup answered for the replaced ISBN', async () => {
        lookup.mockResolvedValue({
            isbn13: '9781529339604',
            title: 'A History of England in 100 Places',
            author: 'Philip Wilkinson',
            subjects,
        } as never);
        create.mockResolvedValue({ id: 9 } as never);

        const { container } = renderToBook();
        await doLookup('9781529339604');
        await waitFor(() => expect(field('title')?.value).toBe('A History of England in 100 Places'));

        // The reader corrects the ISBN after the answer arrived; its subjects
        // belong to the edition that was asked about.
        typeInto('isbn', '9780306406157');
        await submit(container);

        const sent = create.mock.calls[0][0] as { isbn?: string; subjects?: unknown };
        expect(sent.isbn).toBe('9780306406157');
        expect(sent.subjects).toBeUndefined();
    });

    it('saves the subjects of an edition chosen by Find ISBN', async () => {
        findMatches.mockResolvedValue([
            {
                isbn13: '9781529339604',
                title: 'A History of England in 100 Places',
                author: 'Philip Wilkinson',
                subjects,
            },
        ]);
        create.mockResolvedValue({ id: 9 } as never);

        const { container } = renderToBook();
        fireEvent.click(button(/enter title & author/i));
        typeInto('title', 'A History of England in 100 Places');
        typeInto('author', 'Philip Wilkinson');
        fireEvent.click(button(/find isbn from title & author/i));
        await waitFor(() => expect(field('isbn')?.value).toBe('9781529339604'));

        await submit(container);

        expect(create).toHaveBeenCalledWith(expect.objectContaining({ isbn: '9781529339604', subjects }));
    });
});
