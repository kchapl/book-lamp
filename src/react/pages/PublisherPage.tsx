import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getPublisherPage } from '../services/api';
import type { PublisherPage } from '../types';

const PublisherPage: React.FC = () => {
    const { publisherSlug } = useParams<{ publisherSlug: string }>();
    const [data, setData] = useState<PublisherPage | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (publisherSlug) {
            loadPublisherPage(publisherSlug);
        }
    }, [publisherSlug]);

    const loadPublisherPage = async (slug: string) => {
        setLoading(true);
        setError(null);
        try {
            const result = await getPublisherPage(slug);
            setData(result);
        } catch (err) {
            console.error('Failed to load publisher page:', err);
            setError('Failed to load publisher information');
        } finally {
            setLoading(false);
        }
    };

    if (loading) {
        return <div className="loading">Loading...</div>;
    }

    if (error || !data) {
        return <div className="error-message">{error || 'Publisher not found'}</div>;
    }

    return (
        <div className="publisher-page">
            <h1>{data.publisher_name}</h1>
            <p className="book-count">{data.books.length} books</p>

            {data.books.length > 0 ? (
                <div className="book-grid">
                    {data.books.map((book) => (
                        <Link
                            key={book.id}
                            to={`/books/${book.id}`}
                            className="book-card"
                        >
                            {book.thumbnail_url ? (
                                <img src={book.thumbnail_url} alt={book.title} loading="lazy" />
                            ) : (
                                <div className="book-placeholder">📖</div>
                            )}
                            <div className="book-info">
                                <h3>{book.title}</h3>
                                <p className="book-author">{book.author || 'Unknown Author'}</p>
                                {book.publication_year && (
                                    <span className="year">{book.publication_year}</span>
                                )}
                            </div>
                        </Link>
                    ))}
                </div>
            ) : (
                <div className="empty-state">
                    <p>No books found from this publisher.</p>
                </div>
            )}
        </div>
    );
};

export default PublisherPage;