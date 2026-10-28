import React, { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getAuthorPage, createBook } from '../services/api';
import { Button } from '../ui';
import { useResource } from '../hooks/useResource';
import { READING_LIST_CLASS } from '../utils/status';
import type { AuthorPage, ExternalBook } from '../types';

/**
 * Identify an external result while its add is in flight. It has no id yet, and
 * its ISBN is the one value that will collapse it onto an existing Book.
 */
const externalKey = (book: ExternalBook, index: number) =>
    book.isbn13 || `${book.title}-${index}`;

const AuthorPage: React.FC = () => {
    const { authorSlug } = useParams<{ authorSlug: string }>();
    const [addingBook, setAddingBook] = useState<string | null>(null);
    const [addError, setAddError] = useState<string | null>(null);

    const loadAuthorPage = async () => {
        if (!authorSlug) throw new Error('No author slug in the route');
        return getAuthorPage(authorSlug);
    };

    const { data, loading, error, reload } = useResource(loadAuthorPage, [authorSlug], {
        errorMessage: 'Failed to load author information',
    });

    const handleAddExternalBook = async (book: ExternalBook, key: string) => {
        setAddingBook(key);
        setAddError(null);
        try {
            // An external result is not a Book yet, so it cannot go on the
            // Reading List by id. The create path turns it into one — and, when
            // its ISBN already belongs to a Book, queues that Book instead of
            // making a second copy.
            await createBook({
                title: book.title,
                author: book.author || data?.author_name || '',
                // The names themselves, not only their display string: that one
                // joins them with a comma, which storage reads as one person.
                authors: book.authors,
                isbn: book.isbn13 || undefined,
                publication_year: book.publication_year,
                thumbnail_url: book.thumbnail_url,
                publisher: book.publisher,
                description: book.description,
            });
            reload();
        } catch (err) {
            console.error('Failed to add external book to reading list:', err);
            setAddError(`Could not add “${book.title}” to your Reading List. Please try again.`);
        } finally {
            setAddingBook(null);
        }
    };

    if (loading) {
        return <div className="loading">Loading…</div>;
    }

    if (error || !data) {
        return (
            <div className="page">
                <p className="error-message">{error || 'Author not found'}</p>
            </div>
        );
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
                                    <span className={`status-badge ${READING_LIST_CLASS}`}>On Reading List</span>
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
                    {addError && (
                        <p className="error-message" role="alert">{addError}</p>
                    )}
                    <div className="book-list">
                        {data.unread_books.map((book, index) => {
                            const key = externalKey(book, index);
                            return (
                                <div key={key} className="book-item">
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
                                    {book.isbn13 ? (
                                        <Button
                                            variant="filled"
                                            onClick={() => handleAddExternalBook(book, key)}
                                            disabled={addingBook === key}
                                        >
                                            {addingBook === key ? 'Adding...' : 'Add to Reading List'}
                                        </Button>
                                    ) : (
                                        // A Book is identified by its ISBN, and the create
                                        // endpoint refuses one without it: adding this
                                        // result would overwrite an ISBN-less Book.
                                        <span className="section-info">
                                            No ISBN, so it cannot be added automatically.
                                        </span>
                                    )}
                                </div>
                            );
                        })}
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
