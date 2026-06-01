import React, { useState, useEffect } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { getHistory } from '../services/api';
import type { ReadingRecord, HistoryFilters } from '../types';
import '../styles/global.css';

const HistoryPage: React.FC = () => {
    const [searchParams, setSearchParams] = useSearchParams();
    const [history, setHistory] = useState<ReadingRecord[]>([]);
    const [statuses, setStatuses] = useState<string[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const filters: Partial<HistoryFilters> = {
        status: searchParams.get('status') || undefined,
        rating: searchParams.get('min_rating') ? parseInt(searchParams.get('min_rating')!) : undefined,
        year: searchParams.get('year') || undefined,
        sort: searchParams.get('sort') || 'date_desc',
    };

    useEffect(() => {
        loadHistory();
    }, [searchParams]);

    const loadHistory = async () => {
        setLoading(true);
        setError(null);
        try {
            const data = await getHistory(filters);
            setHistory(data.history || []);
            setStatuses(data.statuses || []);
        } catch (err) {
            console.error('Failed to load history:', err);
            setError('Failed to load history');
        } finally {
            setLoading(false);
        }
    };

    const handleFilterChange = (key: string, value: string) => {
        const newParams = new URLSearchParams(searchParams);
        if (value) {
            newParams.set(key, value);
        } else {
            newParams.delete(key);
        }
        setSearchParams(newParams);
    };

    const clearFilters = () => {
        setSearchParams({});
    };

    const hasActiveFilters = filters.status || filters.rating || filters.year;

    // Group history by book
    const groupedHistory = history.reduce((acc, record) => {
        const bookTitle = record.book_title || 'Unknown Book';
        if (!acc[bookTitle]) {
            acc[bookTitle] = [];
        }
        acc[bookTitle].push(record);
        return acc;
    }, {} as Record<string, ReadingRecord[]>);

    return (
        <div className="history-page" style={{ maxWidth: '900px', margin: '0 auto', padding: '0 1rem' }}>
            <h1 style={{ fontFamily: "'Playfair Display', Georgia, serif", fontSize: 'clamp(1.75rem, 4vw, 2.5rem)', fontWeight: 400, marginBottom: '2rem' }}>Reading History</h1>

            <div className="history-controls" style={{ marginBottom: '2rem' }}>
                <div className="filter-controls" style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem', alignItems: 'center' }}>
                    <select
                        value={filters.status || ''}
                        onChange={(e) => handleFilterChange('status', e.target.value)}
                        style={{ minHeight: '48px', minWidth: '140px' }}
                    >
                        <option value="">All Statuses</option>
                        {statuses.map((status) => (
                            <option key={status} value={status}>{status}</option>
                        ))}
                    </select>

                    <select
                        value={filters.rating?.toString() || ''}
                        onChange={(e) => handleFilterChange('min_rating', e.target.value)}
                        style={{ minHeight: '48px', minWidth: '120px' }}
                    >
                        <option value="">All Ratings</option>
                        <option value="5">5 Stars</option>
                        <option value="4">4+ Stars</option>
                        <option value="3">3+ Stars</option>
                        <option value="2">2+ Stars</option>
                        <option value="1">1+ Stars</option>
                    </select>

                    <select
                        value={filters.sort || 'date_desc'}
                        onChange={(e) => handleFilterChange('sort', e.target.value)}
                        style={{ minHeight: '48px', minWidth: '140px' }}
                    >
                        <option value="date_desc">Newest First</option>
                        <option value="date_asc">Oldest First</option>
                        <option value="rating_desc">Highest Rated</option>
                        <option value="title">Title</option>
                    </select>

                    {hasActiveFilters && (
                        <button className="btn btn-text" onClick={clearFilters}>
                            Clear Filters
                        </button>
                    )}
                </div>
            </div>

            {loading ? (
                <div className="loading">Loading...</div>
            ) : history.length === 0 ? (
                <div className="empty-state">
                    <h2>No reading history</h2>
                    <p>Start reading to build your history.</p>
                    <Link to="/books" className="btn btn-primary">Browse Books</Link>
                </div>
            ) : (
                <div className="history-list">
                    {Object.entries(groupedHistory).map(([bookTitle, records]) => (
                        <div key={bookTitle} className="history-group" style={{ marginBottom: '2rem', padding: '1.5rem', background: 'var(--md-sys-color-surface-container-low)', borderRadius: 'var(--md-sys-shape-md)', border: '1px solid var(--md-sys-color-outline-variant)' }}>
                            <h3 className="group-title" style={{ fontFamily: "'Playfair Display', Georgia, serif", fontSize: '1.25rem', marginBottom: '1rem' }}>
                                <Link to={`/books/${records[0].book_id}`} style={{ color: 'var(--md-sys-color-on-surface)', textDecoration: 'none' }}>{bookTitle}</Link>
                            </h3>
                            <div className="records-list" style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                                {records.map((record) => (
                                    <div key={record.id} className="history-record" style={{ display: 'flex', flexWrap: 'wrap', gap: '1rem', alignItems: 'center', padding: '0.75rem', background: 'var(--md-sys-color-surface-container-lowest)', borderRadius: 'var(--md-sys-shape-sm)' }}>
                                        <div className="record-main" style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem', alignItems: 'center' }}>
                                            <span className={`status-badge status-${record.status.toLowerCase().replace(' ', '-')}`}>
                                                {record.status}
                                            </span>
                                            {record.rating && (
                                                <span className="rating" style={{ color: 'var(--md-sys-color-primary)', letterSpacing: '0.1em' }}>{'★'.repeat(record.rating)}{'☆'.repeat(5 - record.rating)}</span>
                                            )}
                                            <span className="dates" style={{ fontFamily: "'DM Sans', system-ui, sans-serif", fontSize: '0.875rem', color: 'var(--md-sys-color-on-surface-variant)' }}>
                                                {record.start_date} — {record.end_date || 'Present'}
                                            </span>
                                        </div>
                                        {record.notes && (
                                            <p className="notes" style={{ width: '100%', margin: '0.5rem 0 0 0', fontSize: '0.9375rem', color: 'var(--md-sys-color-on-surface-variant)' }}>{record.notes}</p>
                                        )}
                                    </div>
                                ))}
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {error && <p className="error-message">{error}</p>}
        </div>
    );
};

export default HistoryPage;