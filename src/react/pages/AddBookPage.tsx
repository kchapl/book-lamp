import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { lookupISBN, findBooksByTitleAuthor, createBook, addToReadingList } from '../services/api';
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
    // The Reading List links here with `add_to_reading_list=1`, so the option
    // starts ticked for a reader who came from the list to queue a Book.
    const [addToReadingListChecked, setAddToReadingListChecked] = useState(
        () => searchParams.get('add_to_reading_list') === '1'
    );
    const [scanning, setScanning] = useState(false);
    const [scannerError, setScannerError] = useState<string | null>(null);
    const scannerRef = useRef<HTMLDivElement>(null);
    const html5QrCodeRef = useRef<Html5Qrcode | null>(null);

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
