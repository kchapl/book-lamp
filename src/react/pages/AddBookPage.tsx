import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { lookupISBN, createBook, addToReadingList } from '../services/api';
import type { Book } from '../types';
import { Html5Qrcode } from 'html5-qrcode';

const AddBookPage: React.FC = () => {
    const navigate = useNavigate();
    const [searchParams] = useSearchParams();
    const [isbn, setIsbn] = useState(searchParams.get('isbn') || '');
    const [title, setTitle] = useState('');
    const [author, setAuthor] = useState('');
    const [publisher, setPublisher] = useState('');
    const [year, setYear] = useState('');
    const [isbnError, setIsbnError] = useState<string | null>(null);
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
        if (!scannerRef.current) return;
        
        setScanning(true);
        setScannerError(null);
        
        try {
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
        
        try {
            const book = await lookupISBN(cleanIsbn);
            if (book) {
                setTitle(book.title || '');
                setAuthor(book.author || '');
                setPublisher(book.publisher || '');
                setYear(book.publication_year ? String(book.publication_year) : '');
            } else {
                setShowManualEntry(true);
            }
        } catch (err) {
            console.error('Lookup error:', err);
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
                <label>
                    ISBN:
                    <input
                        type="text"
                        placeholder="Enter ISBN (10 or 13 digits)"
                        value={isbn}
                        onChange={(e) => setIsbn(e.target.value)}
                    />
                </label>
                <div className="isbn-actions">
                    <button
                        onClick={() => handleLookup(isbn)}
                        disabled={loading}
                        className="btn btn-primary"
                    >
                        {loading ? 'Looking up...' : 'Lookup ISBN'}
                    </button>
                    <button
                        onClick={scanning ? stopScanner : startScanner}
                        className="btn"
                    >
                        {scanning ? 'Stop Scanner' : '📷 Scan Barcode'}
                    </button>
                    <button
                        onClick={() => setShowManualEntry(true)}
                        className="btn btn-text"
                    >
                        Enter manually
                    </button>
                </div>

                {scanning && (
                    <div className="scanner-container">
                        <div id="scanner-reader" ref={scannerRef}></div>
                    </div>
                )}

                {scannerError && <p className="error-message">{scannerError}</p>}
                {isbnError && <p className="error-message">{isbnError}</p>}
            </div>

            {(showManualEntry || title || author) && (
                <form onSubmit={handleSubmit} className="add-book-form">
                    <label>
                        Title *
                        <input
                            type="text"
                            value={title}
                            onChange={(e) => setTitle(e.target.value)}
                            required
                        />
                    </label>
                    
                    <label>
                        Author *
                        <input
                            type="text"
                            value={author}
                            onChange={(e) => setAuthor(e.target.value)}
                            required
                        />
                    </label>
                    
                    <label>
                        Publisher
                        <input
                            type="text"
                            value={publisher}
                            onChange={(e) => setPublisher(e.target.value)}
                        />
                    </label>
                    
                    <label>
                        Publication Year
                        <input
                            type="number"
                            value={year}
                            onChange={(e) => setYear(e.target.value)}
                            min="1000"
                            max={new Date().getFullYear()}
                        />
                    </label>

                    <label className="checkbox-label">
                        <input
                            type="checkbox"
                            checked={addToReadingListChecked}
                            onChange={(e) => setAddToReadingListChecked(e.target.checked)}
                        />
                        Add to reading list
                    </label>

                    <button
                        type="submit"
                        disabled={loading}
                        className="btn btn-primary"
                    >
                        {loading ? 'Adding...' : 'Add Book'}
                    </button>
                </form>
            )}
        </div>
    );
};

export default AddBookPage;