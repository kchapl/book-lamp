import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { lookupISBN, createBook, addToReadingList } from '../services/api';
import { Button, Checkbox, TextField } from '../ui';
import type { Book } from '../types';
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
    const [addToReadingListChecked, setAddToReadingListChecked] = useState(false);
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

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        
        if (!title.trim() || !author.trim()) {
            setIsbnError('Title and author are required');
            return;
        }

        setLoading(true);
        
        try {
            const book = await createBook({
                title: title.trim(),
                author: author.trim(),
                publisher: publisher.trim() || undefined,
                publication_year: year ? parseInt(year) : undefined,
                isbn13: isbn.replace(/[-\s]/g, ''),
            });

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
                    label="ISBN"
                    placeholder="Enter ISBN (10 or 13 digits)"
                    value={isbn}
                    onValueChange={setIsbn}
                />
                <div className="isbn-actions">
                    <Button variant="filled" onClick={() => handleLookup(isbn)} disabled={loading}>
                        {loading ? 'Looking up...' : 'Lookup ISBN'}
                    </Button>
                    <Button variant="tonal" onClick={scanning ? stopScanner : startScanner}>
                        {scanning ? 'Stop Scanner' : '📷 Scan Barcode'}
                    </Button>
                    <Button variant="text" onClick={() => setShowManualEntry(true)}>
                        Enter manually
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

                    <label className="checkbox-label">
                        <Checkbox
                            checked={addToReadingListChecked}
                            onCheckedChange={setAddToReadingListChecked}
                        />
                        Add to reading list
                    </label>

                    <Button type="submit" disabled={loading}>
                        {loading ? 'Adding...' : 'Add Book'}
                    </Button>
                </form>
            )}
        </div>
    );
};

export default AddBookPage;