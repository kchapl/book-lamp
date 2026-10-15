import React from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { getHistory } from '../services/api';
import { Button, Select, SelectOption } from '../ui';
import { useResource } from '../hooks/useResource';
import { useUrlFilters } from '../hooks/useUrlFilters';
import { formatDate } from '../utils/format';
import { statusClass } from '../utils/status';
import type { HistoryFilters } from '../types';

/** The reading log's filters, as they appear in the URL. */
const FILTER_KEYS = ['status', 'min_rating', 'year', 'sort'] as const;

const HistoryPage: React.FC = () => {
    const [searchParams] = useSearchParams();
    const { values, set: setUrlFilters, clear } = useUrlFilters(FILTER_KEYS);

    // The URL holds strings; the log's rating floor is a number on the wire.
    const filters: Partial<HistoryFilters> = {
        status: values.status || undefined,
        min_rating: values.min_rating ? parseInt(values.min_rating) : undefined,
        year: values.year || undefined,
        sort: values.sort || 'date_desc',
    };

    const loadHistory = async () => {
        const data = await getHistory(filters);
        return { history: data.history || [], statuses: data.statuses || [] };
    };

    const { data, loading, error } = useResource(loadHistory, [searchParams], {
        errorMessage: 'Failed to load history',
    });

    const history = data?.history ?? [];
    const statuses = data?.statuses ?? [];
    const hasActiveFilters = values.status || values.min_rating || values.year;

    // Group history by book
    const groupedHistory = history.reduce((acc, record) => {
        const bookTitle = record.book_title || 'Unknown Book';
        if (!acc[bookTitle]) {
            acc[bookTitle] = [];
        }
        acc[bookTitle].push(record);
        return acc;
    }, {} as Record<string, typeof history>);

    return (
        <div className="history-page">
            <h1>Reading History</h1>

            <div className="history-controls">
                <div className="filter-controls">
                    <Select
                        id="history-status"
                        label="Status"
                        value={values.status}
                        onValueChange={(value) => setUrlFilters({ status: value })}
                    >
                        <SelectOption value="">All Statuses</SelectOption>
                        {statuses.map((status) => (
                            <SelectOption key={status} value={status}>{status}</SelectOption>
                        ))}
                    </Select>

                    <Select
                        id="history-rating"
                        label="Rating"
                        value={values.min_rating}
                        onValueChange={(value) => setUrlFilters({ min_rating: value })}
                    >
                        <SelectOption value="">All Ratings</SelectOption>
                        <SelectOption value="5">5 Stars</SelectOption>
                        <SelectOption value="4">4+ Stars</SelectOption>
                        <SelectOption value="3">3+ Stars</SelectOption>
                        <SelectOption value="2">2+ Stars</SelectOption>
                        <SelectOption value="1">1+ Stars</SelectOption>
                    </Select>

                    <Select
                        id="history-sort"
                        label="Sort"
                        value={values.sort || 'date_desc'}
                        onValueChange={(value) => setUrlFilters({ sort: value })}
                    >
                        <SelectOption value="date_desc">Newest First</SelectOption>
                        <SelectOption value="date_asc">Oldest First</SelectOption>
                        <SelectOption value="rating_desc">Highest Rated</SelectOption>
                        <SelectOption value="title">Title</SelectOption>
                    </Select>

                    {hasActiveFilters && (
                        <Button variant="text" onClick={clear}>
                            Clear Filters
                        </Button>
                    )}
                </div>
            </div>

            {loading ? (
                <div className="loading">Loading…</div>
            ) : history.length === 0 ? (
                <div className="empty-state">
                    <h2>No reading history</h2>
                    <p>Start reading to build your history.</p>
                    <Button variant="filled" to="/books">Browse Books</Button>
                </div>
            ) : (
                <div className="history-list">
                    {Object.entries(groupedHistory).map(([bookTitle, records]) => (
                        <div key={bookTitle} className="history-group">
                            <h2 className="group-title">
                                <Link to={`/books/${records[0].book_id}`}>{bookTitle}</Link>
                            </h2>
                            <div className="records-list">
                                {records.map((record) => (
                                    <div key={record.id} className="history-record">
                                        <div className="record-main">
                                            <span className={`status-badge ${statusClass(record.status)}`}>
                                                {record.status}
                                            </span>
                                            {record.rating ? (
                                                <span className="rating">{'★'.repeat(record.rating)}{'☆'.repeat(5 - record.rating)}</span>
                                            ) : null}
                                            <span className="dates">
                                                {formatDate(record.start_date)} –{' '}
                                                {record.end_date ? formatDate(record.end_date) : 'Present'}
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
