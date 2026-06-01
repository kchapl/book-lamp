import React, { useState, useEffect } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { getBooks, searchBooks } from '../services/api';
import type { Book, BooksFilters } from '../types';
import '../styles/books.css';

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
                if (!sortBy) setSortBy(data.sort || 'reading_date');
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

    const hasActiveFilters = Object.values(filters).some(v => v);
    const isSearching = searchParams.get('q');

    return (
        <div className="books-page">
            <h1>My Books</h1>

            <div className="books-controls">
                <form className="search-form" onSubmit={handleSearch}>
                    <input
                        type="text"
                        placeholder="Search by title, author..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        aria-label="Search books"
                    />
                    <button type="submit" className="btn btn-primary">Search</button>
                </form>

                <div className="filter-controls">
                    <select
                        value={filters.status}
                        onChange={(e) => handleFilterChange('status', e.target.value)}
                        aria-label="Filter by status"
                    >
                        <option value="">All Statuses</option>
                        <option value="In Progress">In Progress</option>
                        <option value="Completed">Completed</option>
                        <option value="Abandoned">Abandoned</option>
                    </select>

                    <select
                        value={filters.category}
                        onChange={(e) => handleFilterChange('category', e.target.value)}
                        aria-label="Filter by category"
                    >
                        <option value="">All Categories</option>
                        {categories.map((cat) => (
                            <option key={cat} value={cat}>{cat}</option>
                        ))}
                    </select>

                    <select
                        value={sortBy}
                        onChange={(e) => handleFilterChange('sort', e.target.value)}
                        aria-label="Sort books"
                    >
                        <option value="reading_date">Reading Date</option>
                        <option value="title">Title</option>
                        <option value="author">Author</option>
                        <option value="rating">Rating</option>
                    </select>

                    {hasActiveFilters && (
                        <button className="btn btn-text" onClick={clearFilters}>
                            Clear Filters
                        </button>
                    )}
                </div>
            </div>

            {isSearching && (
                <div className="search-results-badge">
                    Searching for "{searchParams.get('q')}"
                </div>
            )}

            {loading ? (
                <div className="skeleton-grid">
                    {[1, 2, 3, 4, 5, 6].map((i) => (
                        <div key={i} className="skeleton-book-card">
                            <div className="skeleton-image"></div>
                            <div className="skeleton-title"></div>
                        </div>
                    ))}
                </div>
            ) : books.length === 0 ? (
                <div className="empty-state">
                    <h2>No books found</h2>
                    <p>Add your first book to start building your collection.</p>
                    <Link to="/books/new" className="btn btn-primary">Add Book</Link>
                </div>
            ) : (
                <div className="book-grid">
                    {books.map((book) => (
                        <Link
                            key={book.id}
                            to={`/books/${book.id}`}
                            className="book-card"
                        >
                            {book.thumbnail_url ? (
                                <img src={book.thumbnail_url} alt={book.title} loading="lazy" />
                            ) : (
                                <div className="book-placeholder">📚</div>
                            )}
                            <div className="book-info">
                                <h3>{book.title}</h3>
                                <p className="book-author">{book.author || 'Unknown Author'}</p>
                                {book.latest_status && (
                                    <span className={`status-badge status-${book.latest_status.toLowerCase().replace(' ', '-')}`}>
                                        {book.latest_status}
                                    </span>
                                )}
                            </div>
                        </Link>
                    ))}
                </div>
            )}

            {error && <p className="error-message">{error}</p>}
        </div>
    );
};

export default BooksPage;