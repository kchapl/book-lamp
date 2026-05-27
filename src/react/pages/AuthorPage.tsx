import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getAuthorPage, addToReadingList } from '../services/api';
import type { AuthorPage } from '../types';

const AuthorPage: React.FC = () => {
    const { authorSlug } = useParams<{ authorSlug: string }>();
    const [data, setData] = useState<AuthorPage | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [addingBook, setAddingBook] = useState<number | null>(null);

    useEffect(() => {
        if (authorSlug) {
            loadAuthorPage(authorSlug);
        }
    }, [authorSlug]);

    const loadAuthorPage = async (slug: string) => {
        setLoading(true);
        setError(null);
        try {
            const result = await getAuthorPage(slug);
            setData(result);
        } catch (err) {
            console.error('Failed to load author page:', err);
            setError('Failed to load author information');
        } finally {
            setLoading(false);
        }
    };

    const handleAddToReadingList = async (bookId: number) => {
        setAddingBook(bookId);
        try {
            await addToReadingList(bookId);
            loadAuthorPage(authorSlug!);
        } catch (err) {
            console.error('Failed to add to reading list:', err);
        } finally {
            setAddingBook(null);
        }
    };

    if (loading) {
        return <div className="loading">Loading...</div>;
    }

    if (error || !data) {
        return <div className="error-message">{error || 'Author not found'}</div>;
    }

    return (
        <div className="author-page">
            <h1>{data.author_name}</h1>

            {data.read_books.length > 0 && (
                <section className="books-section">
                    <h2>Books Read ({data.read_books.length})</h2>
                    <div className="book-list">
                        {data.read_books.map((book) => (
                            <div key={book.id} className="book-item">
                                {book.thumbnail_url ? (
                                    <img src={book.thumbnail_url} alt={book.title} />
                                ) : (
                                    <div className="book-placeholder">📖</div>
                                )}
                                <div className="book-info">
                                    <Link to={`/books/${book.id}`} className="book-title">{book.title}</Link>
                                    {book.publication_year && (
                                        <span className="year">({book.publication_year})</span>
                                    )}
                                </div>
                            </div>
                        ))}
                    </div>
                </section>
            )}

            {data.reading_list_books.length > 0 && (
                <section className="books-section">
                    <h2>Reading List ({data.reading_list_books.length})</h2>
                    <div className="book-list">
                        {data.reading_list_books.map((book) => (
                            <div key={book.id} className="book-item">
                                {book.thumbnail_url ? (
                                    <img src={book.thumbnail_url} alt={book.title} />
                                ) : (
                                    <div className="book-placeholder">📖</div>
                                )}
                                <div className="book-info">
                                    <Link to={`/books/${book.id}`} className="book-title">{book.title}</Link>
                                    <span className="status-badge">On Reading List</span>
                                </div>
                            </div>
                        ))}
                    </div>
                </section>
            )}

            {data.unread_books.length > 0 && (
                <section className="books-section">
                    <h2>From Open Library ({data.unread_books.length})</h2>
                    <p className="section-info">Books by this author from Open Library that you haven't added yet.</p>
                    <div className="book-list">
                        {data.unread_books.map((book, index) => (
                            <div key={index} className="book-item">
                                {book.thumbnail_url ? (
                                    <img src={book.thumbnail_url} alt={book.title} />
                                ) : (
                                    <div className="book-placeholder">📖</div>
                                )}
                                <div className="book-info">
                                    <span className="book-title">{book.title}</span>
                                    {book.publication_year && (
                                        <span className="year">({book.publication_year})</span>
                                    )}
                                </div>
                                <button 
                                    className="btn btn-primary btn-sm"
                                    onClick={() => handleAddToReadingList(book.id!)}
                                    disabled={addingBook === book.id}
                                >
                                    {addingBook === book.id ? 'Adding...' : 'Add to Reading List'}
                                </button>
                            </div>
                        ))}
                    </div>
                </section>
            )}

            {data.read_books.length === 0 && data.reading_list_books.length === 0 && data.unread_books.length === 0 && (
                <div className="empty-state">
                    <p>No books found for this author.</p>
                </div>
            )}
        </div>
    );
};

export default AuthorPage;