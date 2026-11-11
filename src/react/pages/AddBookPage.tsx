import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
    lookupISBN,
    findBooksByTitleAuthor,
    discoverBooks,
    createBook,
    addToReadingList,
} from '../services/api';
import { Button, Checkbox, TextField } from '../ui';
import type { BookMatch } from '../types';
import type { Html5Qrcode } from 'html5-qrcode';

const AddBookPage: React.FC = () => {
    const navigate = useNavigate();
    const [searchParams] = useSearchParams();
    const [isbn, setIsbn] = useState(searchParams.get('isbn') || '');
    const [title, setTitle] = useState('');
    const [author, setAuthor] = useState('');
    const [publisher, setPublisher] = useState('');
    const [year, setYear] = useState('');
    const [isbnError, setIsbnError] = useState<string | null>(null);
    const [isbnNotice, setIsbnNotice] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);
    const [showManualEntry, setShowManualEntry] = useState(false);
    // The editions a title-and-author search found. More than one means the
    // reader has to say which edition is theirs, so the choice is shown rather
    // than the first result being taken on their behalf.
    const [matches, setMatches] = useState<BookMatch[]>([]);
    // Books the free-text search found outside the collection. A reader who
    // does not have a Book yet needs to find it before they can add it, and
    // chooses from a list rather than having one guess made for them.
    const [discoverQuery, setDiscoverQuery] = useState('');
    const [discoveries, setDiscoveries] = useState<BookMatch[]>([]);
    const [discovering, setDiscovering] = useState(false);
    const [discoverError, setDiscoverError] = useState<string | null>(null);
    const [discoverNotice, setDiscoverNotice] = useState<string | null>(null);
    const [addingCandidate, setAddingCandidate] = useState<string | null>(null);
    // The Reading List links here with `add_to_reading_list=1`, so the option
    // starts ticked for a reader who came from the list to queue a Book.
    const [addToReadingListChecked, setAddToReadingListChecked] = useState(
        () => searchParams.get('add_to_reading_list') === '1'
    );
    const [scanning, setScanning] = useState(false);
    const [scannerError, setScannerError] = useState<string | null>(null);
    const scannerRef = useRef<HTMLDivElement>(null);
    const html5QrCodeRef = useRef<Html5Qrcode | null>(null);
    const discoverInFlight = useRef(false);
    const discoverRequest = useRef(0);

    useEffect(() => {
        const initialIsbn = searchParams.get('isbn');
        if (initialIsbn) {
            setIsbn(initialIsbn);
            handleLookup(initialIsbn);
        }
    }, [searchParams]);

    const startScanner = async () => {
        // Ensure scanner element is present; no early exit
        setScanning(true);
        setScannerError(null);
        
        try {
            // Load the barcode scanner lib lazily (~300KB) only when actually scanning
            const { Html5Qrcode } = await import('html5-qrcode');
            const html5QrCode = new Html5Qrcode('scanner-reader');
            html5QrCodeRef.current = html5QrCode;
            
            await html5QrCode.start(
                { facingMode: 'environment' },
                {
                    fps: 10,
                    qrbox: { width: 250, height: 150 }
                },
                (decodedText) => {
                    setIsbn(decodedText);
                    handleLookup(decodedText);
                    stopScanner();
                },
                () => {}
            );
        } catch (err) {
            console.error('Scanner error:', err);
            setScannerError('Failed to start camera. Please ensure camera permissions are granted.');
            setScanning(false);
        }
    };

    const stopScanner = async () => {
        if (html5QrCodeRef.current) {
            try {
                await html5QrCodeRef.current.stop();
                html5QrCodeRef.current = null;
            } catch (err) {
                console.error('Error stopping scanner:', err);
            }
        }
        setScanning(false);
    };

    const handleLookup = async (isbnToLookup: string) => {
        if (!isbnToLookup.trim()) return;
        
        const cleanIsbn = isbnToLookup.replace(/[-\s]/g, '');
        if (cleanIsbn.length !== 10 && cleanIsbn.length !== 13) {
            setIsbnError('Please enter a valid 10 or 13 digit ISBN');
            return;
        }

        setLoading(true);
        setIsbnError(null);
        setIsbnNotice(null);
        
        try {
            const book = await lookupISBN(cleanIsbn);
            // A partial result (e.g. only an ISBN and a cover) is not usable: it
            // carries no title or author, so the form below would stay hidden and
            // the page would appear unchanged. Treat that as "not found" and fall
            // back to manual entry so the user always gets somewhere to type.
            if (book && (book.title || book.author)) {
                setTitle(book.title || '');
                setAuthor(book.author || '');
                setPublisher(book.publisher || '');
                setYear(book.publication_year ? String(book.publication_year) : '');
            } else {
                setIsbnNotice('No details found for that ISBN. Fill them in below.');
                setShowManualEntry(true);
            }
        } catch (err) {
            console.error('Lookup error:', err);
            setIsbnNotice('Could not look up that ISBN. Fill the details in below.');
            setShowManualEntry(true);
        } finally {
            setLoading(false);
        }
    };

    /** Ask the metadata providers which editions match the title and author. */
    const searchByTitleAuthor = async (): Promise<BookMatch[]> =>
        findBooksByTitleAuthor(title.trim(), author.trim());

    /** Fill the form from a matched edition, ISBN included. */
    const applyMatch = (match: BookMatch) => {
        if (match.isbn13) setIsbn(match.isbn13);
        if (match.title) setTitle(match.title);
        const matchedAuthor = match.author || (match.authors ?? []).join(', ');
        if (matchedAuthor) setAuthor(matchedAuthor);
        if (match.publisher) setPublisher(match.publisher);
        if (match.publication_year) setYear(String(match.publication_year));
        setMatches([]);
        setIsbnError(null);
        setIsbnNotice(`Matched “${match.title}” — the ISBN has been filled in.`);
    };

    /**
     * The ISBN lookup the add form can do without an ISBN.
     *
     * The button exists so the reader can see the search happen before they
     * submit; submitting with a blank ISBN runs the same search.
     */
    const handleFindIsbn = async () => {
        if (!title.trim() || !author.trim()) {
            setIsbnError('Enter a title and an author, and the ISBN can be found from them.');
            return;
        }

        setLoading(true);
        setIsbnError(null);
        setIsbnNotice(null);
        setMatches([]);

        try {
            const found = (await searchByTitleAuthor()).filter((match) => match.isbn13);
            if (found.length === 1) {
                applyMatch(found[0]);
            } else if (found.length > 1) {
                setMatches(found);
                setIsbnNotice('Several editions match. Choose the one you mean.');
            } else {
                setIsbnError('No matching book found. Check the spelling, or type the ISBN.');
            }
        } catch (err) {
            console.error('Title and author lookup error:', err);
            setIsbnError('Could not search by title and author. Type the ISBN instead.');
        } finally {
            setLoading(false);
        }
    };

    /** Find candidate Books the reader does not already have, by title or author. */
    const handleDiscover = async () => {
        const query = discoverQuery.trim();
        if (!query) {
            setDiscoverError('Enter a title or an author to search for.');
            return;
        }
        // Enter can fire while a search is in flight. A second request would
        // race the first, and the loser could paint candidates for a query the
        // reader has already replaced.
        if (discoverInFlight.current) return;

        const requestId = ++discoverRequest.current;
        discoverInFlight.current = true;
        setDiscovering(true);
        setDiscoverError(null);
        setDiscoverNotice(null);
        setDiscoveries([]);

        try {
            const found = await discoverBooks(query);
            if (requestId !== discoverRequest.current) return;
            if (found.length === 0) {
                setDiscoverNotice(
                    `No books found for “${query}”. Check the spelling, or add one by ISBN below.`
                );
            } else {
                setDiscoveries(found);
            }
        } catch (err) {
            if (requestId !== discoverRequest.current) return;
            console.error('Book discovery error:', err);
            // A provider failure is not an empty result: say the search could
            // not run, and leave the ISBN and manual paths in view.
            setDiscoverError('Could not search for books right now. Try again, or add one by ISBN below.');
        } finally {
            if (requestId === discoverRequest.current) {
                discoverInFlight.current = false;
                setDiscovering(false);
            }
        }
    };

    /** The inner input of a Material field is in its shadow root, so Enter does
     *  not submit the form itself: the key is handled here. */
    const handleDiscoverKeyDown = (event: React.KeyboardEvent<HTMLElement>) => {
        if (event.key !== 'Enter') return;
        event.preventDefault();
        handleDiscover();
    };

    /**
     * Add a candidate in one action.
     *
     * The create endpoint already de-duplicates by ISBN and puts the Book on
     * the Reading List, so a candidate whose ISBN is already in the collection
     * queues the existing Book rather than making a second copy.
     */
    const handleChooseCandidate = async (candidate: BookMatch) => {
        const key = candidate.isbn13 || `${candidate.title}-${candidate.publication_year}`;
        setAddingCandidate(key);
        setDiscoverError(null);

        try {
            const book = await createBook({
                title: candidate.title,
                author: candidate.author,
                authors: candidate.authors,
                isbn: candidate.isbn13,
                publication_year: candidate.publication_year,
                thumbnail_url: candidate.thumbnail_url,
                cover_url: candidate.cover_url,
                publisher: candidate.publisher,
                description: candidate.description,
            });
            if (book.id) {
                navigate(`/books/${book.id}`);
            }
        } catch (err) {
            console.error('Failed to add discovered book:', err);
            setDiscoverError(`Could not add “${candidate.title}” to your Reading List. Please try again.`);
        } finally {
            setAddingCandidate(null);
        }
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();

        if (!title.trim() || !author.trim()) {
            setIsbnError('Title and author are required');
            return;
        }

        setLoading(true);
        setIsbnError(null);

        try {
            let isbnToUse = isbn.replace(/[-\s]/g, '');
            let details = {
                title: title.trim(),
                author: author.trim(),
                publisher: publisher.trim() || undefined,
                publication_year: year ? parseInt(year, 10) || undefined : undefined,
            };

            if (!isbnToUse) {
                // A Book is identified by its ISBN, but the reader is not asked to
                // find it themselves: the title and author they already typed are
                // what the lookup needs, so it runs here and fills the ISBN in.
                const found = (await searchByTitleAuthor()).filter((match) => match.isbn13);
                if (found.length === 1) {
                    const match = found[0];
                    isbnToUse = match.isbn13 as string;
                    applyMatch(match);
                    details = {
                        title: (match.title || details.title).trim(),
                        author: (match.author || (match.authors ?? []).join(', ') || details.author).trim(),
                        publisher: match.publisher || details.publisher,
                        publication_year: match.publication_year ?? details.publication_year,
                    };
                } else if (found.length > 1) {
                    setMatches(found);
                    setIsbnError('Several books match that title and author. Choose the one you mean.');
                    return;
                } else {
                    setIsbnError(
                        'No matching book found for that title and author. Check the spelling, or type the ISBN.'
                    );
                    return;
                }
            }

            const book = await createBook({ ...details, isbn: isbnToUse });

            if (addToReadingListChecked && book.id) {
                await addToReadingList(book.id);
            }

            navigate(`/books/${book.id}`);
        } catch (err) {
            console.error('Failed to create book:', err);
            setIsbnError('Failed to create book');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="add-book-page">
            <h1>Add a Book</h1>

            <div className="discover-section">
                <h2>Find a book</h2>
                <p className="section-info">
                    Search by title or author to find a book you have not logged yet.
                </p>
                <form
                    className="discover-form"
                    onSubmit={(event) => {
                        event.preventDefault();
                        handleDiscover();
                    }}
                >
                    <TextField
                        id="discover-query"
                        label="Title or author"
                        type="search"
                        placeholder="e.g. Piranesi, or Susanna Clarke"
                        value={discoverQuery}
                        onValueChange={setDiscoverQuery}
                        onKeyDown={handleDiscoverKeyDown}
                    />
                    <Button
                        variant="filled"
                        icon="search"
                        onClick={handleDiscover}
                        disabled={discovering}
                    >
                        {discovering ? 'Searching...' : 'Search'}
                    </Button>
                </form>

                {discoverError && (
                    <p className="error-message" role="alert">
                        {discoverError}
                    </p>
                )}
                {discoverNotice && (
                    <p className="lookup-notice" role="status">
                        {discoverNotice}
                    </p>
                )}

                {discoveries.length > 0 && (
                    <div className="book-list">
                        {discoveries.map((candidate, index) => {
                            const key =
                                candidate.isbn13 || `${candidate.title}-${candidate.publication_year}`;
                            const author =
                                candidate.author || (candidate.authors ?? []).join(', ');
                            return (
                                <div key={`${key}-${index}`} className="book-item">
                                    {candidate.thumbnail_url ? (
                                        <img src={candidate.thumbnail_url} alt="" />
                                    ) : (
                                        <div className="book-placeholder">📖</div>
                                    )}
                                    <div className="book-info">
                                        <div className="book-title">{candidate.title}</div>
                                        <div className="section-info">
                                            {[author, candidate.publication_year, candidate.publisher]
                                                .filter(
                                                    (value) =>
                                                        value !== undefined &&
                                                        value !== null &&
                                                        value !== ''
                                                )
                                                .join(' · ')}
                                        </div>
                                    </div>
                                    <Button
                                        variant="filled"
                                        onClick={() => handleChooseCandidate(candidate)}
                                        disabled={addingCandidate === key}
                                    >
                                        {addingCandidate === key
                                            ? 'Adding...'
                                            : 'Add to reading list'}
                                    </Button>
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>

            <div className="isbn-section">
                <TextField
                    id="isbn"
                    label="ISBN (optional)"
                    placeholder="Enter ISBN (10 or 13 digits)"
                    value={isbn}
                    onValueChange={setIsbn}
                    supportingText="No ISBN? Enter the title and author below and it will be found for you."
                />
                <div className="isbn-actions">
                    <Button variant="filled" onClick={() => handleLookup(isbn)} disabled={loading}>
                        {loading ? 'Looking up...' : 'Lookup ISBN'}
                    </Button>
                    <Button variant="tonal" onClick={scanning ? stopScanner : startScanner}>
                        {scanning ? 'Stop Scanner' : '📷 Scan Barcode'}
                    </Button>
                    <Button variant="text" onClick={() => setShowManualEntry(true)}>
                        Enter title &amp; author
                    </Button>
                </div>

                <div className="scanner-container" style={{ display: scanning ? 'block' : 'none' }}>
                    <div id="scanner-reader" ref={scannerRef}></div>
                </div>

                {scannerError && <p className="error-message">{scannerError}</p>}
                {isbnError && <p className="error-message">{isbnError}</p>}
                {isbnNotice && <p className="lookup-notice">{isbnNotice}</p>}
            </div>

            {(showManualEntry || title || author) && (
                <form onSubmit={handleSubmit} className="add-book-form">
                    <p className="section-info">
                        Only know the title and author? Leave the ISBN blank: adding the Book will
                        look for a matching edition and use its ISBN.
                    </p>

                    <TextField
                        id="title"
                        label="Title"
                        required
                        value={title}
                        onValueChange={setTitle}
                    />
                    
                    <TextField
                        id="author"
                        label="Author"
                        required
                        value={author}
                        onValueChange={setAuthor}
                    />
                    
                    <TextField
                        id="publisher"
                        label="Publisher"
                        value={publisher}
                        onValueChange={setPublisher}
                    />
                    
                    <TextField
                        id="year"
                        label="Publication Year"
                        type="number"
                        value={year}
                        onValueChange={setYear}
                        min="1000"
                        max={new Date().getFullYear()}
                    />

                    {matches.length > 0 && (
                        <div className="book-matches">
                            <p className="section-info">Which edition is yours?</p>
                            <div className="book-list">
                                {matches.map((match) => (
                                    <div key={match.isbn13} className="book-item">
                                        {match.thumbnail_url ? (
                                            <img src={match.thumbnail_url} alt={match.title} />
                                        ) : (
                                            <div className="book-placeholder">📖</div>
                                        )}
                                        <div className="book-info">
                                            <div className="book-title">{match.title}</div>
                                            <div className="section-info">
                                                {[match.author, match.publication_year, match.publisher, match.isbn13]
                                                    .filter((value) => value !== undefined && value !== null && value !== '')
                                                    .join(' · ')}
                                            </div>
                                        </div>
                                        <Button variant="outlined" onClick={() => applyMatch(match)}>
                                            Use this
                                        </Button>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    <div className="isbn-actions">
                        <Button
                            variant="tonal"
                            onClick={handleFindIsbn}
                            disabled={loading || !title.trim() || !author.trim()}
                        >
                            {loading ? 'Searching...' : 'Find ISBN from title & author'}
                        </Button>
                    </div>

                    <label className="checkbox-label">
                        <Checkbox
                            checked={addToReadingListChecked}
                            onCheckedChange={setAddToReadingListChecked}
                        />
                        Add to reading list
                    </label>

                    <Button type="submit" disabled={loading}>
                        {loading ? 'Adding...' : isbn.trim() ? 'Add Book' : 'Find ISBN & Add Book'}
                    </Button>
                </form>
            )}
        </div>
    );
};

export default AddBookPage;
