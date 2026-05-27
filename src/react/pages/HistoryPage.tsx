import React, { useState, useEffect } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { getHistory } from '../services/api';
import type { ReadingRecord, HistoryFilters } from '../types';

const HistoryPage: React.FC = () => {
    const [searchParams, setSearchParams] = useSearchParams();
    const [history, setHistory] = useState<ReadingRecord[]>([]);
    const [statuses, setStatuses] = useState<string[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [editingRecord, setEditingRecord] = useState<ReadingRecord | null>(null);
    const [editForm, setEditForm] = useState({});

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
        <div className="history-page">
            <h1>Reading History</h1>

            <div className="history-controls">
                <div className="filter-controls">
                    <select
                        value={filters.status || ''}
                        onChange={(e) => handleFilterChange('status', e.target.value)}
                    >
                        <option value="">All Statuses</option>
                        {statuses.map((status) => (
                            <option key={status} value={status}>{status}</option>
                        ))}
                    </select>

                    <select
                        value={filters.rating?.toString() || ''}
                        onChange={(e) => handleFilterChange('min_rating', e.target.value)}
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
                        <div key={bookTitle} className="history-group">
                            <h3 className="group-title">
                                <Link to={`/books/${records[0].book_id}`}>{bookTitle}</Link>
                            </h3>
                            <div className="records-list">
                                {records.map((record) => (
                                    <div key={record.id} className="history-record">
                                        <div className="record-main">
                                            <span className={`status-badge status-${record.status.toLowerCase().replace(' ', '-')}`}>
                                                {record.status}
                                            </span>
                                            {record.rating && (
                                                <span className="rating">{'★'.repeat(record.rating)}{'☆'.repeat(5 - record.rating)}</span>
                                            )}
                                            <span className="dates">
                                                {record.start_date} - {record.end_date || 'Present'}
                                            </span>
                                        </div>
                                        {record.notes && (
                                            <p className="notes">{record.notes}</p>
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