import React from 'react';
import { Link, useParams } from 'react-router-dom';
import { getSeriesPage } from '../services/api';
import { useResource } from '../hooks/useResource';
import { READING_LIST_CLASS, statusClass } from '../utils/status';
import type { SeriesPage as SeriesPageData } from '../types';

/**
 * Every Book in a series, in the order it was published.
 *
 * A series is not a stored record, so this page is the Books themselves: what
 * the reader owns, where they are in it, and — because a Book with no Reading
 * still belongs here — what is left to pick up. The author and publisher pages
 * are its precedent; unlike the author page it makes no external lookup, since
 * the log is what it can speak for.
 */
const SeriesPage: React.FC = () => {
    const { seriesSlug } = useParams<{ seriesSlug: string }>();

    const loadSeriesPage = async () => {
        if (!seriesSlug) throw new Error('No series slug in the route');
        return getSeriesPage(seriesSlug);
    };

    const { data, loading, error } = useResource<SeriesPageData>(loadSeriesPage, [seriesSlug], {
        errorMessage: 'Series not found',
    });

    if (loading) {
        return <div className="loading">Loading…</div>;
    }

    if (error || !data) {
        return (
            <div className="page">
                <p className="error-message">{error || 'Series not found'}</p>
            </div>
        );
    }

    return (
        <div className="series-page page">
            <header className="publisher-header">
                <p className="eyebrow label-placard">Series</p>
                <h1 className="publisher-name">{data.series_name}</h1>
                <p className="publisher-stats">
                    {data.books.length} {data.books.length === 1 ? 'book' : 'books'}
                </p>
            </header>

            <div className="book-list">
                {data.books.map((book) => {
                    const cover = book.cover_url || book.thumbnail_url;
                    return (
                        <div key={book.id} className="book-item">
                            {cover ? (
                                <img src={cover} alt="" loading="lazy" />
                            ) : (
                                <div className="book-placeholder" aria-hidden="true">
                                    📖
                                </div>
                            )}
                            <div className="book-info">
                                <Link to={`/books/${book.id}`} className="book-title">
                                    {book.title}
                                </Link>
                                {book.publication_year && (
                                    <span className="year">({book.publication_year})</span>
                                )}
                                {book.latest_status ? (
                                    <span className={`status-badge ${statusClass(book.latest_status)}`}>
                                        {book.latest_status}
                                    </span>
                                ) : (
                                    book.in_reading_list && (
                                        <span className={`status-badge ${READING_LIST_CLASS}`}>
                                            On Reading List
                                        </span>
                                    )
                                )}
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
};

export default SeriesPage;
