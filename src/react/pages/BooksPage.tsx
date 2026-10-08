import React, { useState, useEffect } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { getBooks, searchBooks } from '../services/api';
import BookExhibit from '../components/BookExhibit';
import Icon from '../components/Icon';
import { Button, Fab, Select, SelectOption, TextField } from '../ui';
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
                            {books.length} {books.length === 1 ? 'book' : 'books'}
                            {activeQuery ? ` matching “${activeQuery}”` : ''}
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
                        onValueChange={(value) => handleFilterChange('status', value)}
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
                        onValueChange={(value) => handleFilterChange('category', value)}
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
                        value={sortBy}
                        onValueChange={(value) => handleFilterChange('sort', value)}
                    >
                        <SelectOption value="reading_date">Reading date</SelectOption>
                        <SelectOption value="title">Title</SelectOption>
                        <SelectOption value="author">Author</SelectOption>
                        <SelectOption value="rating">Rating</SelectOption>
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
                            : 'Add your first book to begin the collection.'}
                    </p>
                    <Button variant="filled" icon="plus" to="/books/new">
                        Add a book
                    </Button>
                </div>
            ) : (
                <div className="exhibit-grid">
                    {books.map((book) => (
                        <BookExhibit key={book.id} book={book} titleAs="h2" />
                    ))}
                </div>
            )}

            {error && <p className="error-message">{error}</p>}

            {!loading && books.length > 0 && (
                <div className="fab-slot">
                    <Fab icon="plus" label="Add book" to="/books/new" />
                </div>
            )}
        </div>
    );
};

export default BooksPage;
