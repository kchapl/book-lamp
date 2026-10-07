import React, { useState, useEffect } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { getBooks, searchBooks } from '../services/api';
import BookExhibit from '../components/BookExhibit';
import Icon from '../components/Icon';
import type { Book, BooksFilters } from '../types';

const BooksPage: React.FC = () => {
    const [searchParams, setSearchParams] = useSearchParams();
    const [books, setBooks] = useState<Book[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [categories, setCategories] = useState<string[]>([]);
    const [searchQuery, setSearchQuery] = useState('');
    const [sortBy, setSortBy] = useState('reading_date');

    const filters: BooksFilters = {
        status: searchParams.get('status') || '',
        year: searchParams.get('year') || '',
        month: searchParams.get('month') || '',
        rating: searchParams.get('rating') || '',
        category: searchParams.get('category') || '',
    };

    useEffect(() => {
        loadBooks();
    }, [searchParams]);

    const loadBooks = async () => {
        setLoading(true);
        setError(null);
        try {
            const query = searchParams.get('q');
            if (query) {
                const data = await searchBooks(query);
                setBooks(data.books || []);
            } else {
                const data = await getBooks(filters);
                setBooks(data.books || []);
                setCategories(data.categories || []);
                if (data.sort) setSortBy(data.sort);
            }
        } catch (err) {
            console.error('Failed to load books:', err);
            setError('Failed to load books');
        } finally {
            setLoading(false);
        }
    };

    const handleSearch = (e: React.FormEvent) => {
        e.preventDefault();
        if (searchQuery.trim()) {
            setSearchParams({ q: searchQuery.trim() });
        } else {
            setSearchParams({});
        }
    };

    const handleFilterChange = (key: string, value: string) => {
        const newParams = new URLSearchParams(searchParams);
        if (value) {
            newParams.set(key, value);
        } else {
            newParams.delete(key);
        }
        newParams.delete('q'); // Clear search when applying filters
        setSearchParams(newParams);
    };

    const clearFilters = () => {
        setSearchParams({});
        setSearchQuery('');
    };

    const activeQuery = searchParams.get('q');
    const hasActiveFilters = Object.values(filters).some((v) => v);

    return (
        <div className="books-page page">
            <header className="page-header">
                <div>
                    <p className="eyebrow label-placard">The collection</p>
                    <h1>My Books</h1>
                    {!loading && (
                        <p className="text-muted">
                            {books.length} {books.length === 1 ? 'exhibit' : 'exhibits'}
                            {activeQuery ? ` matching “${activeQuery}”` : ''}
                        </p>
                    )}
                </div>
            </header>

            <div className="books-controls">
                <form className="search-form" onSubmit={handleSearch} role="search">
                    <label className="sr-only" htmlFor="book-search">
                        Search books
                    </label>
                    <input
                        id="book-search"
                        type="search"
                        placeholder="Search by title, author or ISBN…"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                    />
                    <button type="submit" className="btn btn-primary">
                        <Icon name="search" size="sm" />
                        Search
                    </button>
                </form>

                <div className="filter-controls">
                    <label className="sr-only" htmlFor="filter-status">
                        Filter by status
                    </label>
                    <select
                        id="filter-status"
                        value={filters.status}
                        onChange={(e) => handleFilterChange('status', e.target.value)}
                    >
                        <option value="">All statuses</option>
                        <option value="In Progress">In Progress</option>
                        <option value="Completed">Completed</option>
                        <option value="Abandoned">Abandoned</option>
                    </select>

                    <label className="sr-only" htmlFor="filter-category">
                        Filter by category
                    </label>
                    <select
                        id="filter-category"
                        value={filters.category}
                        onChange={(e) => handleFilterChange('category', e.target.value)}
                    >
                        <option value="">All categories</option>
                        {categories.map((cat) => (
                            <option key={cat} value={cat}>
                                {cat}
                            </option>
                        ))}
                    </select>

                    <label className="sr-only" htmlFor="filter-sort">
                        Sort books
                    </label>
                    <select
                        id="filter-sort"
                        value={sortBy}
                        onChange={(e) => handleFilterChange('sort', e.target.value)}
                    >
                        <option value="reading_date">Reading date</option>
                        <option value="title">Title</option>
                        <option value="author">Author</option>
                        <option value="rating">Rating</option>
                    </select>

                    {(hasActiveFilters || activeQuery) && (
                        <button type="button" className="btn btn-text" onClick={clearFilters}>
                            Clear
                        </button>
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
                            : 'Add your first book to begin the collection.'}
                    </p>
                    <Link to="/books/new" className="btn btn-primary">
                        <Icon name="plus" size="sm" />
                        Add a book
                    </Link>
                </div>
            ) : (
                <div className="exhibit-grid">
                    {books.map((book) => (
                        <BookExhibit key={book.id} book={book} />
                    ))}
                </div>
            )}

            {error && <p className="error-message">{error}</p>}
        </div>
    );
};

export default BooksPage;
