import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { getPublisherPage } from '../services/api';
import BookExhibit from '../components/BookExhibit';
import type { PublisherPage as PublisherPageData } from '../types';

const PublisherPage: React.FC = () => {
    const { publisherSlug } = useParams<{ publisherSlug: string }>();
    const [data, setData] = useState<PublisherPageData | null>(null);
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
        return <div className="loading">Loading…</div>;
    }

    if (error || !data) {
        return (
            <div className="page">
                <p className="error-message">{error || 'Publisher not found'}</p>
            </div>
        );
    }

    return (
        <div className="publisher-page page">
            <header className="publisher-header">
                <p className="eyebrow label-placard">Publisher</p>
                <h1 className="publisher-name">{data.publisher_name}</h1>
                <p className="publisher-stats">
                    {data.books.length} {data.books.length === 1 ? 'book' : 'books'}
                </p>
            </header>

            {data.books.length > 0 ? (
                <div className="exhibit-grid">
                    {data.books.map((book) => (
                        <BookExhibit key={book.id} book={book} />
                    ))}
                </div>
            ) : (
                <div className="empty-state">
                    <h2>Nothing from this publisher</h2>
                    <p>No books in your collection come from {data.publisher_name}.</p>
                </div>
            )}
        </div>
    );
};

export default PublisherPage;
