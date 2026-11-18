import React, { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { fetchCovers, getBooks, getJobStatus, searchBooks } from '../services/api';
import BookExhibit from '../components/BookExhibit';
import Icon from '../components/Icon';
import { Button, Select, SelectOption, TextField } from '../ui';
import { useResource } from '../hooks/useResource';
import { useUrlFilters } from '../hooks/useUrlFilters';
import type { Book, BooksFilters } from '../types';

/**
 * The filters this page keeps in the URL. `q` is deliberately not one of them:
 * the search box holds its own state and is written only on submit, so typing
 * does not refetch.
 */
const FILTER_KEYS = ['status', 'year', 'month', 'rating', 'category', 'sort'] as const;

/** Every filter empty, for writing a search that replaces them. */
const NO_FILTERS: Record<string, string> = Object.fromEntries(
    FILTER_KEYS.map((key) => [key, ''])
);

const BooksPage: React.FC = () => {
    const [searchParams] = useSearchParams();
    const [searchQuery, setSearchQuery] = useState('');
    const [coverRun, setCoverRun] = useState<{
        progress: number;
        result: string | null;
        error: string | null;
    } | null>(null);
    const [fillingCovers, setFillingCovers] = useState(false);
    const {
        values: filters,
        set: setUrlFilters,
        clear: clearUrlFilters,
    } = useUrlFilters(FILTER_KEYS);

    const loadBooks = async () => {
        const query = searchParams.get('q');
        if (query) {
            const data = await searchBooks(query);
            return { books: data.books || [], categories: [] as string[] };
        }
        const data = await getBooks(filters);
        return { books: data.books || [], categories: data.categories || [] };
    };

    const { data, loading, error, reload } = useResource(loadBooks, [searchParams], {
        errorMessage: 'Failed to load books',
    });

    const books = data?.books ?? [];
    const categories = data?.categories ?? [];

    /** Apply a filter, leaving search mode: the search box is not a filter. */
    const applyFilter = (update: Record<string, string>) => setUrlFilters({ ...update, q: '' });

    // A search replaces the filters; an empty one clears everything. Both the
    // form's submit and the field's Enter key reach this, so the two cannot
    // disagree about what a search is.
    const runSearch = () => {
        setUrlFilters({ ...NO_FILTERS, q: searchQuery.trim() });
    };

    const handleSearch = (e: React.FormEvent) => {
        e.preventDefault();
        runSearch();
    };

    /**
     * Enter in the field has to start the search itself. The real input lives in
     * the text field's shadow root and is not in the form's own tree, so the
     * browser's implicit submission never fires — without this the key does
     * nothing at all. The default is prevented so the search cannot also arrive
     * as a native submit.
     */
    const handleSearchKeyDown = (event: React.KeyboardEvent<HTMLElement>) => {
        if (event.key !== 'Enter') return;
        event.preventDefault();
        runSearch();
    };

    const clearFilters = () => {
        clearUrlFilters();
        setSearchQuery('');
    };

    /**
     * Fill covers for Books that have none. The job runs in the background, so
     * the page polls its status and shows the report it finishes with; the
     * collection is refetched once the run is done.
     */
    const fillMissingCovers = async () => {
        setFillingCovers(true);
        setCoverRun({ progress: 0, result: null, error: null });
        try {
            const { job_id } = await fetchCovers([]);
            for (;;) {
                const job = await getJobStatus(job_id);
                const finished = job.status === 'completed' || job.status === 'failed';
                setCoverRun({
                    progress: job.progress ?? 0,
                    result: job.result ?? null,
                    error: job.status === 'failed' ? job.error || 'The cover lookup failed' : null,
                });
                if (finished) break;
                await new Promise((resolve) => setTimeout(resolve, 1000));
            }
            reload();
        } catch (err) {
            setCoverRun({
                progress: 0,
                result: null,
                error: err instanceof Error ? err.message : 'Could not start the cover lookup',
            });
        } finally {
            setFillingCovers(false);
        }
    };

    const activeQuery = searchParams.get('q');
    // Sorting is not a filter: choosing one must not make "Clear" appear.
    const hasActiveFilters = (['status', 'year', 'month', 'rating', 'category'] as const).some(
        (key) => filters[key]
    );

    return (
        <div className="books-page page">
            <header className="page-header">
                <div>
                    <p className="eyebrow label-placard">Your books</p>
                    <h1>My Books</h1>
                    {!loading && (
                        <p className="text-muted">
                            {books.length} {books.length === 1 ? 'book' : 'books'}
                            {activeQuery ? ` matching “${activeQuery}”` : ''}
                        </p>
                    )}
                    <Button variant="tonal" onClick={fillMissingCovers} disabled={fillingCovers}>
                        {fillingCovers ? 'Looking for covers…' : 'Fill missing covers'}
                    </Button>
                    {coverRun && (
                        <p className="text-muted" role="status">
                            {coverRun.error ?? coverRun.result ?? `Checking ${coverRun.progress}%…`}
                        </p>
                    )}
                </div>
            </header>

            <div className="books-controls">
                <form className="search-form" onSubmit={handleSearch} role="search">
                    <TextField
                        id="book-search"
                        label="Search books"
                        type="search"
                        placeholder="Search by title, author or ISBN…"
                        value={searchQuery}
                        onValueChange={setSearchQuery}
                        onKeyDown={handleSearchKeyDown}
                    />
                    <Button variant="filled" icon="search" type="submit">
                        Search
                    </Button>
                </form>

                <div className="filter-controls">
                    <Select
                        id="filter-status"
                        label="Status"
                        value={filters.status}
                        onValueChange={(value) => applyFilter({ status: value })}
                    >
                        <SelectOption value="">All statuses</SelectOption>
                        <SelectOption value="In Progress">In Progress</SelectOption>
                        <SelectOption value="Completed">Completed</SelectOption>
                        <SelectOption value="Abandoned">Abandoned</SelectOption>
                    </Select>

                    <Select
                        id="filter-category"
                        label="Category"
                        value={filters.category}
                        onValueChange={(value) => applyFilter({ category: value })}
                    >
                        <SelectOption value="">All categories</SelectOption>
                        {categories.map((cat) => (
                            <SelectOption key={cat} value={cat}>
                                {cat}
                            </SelectOption>
                        ))}
                    </Select>

                    <Select
                        id="filter-sort"
                        label="Sort"
                        value={filters.sort || 'reading_date'}
                        onValueChange={(value) => applyFilter({ sort: value })}
                    >
                        {/* Only sorts the server implements (see SORT_OPTIONS). There
                            is no rating sort, and offering one silently fell back to
                            the default order. */}
                        <SelectOption value="reading_date">Reading date</SelectOption>
                        <SelectOption value="title">Title</SelectOption>
                        <SelectOption value="author">Author</SelectOption>
                    </Select>

                    {(hasActiveFilters || activeQuery) && (
                        <Button variant="text" onClick={clearFilters}>
                            Clear
                        </Button>
                    )}
                </div>
            </div>

            {loading ? (
                <div className="skeleton-grid" aria-busy="true">
                    {[1, 2, 3, 4, 5, 6].map((i) => (
                        <div key={i} className="skeleton-card">
                            <div className="skeleton-image" />
                            <div className="skeleton-title" />
                        </div>
                    ))}
                </div>
            ) : books.length === 0 ? (
                <div className="empty-state">
                    <Icon name="books" size="lg" />
                    <h2>No books found</h2>
                    <p>
                        {hasActiveFilters || activeQuery
                            ? 'Nothing matches those filters. Try widening the search.'
                            : 'Books you start reading will appear here.'}
                    </p>
                </div>
            ) : (
                <div className="exhibit-grid">
                    {books.map((book) => (
                        <BookExhibit key={book.id} book={book} titleAs="h2" />
                    ))}
                </div>
            )}

            {error && <p className="error-message">{error}</p>}
        </div>
    );
};

export default BooksPage;
